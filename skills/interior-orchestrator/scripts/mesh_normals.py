"""Validate GLB normals and finalize explicitly generated smooth surfaces.

Only NORMAL attributes are replaced; positions, indices, UV seams, colours,
materials, transforms and embedded lights retain their original bytes/data.
Unmarked authored normals are validated and preserved.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import struct

POLICY = 'triangle-area-v1'
KEY = 'interior_normal_policy'
ERROR = 0.0002


def unpack(raw):
    if len(raw) < 20 or struct.unpack_from('<III', raw) != (0x46546c67, 2, len(raw)):
        raise ValueError('Invalid GLB header')
    chunks = []
    offset = 12
    while offset < len(raw):
        size, kind = struct.unpack_from('<II', raw, offset)
        offset += 8
        if offset + size > len(raw):
            raise ValueError('Truncated GLB chunk')
        chunks.append((kind, raw[offset:offset + size])); offset += size
    if len(chunks) != 2 or [c[0] for c in chunks] != [0x4e4f534a, 0x004e4942]:
        raise ValueError('Normals workflow requires embedded JSON/BIN GLB')
    gltf = json.loads(chunks[0][1])
    buffers = gltf.get('buffers', [])
    if len(buffers) != 1 or 'uri' in buffers[0] or buffers[0]['byteLength'] > len(chunks[1][1]):
        raise ValueError('Normals workflow requires one embedded buffer')
    return gltf, bytearray(chunks[1][1][:buffers[0]['byteLength']])


def pack(gltf, binary):
    text = json.dumps(gltf, ensure_ascii=False, separators=(',', ':')).encode()
    text += b' ' * (-len(text) % 4)
    binary = bytes(binary) + b'\0' * (-len(binary) % 4)
    return (struct.pack('<III', 0x46546c67, 2, 28 + len(text) + len(binary))
            + struct.pack('<II', len(text), 0x4e4f534a) + text
            + struct.pack('<II', len(binary), 0x004e4942) + binary)


def accessor(gltf, binary, index, vector=False):
    a = gltf['accessors'][index]
    if 'sparse' in a or 'bufferView' not in a:
        raise ValueError('Sparse or missing normal/position/index buffer is unsupported')
    view = gltf['bufferViews'][a['bufferView']]
    if view.get('buffer', 0) != 0 or view.get('extensions'):
        raise ValueError('Compressed/external geometry needs decoding before normal validation')
    formats = {5126: 'f', 5125: 'I', 5123: 'H', 5121: 'B'}
    if a.get('normalized') or a['componentType'] not in formats or a['type'] != ('VEC3' if vector else 'SCALAR'):
        raise ValueError('Unsupported geometry accessor')
    if vector and a['componentType'] != 5126:
        raise ValueError('Normals workflow requires Float32 positions/normals')
    count = 3 if vector else 1
    fmt = '<' + formats[a['componentType']] * count
    size = struct.calcsize(fmt); stride = view.get('byteStride', size)
    start = view.get('byteOffset', 0) + a.get('byteOffset', 0)
    end = view.get('byteOffset', 0) + view['byteLength']
    if stride < size or start < 0 or a['count'] < 1 or start + (a['count'] - 1) * stride + size > min(end, len(binary)):
        raise ValueError('Invalid geometry buffer range')
    return [struct.unpack_from(fmt, binary, start + i * stride) for i in range(a['count'])]


def area_normals(gltf, binary, primitive):
    positions = accessor(gltf, binary, primitive['attributes']['POSITION'], True)
    if not all(math.isfinite(v) for p in positions for v in p):
        raise ValueError('Non-finite model positions')
    ids = [v[0] for v in accessor(gltf, binary, primitive['indices'])] if 'indices' in primitive else list(range(len(positions)))
    if len(ids) % 3 or any(i >= len(positions) for i in ids):
        raise ValueError('Invalid triangle indices')
    sums = [[0., 0., 0.] for _ in positions]
    for start in range(0, len(ids), 3):
        triangle = ids[start:start + 3]
        a, b, c = [positions[i] for i in triangle]
        u = [b[k] - a[k] for k in range(3)]; v = [c[k] - a[k] for k in range(3)]
        normal = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
        for i in triangle:
            for k in range(3): sums[i][k] += normal[k]
    normals = []
    for normal in sums:
        length = math.sqrt(sum(v*v for v in normal))
        if length < 1e-30:
            raise ValueError('Unused vertex or zero-area triangle fan in generated mesh')
        normals.append(tuple(v / length for v in normal))
    return normals


def process(raw, repair=False, all_static=False):
    gltf, binary = unpack(raw)
    source = copy.deepcopy(gltf)
    for item in gltf.get('nodes', []) + gltf.get('meshes', []):
        if item.get('extras', {}).get(KEY) not in [None, POLICY, 'preserve-authored-v1']:
            raise ValueError('Unsupported generated normal policy')
    marked = {node['mesh'] for node in gltf.get('nodes', [])
              if 'mesh' in node and node.get('extras', {}).get(KEY) == POLICY}
    skinned = {node['mesh'] for node in gltf.get('nodes', []) if 'mesh' in node and 'skin' in node}
    checked = generated = changed = 0; largest = 0.; source_deviation = 0.
    for mi, mesh in enumerate(gltf.get('meshes', [])):
        regenerate = all_static or mi in marked or mesh.get('extras', {}).get(KEY) == POLICY
        for primitive in mesh.get('primitives', []):
            if primitive.get('mode', 4) != 4:
                if regenerate: raise ValueError('Generated normal policy requires triangles')
                continue
            if primitive.get('targets') and regenerate or mi in skinned and regenerate:
                raise ValueError('Generated normal repair is limited to static meshes')
            attrs = primitive['attributes']
            expected = area_normals(gltf, binary, primitive) if regenerate else None
            normals = accessor(gltf, binary, attrs['NORMAL'], True) if 'NORMAL' in attrs else []
            position_count = gltf['accessors'][attrs['POSITION']]['count']
            if normals and len(normals) != position_count and not (repair and regenerate):
                raise ValueError('Surface normal count differs from positions')
            if not normals and not regenerate:
                raise ValueError('Missing surface normals')
            unit_ok = all(all(math.isfinite(x) for x in n) and abs(math.sqrt(sum(x*x for x in n))-1) < ERROR for n in normals)
            normal_error = max((math.dist(a, b) for a, b in zip(normals, expected)), default=0.) if expected else 0.
            if expected and len(expected) != len(normals): normal_error = float('inf')
            needs_repair = not unit_ok or normal_error > ERROR
            if regenerate:
                generated += 1
                source_deviation = max(source_deviation, normal_error)
                if repair and (needs_repair or not normals):
                    binary.extend(b'\0' * (-len(binary) % 4)); offset = len(binary)
                    for normal in expected: binary.extend(struct.pack('<3f', *normal))
                    view_id = len(gltf.setdefault('bufferViews', []))
                    gltf['bufferViews'].append({'buffer': 0, 'byteOffset': offset, 'byteLength': len(expected)*12, 'target': 34962})
                    attrs['NORMAL'] = len(gltf.setdefault('accessors', []))
                    gltf['accessors'].append({'bufferView': view_id, 'componentType': 5126, 'count': len(expected), 'type': 'VEC3'})
                    normals = expected; changed += 1; unit_ok = True; normal_error = 0.
                if normal_error > ERROR or not normals:
                    raise ValueError('Generated surface normals differ from final triangles')
            if not unit_ok: raise ValueError('Non-finite or non-unit surface normal')
            checked += 1
            largest = max(largest, max(abs(math.sqrt(sum(x*x for x in n))-1) for n in normals))
        if all_static and repair: mesh.setdefault('extras', {})[KEY] = POLICY
    gltf['buffers'][0]['byteLength'] = len(binary)
    result = raw if source == gltf else pack(gltf, binary)
    report = {'passed': True, 'policy': POLICY, 'checkedPrimitives': checked, 'generatedPrimitives': generated,
              'regeneratedPrimitives': changed, 'maxUnitError': largest,
              'maxSourceVectorDeviation': source_deviation if math.isfinite(source_deviation) else None,
              'positionsIndicesColorsMaterialsPreserved': True,
              'glb_sha256': hashlib.sha256(result).hexdigest()}
    return result, report


def finalize_glb_normals(path):
    path = Path(path)
    raw, report = process(path.read_bytes(), repair=True)
    path.write_bytes(raw)
    process(raw)  # Re-read the final document and its buffers before accepting it.
    return report


def validate_glb_normals(path):
    return process(Path(path).read_bytes())[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--all-static', action='store_true', help='Explicit repair of a known static asset, including legacy unmarked models')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve() or args.output.exists() or args.report.exists():
        parser.error('Use new output/report paths; source and previous deliveries are retained')
    raw, report = process(args.input.read_bytes(), repair=True, all_static=args.all_static)
    process(raw)
    report['sourceSha256'] = hashlib.sha256(args.input.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_bytes(raw)
    args.report.parent.mkdir(parents=True, exist_ok=True); args.report.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report))


if __name__ == '__main__': main()
