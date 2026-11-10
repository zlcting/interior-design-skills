"""Optional living-room study, anchored to typed furniture rather than case IDs."""
import copy
import math
from furniture_library import validate_parts, world_xy
from white_details import part


def living_pairs(furniture):
    """Pair each coffee table with the closest sofa in its authored room."""
    pairs=[]
    for table in furniture:
        if table['furniture_type']!='coffee_table':continue
        sofas=[f for f in furniture if f['furniture_type']=='sofa' and f.get('room')==table.get('room')]
        if not sofas:continue
        def distance(f):
            a=f['rect'];b=table['rect']
            return (a[0]+a[2]/2-b[0]-b[2]/2)**2+(a[1]+a[3]/2-b[1]-b[3]/2)**2
        pairs.append((min(sofas,key=distance),table))
    return pairs


def refine_living(furniture):
    items=copy.deepcopy(furniture)
    for sofa,table in living_pairs(items):
        _,_,a,b=sofa['rect'];w,d=(b,a) if sofa['facing'] in ('east','west') else (a,b);h=sofa['height_mm']
        arm=min(w*.065,d*.17);foot=h*.085;pieces=[]
        def add(*args,**kw):pieces.append(part(*args,**kw))
        for x in (w*.08,w*.92):
            for y in (d*.16,d*.84):add('recessed foot',[x-18,y-18,36,36],0,foot,'metal',radius=6)
        add('upholstered plinth',[12,12,w-24,d-24],foot,h*.17,'accent',radius=28,bevel_mm=16)
        add('back shell',[arm*.4,d*.84,w-arm*.8,d*.16],h*.23,h*.71,'upholstery','cushion',squareness=.33)
        for x in (0,w-arm):
            add('padded arm',[x,d*.01,arm,d*.97],h*.19,h*.53,'upholstery','cushion',squareness=.30)
        count=max(2,min(4,round(w/850)));bay=(w-arm*2)/count;gap=min(15,bay*.025)
        for i in range(count):
            x=arm+i*bay+gap/2;ww=bay-gap
            seat=[x,d*.055,ww,d*.72]
            add('tailored seat',seat,h*.31,h*.235,'upholstery','cushion',squareness=.30)
            add('seat piping',seat,h*.31,h*.235,'shade','piping',plane='xy',squareness=.30)
            back=[x,d*.69,ww,d*.25]
            add('tailored back',back,h*.52,h*.475,'upholstery','cushion',squareness=.37,lean=.18)
            add('back piping',back,h*.52,h*.475,'shade','piping',plane='xz',squareness=.37,lean=.18)
        # Small square pillows have a crowned face and tucked corners, not oval discs.
        pillow_w=min(w*.145,d*.42);pillow_h=h*.36
        for x in (arm+bay*.13,w-arm-bay*.13-pillow_w):
            rect=[x,d*.52,pillow_w,d*.22]
            add('tailored pillow',rect,h*.53,pillow_h,'shade','cushion',squareness=.52,lean=.24,tuft=.018)
            add('pillow piping',rect,h*.53,pillow_h,'accent','piping',plane='xz',squareness=.52,lean=.24)
        sofa['parts']=validate_parts(sofa,pieces);sofa['refinement']='living-tailored-sofa'
        _,_,a,b=table['rect'];w,d=(b,a) if table['facing'] in ('east','west') else (a,b);h=table['height_mm']
        thick=min(28,h*.085);leg=min(w,d)*.048;inset=min(w,d)*.10
        pieces=[part('slim tabletop',[0,0,w,d],h-thick,thick,'wood',radius=min(w,d)*.045,bevel_mm=4)]
        for x in (inset,w-inset-leg):
            for y in (inset,d-inset-leg):
                pieces.append(part('square table leg',[x,y,leg,leg],0,h-thick,'metal',radius=3,bevel_mm=2))
        for x in (inset,w-inset-leg):
            pieces.append(part('recessed apron',[x,inset,leg*.65,d-2*inset],h-thick-30,30,'wood',radius=2))
        table['parts']=validate_parts(table,pieces);table['refinement']='living-slim-table'
    return items


def plant_parts(size,z):
    pieces=[part('ceramic planter',[size*.30,size*.30,size*.40,size*.40],z,size*.42,'shade','cone',top_ratio=1.15),
            part('planter lip',[size*.295,size*.295,size*.41,size*.41],z+size*.39,size*.025,'shade','oval'),
            part('visible soil',[size*.325,size*.325,size*.35,size*.35],z+size*.416,size*.012,'soil','oval')]
    for i in range(18):
        angle=i*2.399963;outer=i<11;radius=.43 if outer else .28
        tip_z=.28+(i%4)*.095 if outer else .68+(i%3)*.055
        start=[.5+.045*math.cos(angle),.5+.045*math.sin(angle),.035]
        end=[.5+radius*math.cos(angle),.5+radius*math.sin(angle),tip_z]
        for shape,name in (('botanical_leaf','broad leaf '),('botanical_stem','stem ')):
            pieces.append(part(name+str(i),[0,0,size,size],z+size*.42,size*1.05,'foliage',shape,
                               start=start,end=end,arch=.25 if outer else .12,width=.14 if outer else .13))
    return pieces


def living_accessories(model,furniture,accessories):
    details=copy.deepcopy(accessories);pairs=living_pairs(furniture)
    table_ids={t['id'] for s,t in pairs}
    for plant in details:
        if plant['asset_id']!='potted-plant' or plant.get('source_object') not in table_ids:continue
        support=next(f for f in furniture if f['id']==plant['source_object'])
        x,y,w,d=support['rect'];size=min(420,w*.68,d*.68);z=support['height_mm']
        plant.update(rect=[x+w*.5-size/2,y+d*.60-size/2,size,size],height_mm=z+size*1.5,
                     parts=plant_parts(size,z),refinement='broad-leaf-plant')
        validate_parts(plant,plant['parts'])
    for sofa,table in pairs:
        room=next((r for r in model['rooms'] if r['id']==sofa.get('room')),None)
        if not room:continue
        _,_,a,b=sofa['rect'];w,d=(b,a) if sofa['facing'] in ('east','west') else (a,b)
        size=360;rect=None
        for u in (w+250,-250):
            cx,cy=world_xy(sofa,u,d*.55);candidate=[cx-size/2,cy-size/2,size,size]
            rx,ry,rw,rd=room['rect'];x,y,ww,dd=candidate
            if not (rx+25<=x and ry+25<=y and x+ww<=rx+rw-25 and y+dd<=ry+rd-25):continue
            def overlaps(f):
                fx,fy,fw,fd=f['rect']
                return f['furniture_type']!='rug' and x<fx+fw+20 and x+ww>fx-20 and y<fy+fd+20 and y+dd>fy-20
            if any(overlaps(f) for f in furniture):continue
            rect=candidate;break
        if rect is None:continue  # Do not force a new fixture into a circulation/furniture conflict.
        pieces=[part('lamp base',[55,55,250,250],0,24,'metal','oval'),
                part('lamp stem',[174,174,12,12],24,1360,'metal','oval'),
                part('linen lamp shade',[0,0,size,size],1220,350,'lamp_shade','shade_shell',top_ratio=.72),
                part('warm diffuser',[24,24,size-48,size-48],1228,5,'warm_glow','oval'),
                part('lamp finial',[172,172,16,16],1570,14,'metal','oval')]
        fixture=dict(id='DECOR-LAMP-'+sofa['id'],asset_id='living-floor-lamp',rect=rect,facing='south',height_mm=1590,
                     parts=pieces,source_object=sofa['id'],presentation_only=True,
                     light={'z_mm':1215,'energy_w':55,'cct_k':2850,'size_mm':280})
        validate_parts(fixture,pieces);details.append(fixture)
    return details


def living_cameras(furniture):
    """A complete local study; axes rotate with the sofa and include lamp/table."""
    pairs=living_pairs(furniture)
    if not pairs:return []
    sofa,table=pairs[0];sx,sy,sw,sd=sofa['rect'];tx,ty,tw,td=table['rect']
    cx=(min(sx,tx)+max(sx+sw,tx+tw))/2/1000;cy=(min(sy,ty)+max(sy+sd,ty+td))/2/1000
    front={'south':(0,-1),'north':(0,1),'west':(-1,0),'east':(1,0)}[sofa['facing']]
    # Front three-quarter view, avoiding an extreme wide-angle stretch of the cushions.
    fx,fy=front;rx,ry=-fy,fx
    size=max(sw,sd,tw,td)/1000
    sources=[sofa['id'],table['id']]
    return [{'name':'living-detail','type':'ORTHO','ortho_scale':max(5.4,size*2.08),
             'location':[cx+fx*6-rx*6,cy+fy*6-ry*6,8.2], 'target':[cx,cy,.65],
             'presentation_only':True,'study_cutaway_mm':300,'source_objects':sources},
            {'name':'living-close','lens':24,
             'location':[cx+fx*1.8-rx*1.95,cy+fy*1.8-ry*1.95,2.8], 'target':[cx,cy-.2,.65],
             'presentation_only':True,'source_objects':sources}]
