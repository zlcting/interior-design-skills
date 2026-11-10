"""Resolve semantic project metadata to reusable assets; contains no Blender dependency."""
import copy
import hashlib
import json
import math
from style_library import FAMILIES, load_catalog, validate_style
from style_presentation import presentation_settings

FACING = ('south', 'north', 'west', 'east')
# A named legacy adapter, confined to the old demo. Never infer another project's types from IDs.
DEMO_TYPES = {'F01':('sofa','west'),'F02':('coffee_table','south'),'F03':('chair','north'),
              'F04':('table','south'),'F05':('chair','north'),'F06':('chair','north'),
              'F07':('chair','south'),'F08':('chair','south'),'F09':('bed','east'),
              'F10':('bed','south'),'F11':('desk','south'),'F12':('chair','north'),
              'F13':('desk','south'),'F14':('chair','north'),'F15':('sofa','south')}
BASIC_TYPES = ('bed','table','desk','rug','equipment')


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def semantic_model(model):
    model = copy.deepcopy(model)
    adapter = model.get('project_id') == 'DEMO-APT-096'
    for f in model['furniture']:
        if 'furniture_type' not in f:
            if adapter and f['id'] in DEMO_TYPES:
                f['furniture_type'], f['facing'] = DEMO_TYPES[f['id']]
            elif f['kind'] == 'joinery':
                f['furniture_type'] = 'cabinet_front'
            elif f['kind'] in ('rug', 'equipment'):
                f['furniture_type'] = f['kind']
            else:
                raise ValueError(f'{f["id"]} 缺少 furniture_type；新项目须显式指定家具类型')
        if 'facing' not in f:
            if f['kind'] == 'joinery':
                f['facing'] = 'south' if f['rect'][2] >= f['rect'][3] else 'west'
            else:
                f['facing'] = 'south'
    for light in model.get('lights', []):
        if adapter and light.get('type') == '餐桌线性吊灯':
            light.setdefault('fixture_type','pendant')
    # Compatibility roles are only attached to the known demo, not guessed in new models.
    roles = {'M01':'floor','M05':'wall','M06':'wood','M08':'upholstery','M09':'metal'}
    if adapter:
        for mat in model['materials']:
            if mat['id'] in roles:
                mat.setdefault('style_role',roles[mat['id']])
    if adapter:
        model.setdefault('visualization', {}).setdefault('cameras', [
            {'name':'axon','location':[17,-17,20],'target':[6,4,0],'type':'ORTHO','ortho_scale':17.2},
            {'name':'living','location':[.65,3.1,2.05],'target':[2.9,1.65,.8],'lens':25},
            {'name':'dining','location':[5.15,3.05,2.15],'target':[7.2,1.45,1.1],'lens':27},
            {'name':'study','location':[7.25,4.82,1.85],'target':[8.15,7.25,1.15],'lens':23},
        ])
    return model, ('DEMO-APT-096' if adapter else None)


def resolve_plan(model, style, catalog=None):
    catalog = catalog or load_catalog()
    validate_style(style,catalog)
    resolved, adapter = semantic_model(model)
    for collection in ('furniture','lights','materials'):
        ids=[x['id'] for x in resolved.get(collection,[])]
        if len(ids)!=len(set(ids)):raise ValueError(f'{collection} 编号重复')
    materials={m['id'] for m in resolved['materials']}
    items=[]
    for f in resolved['furniture']:
        family=f['furniture_type']; rect=f.get('rect',[]);height=f.get('height_mm')
        if family not in FAMILIES+BASIC_TYPES or family=='pendant':
            raise ValueError(f'{f["id"]} 未支持的家具类型：{family}')
        if len(rect)!=4 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in rect) or min(rect[2:])<=0:
            raise ValueError(f'{f["id"]} 无效 rect')
        if not isinstance(height,(int,float)) or not math.isfinite(height) or height<=0:
            raise ValueError(f'{f["id"]} 无效高度')
        if f['facing'] not in FACING:raise ValueError(f'{f["id"]} 未知朝向')
        if f.get('material') not in materials:raise ValueError(f'{f["id"]} 未知材料')
        aid=f.get('asset_id') or style['forms'].get(family)
        if family in FAMILIES:
            a=catalog['assets'].get(aid)
            if not a or a['family']!=family:raise ValueError(f'{f["id"]} 资产不存在或类型不符：{aid}')
            params=copy.deepcopy(a['parameters'])
        else:
            if f.get('asset_id'):raise ValueError(f'{f["id"]} 基础类型尚不接受 asset_id')
            aid='basic-'+family;params={}
        items.append({**f,'asset_id':aid,'parameters':params,'mode':'styled' if family in FAMILIES else 'basic'})
    lights=[]
    for l in resolved.get('lights',[]):
        if l.get('fixture_type')=='pendant':
            aid=l.get('asset_id') or style['forms']['pendant']
            a=catalog['assets'].get(aid)
            if not a or a['family']!='pendant':raise ValueError(f'{l["id"]} 未知吊灯资产')
            lights.append({**l,'asset_id':aid,'parameters':copy.deepcopy(a['parameters'])})
    for mat in resolved['materials']:
        if mat.get('style_role') and mat['style_role'] not in style['colors']:
            raise ValueError(f'{mat["id"]} 未知 style_role')
    from furniture_library import build_parts, pendant_parts, validate_parts
    for item in items:
        item['parts'] = validate_parts(item, build_parts(item))
        if any(part['role'] not in (*style['colors'], 'source') for part in item['parts']):
            raise ValueError('模型部件引用了未知材质角色')
    for light in lights:
        light['parts'] = validate_parts(
            {'id':light['id'],'rect':[0,0,1100,400],'facing':'south','height_mm':950},
            pendant_parts(light))
        if light['z_mm'] + 950 > resolved['height_mm'] + .001:
            raise ValueError(f'{light["id"]} 吊灯超出层高；需要调整安装高度')
    for light in lights:
        if any(p['role'] not in style['colors'] for p in light['parts']):
            raise ValueError('吊灯使用了未定义材质角色')
    cameras = resolved.get('visualization', {}).get('cameras', [])
    if not cameras:raise ValueError('新项目需要 visualization.cameras')
    import re
    names = []
    for camera in cameras:
        name=camera.get('name')
        if not isinstance(name,str) or not re.fullmatch(r'[a-z][a-z0-9-]*',name):
            raise ValueError('视图名称必须是安全英文标识')
        names.append(name)
        for key in ('location','target'):
            value=camera.get(key)
            if not isinstance(value,list) or len(value)!=3 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in value):
                raise ValueError('无效相机坐标')
        if camera['location']==camera['target']:raise ValueError('相机不能与目标重合')
    if len(names)!=len(set(names)):raise ValueError('相机名称重复')
    result={'schema_version':1,'style':copy.deepcopy(style),'catalog_sha256':digest(catalog),
            'resolved_model':resolved,'legacy_adapter':adapter,'furniture':items,'pendants':lights,
            'basic_objects':[f['id'] for f in items if f['mode']=='basic']}
    settings=presentation_settings(style)
    if settings['detail_level']=='illustrated':
        from white_details import refine_furniture, build_accessories
        result['furniture']=[refine_furniture(item,resolved) for item in items]
        if settings['living_refinement']:
            from living_details import refine_living
            result['furniture']=refine_living(result['furniture'])
        for item in result['furniture']:
            if any(p['role'] not in (*style['colors'],'source','glazing') for p in item['parts']):
                raise ValueError('细节使用了未定义材质角色')
        result['basic_objects']=[f['id'] for f in result['furniture'] if f['mode']=='basic']
        result['refined_objects']={f['id']:f['refinement'] for f in result['furniture'] if f.get('refinement')}
        result['accessories']=build_accessories(resolved,result['furniture']) if settings['accessories'] else []
        if settings['living_refinement'] and settings['accessories']:
            from living_details import living_accessories
            result['accessories']=living_accessories(resolved,result['furniture'],result['accessories'])
        for accessory in result['accessories']:
            if any(p['role'] not in (*style['colors'],'glazing') for p in accessory['parts']):
                raise ValueError('附加物体使用了未定义材质角色')
    return result
