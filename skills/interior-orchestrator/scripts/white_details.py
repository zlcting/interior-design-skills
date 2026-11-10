"""Optional illustrated clay details. All principal furniture stays inside source envelopes."""
import copy
from furniture_library import validate_parts


def part(name,rect,z,height,role='wood',shape='box',radius=0,**extra):
    return dict(name=name,rect=list(rect),z=z,height=height,role=role,shape=shape,radius=radius,**extra)


def equipment_kind(item, model):
    explicit=item.get('equipment_type')
    if explicit:return explicit
    names=[item.get('name','')]+[x.get('name','') for x in model.get('equipment',[]) if x.get('object')==item['id']]
    aliases={'冰箱':'refrigerator','洗烘塔':'washer_stack','坐便器':'toilet'}
    return next((aliases[n] for n in names if n in aliases),None)


def refine_furniture(item, model):
    item=copy.deepcopy(item);_,_,a,b=item['rect'];w,d=(b,a) if item['facing'] in ('east','west') else (a,b);h=item['height_mm']
    family=item['furniture_type'];kind=equipment_kind(item,model) if family=='equipment' else None
    pieces=item['parts'];refined=False;soft=False
    if family=='bed':
        pieces=[part('bed base',[0,0,w,d],h*.13,h*.2,'wood',radius=30),
                part('headboard',[0,d*.95,w,d*.05],0,h,'wood',radius=15),
                part('mattress',[w*.025,d*.02,w*.95,d*.93],h*.33,h*.42,'upholstery',radius=min(w,d)*.07,bevel_mm=35),
                part('duvet',[w*.03,d*.025,w*.94,d*.73],h*.75,h*.09,'shade',radius=min(w,d)*.05,bevel_mm=20),
                part('duvet fold',[w*.03,d*.62,w*.94,d*.12],h*.84,h*.035,'shade',radius=20,bevel_mm=8),
                part('bed throw',[w*.03,d*.12,w*.94,d*.24],h*.84,h*.025,'accent',radius=10)]
        for x in (w*.09,w*.56):pieces.append(part('soft pillow',[x,d*.76,w*.35,d*.19],h*.8,h*.2,'shade',shape='ellipsoid'))
        for x in (w*.07,w*.88):
            for y in (d*.07,d*.87):pieces.append(part('bed foot',[x,y,w*.05,d*.04],0,h*.13,'metal',radius=4))
        refined=True
    elif kind=='refrigerator':
        pieces=[part('fridge body',[0,d*.035,w,d*.965],0,h,'wood',radius=12),
                part('lower door',[w*.01,d*.008,w*.98,d*.024],h*.02,h*.33,'metal',radius=8),
                part('upper door',[w*.01,d*.008,w*.98,d*.024],h*.355,h*.635,'metal',radius=8)]
        for z,hh in ((h*.12,h*.16),(h*.41,h*.25)):
            pieces.append(part('fridge handle',[w*.86,0,w*.025,d*.025],z,hh,'detail',radius=3))
        refined=True
    elif kind=='washer_stack':
        pieces=[part('washer body',[0,d*.04,w,d*.96],0,h,'wood',radius=10)]
        for z in (0,h*.5):
            pieces.extend([part('washer front',[w*.02,d*.015,w*.96,d*.035],z+h*.01,h*.475,'wood',radius=10),
                           part('door bezel',[w*.14,0,w*.72,d*.03],z+h*.09,h*.285,'metal','ellipsoid'),
                           part('door glass',[w*.19,0,w*.62,d*.015],z+h*.11,h*.245,'detail','ellipsoid'),
                           part('control panel',[w*.1,0,w*.8,d*.02],z+h*.415,h*.035,'metal',radius=3)])
        refined=True
    elif kind=='toilet':
        pieces=[part('cistern',[w*.15,d*.72,w*.7,d*.26],0,h*.96,'wood',radius=30),
                part('pedestal',[w*.23,d*.13,w*.54,d*.58],0,h*.43,'wood','oval'),
                part('toilet bowl',[w*.08,0,w*.84,d*.75],h*.22,h*.36,'shade','ellipsoid'),
                part('toilet seat',[w*.08,0,w*.84,d*.74],h*.54,h*.055,'shade','oval'),
                part('bowl inset',[w*.23,d*.12,w*.54,d*.47],h*.596,h*.004,'metal','oval')]
        refined=True
    else:
        for p in pieces:
            if p['name'] in ('seat','back cushion','accent cushion'):
                p['bevel_mm']=min(38,p['height']*.22);soft=True
            if p['name']=='accent cushion':p['shape']='ellipsoid'
    item['parts']=validate_parts(item,pieces)
    item['refinement']=(kind if kind else 'bedding') if refined else ('soft_edges' if soft else None)
    if refined and item['mode']=='basic':item['mode']='refined-basic'
    return item


def build_accessories(model, furniture):
    """Decor and equipment details are explicit presentation objects, not approved model additions."""
    accessories=[]
    def asset(aid,kind,rect,height,parts,**metadata):
        obj={'id':aid,'asset_id':kind,'facing':'south','rect':rect,'height_mm':height,'parts':parts,**metadata}
        validate_parts(obj,parts);accessories.append(obj)
    # Two small plants sit within existing table/cabinet surfaces, never in a circulation route.
    supports=[f for f in furniture if f['furniture_type']=='coffee_table'][:1]
    supports += [f for f in furniture if f['furniture_type']=='cabinet_front' and 700<=f['height_mm']<=1000 and min(f['rect'][2:])>=400][:1]
    for f in supports:
        x,y,w,d=f['rect'];size=min(260,w*.4,d*.4);z=f['height_mm'];pieces=[]
        pieces.append(part('ceramic pot',[size*.22,size*.22,size*.56,size*.56],z,size*.55,'shade','cone',top_ratio=1.18))
        pieces.append(part('soil',[size*.27,size*.27,size*.46,size*.46],z+size*.54,size*.02,'soil','oval'))
        for i,(xx,yy,ww,dd,hh) in enumerate(((.1,.15,.38,.5,1.05),(.5,.12,.4,.5,1.2),(.3,.4,.4,.55,1.15),(.12,.45,.35,.45,.85),(.52,.45,.35,.45,.95),(.35,.15,.3,.4,1.4))):
            pieces.append(part('leaf '+str(i),[size*xx,size*yy,size*ww,size*dd],z+size*.5,size*hh,'foliage','leaf'))
        asset('DECOR-'+f['id'],'potted-plant',[x+w*.5-size*.5,y+d*.5-size*.5,size,size],z+size*2,pieces,source_object=f['id'],presentation_only=True)
    # Existing countertop appliances are positioned by their authored point and containing cabinet.
    for e in model.get('equipment',[]):
        kind={'电磁灶':'cooktop','厨房水槽':'sink'}.get(e.get('name'))
        if kind is None or 'xy' not in e:continue
        x,y=e['xy'];cab=next((f for f in furniture if f.get('countertop') and f['rect'][0]<=x<=f['rect'][0]+f['rect'][2] and f['rect'][1]<=y<=f['rect'][1]+f['rect'][3]),None)
        if not cab:continue
        cx,cy,cw,cd=cab['rect'];w=min(600,cw*.85);d=min(500,cd*.85)
        x=max(cx,min(x-w/2,cx+cw-w));y=max(cy,min(y-d/2,cy+cd-d));z=cab['height_mm']
        if kind=='cooktop':
            pieces=[part('cooktop surface',[0,0,w,d],z+.5,4,'detail',radius=10)]
            for xx in (.22,.7):
                for yy in (.2,.65):pieces.append(part('burner',[w*xx,d*yy,w*.15,d*.18],z+5,2,'metal','oval'))
        else:
            pieces=[part('sink rim',[0,0,w,d],z+.5,8,'metal',radius=20),part('sink inset',[w*.08,d*.08,w*.84,d*.78],z+9,1,'detail',radius=35),part('tap stem',[w*.72,d*.87,w*.035,d*.04],z+8,160,'metal',radius=4),part('tap spout',[w*.45,d*.87,w*.305,d*.04],z+155,12,'metal',radius=4)]
        asset('DETAIL-'+e['id'],kind,[x,y,w,d],z+180,pieces,source_equipment=e['id'])
    for f in furniture:
        if f.get('name')=='浴室柜':
            x,y,a,b=f['rect'];w,d=(b,a) if f['facing'] in ('east','west') else (a,b);z=f['height_mm']
            pieces=[part('basin shell',[w*.16,d*.08,w*.68,d*.74],z,100,'shade','oval'),part('basin inset',[w*.23,d*.15,w*.54,d*.56],z+95,3,'metal','oval')]
            asset('DETAIL-'+f['id'],'vanity-basin',f['rect'],z+110,pieces,source_object=f['id'],facing=f['facing'])
        if f.get('name') in ('电视矮柜','电视柜'):
            x,y,a,b=f['rect'];room=next((r for r in model['rooms'] if r['id']==f.get('room')),None)
            facing=f['facing']
            if room:
                rx,ry,rw,rd=room['rect'];dx=rx+rw/2-(x+a/2);dy=ry+rd/2-(y+b/2)
                facing=('east' if dx>=0 else 'west') if abs(dx)>=abs(dy) else ('north' if dy>=0 else 'south')
            w,d=(b,a) if facing in ('east','west') else (a,b);z=f['height_mm'];screen_w=min(1400,w*.7)
            left=(w-screen_w)/2;back=d*.65;depth=min(35,d*.15)
            pieces=[part('screen frame',[left,back,screen_w,depth],z+130,700,'metal',radius=8),part('screen inset',[left+15,back-2,screen_w-30,3],z+145,670,'detail',radius=4),part('screen stand',[w*.46,d*.32,w*.08,d*.5],z,130,'metal',radius=4)]
            asset('DETAIL-TV-'+f['id'],'television',f['rect'],z+850,pieces,source_object=f['id'],facing=facing,presentation_only=True)
    # Shower enclosure uses the existing authored shower rectangle and glass height.
    shower=model.get('shower')
    if shower:
        x,y,w,d=shower['rect'];h=shower.get('glass_height_mm',2100)
        pieces=[part('shower tray',[0,0,w,d],0,35,'shade',radius=8),part('shower glass front',[0,0,w,10],35,h-35,'glazing'),part('shower glass side',[w-10,0,10,d],35,h-35,'glazing')]
        for xx,yy in ((0,0),(w-18,0),(w-18,d-18)):
            pieces.append(part('shower post',[xx,yy,18,18],35,h-35,'metal',radius=2))
        asset('DETAIL-SHOWER','shower',shower['rect'],h,pieces,source='model.shower')
    return accessories
