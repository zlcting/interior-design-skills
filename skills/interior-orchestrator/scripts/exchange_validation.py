"""Blender GLB export with evaluated-geometry round-trip verification.

Run inside Blender. Importing this module does not mutate the current scene.
"""
import hashlib
import json
from pathlib import Path

def signature(obj, depsgraph=None):
    import bpy
    depsgraph = depsgraph or bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        # glTF can split a vertex for normals/UVs. Compare unique world positions,
        # not array ordering or raw vertex counts. Quantization is a candidate
        # accelerator; acceptance uses nearest positions within 0.02 mm.
        points = {tuple(float(v) for v in (evaluated.matrix_world @ vertex.co)) for vertex in mesh.vertices}
        return sorted(points)
    finally:
        evaluated.to_mesh_clear()

def match_positions(expected, actual, tolerance_m=0.00002):
    import math
    from itertools import product
    def cells(points):
        table = {}
        for p in points:
            table.setdefault(tuple(math.floor(x/tolerance_m) for x in p), []).append(p)
        return table
    def directed(a, b):
        table = cells(b)
        for p in a:
            cell = tuple(math.floor(x/tolerance_m) for x in p)
            nearby = (q for shift in product((-1,0,1), repeat=3)
                      for q in table.get(tuple(x+d for x,d in zip(cell,shift)), []))
            if not any(sum((x-y)**2 for x,y in zip(p,q)) <= tolerance_m**2 for q in nearby):
                return False
        return True
    return bool(expected) and bool(actual) and directed(expected, actual) and directed(actual, expected)

def verify_roundtrip(path, expected):
    import bpy
    path = Path(path)
    datablocks = [bpy.data.objects, bpy.data.meshes, bpy.data.materials,
                  bpy.data.collections, bpy.data.images, bpy.data.cameras, bpy.data.lights]
    before = [set(block) for block in datablocks]
    camera = bpy.context.scene.camera
    selected = list(bpy.context.selected_objects)
    try:
        bpy.ops.object.select_all(action='DESELECT')
        bpy.ops.import_scene.gltf(filepath=str(path))
        imported = [o for o in set(bpy.data.objects)-before[0] if o.type == 'MESH']
        found = {}
        for obj in imported:
            source_id = obj.get('exchange_source_id')
            if not source_id or source_id in found:
                raise ValueError('Missing/duplicate exported source ID: '+obj.name)
            found[source_id] = signature(obj)
        if set(expected) != set(found):
            raise ValueError('Object set differs after GLB import')
        details = []
        for name, points in expected.items():
            if not match_positions(points, found[name]):
                raise ValueError('Evaluated geometry differs after GLB import: '+name)
            details.append({'id':name, 'evaluated_unique_positions':len(points),
                            'imported_unique_positions':len(found[name]), 'passed':True})
        return {'passed':True, 'tolerance_mm':0.02, 'objects':details,
                'glb_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'scope':'evaluated mesh world positions and object set; excludes lighting/material appearance'}
    finally:
        for block, old in zip(datablocks, before):
            for item in set(block)-old:
                block.remove(item, do_unlink=True)
        bpy.context.scene.camera = camera
        for obj in selected:
            if obj.name in bpy.data.objects:
                obj.select_set(True)

def export_glb_verified(path, objects):
    import bpy
    objects = [o for o in objects if o.type == 'MESH']
    if not objects:
        raise ValueError('No exportable meshes')
    for obj in objects:
        obj['exchange_source_id'] = obj.name
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    expected = {o.name:signature(o, graph) for o in objects}
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(path), use_selection=True, export_format='GLB',
                             export_apply=True, export_extras=True,
                             export_cameras=False, export_lights=False)
    report = verify_roundtrip(path, expected)
    report['apply_modifiers'] = True
    return report
