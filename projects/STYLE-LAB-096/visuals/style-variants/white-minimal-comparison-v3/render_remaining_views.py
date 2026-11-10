"""Re-render the archived v3 comparison cameras from their recorded native scene.

Run with Python and --check-only to inspect inputs without Blender. To render:
blender -b --python render_remaining_views.py -- --out /path/to/output
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
parser=argparse.ArgumentParser(description='Re-render the recorded v3 comparison views')
parser.add_argument('--out',type=Path,default=HERE/'rerender')
parser.add_argument('--check-only',action='store_true')
args=parser.parse_args(argv)
archive_path=HERE/'render-manifest.json'
archive=json.loads(archive_path.read_text())
source=(HERE/archive['source_scene']).resolve()
source_manifest=(HERE/archive['source_manifest']).resolve()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
if sha(source)!=archive['source_scene_sha256'] or sha(source_manifest)!=archive['source_manifest_sha256']:
    parser.error('Archived source scene or source manifest has changed')
if args.check_only:
    print('V3_SOURCE_VERIFIED',len(archive['views']),'recorded views; no output written')
    sys.exit(0)

import bpy
from mathutils import Vector
bpy.ops.wm.open_mainfile(filepath=str(source))
scene=bpy.context.scene
for collection in bpy.data.collections:
    if collection.name.startswith('Cutaway'):collection.hide_render=True
bpy.data.collections['Full walls'].hide_render=False
settings=archive['render_settings']
scene.render.resolution_x=settings['width'];scene.render.resolution_y=settings['height']
scene.render.resolution_percentage=100
scene.cycles.samples=settings['samples'];scene.cycles.use_denoising=settings['denoising']
out=args.out.expanduser().resolve();out.mkdir(parents=True,exist_ok=True)
camera=scene.camera
for view in archive['views']:
    camera.location=view['location']
    camera.rotation_euler=(Vector(view['target'])-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.type='PERSP';camera.data.lens=view.get('lens',25)
    scene.render.filepath=str(out/view['file'])
    bpy.ops.render.render(write_still=True)
manifest=copy.deepcopy(archive)
manifest.update(source_scene=os.path.relpath(source,out),source_manifest=os.path.relpath(source_manifest,out),
                source_archive_manifest_sha256=sha(archive_path),script=os.path.relpath(Path(__file__).resolve(),out),
                script_sha256=sha(Path(__file__)))
manifest.pop('execution_script_sha256',None);manifest.pop('script_provenance',None)
manifest['outputs']={v['file']:sha(out/v['file']) for v in archive['views']}
(out/'render-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print('COMPARISON_V3_RENDER_COMPLETE',len(archive['views']))
