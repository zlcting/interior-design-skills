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
print('EXCHANGE_BEHAVIOR_VERIFIED: evaluated roundtrip passes; unapplied bevel rejected')
