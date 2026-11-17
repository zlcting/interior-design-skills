"""Blender behavioral regression: bevel survives, missing modifiers are rejected."""
import bpy
import json
from pathlib import Path
import sys
import tempfile
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'skills/interior-orchestrator/scripts'))
from exchange_validation import export_glb_verified, verify_roundtrip, signature
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add(size=1, location=(2, 3, 1))
obj = bpy.context.object
obj.name = 'rounded-seat'
obj.scale = (1.4, .8, .35)
bevel = obj.modifiers.new('soft edge', 'BEVEL')
bevel.width = .08
bevel.segments = 3
with tempfile.TemporaryDirectory() as folder:
    folder = Path(folder)
    report = export_glb_verified(folder/'good.glb', [obj])
    assert report['passed']
    assert report['objects'][0]['evaluated_unique_positions'] > 8
    expected = {obj.name:signature(obj)}
    bpy.ops.export_scene.gltf(filepath=str(folder/'bad.glb'), export_format='GLB',
                             use_selection=True, export_apply=False, export_extras=True)
    try:
        verify_roundtrip(folder/'bad.glb', expected)
    except ValueError as error:
        assert 'geometry differs' in str(error)
    else:
        raise AssertionError('Missing bevel was not rejected')
# A generated smooth cushion is checked against final triangle normals, not only positions.
from style_renderer import mesh_part
from mesh_normals import process, unpack, pack
import struct
mat=bpy.data.materials.new('cushion');mat.use_nodes=True
seat=mesh_part({'id':'SOFA','facing':'south','rect':[0,0,1400,800]},
 {'name':'seat','shape':'cushion','rect':[0,0,700,600],'z':0,'height':200,'role':'upholstery'},mat,bpy.context.scene.collection)
with tempfile.TemporaryDirectory() as folder:
 path=Path(folder)/'seat.glb';report=export_glb_verified(path,[seat])
 assert report['normals']['generatedPrimitives']>0
 raw=path.read_bytes();g,binary=unpack(raw);index=g['meshes'][0]['primitives'][0]['attributes']['NORMAL'];a=g['accessors'][index];view=g['bufferViews'][a['bufferView']];offset=view.get('byteOffset',0)+a.get('byteOffset',0)
 normal=struct.unpack_from('<3f',binary,offset);struct.pack_into('<3f',binary,offset,*[-v for v in normal])
 try:process(pack(g,binary))
 except ValueError as error:assert 'normals differ' in str(error)
 else:raise AssertionError('Corrupted generated normals were accepted')
print('EXCHANGE_BEHAVIOR_VERIFIED: evaluated roundtrip passes; unapplied bevel rejected')
