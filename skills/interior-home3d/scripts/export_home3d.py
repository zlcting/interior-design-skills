#!/usr/bin/env python3
"""Export a locked interior project as an editable, self-contained Home3D v4 project package."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
NS = 'org.houzzkit.interior'
sys.path.insert(0, str(HERE))
from rendering_config import prepare as prepare_rendering
from structure_materials import white_structure_materials


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def finite(value, label, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or positive and value <= 0:
        raise ValueError('Invalid ' + label)
    return value


def identity(value):
    import re
    if not isinstance(value, str) or not value:
        raise ValueError('Missing stable source object ID')
    return value if re.fullmatch(r'[A-Za-z][A-Za-z0-9_.:-]{0,100}', value) else 'id-' + hashlib.sha256(value.encode()).hexdigest()[:24]


def geometry_model(model):
    if model.get('units') != 'mm':
        raise ValueError('model/project.json must explicitly use mm')
    for field in ['walls', 'openings', 'rooms', 'furniture']:
        if not isinstance(model.get(field), list):
            raise ValueError('Missing editable structure: ' + field)
    all_ids = []
    for field in ['walls', 'openings', 'rooms', 'furniture']:
        ids = [o.get('id') for o in model[field]]
        for item in ids:
            identity(item)
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate source IDs in ' + field)
        all_ids.extend(ids)
    walls = {w['id']: w for w in model['walls']}
    height = model.get('height_mm', model.get('ceiling_height_mm'))
    if height is None:
        height = max((w.get('height', 0) for w in walls.values()), default=0)
    finite(height, 'floor height', True)
    floor_id = 'floor-main'
    floor = {'id': floor_id, 'name': '一层', 'elevation': 0, 'height': height / 1000,
             'walls': [], 'openings': [], 'rooms': [], 'regions': [], 'dividers': []}
    for wall in walls.values():
        if wall.get('axis') not in ['x', 'y']:
            raise ValueError('Only straight axis-aligned source walls are supported: ' + wall['id'])
        start, end, at, thickness = [finite(wall.get(k), 'wall ' + k) for k in ['start', 'end', 'at', 'thickness']]
        if end <= start or thickness <= 0:
            raise ValueError('Invalid wall extent: ' + wall['id'])
        center = at + thickness / 2
        points = [[start, center], [end, center]] if wall['axis'] == 'x' else [[center, start], [center, end]]
        floor['walls'].append({'id': 'wall-' + identity(wall['id']), 'kind': 'straight',
            'start': {'x': points[0][0] / 1000, 'z': -points[0][1] / 1000},
            'end': {'x': points[1][0] / 1000, 'z': -points[1][1] / 1000},
            'height': finite(wall.get('height', height), 'wall height', True) / 1000,
            'thickness': thickness / 1000, 'materialKey': None,
            'extensions': {NS: {'sourceId': wall['id']}}})
    for opening in model['openings']:
        wall = walls.get(opening.get('wall'))
        if wall is None:
            raise ValueError('Missing opening host: ' + opening['id'])
        offset = finite(opening.get('start'), 'opening start') - wall['start']
        width = finite(opening.get('width'), 'opening width', True)
        sill = finite(opening.get('sill', 0), 'opening sill')
        h = finite(opening.get('height'), 'opening height', True)
        if opening.get('kind') not in ['door', 'sliding', 'window'] or offset < -0.001 or offset + width > wall['end'] - wall['start'] + 0.001 or sill < 0:
            raise ValueError('Invalid opening placement: ' + opening['id'])
        floor['openings'].append({'id': 'opening-' + identity(opening['id']), 'wallId': 'wall-' + identity(wall['id']),
            'kind': 'window' if opening['kind'] == 'window' else 'door', 'offset': (max(0, offset) + width / 2) / 1000, 'width': width / 1000,
            'height': h / 1000, 'sillHeight': sill / 1000,
            'extensions': {NS: {'sourceId': opening['id'], 'sourceKind': opening['kind']},
                'com.houzzkit.editor': {'sourceDoorKind': opening['kind']}}})
    for room in model['rooms']:
        rect = room.get('rect')
        if not isinstance(rect, list) or len(rect) != 4:
            raise ValueError('Missing room rectangle: ' + room['id'])
        x, y, width, depth = [finite(v, 'room rectangle') for v in rect]
        if width <= 0 or depth <= 0:
            raise ValueError('Invalid room rectangle: ' + room['id'])
        floor['rooms'].append({'id': 'room-' + identity(room['id']), 'name': room.get('name', room['id']),
            'boundary': [{'x': a / 1000, 'z': -b / 1000} for a, b in [(x, y), (x, y + depth), (x + width, y + depth), (x + width, y)]],
            'materialKey': None, 'extensions': {NS: {'sourceId': room['id']}}})
    for item in model['furniture']:
        if item.get('room') not in {r['id'] for r in model['rooms']}:
            raise ValueError('Missing furniture room: ' + item['id'])
    return {'schema': 'home3d.floorplan-scene.v5', 'id': 'scene-' + identity(model.get('project_id', 'project')),
            'revision': max(1, model.get('revision', 1)) if isinstance(model.get('revision', 1), int) else 1, 'parentDigest': None,
            'unit': 'm', 'coordinateSystem': 'right-handed-y-up', 'floors': [floor], 'instances': [],
            'projectMetadata': {'name': model.get('title', '室内可编辑工程'), 'activeFloorId': floor_id, 'mainRoomId': None},
            'extensions': {NS: {'sourceRevision': model.get('revision', 1), 'sourceUnits': 'mm',
                'inputKind': model.get('input_kind', 'unknown'), 'locationStatus': model.get('location_status', 'unknown')}}}


def find_blender(explicit):
    candidate = explicit or shutil.which('blender')
    if not candidate and Path('/Applications/Blender.app/Contents/MacOS/Blender').is_file():
        candidate = '/Applications/Blender.app/Contents/MacOS/Blender'
    if not candidate:
        raise ValueError('Blender is required; provide --blender')
    return str(candidate)


def build(args):
    project = args.project.resolve()
    model_file = project / 'model/project.json'
    if not model_file.is_file():
        raise ValueError('Missing authoritative model/project.json; a whole-house GLB alone cannot restore editable walls, openings and rooms')
    model = load(model_file)
    scene = geometry_model(model)
    if args.name:
        scene['projectMetadata']['name'] = args.name
    geometry = args.geometry.resolve()
    if geometry.suffix.lower() not in ['.glb', '.blend']:
        raise ValueError('--geometry must be a GLB or Blender file')
    geometry_hash = sha(geometry)
    lighting = load(args.lighting) if args.lighting else None
    if lighting:
        expected = lighting.get('geometrySha256', lighting.get('modelDigest', '')).removeprefix('sha256:')
        if expected != geometry_hash:
            raise ValueError('LIGHTING_SOURCE_MISMATCH: configuration must match the exact source GLB')
    if lighting and lighting.get('profileId') == 'white-home3d-v1':
        profile = HERE.parents[1] / 'interior-orchestrator/references/white-render-profile.json'
        if lighting.get('profileVersion') != 1 or lighting.get('profileSha256') != sha(profile):
            raise ValueError('WHITE_PROFILE_MISMATCH: use the locked versioned white profile')
        scene['presentation'] = {'profile': {'id': 'white-home3d-v1', 'version': 1}}
        focus = lighting.get('focusRoomId')
        if focus in {room['id'] for room in model['rooms']}:
            scene['projectMetadata']['mainRoomId'] = 'room-' + identity(focus)
    out = args.out.resolve()
    if out.exists():
        raise ValueError('Output already exists; choose a new directory: ' + str(out))
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.home3d-build-', dir=out.parent) as tmp:
        stage = Path(tmp) / 'delivery'
        stage.mkdir()
        (stage / 'models').mkdir()
        job = {'schema': 'interior.home3d-export-job.v1', 'project': model, 'scene': scene,
               'geometry': str(geometry), 'geometrySha256': geometry_hash,
               'fullSource': str(args.full_source.resolve()) if args.full_source else None,
               'lighting': lighting, 'structureMaterials': white_structure_materials(model, lighting, getattr(args, 'style', None)),
               'rendering': prepare_rendering(stage, lighting, args.rendering, args.rendering_assets), 'mapping': load(args.object_map) if args.object_map else {},
               'sourceModelSha256': sha(model_file),
               'lightingSha256': sha(args.lighting) if args.lighting else None,
               'fullSourceSha256': sha(args.full_source) if args.full_source else None,
               'objectMapSha256': sha(args.object_map) if args.object_map else None, 'skillSha256': sha(HERE.parent / 'SKILL.md'),
               'geometryToleranceM': 0.00002}
        job_file = stage / 'job.json'
        job_file.write_text(json.dumps(job, ensure_ascii=False, indent=2) + '\n')
        executable = find_blender(args.blender)
        with (stage / 'blender.log').open('w') as log:
            result = subprocess.run([executable, '-b', '-t', '2', '--python-exit-code', '1', '--python',
                str(HERE / 'extract_models.py'), '--', str(job_file)], stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            tail = (stage / 'blender.log').read_text()[-5000:]
            raise ValueError('Model extraction failed:\n' + tail)
        node = args.node or shutil.which('node')
        if not node:
            raise ValueError('Node.js 20+ is required')
        subprocess.run([str(node), str(HERE / 'package_home3d.mjs'), 'build', str(job_file)], check=True)
        subprocess.run([sys.executable, str(HERE / 'verify_world.py'), str(job_file)], check=True)
        job_file.unlink()
        os.rename(stage, out)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', type=Path)
    parser.add_argument('--name', help='Optional delivery name; source model is unchanged')
    parser.add_argument('--geometry', required=True, type=Path)
    parser.add_argument('--lighting', type=Path)
    parser.add_argument('--style', choices=['white-minimal'], help='Explicitly bind native wall/floor materials from the white-model palette')
    parser.add_argument('--rendering', type=Path, help='Complete rendering v1 authoring template; rebinds to the exported project')
    parser.add_argument('--rendering-assets', type=Path, help='Environment asset root for --rendering; defaults to the template directory')
    parser.add_argument('--full-source', type=Path, help='Same-source full-height .blend or .glb for window frames')
    parser.add_argument('--object-map', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--blender')
    parser.add_argument('--node')
    args = parser.parse_args()
    try:
        print('HOME3D_EXPORTED ' + str(build(args)))
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
