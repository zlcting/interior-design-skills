"""Rendering export behavior, using the real bundled SDK, Blender and editor runtime."""
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
from test_home3d import ROOT, SCRIPT, NODE, BLENDER, EDITOR_SOURCE, glb, project, exporter

sys.path.insert(0, str(ROOT / 'skills/interior-orchestrator/scripts'))
from white_render_profile import build_config
from rendering_config import white_document, freeze_environment


def white_config(model, raw, fixtures=False):
    plan = {'style': {'id': 'white-minimal'}, 'furniture': [], 'accessories': []}
    c = build_config(model, plan, 'ROOM')
    c['geometrySha256'] = hashlib.sha256(raw).hexdigest()
    if fixtures:
        c['fixtures'] = [{'id': 'FURN_A', 'position': [1.12, .85, -.92], 'color': '#ffce8b', 'maxIntensity': 30,
                          'initialBrightness': 65, 'initialCctK': 2700, 'rangeM': 4.8, 'emitterOffsetM': [.04, .02, -.03]}]
    return c


class RenderingSourceTests(unittest.TestCase):
    def test_project_coordinates_and_source_settings_are_preserved(self):
        c = white_config(project(), glb()); before = copy.deepcopy(c)
        r, image, _ = white_document(c)
        self.assertEqual(c, before)
        self.assertEqual(r['lights'][1]['positionM'], c['studio']['keyPosition'])
        self.assertEqual(r['lights'][1]['shadow']['camera']['left'], c['shadows']['frustum']['left'])
        self.assertEqual(r['renderer']['exposureMultiplier'], c['renderer']['exposure'])
        self.assertEqual(r['views'][0]['positionM'], c['views']['overview']['position'])
        self.assertEqual(r['environment']['digest'], 'sha256:' + hashlib.sha256(image).hexdigest())
        self.assertEqual(struct.unpack('>II', image[16:24]), (256, 128))
        self.assertEqual(image, freeze_environment(c['studio']['environment']))
        shifted = project(); shifted['rooms'][0]['rect'][0] -= 15000; shifted['rooms'][0]['rect'][1] += 3500
        t, shifted_image, _ = white_document(white_config(shifted, glb()))
        for key in ['positionM', 'targetM']:
            self.assertAlmostEqual(t['lights'][1][key][0] - r['lights'][1][key][0], -15)
            self.assertAlmostEqual(t['lights'][1][key][2] - r['lights'][1][key][2], -3.5)
        self.assertEqual(image, shifted_image)

    def test_unsupported_pipeline_and_invalid_environment_are_rejected(self):
        c = white_config(project(), glb()); c['renderer']['toneMapping'] = 'AgX'
        with self.assertRaisesRegex(ValueError, 'different versioned rendering pipeline'):
            white_document(c)
        c = white_config(project(), glb()); c['studio']['environment']['width'] = 100000
        with self.assertRaisesRegex(ValueError, 'rasterizer limits'):
            white_document(c)


class RenderingComparisonTests(unittest.TestCase):
    def test_viewport_and_nearest_rank_p99_are_enforced(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'browser.json').write_text(json.dumps({'views':['overview','focus'],'capture':{'widthPx':10,'heightPx':10}}))
            for client in ['chrome','webkit']:
                for state in ['original','reimported']:
                    for view in ['overview','focus']:
                        Image.new('RGB',(10,10),(100,100,100)).save(root/f'{client}-{state}-{view}.png')
            for name in ['half-exposure','key-off','shadows-off','environment-off']:
                Image.new('RGB',(10,10),(130,130,130)).save(root/f'chrome-{name}.png')
            changed=root/'webkit-reimported-focus.png'
            image=Image.open(changed);image.putpixel((0,0),(255,100,100));image.save(changed)
            tool=ROOT/'tests/compare_home3d_rendering.py'
            a=subprocess.run([sys.executable,str(tool),str(root)],capture_output=True,text=True)
            self.assertEqual(a.returncode,0,a.stderr)
            self.assertEqual(json.loads((root/'pixels.json').read_text())['pairs'][-1]['p99MaxChannelError'],0)
            image.putpixel((1,0),(255,100,100));image.save(changed)
            b=subprocess.run([sys.executable,str(tool),str(root)],capture_output=True,text=True)
            self.assertNotEqual(b.returncode,0)
            pixels=json.loads((root/'pixels.json').read_text())
            self.assertLess(pixels['pairs'][-1]['meanAbsoluteError'],2/255)
            self.assertGreater(pixels['pairs'][-1]['p99MaxChannelError'],8/255)
            Image.new('RGB',(9,10)).save(changed)
            c=subprocess.run([sys.executable,str(tool),str(root)],capture_output=True,text=True)
            self.assertNotEqual(c.returncode,0)
            self.assertIn('viewport sizes differ',c.stderr)


@unittest.skipUnless(BLENDER and NODE, 'Blender and Node required for full export')
class RenderingExportTests(unittest.TestCase):
    def export(self, root, *, embedded=False, sidecar=False, explicit=False, corrupt=False, out='out'):
        model = project(); model['openings'] = [{'id': 'DOOR', 'kind': 'door', 'wall': 'SOUTH', 'start': 500, 'width': 900, 'height': 2100, 'sill': 0}]
        (root / 'model').mkdir(exist_ok=True); (root / 'model/project.json').write_text(json.dumps(model))
        raw = glb(embedded_light=embedded); (root / 'source.glb').write_bytes(raw)
        c = white_config(model, raw, sidecar); extra = []
        if explicit:
            r, image, _ = white_document(c); r['renderer']['exposureMultiplier'] = 1.15
            r['lights'][1]['intensity'] = 1.9
            assets = root / 'authoring'; asset = assets / r['environment']['file']; asset.parent.mkdir(parents=True, exist_ok=True)
            asset.write_bytes(image[:-1] + bytes([image[-1] ^ 1]) if corrupt else image)
            (root / 'rendering.json').write_text(json.dumps(r))
            extra = ['--rendering', str(root / 'rendering.json'), '--rendering-assets', str(assets)]
        else:
            (root / 'lighting.json').write_text(json.dumps(c)); extra = ['--lighting', str(root / 'lighting.json')]
        result = subprocess.run([sys.executable, str(SCRIPT / 'export_home3d.py'), str(root), '--geometry', str(root / 'source.glb'), '--out', str(root / out), *extra], text=True, capture_output=True)
        self.assertEqual(hashlib.sha256((root / 'source.glb').read_bytes()).hexdigest(), hashlib.sha256(raw).hexdigest())
        return result

    def test_white_export_is_complete_deterministic_and_capability_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); result = self.export(root, sidecar=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            a = (root / 'out/project.home3d').read_bytes()
            result = self.export(root, sidecar=True, out='repeat')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(a, (root / 'repeat/project.home3d').read_bytes())
            with zipfile.ZipFile(root / 'out/project.home3d') as z:
                m, r = json.loads(z.read('package.json')), json.loads(z.read('rendering.json'))
                self.assertEqual(m['entries']['rendering'], 'rendering.json')
                self.assertEqual(r['profile']['id'], 'soft-studio-v1')
                self.assertEqual(r['lights'][1]['shadow']['blurSamples'], 16)
                self.assertLessEqual(r['lights'][1]['shadow']['radiusTexels'], 24)
                scene=json.loads(z.read('project.json'))
                self.assertTrue(all(w['materialKey'] for w in scene['floors'][0]['walls']))
                self.assertTrue(all(r['materialKey'] for r in scene['floors'][0]['rooms']))
                self.assertTrue({'render.scene.v1', 'render.pipeline.three-r171-white.v1'} <= set(m['requiredCapabilities']))
                self.assertEqual(r['projectDigest'], 'sha256:' + hashlib.sha256(z.read('project.json')).hexdigest())
                self.assertEqual(r['environment']['digest'], 'sha256:' + hashlib.sha256(z.read(r['environment']['file'])).hexdigest())
                self.assertEqual(r['modelLightShadows'][0]['instanceId'], 'instance-FURN_A')
                self.assertEqual(r['modelLightShadows'][0]['lightId'], 'FURN_A')
                self.assertTrue(r['modelLightShadows'][0]['shadow']['enabled'])
                self.assertEqual(len(r['lights']), 6)  # 4 key samples, fill, hemisphere; model lamps stay local
                keys = [light for light in r['lights'] if light['kind'] == 'directional' and light['shadow']['enabled']]
                self.assertEqual(len(keys), 4)
                self.assertAlmostEqual(sum(light['intensity'] for light in keys), 1.5)
                self.assertEqual(r['shadowPolicy']['maxShadowedDirectionalLights'], 4)
            report = json.loads((root / 'out/acceptance.json').read_text())
            self.assertEqual(report['sdk']['version'], '0.3.1')
            self.assertEqual(report['rendering']['status'], 'protocol-passed')
            self.assertEqual(report['visualReview']['status'], 'not_reviewed')
            self.assertTrue(json.loads((root / 'out/world-verification.json').read_text())['passed'])
            script = "const s=require(process.argv[1]),f=require('fs');(async()=>{const b=f.readFileSync(process.argv[2]);let r=await s.validatePackage(b,{capabilities:s.CAPABILITIES.filter(x=>!x.startsWith('render.'))});if(r.valid||r.errors[0].code!=='UNSUPPORTED_CAPABILITY')throw Error(JSON.stringify(r));const p=await s.readPackage(b);p.rendering.projectDigest='sha256:'+'0'.repeat(64);const entries=Object.fromEntries(Object.entries(p.entries).filter(([k])=>!['package.json',...Object.values(p.manifest.entries)].includes(k)));try{await s.writePackage({version:4,kind:'project',name:p.manifest.name,project:p.project,resources:p.resources,devices:p.devices,presentation:p.presentation,rendering:p.rendering,entries,requiredCapabilities:p.manifest.requiredCapabilities});throw Error('accepted stale digest')}catch(e){if(e.code!=='RENDER_PROJECT_DIGEST')throw e}})().catch(e=>{console.error(e);process.exit(1)})"
            checked = subprocess.run([NODE, '-e', script, str(SCRIPT / 'vendor/home3d-package.cjs'), str(root / 'out/project.home3d')], text=True, capture_output=True)
            self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_explicit_configuration_is_kept_and_environment_corruption_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); result = self.export(root, explicit=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            with zipfile.ZipFile(root / 'out/project.home3d') as z:
                r = json.loads(z.read('rendering.json')); self.assertEqual(r['renderer']['exposureMultiplier'], 1.15)
                self.assertEqual(r['lights'][1]['intensity'], 1.9)
            result = self.export(root, explicit=True, corrupt=True, out='bad')
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue('HASH_MISMATCH' in result.stderr or 'BLOB_ADDRESS' in result.stderr, result.stderr)
            self.assertFalse((root / 'bad').exists())

    def test_embedded_point_lights_have_explicit_noninvented_shadow_policies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); result = self.export(root, embedded=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            with zipfile.ZipFile(root / 'out/project.home3d') as z:
                r = json.loads(z.read('rendering.json')); self.assertEqual(len(r['modelLightShadows']), 1)
                self.assertEqual(r['modelLightShadows'][0]['shadow'], {'enabled': False})
                self.assertEqual(r['modelLightShadows'][0]['instanceId'], 'instance-FURN_A')

    @unittest.skipUnless(EDITOR_SOURCE, 'Set HOME3D_EDITOR_SOURCE for editor runtime')
    def test_rendering_survives_real_editor_save_and_reimport(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); result = self.export(root, sidecar=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            checked = subprocess.run([NODE, str(ROOT / 'tests/verify_home3d_editor.mjs'), str(root / 'out/project.home3d'), EDITOR_SOURCE, str(root / 'editor-review')], text=True, capture_output=True)
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            report = json.loads((root / 'editor-review/acceptance.json').read_text())
            self.assertTrue(report['checks']['renderingPreserved'])
