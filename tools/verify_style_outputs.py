"""Verify generated files against source, library and output hashes; no writes."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/interior-orchestrator/scripts'))
from style_library import load_styles, load_catalog
from style_plan import resolve_plan, digest
from style_presentation import presentation_views

def verify(project, style_ids=None, require_current=False, output=None):
    model_text=(project/'model/project.json').read_text(encoding='utf-8')
    model=json.loads(model_text);views=None;results={};signatures={}
    styles=load_styles()
    if style_ids:
        unknown=set(style_ids)-set(styles)
        if unknown:raise ValueError('未知风格：'+', '.join(sorted(unknown)))
        styles={sid:styles[sid] for sid in style_ids}
    if output is not None and len(styles)!=1:raise ValueError('--out 必须配合单个 --style')
    for sid,style in styles.items():
        out=Path(output) if output is not None else project/'visuals/style-variants'/sid
        m=json.loads((out/'render-manifest.json').read_text())
        historical_style=m['style']['preset']!=style
        if require_current:assert not historical_style,(sid,'style snapshot stale')
        if historical_style:style=m['style']['preset']
        assert m['model_sha256']==hashlib.sha256(model_text.encode()).hexdigest(),(sid,'source stale')
        assert m['model_sha256']==hashlib.sha256((out/'render-input.json').read_bytes()).hexdigest()
        plan=resolve_plan(model,style)
        assert m['resolved_model_sha256']==digest(plan['resolved_model'])
        catalog=load_catalog()
        changed_catalog=m['style']['catalog_sha256']!=digest(catalog)
        # Appending an unused asset does not invalidate historical geometry. Used material profiles still must match.
        assert m['material_profiles']=={role:catalog['material_profiles'][profile] for role,profile in style['surfaces'].items()}
        if changed_catalog:
            if require_current:raise AssertionError((sid,'catalog stale'))
            plan['catalog_sha256']=m['style']['catalog_sha256']
        assert m['style']['resolved_plan_sha256']==digest(plan),(sid,'plan stale')
        assert m['style']['applied_forms']=={i['id']:i['asset_id'] for i in plan['furniture'] if i['mode']=='styled'}
        changed_generators=[]
        for name,expected in m['generator_sha256'].items():
            if hashlib.sha256((ROOT/'skills/interior-orchestrator/scripts'/name).read_bytes()).hexdigest()!=expected:
                changed_generators.append(name)
        if require_current:assert not changed_generators,(sid,changed_generators,'generator stale')
        for name,expected in m['outputs'].items():
            assert (out/name).stat().st_size>0
            assert hashlib.sha256((out/name).read_bytes()).hexdigest()==expected,(sid,name,'output modified')
        if 'render_quality' in m:
            q=m['render_quality'];assert q['width']==m['width'] and q['samples']==m['samples']
            for view in m['views']:
                assert struct.unpack('>II',(out/view['file']).read_bytes()[16:24])==(q['width'],q['height']),(sid,'image dimensions differ')
        names=[v['name'] for v in m['views']]
        assert names and len(names)==len(set(names)),(sid,'missing or duplicate views')
        expected_views=[{**v,'file':v['name']+'.png'} for v in presentation_views(plan) if v['name'] in names]
        assert m['views']==expected_views,(sid,'camera framing differs from configuration')
        glb=(out/'interior.glb').read_bytes()
        magic,version,length=struct.unpack_from('<4sII',glb)
        assert magic==b'glTF' and version==2 and length==len(glb)
        size,kind=struct.unpack_from('<I4s',glb,12);assert kind==b'JSON'
        content=json.loads(glb[20:20+size]);assert content['meshes'] and content['materials']
        if style.get('presentation',{}).get('living_refinement'):
            glass=next(mat for mat in content['materials'] if mat['name']=='Presentation glazing')
            assert glass.get('extensions',{}).get('KHR_materials_transmission',{}).get('transmissionFactor',0)>.9,(sid,'GLB glazing lost transmission')
        signatures[sid]=digest([i['parts'] for i in plan['furniture']])
        results[sid]={'views':len(m['views']),'styled_objects':len(m['style']['applied_forms']),
                      'basic_objects':len(m['style']['basic_objects']),'glb_meshes':len(content['meshes']),
                      'outputs_verified':len(m['outputs']),
                      'style_status':'historical' if historical_style else 'current',
                      'generator_status':'historical' if changed_generators else 'current',
                      'changed_generators':changed_generators,'catalog_status':'historical' if changed_catalog else 'current'}
    if all(sid in signatures for sid in ('japanese-natural','italian-modern','mid-century')):
        assert len({signatures[sid] for sid in ('japanese-natural','italian-modern','mid-century')})==3,'original styles have identical geometry'
    return results

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='核验风格输出；旧图明确标记历史生成器版本')
    parser.add_argument('project',type=Path,nargs='?',default=ROOT/'projects/STYLE-LAB-096')
    parser.add_argument('--style',action='append',help='只核验指定风格；可重复')
    parser.add_argument('--require-current',action='store_true',help='同时要求生成器哈希与当前代码一致')
    parser.add_argument('--out',type=Path,help='指定候选输出目录；须配合单个 --style')
    args=parser.parse_args()
    print(json.dumps(verify(args.project,args.style,args.require_current,args.out),ensure_ascii=False,indent=2))
