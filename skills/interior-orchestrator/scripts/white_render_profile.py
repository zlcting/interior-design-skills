"""Home3D white-lighting contract, adapted to a project's geometry; no Blender imports."""
import copy
import hashlib
import json
import math
from pathlib import Path
PROFILE_PATH=Path(__file__).resolve().parents[1]/'references/white-render-profile.json'

def load_profile():
    value=json.loads(PROFILE_PATH.read_text())
    if value.get('id')!='white-home3d-v1' or value.get('version')!=1:raise ValueError('未知白模光影预设版本')
    return value

def _bounds(rects):
    if not rects:raise ValueError('白模相机需要项目房间或轮廓')
    for r in rects:
        if len(r)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in r) or min(r[2:])<=0:raise ValueError('无效房间范围')
    x=min(r[0] for r in rects)/1000;y=min(r[1] for r in rects)/1000
    xx=max(r[0]+r[2] for r in rects)/1000;yy=max(r[1]+r[3] for r in rects)/1000
    return x,y,xx-x,yy-y

def build_config(model,plan,focus_room_id=None):
    if plan['style']['id']!='white-minimal':raise ValueError('白模光影预设仅适用于 white-minimal')
    if model.get('visualization',{}).get('white_render_profile','white-home3d-v1')!='white-home3d-v1':raise ValueError('未知 white_render_profile；不要静默替换预设')
    if model.get('units','mm')!='mm':raise ValueError('白模项目长度单位必须为mm')
    p=load_profile();rooms=model.get('rooms',[]);bounds=_bounds([r['rect'] for r in rooms]);x,y,w,d=bounds;span=max(w,d)
    if not .1<=span<=100:raise ValueError('户型尺度超出本白模预设验证范围')
    centre=[x+w/2,0,-(y+d/2)]
    focus_room_id=focus_room_id or model.get('visualization',{}).get('focus_room_id')
    if focus_room_id is None:
        sofas=[i for i in plan['furniture'] if i.get('furniture_type')=='sofa']
        if sofas:focus_room_id=max(sofas,key=lambda f:f['rect'][2]*f['rect'][3]).get('room')
    room=next((r for r in rooms if r['id']==focus_room_id),None)
    if focus_room_id is not None and room is None:raise ValueError('指定代表房间不存在')
    def view(b,label):
        a,c,bw,bd=b;s=max(bw,bd);target=[a+bw/2,p['camera']['targetHeightM'],-(c+bd/2)]
        offset=p['camera']['offsetPerSpan'];return {'name':label,'projection':'orthographic','target':target,'position':[target[i]+offset[i]*s for i in range(3)],'width':max(p['camera']['minFocusWidthM'],s*p['camera']['margin'])}
    views={'overview':view(bounds,'全屋')}
    if room:views['focus']=view(_bounds([room['rect']]),room['name'])
    studio=copy.deepcopy(p['studio'])
    for kind in ('key','fill'):
        studio[kind+'Position']=[centre[i]+p['studio'][kind+'OffsetPerSpan'][i]*span for i in range(3)]
    studio['target']=centre;studio['groundPosition']=[centre[0],-.245,centre[2]]
    fixtures=[]
    # Only actual resolved light accessories become local lights. Never invent a lamp.
    for item in plan.get('accessories',[]):
        light=item.get('light')
        if not light:continue
        a,c,bw,bd=item['rect'];fixtures.append({'id':item['id'],'position':[(a+bw/2)/1000,light['z_mm']/1000,-(c+bd/2)/1000],**copy.deepcopy(p['fixture'])})
    return {'schemaVersion':1,'profileId':p['id'],'profileVersion':p['version'],'profileSha256':hashlib.sha256(PROFILE_PATH.read_bytes()).hexdigest(),'sourceRevision':model['revision'],'style':'white-minimal','furnitureDetail':model.get('visualization',{}).get('furniture_detail','legacy-default'),'renderer':copy.deepcopy(p['renderer']),'camera':copy.deepcopy(p['camera']),'studio':studio,'shadows':{**copy.deepcopy(p['shadows']),'frustum':{'left':-span*1.2,'right':span*1.2,'top':span*1.2,'bottom':-span*1.2,'near':.1,'far':max(10,span*5)}},'contactAO':copy.deepcopy(p['contactAO']),'views':views,'defaultView':'focus' if room else 'overview','focusRoomId':room['id'] if room else None,'boundsM':list(bounds),'fixtures':fixtures,'review':copy.deepcopy(p['review'])}
