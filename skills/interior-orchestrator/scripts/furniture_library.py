"""Procedural asset builders in local millimetres. Pure data, reusable outside Blender."""
import math


ENUMS = {
    'sofa': {'base':('wood','upholstery'),'legs':('wood','hidden','tapered'),'arm':('wood','upholstery')},
    'coffee_table': {'top':('rounded','oval'),'surface':('wood','stone'),'legs':('round','slab','tapered')},
    'chair': {'frame':('wood','metal'),'legs':('round','slim','tapered'),'back':('slatted','padded','curved')},
    'cabinet_front': {'door':('flat','framed'),'base':('plinth','recessed','legs'),'handles':('wood','none','metal')},
    'pendant': {'shape':('paper','linear','globe','cone'),'surface':('shade','metal')},
}
NUMBERS = {'sofa':('seat_z','seat_h','back_z','back_h','rounding'),
           'coffee_table':('thickness',), 'chair':('rounding',)}


def validate_parameters(family,params):
    for key,choices in ENUMS.get(family,{}).items():
        if params.get(key) not in choices:
            raise ValueError(f'{family} 不支持参数 {key}={params.get(key)}')
    for key in NUMBERS.get(family,()):
        value=params.get(key)
        if not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<value<1:
            raise ValueError(f'{family} 无效比例 {key}')
    if family=='sofa' and (type(params.get('seat_count')) is not int or not 1<=params['seat_count']<=8):
        raise ValueError('沙发坐垫数量必须在1至8之间')


def build_parts(item):
    """All parts stay inside the item's declared envelope. Front is local y=0."""
    _,_,wx,dy=item['rect'];h=item['height_mm']
    w,d=(dy,wx) if item['facing'] in ('west','east') else (wx,dy)
    family=item['furniture_type'];p=item['parameters'];parts=[]
    validate_parameters(family,p)
    def part(name,rect,z,height,role='wood',shape='box',radius=0,**extra):
        parts.append(dict(name=name,rect=list(rect),z=z,height=height,role=role,shape=shape,radius=radius,**extra))
    def block(name,x,y,bw,bd,z,bh,role='wood',rounding=0):
        part(name,[x,y,bw,bd],z,bh,role,radius=rounding)
    def leg(x,y,z,height,radius,role='wood',taper=False):
        part('leg',[x-radius,y-radius,2*radius,2*radius],z,height,role,'cone' if taper else 'oval',top_ratio=1.35 if taper else 1)
    if family=='sofa':
        leg_h=h*.18 if p['legs']!='hidden' else h*.025
        base_z=leg_h;base_h=h*.12
        if p['legs']!='hidden':
            for x in (w*.08,w*.92):
                for y in (d*.15,d*.85):leg(x,y,0,leg_h,min(w,d)*.035,'wood',p['legs']=='tapered')
        arm=w*(.045 if p['arm']=='wood' else .095)
        block('base',arm,0,w-2*arm,d,base_z,base_h,p['base'],min(w,d)*.025)
        # Slim timber arms vs broad upholstered arms are part of the reusable asset parameters.
        arm=w*(.045 if p['arm']=='wood' else .095)
        seat_z=h*p['seat_z'];seat_h=h*p['seat_h'];back_z=h*p['back_z'];back_h=h*p['back_h']
        for x in (0,w-arm):block('arm',x,0,arm,d*.94,base_z,h*.52,p['arm'],arm*.25)
        count=p['seat_count'];span=(w-2*arm)/count
        for i in range(count):
            block('seat',arm+i*span+span*.015,d*.05,span*.97,d*.71,seat_z,seat_h,'upholstery',min(span,d)*p['rounding'])
            block('back cushion',arm+i*span+span*.015,d*.76,span*.97,d*.23,back_z,back_h,'upholstery',min(span,d)*p['rounding'])
        for x in (w*.18,w*.69):
            block('accent cushion',x,d*.64,w*.13,d*.13,seat_z+seat_h,h*.27,'accent',min(w,d)*.045)
    elif family=='coffee_table':
        thick=h*p['thickness'];r=min(w,d)*(.2 if p['top']=='rounded' else 0)
        part('top',[0,0,w,d],h-thick,thick,p['surface'],'oval' if p['top']=='oval' else 'box',r)
        if p['legs']=='slab':
            for y in (d*.15,d*.73):block('slab support',w*.22,y,w*.56,d*.12,0,h-thick,'metal',10)
        else:
            for x in (w*.23,w*.77):
                for y in (d*.23,d*.77):leg(x,y,0,h-thick,min(w,d)*(.055 if p['legs']=='round' else .035),'wood',p['legs']=='tapered')
    elif family=='chair':
        seat_z=h*.46;seat_h=h*.13;radius=min(w,d)*(.025 if p['legs']=='slim' else .035)
        for x in (w*.13,w*.87):
            for y in (d*.13,d*.84):leg(x,y,0,seat_z,radius,p['frame'],p['legs']=='tapered')
        part('seat',[w*.04,d*.03,w*.92,d*.88],seat_z,seat_h,'upholstery','box',min(w,d)*p['rounding'])
        if p['back']=='slatted':
            for x in (w*.08,w*.88):block('back post',x,d*.86,w*.04,d*.08,seat_z,h-seat_z,'wood',5)
            for z in (.72,.88):block('back rail',w*.12,d*.85,w*.76,d*.1,h*z,h*.1,'wood',10)
        else:
            part('back',[w*.06,d*.8,w*.88,d*.18],h*.62,h*.38,'upholstery' if p['back']=='padded' else 'wood','box',min(w,d)*.1)
    elif family=='cabinet_front':
        base_h=min(140,h*.15)
        if p['base']=='legs' and h<1200:
            for x in (w*.08,w*.92):
                for y in (d*.18,d*.82):leg(x,y,0,base_h,min(w,d)*.04,'wood',True)
        else:block('plinth',w*.04,d*.08,w*.92,d*.84,0,base_h,'metal' if p['base']=='recessed' else 'wood',2)
        top_h=h-20 if item.get('countertop') else h
        block('carcass',0,18,w,max(1,d-18),base_h,top_h-base_h,'wood',3)
        count=max(1,math.ceil(w/600));bay=w/count;gap=min(3,bay*.02)
        for i in range(count):
            x=i*bay+gap;bw=bay-2*gap;bottom=base_h+gap;dh=top_h-base_h-2*gap
            if p['door']=='framed':
                rail=min(45,bw*.12,dh*.12)
                block('door panel',x+rail,4,bw-2*rail,12,bottom+rail,dh-2*rail,'wood',2)
                for xx in (x,x+bw-rail):block('frame',xx,0,rail,16,bottom+rail,dh-2*rail,'wood',1)
                for zz in (bottom,bottom+dh-rail):block('frame',x,0,bw,16,zz,rail,'wood',1)
            else:
                block('door',x,2,bw,14,bottom,dh,'wood',2)
            if p['handles']!='none':
                block('handle',x+bw*.76,0,max(6,bw*.025),10,base_h+(top_h-base_h)*.48,min(100,(top_h-base_h)*.2),p['handles'],2)
        if item.get('countertop'):
            block('countertop',0,0,w,d,h-20,20,'stone',3)
    elif family in ('table','desk'):
        block('top',0,0,w,d,h-35,35,'wood',min(w,d)*.05)
        for x in (w*.09,w*.91):
            for y in (d*.13,d*.87):leg(x,y,0,h-35,min(w,d)*.035)
    elif family=='bed':
        block('frame',0,0,w,d,h*.1,h*.32,'wood',20)
        block('mattress',w*.02,d*.02,w*.96,d*.94,h*.42,h*.44,'upholstery',min(w,d)*.06)
        for x in (w*.08,w*.55):block('pillow',x,d*.73,w*.36,d*.2,h*.86,h*.14,'shade',min(w,d)*.035)
        block('throw',w*.03,d*.12,w*.94,d*.32,h*.86,h*.03,'accent',10)
    elif family=='rug':part('rug',[0,0,w,d],0,h,'upholstery',radius=10)
    elif family=='equipment':block('equipment',0,0,w,d,0,h,'source',10)
    else:raise ValueError(f'未知家具生成器：{family}')
    return parts


def pendant_parts(item):
    p=item['parameters'];validate_parameters('pendant',p);shape=p['shape'];parts=[]
    def add(name,rect,z,h,role,geometry='box',**extra):
        parts.append(dict(name=name,rect=rect,z=z,height=h,role=role,shape=geometry,radius=5,**extra))
    if shape=='linear':
        add('beam',[0,170,1100,60],0,55,'metal')
        for x in (110,990):add('cable',[x-2,198,4,4],55,895,'metal')
    elif shape=='cone':
        add('conical shade',[390,90,320,220],30,230,'shade','frustum',ring_scales=[1,.32])
        add('warm bulb',[445,125,210,150],0,75,'warm_glow','ellipsoid')
        add('cable',[548,198,4,4],260,690,'metal')
    elif shape=='paper':
        add('paper shade',[210,0,680,400],0,420,'shade','ellipsoid')
        add('cable',[548,198,4,4],420,530,'metal')
    elif shape=='globe':
        add('brass beam',[120,190,860,20],400,22,'metal')
        for x,z in ((170,0),(440,80),(710,0)):
            add('globe',[x,70,220,260],z,260,'shade','ellipsoid')
            add('stem',[x+105,195,10,10],z+260,422-z-260,'metal')
        add('cable',[548,198,4,4],422,528,'metal')
    else:raise ValueError(f'未知吊灯造型：{shape}')
    return parts


def world_xy(item,u,v):
    x,y,w,d=item['rect'];face=item['facing']
    if face=='south':return x+u,y+v
    if face=='north':return x+w-u,y+d-v
    if face=='west':return x+v,y+d-u
    if face=='east':return x+w-v,y+u
    raise ValueError('未知朝向')


def validate_parts(item,parts):
    _,_,a,b=item['rect'];w,d=(b,a) if item['facing'] in ('west','east') else (a,b)
    h=item['height_mm']
    for p in parts:
        x,y,pw,pd=p['rect'];z=p['z'];ph=p['height']
        vals=(x,y,pw,pd,z,ph)
        if not all(math.isfinite(v) for v in vals) or min(pw,pd,ph)<=0:
            raise ValueError(f'{item["id"]}/{p["name"]} 无效构件尺寸')
        if min(x,y,z)<-.001 or x+pw>w+.001 or y+pd>d+.001 or z+ph>h+.001:
            raise ValueError(f'{item["id"]}/{p["name"]} 超出家具外包尺寸')
    return parts
