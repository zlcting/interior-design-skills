"""Create a portable, self-contained white viewer from locked model/GLB inputs."""
from pathlib import Path
import argparse,json,hashlib,shutil,subprocess,sys,base64
from white_render_profile import build_config
from style_library import get_style,load_catalog
from style_plan import resolve_plan
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build(project,glb,out,plan_path=None,room=None,blender=None):
 model=json.loads((project/'model/project.json').read_text());plan=json.loads(plan_path.read_text()) if plan_path else resolve_plan(model,get_style('white-minimal'),load_catalog())
 if plan['resolved_model']['rooms']!=model['rooms']:raise ValueError('解析方案与权威房间数据不一致')
 if {f['id']:f['rect'] for f in plan['furniture']}!={f['id']:f['rect'] for f in model['furniture']}:raise ValueError('解析方案与权威家具占地不一致')
 config=build_config(model,plan,room)
 if out.exists() and any(out.iterdir()):raise ValueError('输出目录非空；请保留已有版本并选择新目录')
 executable=blender or shutil.which('blender')
 if not executable and Path('/Applications/Blender.app/Contents/MacOS/Blender').exists():executable='/Applications/Blender.app/Contents/MacOS/Blender'
 if not executable:raise ValueError('需要 Blender 进行白模接触阴影烘焙与几何回读检查')
 out.mkdir(parents=True,exist_ok=True);(out/'white-render-config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n')
 with (out/'ao-bake.log').open('w') as log:
  subprocess.run([str(executable),'--background','--python',str(ROOT/'scripts/bake_white_web.py'),'--','--input',str(glb.resolve()),'--output',str((out/'white-web.glb').resolve()),'--config',str((out/'white-render-config.json').resolve()),'--report',str((out/'white-web-validation.json').resolve())],stdout=log,stderr=subprocess.STDOUT,check=True)
 report=json.loads((out/'white-web-validation.json').read_text());assert report['passed'] and report['source_geometry_preserved'] and report['glb_sha256']==sha(out/'white-web.glb')
 config['geometrySha256']=sha(out/'white-web.glb');(out/'white-render-config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n')
 assets=ROOT/'assets/white-viewer';scripts='\n'.join((assets/f).read_text() for f in ['engine.js','studio.js','viewer.js']);scripts=scripts.replace('</script','<\\/script')
 html='''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>精细白模 · 空间体验</title><style>body{margin:0;font:14px/1.6 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;color:#294235;background:#f4f3ee}header{padding:16px 24px;display:flex;justify-content:space-between;gap:16px}header small{color:#6a786c}#stage{height:calc(100vh - 66px);min-height:420px;position:relative;background:#7898c7}canvas{display:block;width:100%;height:100%;touch-action:none}#title{position:absolute;left:24px;top:18px;pointer-events:none}#views{position:absolute;bottom:22px;left:12px;right:12px;display:flex;justify-content:center;gap:7px;flex-wrap:wrap}button{border:1px solid #d2dbce;background:#f4f3eef0;color:#294235;padding:9px 14px;border-radius:10px;cursor:pointer}button[aria-pressed=true]{background:#365b42;color:#fff}button:focus-visible{outline:3px solid #86a48c;outline-offset:3px}#loading{position:absolute;inset:0;display:grid;place-items:center;background:#eef0e9df}#loading[hidden]{display:none}#controls{display:flex;gap:7px}header strong{font-weight:500}@media(max-width:600px){header{padding:12px 16px}header small{display:none}#stage{height:calc(100dvh - 58px)}button{padding:9px 11px}}</style></head><body><header><strong>空间 · 精细白模</strong><small>依据项目模型展示 · 尺寸待实测复核</small></header><main id="stage"><canvas aria-label="可旋转缩放的白模空间"></canvas><div id="title"><strong id="view"></strong><div>拖动旋转 · 滚轮缩放</div></div><nav id="views"><div id="controls"><button id="reset">复位</button><button id="lamp" aria-pressed="true">局部灯光：开</button></div></nav><div id="loading">正在打开空间</div></main>'''
 html+='<script id="white-config" type="application/json">'+json.dumps(config,ensure_ascii=False).replace('<','\\u003c')+'</script><script id="white-model" type="application/octet-stream">'+base64.b64encode((out/'white-web.glb').read_bytes()).decode()+'</script><script>'+scripts+'</script></body></html>'
 (out/'打开精细白模.html').write_text(html);shutil.copy2(assets/'THIRD-PARTY-NOTICES.md',out/'THIRD-PARTY-NOTICES.md')
 manifest={'profile':config['profileId'],'profileVersion':config['profileVersion'],'profileSha256':config['profileSha256'],'sourceModelSha256':sha(project/'model/project.json'),'sourceGlbSha256':sha(glb),'configuration_check':'passed','geometry_check':'passed','visual_review':'not_reviewed','direct_file_test':'not_tested','generator_sha256':{f:sha(ROOT/'scripts'/f) for f in ['white_render_profile.py','prepare_white_viewer.py','bake_white_web.py']},'runtime_sha256':{f:sha(assets/f) for f in ['engine.js','studio.js','viewer.js']},'outputs':{f.name:sha(f) for f in out.iterdir() if f.is_file()}}
 (out/'white-viewer-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');return manifest
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('project',type=Path);p.add_argument('--glb',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--plan',type=Path);p.add_argument('--room');p.add_argument('--blender');a=p.parse_args();print(json.dumps(build(a.project,a.glb,a.out,a.plan,a.room,a.blender),ensure_ascii=False,indent=2))
