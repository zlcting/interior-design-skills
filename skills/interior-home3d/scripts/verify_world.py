"""Compare actual package world vertices against evaluated source clouds, after SDK validation."""
from collections import defaultdict
from itertools import product
import json
import math
from pathlib import Path
import struct
import sys
import zipfile


def load_glb(data):
    length = struct.unpack_from('<I', data, 12)[0]
    return json.loads(data[20:20 + length]), data[28 + length:]


def rotate(point, quaternion):
    x, y, z, w = quaternion
    a, b, c = point
    tx, ty, tz = 2 * (y * c - z * b), 2 * (z * a - x * c), 2 * (x * b - y * a)
    return [a + w * tx + y * tz - z * ty, b + w * ty + z * tx - x * tz, c + w * tz + x * ty - y * tx]


def node_transform(point, node):
    if 'matrix' in node:
        matrix = node['matrix']
        return [sum(matrix[k * 4 + r] * point[k] for k in range(3)) + matrix[12 + r] for r in range(3)]
    point = rotate([v * node.get('scale', [1, 1, 1])[i] for i, v in enumerate(point)], node.get('rotation', [0, 0, 0, 1]))
    return [v + node.get('translation', [0, 0, 0])[i] for i, v in enumerate(point)]


def positions(data):
    document, binary = load_glb(data)
    result = []
    def visit(index, parents):
        node = document['nodes'][index]
        chain = [node] + parents
        if 'mesh' in node:
            for primitive in document['meshes'][node['mesh']]['primitives']:
                accessor = document['accessors'][primitive['attributes']['POSITION']]
                if accessor['componentType'] != 5126 or accessor['type'] != 'VEC3' or 'sparse' in accessor:
                    raise ValueError('Expected evaluated float32 POSITION accessors')
                view = document['bufferViews'][accessor['bufferView']]
                start = view.get('byteOffset', 0) + accessor.get('byteOffset', 0)
                stride = view.get('byteStride', 12)
                for i in range(accessor['count']):
                    point = struct.unpack_from('<3f', binary, start + i * stride)
                    for transform in chain:
                        point = node_transform(point, transform)
                    result.append(point)
        for child in node.get('children', []):
            visit(child, chain)
    for index in document['scenes'][document.get('scene', 0)]['nodes']:
        visit(index, [])
    return result


def distance_check(expected, actual, tolerance):
    expected = set(tuple(p) for p in expected)
    actual = set(tuple(p) for p in actual)
    def directed(source, target):
        cells = defaultdict(list)
        for point in target:
            cells[tuple(math.floor(v / tolerance) for v in point)].append(point)
        maximum = 0
        for point in source:
            key = tuple(math.floor(v / tolerance) for v in point)
            best = math.inf
            for delta in product((-1, 0, 1), repeat=3):
                for candidate in cells.get(tuple(key[i] + delta[i] for i in range(3)), []):
                    best = min(best, sum((point[i] - candidate[i]) ** 2 for i in range(3)))
            if best > tolerance ** 2:
                return False, None
            maximum = max(maximum, math.sqrt(best))
        return True, maximum
    forward, error1 = directed(expected, actual)
    backward, error2 = directed(actual, expected)
    return {'passed': forward and backward, 'sourcePoints': len(expected), 'packagePoints': len(actual),
            'maxErrorM': max(error1, error2) if forward and backward else None}


def verify(job_file):
    root = job_file.parent
    job = json.loads(job_file.read_text())
    components = json.loads((root / 'components.json').read_text())['components']
    mappings = json.loads((root / 'object-map.json').read_text())['objects']
    details = []
    with zipfile.ZipFile(root / 'project.home3d') as archive:
        manifest = json.loads(archive.read('package.json'))
        documents = manifest['entries']
        scene = json.loads(archive.read(documents.get('project', documents.get('scene'))))
        resources = json.loads(archive.read(documents['resources']))['resources']
        definitions = {r['key']: json.loads(archive.read(r['definitionPath'])) for r in resources}
        instances = {i['id']: i for i in scene['instances']}
        for component in components:
            mapping = next(m for m in mappings if m['sourceId'] == component['sourceId'])
            instance = instances[mapping['instanceId']]
            definition = definitions[instance['resourceKey']]
            cloud = (root / component['sourceWorldVertices']).read_bytes()
            expected = list(struct.iter_unpack('<3d', cloud))
            normalization = definition.get('normalization', {'translation': [0, 0, 0], 'scale': [1, 1, 1]})
            scale = [instance['transform']['size'][axis] / definition['defaultSize'][axis] for axis in ['width', 'height', 'depth']]
            actual = []
            for point in positions(archive.read(definition['file'])):
                point = [(point[i] + normalization['translation'][i]) * normalization['scale'][i] * scale[i] for i in range(3)]
                point = rotate(point, instance['transform']['rotation'])
                actual.append([point[i] + instance['transform']['position'][i] for i in range(3)])
            checked = distance_check(expected, actual, job['geometryToleranceM'])
            details.append({'sourceId': component['sourceId'], **checked})
            if not checked['passed']:
                raise ValueError('SOURCE_WORLD_GEOMETRY_MISMATCH: ' + component['sourceId'])
    report = {'schema': 'interior.home3d-world-verification.v1', 'passed': True, 'toleranceMm': job['geometryToleranceM'] * 1000,
              'scope': 'evaluated source world positions versus actual package GLB + normalization + instance transforms', 'objects': details}
    (root / 'world-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    acceptance_file = root / 'acceptance.json'
    acceptance = json.loads(acceptance_file.read_text())
    acceptance['geometry']['sourceWorldPassed'] = True
    acceptance['geometry']['worldVerification'] = 'world-verification.json'
    acceptance_file.write_text(json.dumps(acceptance, ensure_ascii=False, indent=2) + '\n')
    print('SOURCE_WORLD_GEOMETRY_VERIFIED', len(details))
    return report


if __name__ == '__main__':
    verify(Path(sys.argv[1]).resolve())
