"""Validated, optional presentation settings; no Blender dependency."""
import copy
import math
import re

DEFAULTS = {
    'material_mode': 'project',
    'detail_level': 'basic',
    'aspect_ratio': 1600/1060,
    'lighting_rig': 'daylight',
    'contact_shadow_strength': 0,
    'contact_shadow_distance_mm': 250,
    'accessories': False,
    'living_refinement': False,
    'exposure': -.35,
    'contrast': 'standard',
    'orthographic_margin': 1,
    'orthographic_target_lift_mm': 0,
    'background_color': None,
    'ground_plane': False,
    'foundation': False,
    'floor_joints': True,
    'cutaway_mode': 'uniform',
    'cutaway_height_mm': 1050,
    'glazing_color': None,
    'glazing_roughness': .25,
    'glazing_transmission': 0,
    'hard_edge_bevel_mm': None,
    'studio_key_strength': None,
    'studio_key_angle': None,
    'studio_fill_scale': 1,
    'pixel_filter_width': None,
    'default_render_width': 1200,
    'default_render_samples': 32,
}


def presentation_settings(style):
    supplied = style.get('presentation', {})
    if not isinstance(supplied, dict):
        raise ValueError('presentation 必须是对象')
    if set(supplied) - set(DEFAULTS):
        raise ValueError('未知显示参数：' + ', '.join(sorted(set(supplied) - set(DEFAULTS))))
    p = {**DEFAULTS, **supplied}
    if p['material_mode'] not in ('project', 'clay'):
        raise ValueError('未知 material_mode')
    if p['detail_level'] not in ('basic','illustrated') or p['lighting_rig'] not in ('daylight','studio'):
        raise ValueError('未知白模细节或灯光配置')
    if p['contrast'] not in ('standard','medium-high'):
        raise ValueError('未知 contrast')
    if p['cutaway_mode'] not in ('uniform', 'camera'):
        raise ValueError('未知 cutaway_mode')
    for key in ('background_color', 'glazing_color'):
        if p[key] is not None and (not isinstance(p[key], str) or not re.fullmatch(r'#[0-9A-Fa-f]{6}', p[key])):
            raise ValueError(f'无效显示颜色：{key}')
    for key in ('ground_plane', 'foundation', 'floor_joints', 'accessories', 'living_refinement'):
        if type(p[key]) is not bool:
            raise ValueError(f'{key} 必须为布尔值')
    for key,lo,hi in (('aspect_ratio',.75,2.5),('contact_shadow_strength',0,1),('contact_shadow_distance_mm',1,2000),('exposure',-5,5),('orthographic_margin',1,2),('orthographic_target_lift_mm',0,3000),('cutaway_height_mm',100,4000),('glazing_roughness',0,1),('glazing_transmission',0,1)):
        value=p[key]
        if type(value) not in (int,float) or not math.isfinite(value) or not lo<=value<=hi:
            raise ValueError(f'无效显示参数：{key}')
    if p['living_refinement'] and p['detail_level']!='illustrated':
        raise ValueError('living_refinement 需要 illustrated 细节模式')
    for key,lo,hi in (('hard_edge_bevel_mm',.1,20),('studio_key_strength',.1,10),('studio_key_angle',.01,1),('pixel_filter_width',.5,3)):
        value=p[key]
        if value is not None and (type(value) not in (int,float) or not math.isfinite(value) or not lo<=value<=hi):
            raise ValueError('无效清晰度参数：'+key)
    value=p['studio_fill_scale']
    if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=2:
        raise ValueError('无效 studio_fill_scale')
    for key,lo,hi in (('default_render_width',320,8000),('default_render_samples',1,4096)):
        if type(p[key]) is not int or not lo<=p[key]<=hi:raise ValueError('无效默认渲染质量：'+key)
    return p


def render_quality(style,width=None,samples=None):
    p=presentation_settings(style or {})
    width=p['default_render_width'] if width is None else width
    samples=p['default_render_samples'] if samples is None else samples
    if type(width) is not int or not 320<=width<=8000 or type(samples) is not int or not 1<=samples<=4096:
        raise ValueError('samples 应为1至4096，width 应为320至8000')
    return width,samples


def presentation_part(part,settings,material_role=None):
    """Tighten hard surfaces at render time, preserving soft bodies and authored bounds."""
    limit=settings.get('hard_edge_bevel_mm') if settings else None
    role=part.get('role',material_role)
    if role=='source':role=material_role
    if limit is None or part['shape']!='box' or role not in ('wall','floor','wood','metal','stone','detail','glazing'):
        return part
    result=copy.deepcopy(part)
    result['radius']=min(result.get('radius',0),limit*4)
    result['bevel_mm']=min(result.get('bevel_mm',8),limit)
    result['hard_edge_applied']=True
    return result


def cutaway_wall_height(wall, model, camera, settings):
    """Retain far exterior walls, lower nearer/interior walls for each camera."""
    full=min(wall.get('height',model['height_mm']),model['height_mm'])
    height=camera.get('study_cutaway_mm',settings['cutaway_height_mm']) if camera and camera.get('presentation_only') else settings['cutaway_height_mm']
    low=min(height,full)
    if settings['cutaway_mode']=='uniform':
        return low
    x,y,w,d=model['envelope'];cx,cy=camera['location'][:2]
    cx*=1000;cy*=1000
    mid=wall['at']+wall['thickness']/2
    # Only exterior sides of the envelope qualify. Never guess from wall IDs.
    exterior=not wall.get('internal',False)
    if wall['axis']=='x':
        far=(mid>=y+d and cy<y+d/2) or (mid<=y and cy>=y+d/2)
    else:
        far=(mid>=x+w and cx<x+w/2) or (mid<=x and cx>=x+w/2)
    return full if exterior and far else low


def presentation_camera(camera, settings):
    """Framing is a render-time choice; never alter authoritative project cameras."""
    result=copy.deepcopy(camera)
    if result.get('type')=='ORTHO':
        lift=settings['orthographic_target_lift_mm']/1000
        result['location'][2]+=lift;result['target'][2]+=lift
        if 'ortho_scale' in result:
            result['ortho_scale']*=settings['orthographic_margin']
    return result


def presentation_views(plan):
    settings=presentation_settings(plan['style'])
    views=[presentation_camera(v,settings) for v in plan['resolved_model']['visualization']['cameras']]
    if settings['living_refinement']:
        from living_details import living_cameras
        for study in living_cameras(plan['furniture']):
            if not any(v['name']==study['name'] for v in views):views.append(study)
    return views
