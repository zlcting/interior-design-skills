"""Behavior checks for structured Home3D export and the real bundled SDK."""
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/interior-home3d'
SCRIPT = SKILL / 'scripts'
spec = importlib.util.spec_from_file_location('home3d_export', SCRIPT / 'export_home3d.py')
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)
NODE = shutil.which('node')
BLENDER = shutil.which('blender')
EDITOR_SOURCE = os.environ.get('HOME3D_EDITOR_SOURCE')


def project():
    return {'project_id': 'test-home', 'title': 'Test home', 'revision': 1, 'units': 'mm', 'height_mm': 2800,
        'rooms': [{'id': 'ROOM', 'name': 'Room', 'rect': [0, 0, 4000, 3000]}],
        'walls': [{'id': 'SOUTH', 'axis': 'x', 'start': 0, 'end': 4000, 'at': -200, 'thickness': 200, 'height': 2800}],
        'openings': [], 'furniture': [{'id': 'FURN_A', 'name': 'Chair A', 'room': 'ROOM', 'rect': [750, 750, 500, 500]},
            {'id': 'FURN_B', 'name': 'Chair B', 'room': 'ROOM', 'rect': [1750, 750, 500, 500]}]}


def glb(with_ids=True, asymmetric=False, embedded_light=False):
    vertices = [(-.25, 0, -.25), (.25, 0, -.25), (.25, 1, -.25), (-.25, 1, -.25),
                (-.25, 0, .25), (.25, 0, .25), (.25, 1, .25), (-.25, 1, .25)]
    if asymmetric:
        vertices[0] = (-.13, 0, -.25)
    indices = [0, 2, 1, 0, 3, 2, 4, 5, 6, 4, 6, 7, 0, 1, 5, 0, 5, 4, 3, 7, 6, 3, 6, 2, 0, 4, 7, 0, 7, 3, 1, 2, 6, 1, 6, 5]
    position = struct.pack('<24f', *(v for p in vertices for v in p))
    colors = struct.pack('<32f', *([.7, .7, .7, 1] * 8))
    triangles = struct.pack('<36H', *indices)
    binary = position + colors + triangles
    nodes = [{'name': name, 'mesh': 0, 'translation': [x, 0, -1], **({'extras': {'object_id': name, 'interior_normal_policy':'triangle-area-v1'}} if with_ids else {})}
             for name, x in [('FURN_A', 1), ('FURN_B', 2)]]
    document = {'asset': {'version': '2.0'}, 'scene': 0, 'scenes': [{'nodes': [0, 1]}], 'nodes': nodes,
        'buffers': [{'byteLength': len(binary)}], 'bufferViews': [{'buffer': 0, 'byteOffset': 0, 'byteLength': len(position)},
            {'buffer': 0, 'byteOffset': len(position), 'byteLength': len(colors)},
            {'buffer': 0, 'byteOffset': len(position) + len(colors), 'byteLength': len(triangles)}],
        'accessors': [{'bufferView': 0, 'componentType': 5126, 'count': 8, 'type': 'VEC3', 'min': [-.25, 0, -.25], 'max': [.25, 1, .25]},
            {'bufferView': 1, 'componentType': 5126, 'count': 8, 'type': 'VEC4'},
            {'bufferView': 2, 'componentType': 5123, 'count': 36, 'type': 'SCALAR'}],
        'materials': [{'name': 'White', 'doubleSided': True, 'pbrMetallicRoughness': {'baseColorFactor': [1, 1, 1, 1], 'roughnessFactor': .8, 'metallicFactor': 0}}],
        'meshes': [{'primitives': [{'attributes': {'POSITION': 0, 'COLOR_0': 1}, 'indices': 2, 'material': 0}]}]}
    if embedded_light:
        document['extensionsUsed'] = ['KHR_lights_punctual']
        document['extensions'] = {'KHR_lights_punctual': {'lights': [{'type': 'point', 'intensity': 15, 'color': [1, .8, .6]}]}}
        document['nodes'].append({'name': 'Chair light', 'translation': [0, .8, 0], 'extensions': {'KHR_lights_punctual': {'light': 0}}})
        document['nodes'][0]['children'] = [2]
    text = json.dumps(document, separators=(',', ':')).encode()
    text += b' ' * (-len(text) % 4)
    binary += b'\0' * (-len(binary) % 4)
    return struct.pack('<III', 0x46546C67, 2, 28 + len(text) + len(binary)) + struct.pack('<II', len(text), 0x4E4F534A) + text + struct.pack('<II', len(binary), 0x004E4942) + binary


class StructureTests(unittest.TestCase):
    def test_centerline_units_and_room_orientation(self):
        scene = exporter.geometry_model(project())
        wall = scene['floors'][0]['walls'][0]
        self.assertEqual(wall['start'], {'x': 0, 'z': .1})
        self.assertEqual(wall['end'], {'x': 4, 'z': .1})
        self.assertEqual(wall['height'], 2.8)
        self.assertEqual(scene['floors'][0]['rooms'][0]['boundary'][1], {'x': 0, 'z': -3})

    def test_offset_negative_coordinates_and_sliding_door(self):
        model = project()
        wall = model['walls'][0]
        wall.update(axis='y', start=-3000, end=1000, at=-2200)
        model['openings'] = [{'id': 'DOOR', 'wall': 'SOUTH', 'kind': 'sliding', 'start': -2000, 'width': 900, 'height': 2100, 'sill': 0}]
        scene = exporter.geometry_model(model)
        self.assertEqual(scene['floors'][0]['walls'][0]['start'], {'x': -2.1, 'z': 3})
        opening = scene['floors'][0]['openings'][0]
        self.assertEqual(opening['offset'], 1.45)
        self.assertEqual(opening['kind'], 'door')
        self.assertEqual(opening['wallId'], 'wall-SOUTH')

    def test_l_shaped_source_preserves_independent_rooms(self):
        scene = exporter.geometry_model(exporter.load(ROOT / 'projects/TEST-L-084/model/project.json'))
        self.assertEqual(len(scene['floors'][0]['rooms']), 6)
        self.assertEqual(len(scene['floors'][0]['walls']), 11)
        self.assertEqual(len(scene['floors'][0]['openings']), 12)

    def test_missing_structure_is_not_treated_as_a_whole_furniture(self):
        model = project()
        del model['walls']
        with self.assertRaisesRegex(ValueError, 'Missing editable structure'):
            exporter.geometry_model(model)

    def test_invalid_host_duplicate_id_and_unit_rejected(self):
        model = project()
        model['openings'] = [{'id': 'O', 'wall': 'NO-WALL'}]
        with self.assertRaisesRegex(ValueError, 'Missing opening host'):
            exporter.geometry_model(model)
        model = project()
        model['furniture'].append(copy.deepcopy(model['furniture'][0]))
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            exporter.geometry_model(model)
        model = project()
        model['units'] = 'm'
        with self.assertRaisesRegex(ValueError, 'explicitly use mm'):
            exporter.geometry_model(model)

    def test_text_source_revision_preserved_separately(self):
        model = project()
        model['revision'] = 'white-v2'
        scene = exporter.geometry_model(model)
        self.assertEqual(scene['revision'], 1)
        self.assertEqual(scene['extensions'][exporter.NS]['sourceRevision'], 'white-v2')


@unittest.skipUnless(NODE, 'Node 20+ required for bundled SDK')
class SdkTests(unittest.TestCase):
    def test_real_sdk_determinism_references_and_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            module = (SCRIPT / 'vendor/home3d-package.cjs').as_posix()
            model_file = root / 'box.glb'
            # One instance of a bottom-center cube for this SDK-only fixture.
            raw = glb()
            model_file.write_bytes(raw)
            script = root / 'sdk.cjs'
            script.write_text("""const fs=require('fs'); const sdk=require(MODULE);
(async()=>{
 const raw=fs.readFileSync(MODEL); const info=await sdk.inspectModel(raw,'box.glb');
 const file='blobs/'+sdk.digest(raw).slice(7)+'.glb';
 const def={schema:'home3d.model-definition.v1',kind:'model',file,defaultSize:{width:1.5,height:1,depth:.5},pivot:'bottom-center',targets:[],normalization:{translation:[-1.5,0,1],scale:[1,1,1]}};
 const input={name:'fixture',requiredCapabilities:['scene.structure.v1','model.glb.v1','model.normalization.v1'],scene:SCENE,resources:{schema:'home3d.runtime-resources.v4',resources:[{key:'box',kind:'model',definitionPath:'resources/box.json'}]},entries:{[file]:raw,'resources/box.json':def}};
 input.scene.instances=[{id:'a',kind:'furnishing',name:'a',resourceKey:'box',floorId:'floor-main',roomId:null,regionId:null,materialKey:null,visible:true,placement:'floor',host:null,transform:{position:[1,0,-1],rotation:[0,0,0,1],size:def.defaultSize}}];
 const a=await sdk.writePackage(input);const b=await sdk.writePackage(input);if(sdk.digest(a)!==sdk.digest(b))throw Error('non deterministic');
 const ok=await sdk.validatePackage(a);if(!ok.valid)throw Error('invalid fixture');
 const unsupported=await sdk.validatePackage(a,{capabilities:['scene.structure.v1']});if(unsupported.valid)throw Error('accepted unsupported editor capability');
 const unified={...input,version:4,kind:'project',project:input.scene,devices:{schema:'home3d.devices.v1',instances:[]},presentation:{schema:'home3d.presentation.v1',bindings:[]},requiredCapabilities:[...input.requiredCapabilities,'device.contracts.v1','device.presentation.v1','device.simulation.v1']};
 delete unified.scene;
 const v4=await sdk.writePackage(unified), v4repeat=await sdk.writePackage(unified), parsed=await sdk.readPackage(v4);
 if(sdk.digest(v4)!==sdk.digest(v4repeat)||parsed.format!=='v4')throw Error('invalid v4 roundtrip');
 if(JSON.stringify(parsed.project)!==JSON.stringify((await sdk.readPackage(a)).scene))throw Error('v4 geometry changed');
 const legacyOnly=await sdk.validatePackage(v4,{capabilities:input.requiredCapabilities});if(legacyOnly.valid)throw Error('accepted v3-only consumer');
 unified.requiredCapabilities=unified.requiredCapabilities.filter(c=>c!=='device.simulation.v1');
 let missingCapability=false;try{await sdk.writePackage(unified)}catch(e){missingCapability=e.code==='MISSING_CAPABILITY'}if(!missingCapability)throw Error('accepted missing v4 capability');
 input.scene.instances[0].resourceKey='missing';let failed=false;try{await sdk.writePackage(input)}catch(e){failed=true}if(!failed)throw Error('accepted broken reference');
 a[a.length>>1]^=1; const bad=await sdk.validatePackage(a);if(bad.valid)throw Error('accepted corruption');
 console.log('SDK_BEHAVIOR_PASSED');
})().catch(e=>{console.error(e);process.exitCode=1});
""".replace('MODULE', json.dumps(module)).replace('MODEL', json.dumps(str(model_file))).replace('SCENE', json.dumps(exporter.geometry_model(project()))))
            result = subprocess.run([NODE, str(script)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('SDK_BEHAVIOR_PASSED', result.stdout)

    def test_whole_house_glb_without_canonical_structure_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'source.glb').write_bytes(glb())
            result = subprocess.run([sys.executable, str(SCRIPT / 'export_home3d.py'), str(root), '--geometry', str(root / 'source.glb'), '--out', str(root / 'out')], text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Missing authoritative model/project.json', result.stderr)
            self.assertFalse((root / 'out').exists())

    def test_lighting_hash_rejected_before_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'model').mkdir()
            (root / 'model/project.json').write_text(json.dumps(project()))
            (root / 'box.glb').write_bytes(glb())
            (root / 'light.json').write_text(json.dumps({'geometrySha256': '0' * 64}))
            result = subprocess.run([sys.executable, str(SCRIPT / 'export_home3d.py'), str(root), '--geometry', str(root / 'box.glb'), '--lighting', str(root / 'light.json'), '--out', str(root / 'out')], text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('LIGHTING_SOURCE_MISMATCH', result.stderr)
            self.assertFalse((root / 'out').exists())


@unittest.skipUnless(BLENDER and NODE, 'Blender and Node required for actual geometry exchange')
class BlenderTests(unittest.TestCase):
    def run_export(self, root, with_ids=True, extra=(), source_model=None, asymmetric=False, embedded_light=False):
        (root / 'model').mkdir(exist_ok=True)
        (root / 'model/project.json').write_text(json.dumps(source_model or project()))
        source = root / 'source.glb'
        source.write_bytes(glb(with_ids, asymmetric, embedded_light))
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        result = subprocess.run([sys.executable, str(SCRIPT / 'export_home3d.py'), str(root), '--geometry', str(source), '--out', str(root / 'out'), *extra], text=True, capture_output=True)
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)
        return result

    def test_actual_grouping_reuse_vertex_colors_and_portable_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_export(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = exporter.load(root / 'out/acceptance.json')
            self.assertEqual(report['objects']['instances'], 2)
            self.assertEqual(report['objects']['modelDefinitions'], 1)
            self.assertEqual(report['package']['format'], 'v4')
            self.assertEqual(report['package']['version'], 4)
            self.assertEqual(report['package']['kind'], 'project')
            self.assertEqual(report['editorReview']['status'], 'not_reviewed')
            self.assertEqual(report['visualReview']['status'], 'not_reviewed')
            with zipfile.ZipFile(root / 'out/project.home3d') as archive:
                manifest = json.loads(archive.read('package.json'))
                self.assertEqual(manifest['schema'], 'home3d.package.v4')
                self.assertEqual(manifest['entries'], {'project': 'project.json', 'resources': 'resources.json',
                    'devices': 'devices.json', 'presentation': 'presentation.json'})
                self.assertNotIn('scene.json', archive.namelist())
                self.assertNotIn('runtime-resources.json', archive.namelist())
                self.assertEqual(json.loads(archive.read('devices.json')), {'schema': 'home3d.devices.v1', 'instances': []})
                self.assertEqual(json.loads(archive.read('presentation.json')), {'schema': 'home3d.presentation.v1', 'bindings': []})
                self.assertFalse(any('modelVersionId' in r for r in json.loads(archive.read('resources.json'))['resources']))
                self.assertNotIn('model.lighting.v1', manifest['requiredCapabilities'])
                scene=json.loads(archive.read('project.json'))
                self.assertTrue(all(w['materialKey'] is None for w in scene['floors'][0]['walls']))
                self.assertTrue(all(r['kind']=='model' for r in json.loads(archive.read('resources.json'))['resources']))
            components = exporter.load(root / 'out/components.json')['components']
            self.assertTrue(all(c['colorPrimitives'] > 0 and c['geometryVerification']['passed'] for c in components))
            check = subprocess.run([NODE, str(SCRIPT / 'package_home3d.mjs'), 'validate', str(root / 'out/project.home3d')], text=True, capture_output=True)
            self.assertEqual(check.returncode, 0, check.stderr)

    def test_white_preference_binds_native_walls_and_floors_without_tinting_models(self):
        colors=json.loads((ROOT/'skills/interior-orchestrator/references/style-presets.json').read_text())['styles']
        palette=next(style for style in colors if style['id']=='white-minimal')
        for explicit in (True,False):
            with self.subTest(explicit=explicit),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);model=project()
                if not explicit:model['visualization']={'style_id':'white-minimal'}
                result=self.run_export(root,extra=('--style','white-minimal') if explicit else (),source_model=model)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                report=exporter.load(root/'out/acceptance.json')
                self.assertEqual(report['objects']['modelDefinitions'],1)
                self.assertEqual(report['objects']['materialDefinitions'],2)
                self.assertEqual(report['structureMaterials']['status'],'bound')
                self.assertEqual(report['structureMaterials']['consumerVisualReview'],'not_reviewed')
                self.assertEqual(report['visualReview']['status'],'not_reviewed')
                with zipfile.ZipFile(root/'out/project.home3d') as z:
                    scene=json.loads(z.read('project.json'))
                    resources={r['key']:r for r in json.loads(z.read('resources.json'))['resources']}
                    for role,collection in [('wall','walls'),('floor','rooms')]:
                        for obj in scene['floors'][0][collection]:
                            resource=resources[obj['materialKey']]
                            self.assertEqual(resource['kind'],'material')
                            definition=json.loads(z.read(resource['definitionPath']))
                            rgb=[int(palette['colors'][role][i:i+2],16)/255 for i in (1,3,5)]
                            expected=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in rgb]
                            for a,b in zip(definition['baseColor'],expected):self.assertAlmostEqual(a,b,places=7)
                            self.assertEqual(definition['baseColor'][3],1)
                    resource=next(r for r in resources.values() if r['kind']=='model')
                    definition=json.loads(z.read(resource['definitionPath']));raw=z.read(definition['file'])
                    size=struct.unpack_from('<I',raw,12)[0];doc=json.loads(raw[20:20+size])
                    self.assertEqual(doc['materials'][0]['pbrMetallicRoughness'].get('baseColorFactor',[1,1,1,1]),[1,1,1,1])

    def test_rotated_sidecar_lighting_preserves_world_position_and_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = project()
            model['furniture'][0]['facing'] = 'east'
            fixture = {'id': 'LIGHT_A', 'position': [1.12, .85, -.92], 'color': '#ffce8b',
                'maxIntensity': 30, 'initialBrightness': 65, 'initialCctK': 2700, 'rangeM': 4.8,
                'emitterOffsetM': [.04, .02, -.03]}
            lighting = {'schema': 'home3d.model-lighting.v1', 'coordinateSystem': 'right-handed-y-up',
                'modelDigest': 'sha256:' + hashlib.sha256(glb(asymmetric=True)).hexdigest(), 'fixtures': [fixture]}
            (root / 'lighting.json').write_text(json.dumps(lighting))
            (root / 'mapping.json').write_text(json.dumps({'fixtures': {'LIGHT_A': 'FURN_A'}}))
            result = self.run_export(root, source_model=model, asymmetric=True,
                extra=('--lighting', str(root / 'lighting.json'), '--object-map', str(root / 'mapping.json')))
            self.assertEqual(result.returncode, 0, result.stderr)
            with zipfile.ZipFile(root / 'out/project.home3d') as archive:
                manifest = json.loads(archive.read('package.json'))
                self.assertIn('model.lighting.v1', manifest['requiredCapabilities'])
                scene = json.loads(archive.read('project.json'))
                instance = next(i for i in scene['instances'] if i['id'] == 'instance-FURN_A')
                resource = next(r for r in json.loads(archive.read('resources.json'))['resources'] if r['key'] == instance['resourceKey'])
                definition = json.loads(archive.read(resource['definitionPath']))
                light = json.loads(archive.read(definition['lightingPath']))
                self.assertEqual(light['modelDigest'], 'sha256:' + hashlib.sha256(archive.read(definition['file'])).hexdigest())
                actual = light['fixtures'][0]
                self.assertEqual(len(light['fixtures']), 1)
                for field in ['id', 'color', 'maxIntensity', 'initialBrightness', 'initialCctK', 'rangeM']:
                    self.assertEqual(actual[field], fixture[field])
                def world(vector):
                    x, y, z = vector
                    angle = math.pi / 2
                    return [math.cos(angle) * x + math.sin(angle) * z, y,
                        -math.sin(angle) * x + math.cos(angle) * z]
                offset = world(actual['emitterOffsetM'])
                position = world(actual['position'])
                for axis in range(3):
                    self.assertAlmostEqual(offset[axis], fixture['emitterOffsetM'][axis], places=6)
                    self.assertAlmostEqual(position[axis] + instance['transform']['position'][axis], fixture['position'][axis], places=6)
            self.assertTrue(exporter.load(root / 'out/world-verification.json')['passed'])

    @unittest.skipUnless(EDITOR_SOURCE, 'Set HOME3D_EDITOR_SOURCE for actual editor runtime compatibility')
    def test_v4_editor_save_refresh_export_and_reimport(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = project()
            model['openings'] = [{'id': 'DOOR', 'kind': 'door', 'wall': 'SOUTH', 'start': 500,
                'width': 900, 'height': 2100, 'sill': 0}]
            result = self.run_export(root, source_model=model, asymmetric=True, embedded_light=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            checked = subprocess.run([NODE, str(ROOT / 'tests/verify_home3d_editor.mjs'),
                str(root / 'out/project.home3d'), EDITOR_SOURCE, str(root / 'editor-review')], capture_output=True, text=True)
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            self.assertIn('HOME3D_EDITOR_ROUNDTRIP_PASSED', checked.stdout)

    def test_owned_embedded_light_is_preserved_without_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_export(root, embedded_light=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = exporter.load(root / 'out/acceptance.json')
            self.assertEqual(report['objects']['embeddedLights'], 1)
            self.assertEqual(report['objects']['lightingFixtures'], 0)
            self.assertTrue(report['protocol']['valid'])
            self.assertEqual(report['objects']['modelDefinitions'], 2)

    def test_embedded_and_sidecar_lighting_cannot_stack(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lighting = {'geometrySha256': hashlib.sha256(glb(embedded_light=True)).hexdigest(), 'fixtures': [{'id': 'FURN_A'}]}
            (root / 'lighting.json').write_text(json.dumps(lighting))
            result = self.run_export(root, embedded_light=True, extra=('--lighting', str(root / 'lighting.json')))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('DUPLICATE_LIGHTING', result.stderr)
            self.assertFalse((root / 'out').exists())

    def test_blend_is_an_explicit_geometry_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'model').mkdir()
            (root / 'model/project.json').write_text(json.dumps(project()))
            (root / 'source.glb').write_bytes(glb())
            worker = root / 'convert.py'
            worker.write_text('import bpy\nbpy.ops.wm.read_factory_settings(use_empty=True)\nbpy.ops.import_scene.gltf(filepath=' + repr(str(root / 'source.glb')) + ')\nbpy.ops.wm.save_as_mainfile(filepath=' + repr(str(root / 'source.blend')) + ')\n')
            converted = subprocess.run([BLENDER, '-b', '-t', '2', '--python-exit-code', '1', '--python', str(worker)], text=True, capture_output=True)
            self.assertEqual(converted.returncode, 0, converted.stderr)
            result = subprocess.run([sys.executable, str(SCRIPT / 'export_home3d.py'), str(root), '--geometry', str(root / 'source.blend'), '--out', str(root / 'out')], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(exporter.load(root / 'out/world-verification.json')['passed'])

    def test_quarter_turn_world_geometry_and_forged_rotation_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = project()
            for item in model['furniture']:
                item['facing'] = 'east'
            result = self.run_export(root, source_model=model, asymmetric=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            world = exporter.load(root / 'out/world-verification.json')
            self.assertTrue(world['passed'])
            script = root / 'forge.cjs'
            script.write_text("""const fs=require('fs');const sdk=require(MODULE);
(async()=>{const p=await sdk.readPackage(fs.readFileSync(FILE));p.project.instances[0].transform.rotation[1]*=-1;
const entries=Object.fromEntries(Object.entries(p.entries).filter(([k])=>!['package.json',...Object.values(p.manifest.entries)].includes(k)));
const raw=await sdk.writePackage({version:4,kind:'project',name:p.manifest.name,project:p.project,resources:p.resources,devices:p.devices,presentation:p.presentation,requiredCapabilities:p.manifest.requiredCapabilities,entries});fs.writeFileSync(FILE,raw)})().catch(e=>{console.error(e);process.exitCode=1});
""".replace('MODULE', json.dumps(str(SCRIPT / 'vendor/home3d-package.cjs'))).replace('FILE', json.dumps(str(root / 'out/project.home3d'))))
            forged = subprocess.run([NODE, str(script)], capture_output=True, text=True)
            self.assertEqual(forged.returncode, 0, forged.stderr)
            check_job = root / 'out/recheck.json'
            check_job.write_text(json.dumps({'geometryToleranceM': .00002}))
            checked = subprocess.run([sys.executable, str(SCRIPT / 'verify_world.py'), str(check_job)], capture_output=True, text=True)
            self.assertNotEqual(checked.returncode, 0)
            self.assertIn('SOURCE_WORLD_GEOMETRY_MISMATCH', checked.stderr)

    def test_missing_full_height_window_geometry_is_not_silently_reconstructed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = project()
            model['openings'] = [{'id': 'WINDOW', 'kind': 'window', 'wall': 'SOUTH', 'start': 500, 'width': 1000, 'height': 1000, 'sill': 850}]
            result = self.run_export(root, source_model=model)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('FULL_HEIGHT_WINDOW_REQUIRED', result.stderr)
            self.assertFalse((root / 'out').exists())

    def test_incomplete_node_mapping_fails_without_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_export(root, False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('OBJECT_MAPPING_REQUIRED', result.stderr)
            self.assertFalse((root / 'out').exists())


if __name__ == '__main__':
    unittest.main()
