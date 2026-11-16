"""Blender worker: preserve evaluated geometry and materials while exporting logical objects."""
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'interior-orchestrator/scripts'))
from exchange_validation import signature, verify_roundtrip

job_file = Path(sys.argv[sys.argv.index('--') + 1])
job = json.loads(job_file.read_text())
root = job_file.parent
model = job['project']
source_items = {v['id']: v for v in model['furniture']}
source_items.update({v['id']: v for v in model.get('lights', [])})
walls = {v['id'] for v in model['walls']}
rooms = {v['id'] for v in model['rooms']}
windows = {v['id']: v for v in model['openings'] if v['kind'] == 'window'}
node_owners = job['mapping'].get('nodeOwners', {})
objects_meta = job['mapping'].get('objects', {})
records = []
skipped = []
light_groups = {}


def read_scene(file):
    if Path(file).suffix.lower() == '.blend':
        bpy.ops.wm.open_mainfile(filepath=str(file))
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=str(file))
    bpy.context.view_layer.update()


def owner(obj):
    value = node_owners.get(obj.name, obj.get('object_id'))
    if not isinstance(value, str) or not value:
        raise ValueError('OBJECT_MAPPING_REQUIRED: ' + obj.name)
    return value


def window_owner(value):
    return next((key for key in windows if value == key or value.startswith(key + ' ')), None)


def collect(full_windows=False):
    groups = {}
    is_blend = Path(job['fullSource'] if full_windows else job['geometry']).suffix.lower() == '.blend'
    for obj in list(bpy.context.scene.objects):
        if obj.type != 'MESH':
            continue
        value = owner(obj)
        window = window_owner(value)
        if full_windows:
            if not window or is_blend and not any(c.name.startswith('Full walls') for c in obj.users_collection):
                continue
            groups.setdefault(window, []).append(obj)
        elif window:
            if not is_blend or any(c.name.startswith('Full walls') for c in obj.users_collection):
                groups.setdefault('window:' + window, []).append(obj)
        elif value in walls or value in {r + ' floor' for r in rooms} or value in ['floor joint', 'tile joint', 'Presentation foundation']:
            skipped.append({'node': obj.name, 'sourceId': value, 'reason': 'native-architecture'})
        else:
            groups.setdefault(value, []).append(obj)
    return groups


def points(objects):
    graph = bpy.context.evaluated_depsgraph_get()
    return [Vector(p) for obj in objects for p in signature(obj, graph)]


def frame_height(objects):
    ps = points(objects)
    return max(p.z for p in ps) - min(p.z for p in ps)


def export_group(key, objects, opening=None):
    pts = points(objects)
    low = [min(p[i] for p in pts) for i in range(3)]
    high = [max(p[i] for p in pts) for i in range(3)]
    origin = Vector(((low[0] + high[0]) / 2, (low[1] + high[1]) / 2, low[2]))
    data = {**source_items.get(key, {}), **objects_meta.get(key, {})}
    angle = {'south': 0, 'north': math.pi, 'east': math.pi / 2, 'west': -math.pi / 2}.get(data.get('facing'), 0)
    local_matrix = Matrix.Rotation(-angle, 4, 'Z') @ Matrix.Translation(-origin)
    collection = bpy.data.collections.new('Home3D export')
    bpy.context.scene.collection.children.link(collection)
    copies = []
    for index, obj in enumerate(sorted(objects, key=lambda item: (str(item.get('part_name', item.name)).replace(key, ''), item.name))):
        mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(bpy.context.evaluated_depsgraph_get()), preserve_all_data_layers=True, depsgraph=bpy.context.evaluated_depsgraph_get())
        mesh.name = 'home3d-mesh-' + str(index)
        mesh.transform(local_matrix @ obj.matrix_world)
        for vertex in mesh.vertices:
            vertex.co = tuple(round(float(v), 6) for v in vertex.co)
        clone = bpy.data.objects.new('home3d-part-' + str(index), mesh)
        collection.objects.link(clone)
        clone['exchange_source_id'] = clone.name
        copies.append(clone)
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    local_pts = [Vector(v) for item in copies for v in signature(item, graph)]
    center = Vector(((min(p.x for p in local_pts) + max(p.x for p in local_pts)) / 2,
                     (min(p.y for p in local_pts) + max(p.y for p in local_pts)) / 2, min(p.z for p in local_pts)))
    for clone in copies:
        clone.data.transform(Matrix.Translation(-center))
    origin += Matrix.Rotation(angle, 3, 'Z') @ center
    light_copies = []
    for index, light in enumerate(light_groups.get(key, [])):
        clone = bpy.data.objects.new('home3d-light-' + str(index), light.data.copy())
        collection.objects.link(clone)
        clone.matrix_world = Matrix.Translation(-center) @ local_matrix @ light.matrix_world
        light_copies.append(clone)
    bpy.context.view_layer.update()
    expected = {item.name: signature(item) for item in copies}
    bpy.ops.object.select_all(action='DESELECT')
    for clone in copies + light_copies:
        clone.select_set(True)
    file = root / 'models' / (hashlib.sha256(key.encode()).hexdigest()[:24] + '.glb')
    bpy.ops.export_scene.gltf(filepath=str(file), use_selection=True, export_format='GLB', export_apply=True,
        export_extras=True, export_cameras=False, export_lights=bool(light_copies), export_vertex_color='ACTIVE')
    verification = verify_roundtrip(file, expected)
    raw = file.read_bytes()
    gltf = json.loads(raw[20:20 + struct.unpack_from('<I', raw, 12)[0]])
    color_count = sum('COLOR_0' in primitive['attributes'] for mesh in gltf.get('meshes', []) for primitive in mesh['primitives'])
    expected_color = sum(bool(o.data.color_attributes) for o in objects)
    if expected_color and not color_count:
        raise ValueError('Vertex colors lost: ' + key)
    cloud = file.with_suffix('.world.bin')
    cloud.write_bytes(b''.join(struct.pack('<3d', p.x, p.z, -p.y) for p in pts))
    record = {'sourceWorldVertices': cloud.relative_to(root).as_posix(), 'sourceId': key, 'name': data.get('name', key), 'room': data.get('room'),
        'file': file.relative_to(root).as_posix(), 'sourceNodes': [o.name for o in objects],
        'position': [origin.x, origin.z, -origin.y], 'rotationY': angle,
        'rotation': [0, math.sin(angle / 2), 0, math.cos(angle / 2)],
        'sourceWorldBounds': {'min': [low[0], low[2], -high[1]], 'max': [high[0], high[2], -low[1]]},
        'geometryVerification': verification, 'colorPrimitives': color_count, 'embeddedLights': len(light_copies),
        'openingId': opening, 'sourceWindowHeightM': (windows[opening]['height'] / 1000 if opening else None)}
    records.append(record)
    for clone in light_copies:
        data = clone.data
        bpy.data.objects.remove(clone, do_unlink=True)
        bpy.data.lights.remove(data)
    for clone in copies:
        mesh = clone.data
        bpy.data.objects.remove(clone, do_unlink=True)
        bpy.data.meshes.remove(mesh)
    bpy.data.collections.remove(collection)


read_scene(job['geometry'])
groups = collect()
missing = set(v['id'] for v in model['furniture']) - set(groups)
if missing:
    raise ValueError('Missing furniture geometry: ' + ', '.join(sorted(missing)))
source_lights = [obj for obj in bpy.context.scene.objects if obj.type == 'LIGHT']
for light in source_lights:
    candidate = light
    logical = None
    while candidate:
        logical = node_owners.get(candidate.name, candidate.get('object_id'))
        if logical in groups:
            break
        candidate = candidate.parent
    if not logical or logical not in groups:
        if Path(job['geometry']).suffix.lower() == '.blend' and light.data.type in ['AREA', 'SUN']:
            skipped.append({'node': light.name, 'reason': 'Cycles studio light; supply declarative GLB lighting for portable fixtures'})
            continue
        raise ValueError('LIGHT_OWNER_REQUIRED: ' + light.name)
    if (job.get('lighting') or {}).get('fixtures'):
        raise ValueError('DUPLICATE_LIGHTING: embedded light plus sidecar fixtures')
    if light.data.type not in ['POINT', 'SPOT', 'SUN']:
        raise ValueError('Unsupported portable light type: ' + light.name)
    light_groups.setdefault(logical, []).append(light)
for key in sorted(groups):
    if not key.startswith('window:'):
        export_group(key, groups[key])
if windows:
    if job.get('fullSource'):
        read_scene(job['fullSource'])
        frame_groups = collect(True)
    else:
        frame_groups = {key[7:]: values for key, values in groups.items() if key.startswith('window:')}
    for key, opening in windows.items():
        items = frame_groups.get(key, [])
        if not items or abs(frame_height(items) - opening['height'] / 1000) > 0.002:
            raise ValueError('FULL_HEIGHT_WINDOW_REQUIRED: ' + key + '; provide --full-source from the same project')
        ps = points(items)
        bounds = [[min(p[i] for p in ps), max(p[i] for p in ps)] for i in range(3)]
        wall = next(w for w in model['walls'] if w['id'] == opening['wall'])
        center = [opening['start'] + opening['width'] / 2, wall['at'] + wall['thickness'] / 2] if wall['axis'] == 'x' else [wall['at'] + wall['thickness'] / 2, opening['start'] + opening['width'] / 2]
        if any(abs((bounds[i][0] + bounds[i][1]) / 2 - center[i] / 1000) > .002 for i in range(2)):
            raise ValueError('FULL_SOURCE_POSITION_MISMATCH: ' + key)
        if abs(bounds[2][0] - opening.get('sill', 0) / 1000) > .002:
            raise ValueError('FULL_SOURCE_SILL_MISMATCH: ' + key)
        export_group(key, items, key)
(root / 'components.json').write_text(json.dumps({'schema': 'interior.home3d-components.v1',
    'components': records, 'skippedArchitecture': skipped}, ensure_ascii=False, indent=2) + '\n')
print('HOME3D_COMPONENTS', len(records), flush=True)
