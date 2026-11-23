"""Translate trusted realtime white settings into a complete Home3D rendering v1 document."""
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import zlib

HERE = Path(__file__).resolve().parent


def number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('RENDER_SOURCE: expected a finite numeric setting')
    return value


def rgb(color):
    if not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
        raise ValueError('RENDER_SOURCE: environment colors must be #RRGGBB')
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def freeze_environment(environment):
    """Fixed sRGB byte interpolation at pixel centers; no browser Canvas or network."""
    w, h = environment['width'], environment['height']
    if type(w) is not int or type(h) is not int or not (1 <= w <= 4096 and 1 <= h <= 4096):
        raise ValueError('RENDER_SOURCE: environment size exceeds rasterizer limits')
    stops = [(number(t), rgb(c)) for t, c in environment['stops']]
    if len(stops) < 2 or stops[0][0] != 0 or stops[-1][0] != 1 or any(a[0] >= b[0] for a, b in zip(stops, stops[1:])):
        raise ValueError('RENDER_SOURCE: ordered environment stops must span 0..1')
    box = environment['softbox']
    if len(box) != 4 or any(type(v) is not int for v in box) or min(box[2:]) <= 0:
        raise ValueError('RENDER_SOURCE: softbox requires integer pixel bounds')
    raw = bytearray()
    for y in range(h):
        t = (y + .5) / h
        a, b = next((a, b) for a, b in zip(stops, stops[1:]) if a[0] <= t <= b[0])
        f = (t - a[0]) / (b[0] - a[0])
        color = bytes(math.floor(a[1][i] + (b[1][i] - a[1][i]) * f + .5) for i in range(3))
        row = bytearray(color * w)
        if box[1] <= y < box[1] + box[3]:
            for x in range(max(0, box[0]), min(w, box[0] + box[2])):
                row[x * 3:x * 3 + 3] = b'\xff\xff\xff'
        raw.extend(b'\0' + row)
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b'')


def white_document(config):
    c = copy.deepcopy(config)
    if (c.get('schemaVersion'), c.get('profileId'), c.get('profileVersion'), c.get('style')) != (1, 'white-home3d-v1', 1, 'white-minimal'):
        raise ValueError('RENDER_SOURCE: unsupported white realtime configuration')
    renderer, s, p, ao = c['renderer'], c['studio'], c['shadows'], c['contactAO']
    if renderer['toneMapping'] != 'ACESFilmicToneMapping' or renderer['outputColorSpace'] != 'SRGBColorSpace' or renderer['antialias'] is not True or c['camera']['projection'] != 'orthographic' or p['filter'] != 'VSMShadowMap' or ao['vertexAttribute'] != 'COLOR_0' or ao['bakeLightEmission'] is not False:
        raise ValueError('RENDER_SOURCE: settings require a different versioned rendering pipeline')
    aspect = number(c['camera']['aspectReference'])
    if abs(aspect - 4 / 3) > 1e-8:
        raise ValueError('RENDER_SOURCE: reference capture requires the authored 4:3 camera')
    image = freeze_environment(s['environment'])
    digest = 'sha256:' + hashlib.sha256(image).hexdigest()
    r = {
        'schema': 'home3d.rendering.v1', 'version': 1, 'projectDigest': 'sha256:' + '0' * 64,
        'profile': {'id': c['profileId'], 'version': c['profileVersion'], 'sourceDigest': 'sha256:' + c['profileSha256']},
        'pipeline': {'id': 'home3d.white-three-r171.v1', 'requiredCapability': 'render.pipeline.three-r171-white.v1', 'materialModel': 'gltf-pbr-three-r171.v1', 'toneMapping': 'aces-filmic-three-r171.v1', 'environmentFilter': 'pmrem-ggx-three-r171.v1', 'studioSourceDigest': 'sha256:' + hashlib.sha256((HERE.parents[1] / 'interior-orchestrator/assets/white-viewer/studio.js').read_bytes()).hexdigest()},
        'compatibility': {'mode': 'strict', 'onUnsupported': 'reject', 'allowAutomaticQualityReduction': False},
        'renderer': {'workingColorSpace': 'linear-srgb', 'outputColorSpace': 'srgb', 'whitePoint': 'D65', 'exposureMultiplier': number(renderer['exposure']), 'exposureCompensationEV': 0, 'autoExposure': False, 'whiteBalance': 'identity', 'outputAlpha': 1, 'referenceTarget': 'rgba8-unorm', 'premultipliedAlpha': False, 'logarithmicDepthBuffer': False, 'reverseDepthBuffer': False, 'antialias': {'method': 'msaa', 'samples': 4}, 'interactiveMaxPixelRatio': renderer['maxPixelRatio'], 'postprocessing': {k: False for k in ['ssao', 'bloom', 'fxaa', 'taa', 'dithering', 'fog']}},
        'background': {'color': s['background'].lower(), 'toneMapped': False},
        'environment': {'mode': 'equirectangular-image', 'file': 'blobs/' + digest[7:] + '.png', 'digest': digest, 'width': s['environment']['width'], 'height': s['environment']['height'], 'colorSpace': 'srgb', 'intensity': s['environmentIntensity'], 'rotationYRadians': 0, 'projection': 'three-r171-equirect.v1', 'wrapS': 'repeat', 'wrapT': 'clamp', 'filter': 'linear', 'useAsBackground': False},
        'lights': [
            {'id': 'studio-hemi', 'kind': 'hemisphere', 'skyColor': s['hemisphereSky'].lower(), 'groundColor': s['hemisphereGround'].lower(), 'intensity': s['hemisphereIntensity'], 'intensityUnit': 'three-r171-linear', 'up': [0, 1, 0]},
            {'id': 'studio-key', 'kind': 'directional', 'color': s['keyColor'].lower(), 'positionM': s['keyPosition'], 'targetM': s['target'], 'intensity': s['keyIntensity'], 'intensityUnit': 'three-r171-linear', 'shadow': {'enabled': True, 'algorithm': 'three-r171-vsm.v1', 'mapSize': [p['mapSize']] * 2, 'bias': p['bias'], 'normalBiasM': p['normalBias'], 'radiusTexels': p['radius'], 'blurSamples': p['blurSamples'], 'camera': {'projection': 'orthographic', **p['frustum']}}},
            {'id': 'studio-fill', 'kind': 'directional', 'color': s['fillColor'].lower(), 'positionM': s['fillPosition'], 'targetM': s['target'], 'intensity': s['fillIntensity'], 'intensityUnit': 'three-r171-linear', 'shadow': {'enabled': False}}],
        'modelLightShadows': [],
        'shadowPolicy': {'enabled': True, 'update': 'on-change-before-frame', 'maxShadowedDirectionalLights': 1, 'maxShadowedPointLights': p['maxShadowedFixtures'], 'opaque': {'cast': True, 'receive': True}, 'transparent': {'cast': False, 'receive': False}, 'overrides': []},
        'contactAO': {'mode': 'baked-vertex', 'attribute': 'COLOR_0', 'valueColorSpace': 'linear', 'combine': 'multiply-base-color-once', 'runtimeStrength': 1, 'bakeProvenance': {'samples': ao['samples'], 'distanceM': ao['distanceM'], 'strength': ao['strength'], 'lightEmissionBaked': False}, 'onGeometryChange': 'keep-bake-and-report-stale'},
        'ground': {'enabled': True, 'positionM': s['groundPosition'], 'sizeM': [max(c['boundsM'][2:]) * 10] * 2, 'color': s['ground'].lower(), 'roughness': 1, 'metallic': 0, 'castShadow': False, 'receiveShadow': True},
        'geometryPresentation': {'cutaway': False, 'frontWallFade': False, 'roomIsolation': False, 'outlines': False},
        'views': [{'id': key, 'name': v['name'], 'projection': 'orthographic', 'positionM': v['position'], 'targetM': v['target'], 'up': [0, 1, 0], 'verticalSpanM': v['width'] / aspect, 'nearM': .05, 'farM': max(160, p['frustum']['far'] * 2), 'aspectRatio': aspect} for key, v in c['views'].items()],
        'defaultViewId': c['defaultView'],
        'referenceCapture': {'pixelRatio': 1, 'widthPx': 1600, 'heightPx': 1200, 'timeMs': 0, 'deviceState': 'contract-initial', 'waitForAssets': True, 'waitForShadowUpdate': True, 'disableAdaptiveQuality': True}}
    policies = {'shadowedFixtureIds': [f['id'] for f in c['fixtures'][:p['maxShadowedFixtures']]], 'mapSize': p['pointMapSize']}
    return r, image, policies


def prepare(stage, lighting, explicit=None, asset_root=None):
    if asset_root and not explicit:
        raise ValueError('--rendering-assets requires --rendering')
    if explicit:
        source = Path(explicit).resolve()
        document = json.loads(source.read_text())
        file = document['environment']['file']
        if not re.fullmatch(r'blobs/[0-9a-f]{64}\.png', file):
            raise ValueError('RENDER_SOURCE: environment must be a package PNG content address')
        root = Path(asset_root).resolve() if asset_root else source.parent
        asset = (root / file).resolve()
        try:
            asset.relative_to(root)
        except ValueError:
            raise ValueError('RENDER_SOURCE: environment escapes the authoring asset root') from None
        image = asset.read_bytes()
        generated = None
        provenance = {'kind': 'explicit', 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
    elif lighting and lighting.get('profileId') == 'white-home3d-v1':
        document, image, generated = white_document(lighting)
        provenance = {'kind': 'white-profile', 'environmentRasterizer': 'vertical-srgb-pixel-centers.v1'}
    else:
        return None
    file = document['environment']['file']
    target = stage / file
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(image)
    (stage / 'rendering.json').write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n')
    return {'file': 'rendering.json', 'generatedModelShadows': generated, 'provenance': provenance}
