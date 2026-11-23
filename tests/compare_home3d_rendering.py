"""Compare fixed 8-bit sRGB reference images without excluding shadows or highlights."""
import json
import math
from pathlib import Path
import sys
from PIL import Image, ImageChops, ImageEnhance

root = Path(sys.argv[1])
report = json.loads((root / 'browser.json').read_text())

def difference(a, b):
    a, b = Image.open(a).convert('RGB'), Image.open(b).convert('RGB')
    if a.size != b.size or a.size != (report['capture']['widthPx'], report['capture']['heightPx']):
        raise ValueError('Reference viewport sizes differ')
    d = ImageChops.difference(a, b)
    count = a.width * a.height
    hist = d.histogram()
    mae = sum((i % 256) * v for i, v in enumerate(hist)) / (count * 3 * 255)
    r, g, b = d.split()
    hist = ImageChops.lighter(ImageChops.lighter(r, g), b).histogram()
    rank = math.ceil(.99 * count)
    total = 0
    for value, n in enumerate(hist):
        total += n
        if total >= rank:
            return mae, value / 255, d

pairs = []
for state in ['original', 'reimported']:
    for view in report['views']:
        a, b = root / f'chrome-{state}-{view}.png', root / f'webkit-{state}-{view}.png'
        mae, p99, d = difference(a, b)
        ImageEnhance.Brightness(d).enhance(8).save(root / f'difference-{state}-{view}.png')
        pairs.append({'state': state, 'view': view, 'meanAbsoluteError': mae, 'p99MaxChannelError': p99, 'passed': mae <= 2 / 255 and p99 <= 8 / 255})
variants = {}
for name in ['half-exposure', 'key-off', 'shadows-off', 'environment-off']:
    mae, _, _ = difference(root / f'chrome-original-{report["views"][0]}.png', root / f'chrome-{name}.png')
    variants[name] = {'meanAbsoluteChange': mae, 'passed': mae > .0005}
result = {'limits': {'meanAbsoluteError': 2 / 255, 'p99MaxChannelError': 8 / 255}, 'pairs': pairs, 'configurationAffectsPixels': variants, 'passed': all(x['passed'] for x in pairs) and all(x['passed'] for x in variants.values())}
(root / 'pixels.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
if not result['passed']:
    sys.exit(1)
