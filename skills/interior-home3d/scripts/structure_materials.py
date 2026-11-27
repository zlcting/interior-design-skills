"""Native white-model materials, using the same palette as generated furniture."""
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'interior-orchestrator/scripts'))
from style_library import get_style


def white_structure_materials(model, lighting=None, style_id=None):
    selected=style_id
    if selected is None:
        selected='white-minimal' if (lighting or {}).get('profileId')=='white-home3d-v1' else model.get('visualization',{}).get('style_id')
    if selected!='white-minimal':return None
    style=get_style(selected);roles={}
    for role in ('wall','floor'):
        color=style['colors'][role]
        rgb=[int(color[i:i+2],16)/255 for i in (1,3,5)]
        linear=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in rgb]
        roles[role]={'colorSrgb':color,'definition':{'schema':'home3d.material-definition.v1','kind':'material',
            'baseColor':linear+[1],'metallic':0,'roughness':.65,'textures':{}}}
    snapshot=json.dumps(style,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    return {'styleId':style['id'],'styleVersion':style['version'],'styleDigest':'sha256:'+hashlib.sha256(snapshot).hexdigest(),
        'colorSpace':'linear-srgb','roles':roles}
