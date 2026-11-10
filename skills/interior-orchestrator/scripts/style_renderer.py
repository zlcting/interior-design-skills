"""Blender backend for the semantic furniture library and style materials."""
import hashlib
import json
import math
from pathlib import Path
import bpy
from mathutils import Vector
from furniture_library import world_xy
from style_plan import digest
from style_presentation import presentation_settings, cutaway_wall_height, presentation_views, presentation_part


def linear(color):
    rgb=[int(color[i:i+2],16)/255 for i in (1,3,5)]
    return tuple(v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in rgb)


def make_material(name,color,profile):
    m=bpy.data.materials.new(name);m.use_nodes=True;rgb=linear(color)
    m.diffuse_color=(*rgb,1);n=m.node_tree.nodes;links=m.node_tree.links
    bsdf=n.get('Principled BSDF');bsdf.inputs['Base Color'].default_value=(*rgb,1)
    bsdf.inputs['Roughness'].default_value=profile['roughness'];bsdf.inputs['Metallic'].default_value=profile['metallic']
    m['texture_kind']=profile['texture'];m['profile']=json.dumps(profile,sort_keys=True)
    if profile['texture']!='plain':
        tc=n.new('ShaderNodeTexCoord');mapping=n.new('ShaderNodeVectorMath');mapping.operation='MULTIPLY'
        mapping.inputs[1].default_value=(2,35,3) if profile['texture']=='wood' else (1,1,1)
        links.new(tc.outputs['Generated'],mapping.inputs[0])
        noise=n.new('ShaderNodeTexNoise');noise.name='Style texture';noise.inputs['Scale'].default_value=profile['scale'];noise.inputs['Detail'].default_value=3
        links.new(mapping.outputs['Vector'],noise.inputs['Vector'])
        ramp=n.new('ShaderNodeValToRGB');dark=.64 if profile['texture']=='wood' else .86
        ramp.color_ramp.elements[0].color=(*[v*dark for v in rgb],1)
        ramp.color_ramp.elements[1].color=(*rgb,1)
        links.new(noise.outputs['Fac'],ramp.inputs[0]);links.new(ramp.outputs[0],bsdf.inputs['Base Color'])
        bump=n.new('ShaderNodeBump');bump.inputs['Strength'].default_value=profile['bump'];bump.inputs['Distance'].default_value=.003
        links.new(noise.outputs['Fac'],bump.inputs['Height']);links.new(bump.outputs['Normal'],bsdf.inputs['Normal'])
    return m


def contact_shadow(material, strength, distance_mm):
    if strength<=0:return
    nodes=material.node_tree.nodes;links=material.node_tree.links
    bsdf=nodes.get('Principled BSDF');color=bsdf.inputs['Base Color'].default_value[:]
    ao=nodes.new('ShaderNodeAmbientOcclusion');ao.name='Contact shading';ao.inputs['Distance'].default_value=distance_mm/1000;ao.samples=16
    mix=nodes.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=strength;mix.inputs[1].default_value=color
    links.new(ao.outputs['Color'],mix.inputs[2]);links.new(mix.outputs[0],bsdf.inputs['Base Color'])


def outline_points(rect,shape,radius):
    x,y,w,d=rect
    if shape in ('oval','cone','frustum'):
        return [(x+w/2+w/2*math.cos(i*math.tau/64),y+d/2+d/2*math.sin(i*math.tau/64)) for i in range(64)]
    r=min(radius,w*.49,d*.49)
    if r<=0:return [(x,y),(x+w,y),(x+w,y+d),(x,y+d)]
    points=[]
    for cx,cy,start in ((x+w-r,y+r,-90),(x+w-r,y+d-r,0),(x+r,y+d-r,90),(x+r,y+r,180)):
        for i in range(9):
            angle=math.radians(start+90*i/8)
            points.append((cx+r*math.cos(angle),cy+r*math.sin(angle)))
    return points


def mesh_part(item,p,mat,collection,settings=None):
    p=presentation_part(p,settings,mat.name)
    z=p['z'];h=p['height'];name=item['id']+' '+p['name'];points=outline_points(p['rect'],p['shape'],p.get('radius',0))
    if p['shape'] in ('cushion','piping','botanical_leaf','botanical_stem','shade_shell'):
        from illustration_meshes import detailed_mesh
        local,faces=detailed_mesh(p);verts=[]
        for u,v,zz in local:
            xx,yy=world_xy(item,u,v);verts.append((xx/1000,yy/1000,zz/1000))
        mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
        obj=bpy.data.objects.new(name,mesh);bpy.context.scene.collection.objects.link(obj)
        for face in mesh.polygons:face.use_smooth=True
        if p['shape']=='botanical_leaf':
            mod=obj.modifiers.new('Leaf membrane','SOLIDIFY');mod.thickness=.00035
    elif p['shape']=='leaf':
        x,y,w,d=p['rect']
        local=[(x+w*.5,y,z),(x+w,y+d*.4,z+h*.3),(x+w*.8,y+d*.8,z+h*.7),(x+w*.5,y+d,z+h),(x+w*.2,y+d*.8,z+h*.7),(x,y+d*.4,z+h*.3),(x+w*.5,y+d*.45,z+h*.45)]
        verts=[]
        for u,v,zz in local:
            xx,yy=world_xy(item,u,v);verts.append((xx/1000,yy/1000,zz/1000))
        mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],[(6,i,(i+1)%6) for i in range(6)]);mesh.update()
        obj=bpy.data.objects.new(name,mesh);bpy.context.scene.collection.objects.link(obj)
        mod=obj.modifiers.new('Leaf thickness','SOLIDIFY');mod.thickness=.0015
    elif p['shape']=='ellipsoid':
        x,y,w,d=p['rect'];cx,cy=world_xy(item,x+w/2,y+d/2)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=16,location=(cx/1000,cy/1000,(z+h/2)/1000))
        obj=bpy.context.object;obj.name=name
        dims=(d,w,h) if item['facing'] in ('east','west') else (w,d,h)
        obj.dimensions=tuple(v/1000 for v in dims);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        for f in obj.data.polygons:f.use_smooth=True
    else:
        verts=[];cx=sum(x for x,y in points)/len(points);cy=sum(y for x,y in points)/len(points)
        for level in (0,1):
            ratio=p['ring_scales'][level] if p['shape']=='frustum' else (1/p.get('top_ratio',1) if p['shape']=='cone' and level==0 else 1)
            for x,y in points:
                xx,yy=world_xy(item,cx+(x-cx)*ratio,cy+(y-cy)*ratio)
                verts.append((xx/1000,yy/1000,(z+level*h)/1000))
        k=len(points);faces=[tuple(reversed(range(k))),tuple(range(k,2*k))]
        faces += [(i,(i+1)%k,(i+1)%k+k,i+k) for i in range(k)]
        mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
        obj=bpy.data.objects.new(name,mesh);bpy.context.scene.collection.objects.link(obj)
        bevel=obj.modifiers.new('Edge softness','BEVEL');bevel.width=min(p['bevel_mm']/1000,h/2500) if 'bevel_mm' in p else min(.008,h/6000);bevel.segments=4 if 'bevel_mm' in p else 2
        obj.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
    obj.data.materials.append(mat)
    for c in list(obj.users_collection):c.objects.unlink(obj)
    collection.objects.link(obj)
    obj['object_id']=item['id'];obj['asset_id']=item.get('asset_id','architecture');obj['part_name']=p['name'];obj['material_role']=p.get('role',mat.name)
    if p.get('hard_edge_applied'):obj['hard_edge_bevel_mm']=p['bevel_mm']
    return obj


def area(name,loc,energy,size,target,color=(1,1,1)):
    data=bpy.data.lights.new(name,'AREA');data.energy=energy;data.shape='DISK';data.size=size;data.color=color
    obj=bpy.data.objects.new(name,data);bpy.context.scene.collection.objects.link(obj);obj.location=loc
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()


def warm_rgb(k):
    t=k/100
    r=255 if t<=66 else 329.698727446*(t-60)**-.1332047592
    g=99.4708025861*math.log(t)-161.1195681661 if t<=66 else 288.1221695283*(t-60)**-.0755148492
    b=255 if t>=66 else (0 if t<=19 else 138.5177312231*math.log(t-10)-305.0447927307)
    return tuple(max(0,min(255,v))/255 for v in (r,g,b))


def compute_device(scene,requested):
    """Configure this session only. CPU remains an explicit, portable default."""
    if requested=='auto':
        prefs=bpy.context.preferences.addons['cycles'].preferences
        for backend in ('OPTIX','CUDA','HIP','ONEAPI','METAL'):
            try:
                prefs.compute_device_type=backend
                devices=prefs.get_devices_for_type(backend)
                selected=[d for d in devices if d.type==backend]
                if not selected:continue
                for device in devices:device.use=device.type==backend
                scene.cycles.device='GPU'
                return {'backend':backend,'devices':[d.name for d in selected]}
            except (TypeError,ValueError,RuntimeError):continue
    scene.cycles.device='CPU'
    return {'backend':'CPU','devices':['CPU']}


def render_style(project,source_text,plan,catalog,args,out):
    m=plan['resolved_model'];style=plan['style'];presentation=presentation_settings(style);scene=bpy.context.scene
    bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene
    scene.render.engine='CYCLES';scene.cycles.samples=args.samples;scene.cycles.use_denoising=not args.no_denoise
    device=compute_device(scene,args.device)
    print('COMPUTE_DEVICE',json.dumps(device),flush=True)
    if presentation['pixel_filter_width'] is not None:scene.cycles.filter_width=presentation['pixel_filter_width']
    scene.cycles.transmission_bounces=8
    scene.render.resolution_x=args.width;scene.render.resolution_y=round(args.width/presentation['aspect_ratio'])
    scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
    scene.world=bpy.data.worlds.new('Daylight');scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.79,.83,.88,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=style['lighting']['ambient_strength']
    if presentation['background_color']:
        scene.world.node_tree.nodes['Background'].inputs[0].default_value=(*linear(presentation['background_color']),1)
    scene.view_settings.view_transform='AgX';scene.view_settings.exposure=presentation['exposure']
    if presentation['contrast']=='medium-high':scene.view_settings.look='AgX - Medium High Contrast'
    roles={role:make_material(role,style['colors'][role],catalog['material_profiles'][profile]) for role,profile in style['surfaces'].items()}
    for material in roles.values():contact_shadow(material,presentation['contact_shadow_strength'],presentation['contact_shadow_distance_mm'])
    if 'warm_glow' in roles:
        bsdf=roles['warm_glow'].node_tree.nodes['Principled BSDF'];bsdf.inputs['Emission Color'].default_value=(*linear(style['colors']['warm_glow']),1);bsdf.inputs['Emission Strength'].default_value=2
    if 'lamp_shade' in roles:
        bsdf=roles['lamp_shade'].node_tree.nodes['Principled BSDF'];bsdf.inputs['Emission Color'].default_value=(*linear(style['colors']['lamp_shade']),1);bsdf.inputs['Emission Strength'].default_value=.4
    neutral=make_material('neutral white','#F0EDE5',catalog['material_profiles']['plain'])
    sources={mat['id']:roles[mat['style_role']] if mat.get('style_role') else make_material(mat['id'],mat['color'],catalog['material_profiles']['plain']) for mat in m['materials']}
    if presentation['material_mode']=='clay':
        neutral=roles['shade']
        # Include untagged materials and equipment; no old wood/metal colors may leak into clay mode.
        sources={mat['id']:roles.get(mat.get('style_role'),roles['wall']) for mat in m['materials']}
    glazing=neutral
    if presentation['glazing_color']:
        profile={**catalog['material_profiles']['plain'],'roughness':presentation['glazing_roughness']}
        glazing=make_material('Presentation glazing',presentation['glazing_color'],profile)
        bsdf=glazing.node_tree.nodes.get('Principled BSDF')
        bsdf.inputs['Transmission Weight'].default_value=presentation['glazing_transmission']
        bsdf.inputs['IOR'].default_value=1.45
        if presentation['living_refinement']:
            # Keep direct daylight through thin model glass without a dark caustic shadow.
            nodes=glazing.node_tree.nodes;links=glazing.node_tree.links
            transparent=nodes.new('ShaderNodeBsdfTransparent');path=nodes.new('ShaderNodeLightPath');mix=nodes.new('ShaderNodeMixShader')
            links.new(path.outputs['Is Shadow Ray'],mix.inputs[0]);links.new(bsdf.outputs['BSDF'],mix.inputs[1]);links.new(transparent.outputs[0],mix.inputs[2]);links.new(mix.outputs[0],nodes.get('Material Output').inputs['Surface'])
    roles['glazing']=glazing
    views=m.get('visualization',{}).get('cameras')
    if not views:raise ValueError('风格渲染需要 visualization.cameras；不要沿用其他户型相机')
    views=presentation_views(plan)
    full=bpy.data.collections.new('Full walls');cut=bpy.data.collections.new('Cutaway walls');furn=bpy.data.collections.new('Furniture')
    for c in (full,cut,furn):scene.collection.children.link(c)
    def block(name,rect,z,h,mat,collection=furn,radius=0):
        return mesh_part({'id':name,'rect':rect,'facing':'south'},dict(name=name,rect=[0,0,rect[2],rect[3]],z=z,height=h,shape='box',radius=radius),mat,collection,presentation)
    ceiling=m['height_mm']
    cut_sets={'default':cut};cut_cameras={'default':None}
    if presentation['cutaway_mode']=='camera':
        for view in views:
            if view.get('type')=='ORTHO':
                collection=bpy.data.collections.new('Cutaway '+view['name']);scene.collection.children.link(collection)
                cut_sets[view['name']]=collection;cut_cameras[view['name']]=view
    cut_heights={}
    for key,collection in [('full',full),*cut_sets.items()]:
        limits={}
        for wall in m['walls']:
            camera=cut_cameras.get(key)
            if key=='full':limit=min(ceiling,wall.get('height',ceiling))
            elif camera:limit=cutaway_wall_height(wall,m,camera,presentation)
            else:limit=min(presentation['cutaway_height_mm'],wall.get('height',ceiling),ceiling)
            limits[wall['id']]=limit
            openings=[o for o in m['openings'] if o['wall']==wall['id']]
            bounds=sorted({wall['start'],wall['end']}|{v for o in openings for v in (o['start'],o['start']+o['width'])})
            for a,b in zip(bounds,bounds[1:]):
                opening=next((o for o in openings if o['start']<=(a+b)/2<o['start']+o['width']),None)
                spans=[(0,min(limit,opening['sill'])),(min(limit,opening['sill']+opening['height']),limit)] if opening else [(0,limit)]
                rect=[a,wall['at'],b-a,wall['thickness']] if wall['axis']=='x' else [wall['at'],a,wall['thickness'],b-a]
                for bottom,top in spans:
                    if top>bottom:block(wall['id'],rect,bottom,top-bottom,roles['wall'],collection)
        cut_heights[key]=limits
    for room in m['rooms']:
        rect=room['rect'];matid=room['floor']
        floor_material=roles['floor'] if presentation['hard_edge_bevel_mm'] is not None and presentation['material_mode']=='clay' else sources[matid]
        block(room['id']+' floor',rect,-40,40,floor_material)
        if not presentation['floor_joints']:continue
        material=next(mm for mm in m['materials'] if mm['id']==matid)
        texture=style['surfaces']['floor'] if material.get('style_role')=='floor' else 'stone'
        spacing=180 if catalog['material_profiles'][texture]['texture']=='wood' else 600
        x,y,w,d=rect
        for xx in range(int(x+spacing),int(x+w),spacing):block('floor joint',[xx,y,1,d],.1,.2,roles['wall'])
        if spacing==600:
            for yy in range(int(y+spacing),int(y+d),spacing):block('tile joint',[x,yy,w,1],.1,.2,roles['wall'])
    for item in plan['furniture']:
        for p in item['parts']:
            mat=sources[item['material']] if p['role']=='source' else roles[p['role']]
            mesh_part(item,p,mat,furn,presentation)
    for detail in plan.get('accessories',[]):
        for p in detail['parts']:mesh_part(detail,p,roles[p['role']],furn,presentation)
    for light in plan['pendants']:
        x,y=light['xy'];item={**light,'rect':[x-550,y-200,1100,400],'facing':'south'}
        for p in light['parts']:
            p={**p,'z':p['z']+light['z_mm']}
            mesh_part(item,p,roles[p['role']],furn,presentation)
    styled_lights={x['id'] for x in plan['pendants']}
    for light in m.get('lights',[]):
        if light['id'] not in styled_lights:
            x,y=light['xy'];block(light['id'],[x-65,y-65,130,130],min(light['z_mm'],ceiling-40),30,neutral,full)
    # Retained cutaway windows stop at their wall height; glazing never floats above a cut wall.
    window_sets=[('full',full)]
    if presentation['cutaway_mode']=='camera':
        window_sets += [(key,col) for key,col in cut_sets.items() if key!='default']
    for key,collection in window_sets:
        for opening in m['openings']:
            if opening['kind']!='window':continue
            wall=next(w for w in m['walls'] if w['id']==opening['wall']);a=opening['start'];length=opening['width'];at=wall['at']
            height=min(opening['sill']+opening['height'],cut_heights[key][wall['id']])-opening['sill']
            if height<=0:continue
            rect=[a,at+wall['thickness']*.4,length,20] if wall['axis']=='x' else [at+wall['thickness']*.4,a,20,length]
            block(opening['id']+' glazing',rect,opening['sill'],height,glazing,collection)
            for t in (0,.5,1):
                r=[a+length*t-10,at,20,wall['thickness']] if wall['axis']=='x' else [at,a+length*t-10,wall['thickness'],20]
                block(opening['id']+' frame',r,opening['sill'],height,roles['metal'],collection)
            if presentation['living_refinement']:
                for zz in (opening['sill'],opening['sill']+height-24):
                    r=[a,at+wall['thickness']*.35,length,35] if wall['axis']=='x' else [at+wall['thickness']*.35,a,35,length]
                    block(opening['id']+' horizontal frame',r,zz,24,roles['metal'],collection)
    ex,ey,ew,ed=m['envelope'];cx=(ex+ew/2)/1000;cy=(ey+ed/2)/1000
    environment=bpy.data.collections.new('Presentation environment');scene.collection.children.link(environment)
    if presentation['foundation']:
        block('Presentation foundation',[ex-220,ey-220,ew+440,ed+440],-220,180,roles['wall'],radius=8)
    if presentation['ground_plane']:
        ground=make_material('Presentation background',presentation['background_color'] or '#808894',catalog['material_profiles']['plain'])
        block('Presentation ground',[ex-50000,ey-50000,ew+100000,ed+100000],-231,1,ground,environment)
    if presentation['lighting_rig']=='studio':
        # Directional key avoids the distance-related dark gradient on a large blue ground.
        scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.72,.77,.86,1)
        data=bpy.data.lights.new('Studio key','SUN');data.energy=1.65 if presentation['living_refinement'] else 2.0;data.angle=.26 if presentation['living_refinement'] else .16
        if presentation['studio_key_strength'] is not None:data.energy=presentation['studio_key_strength']
        if presentation['studio_key_angle'] is not None:data.angle=presentation['studio_key_angle']
        key=bpy.data.objects.new('Studio key',data);scene.collection.objects.link(key);key.location=(cx-6,cy-8,10)
        key.rotation_euler=(Vector((cx,cy,0))-key.location).to_track_quat('-Z','Y').to_euler()
        area('Studio fill',(cx+5,cy+4,9),300*presentation['studio_fill_scale'],7,(cx,cy,0))
        if presentation['living_refinement']:
            area('Studio front softbox',(cx-3,cy-5,8),200*presentation['studio_fill_scale'],6,(cx,cy,0))
            for detail in plan.get('accessories',[]):
                if 'light' not in detail:continue
                light=detail['light'];x,y,w,d=detail['rect'];lx=(x+w/2)/1000;ly=(y+d/2)/1000
                area('Warm floor lamp '+detail['id'],(lx,ly,light['z_mm']/1000),light['energy_w'],light['size_mm']/1000,(lx,ly,0),warm_rgb(light['cct_k']))
        for light in plan['pendants']:
            x,y=light['xy'];z=light['z_mm']
            area('Warm pendant '+light['id'],(x/1000,y/1000,(z+30)/1000),12,.18,(x/1000,y/1000,0),warm_rgb(3000))
    else:
        area('Daylight south',(cx,(ey-3000)/1000,7),1800,7,(cx,cy,0))
        area('Daylight west',((ex-3000)/1000,cy,6),1100,6,(cx,cy,1))
        area('Ambient',(cx,cy,5),600,8,(cx,cy,0))
        for room in m['rooms']:
            x,y,w,d=room['rect'];loc=((x+w/2)/1000,(y+d/2)/1000,ceiling/1000-.1)
            area(room['id'],loc,65,2,(loc[0],loc[1],0),warm_rgb(style['lighting']['cct_k']))
    camera_data=bpy.data.cameras.new('Camera');camera=bpy.data.objects.new('Camera',camera_data);scene.collection.objects.link(camera);scene.camera=camera
    selected=views if args.view=='all' else [v for v in views if v['name'] in args.view.split(',')]
    if not selected:raise ValueError('项目没有指定视图：'+args.view)
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    (out/'render-input.json').write_text(source_text,encoding='utf-8')
    (out/'resolved-input.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    manifest={'schema_version':2,'model_sha256':hashlib.sha256(source_text.encode()).hexdigest(),'resolved_model_sha256':digest(m),
              'revision':m['revision'],'engine':'Cycles','samples':args.samples,'width':args.width,'views':[],
              'render_quality':{'width':args.width,'height':scene.render.resolution_y,'samples':args.samples,'denoising':scene.cycles.use_denoising,'pixel_filter_width':scene.cycles.filter_width,'compute_device':device},
              'style':{'preset':style,'applied_features':['colors','material_profiles','furniture_forms','pendant_forms','lighting'],
                       'catalog_sha256':plan['catalog_sha256'],'resolved_plan_sha256':digest(plan),'legacy_adapter':plan['legacy_adapter'],
                       'applied_forms':{i['id']:i['asset_id'] for i in plan['furniture'] if i['mode']=='styled'},
                       'applied_pendants':{i['id']:i['asset_id'] for i in plan['pendants']},'basic_objects':plan['basic_objects']},
              'material_profiles':{r:catalog['material_profiles'][p] for r,p in style['surfaces'].items()},
              'generator_sha256':{f:hashlib.sha256((Path(__file__).parent/f).read_bytes()).hexdigest() for f in ('style_renderer.py','furniture_library.py','style_plan.py','style_library.py','style_presentation.py','white_details.py','living_details.py','illustration_meshes.py')},
              'presentation':presentation,'cutaway_wall_heights':cut_heights,
              'illustration_details':{'refined_objects':plan.get('refined_objects',{}),'accessories':plan.get('accessories',[])}}
    if style.get('presentation'):
        manifest['style']['applied_features'].append('presentation')
        if presentation['detail_level']=='illustrated':manifest['style']['applied_features'].append('illustrated_details')
        if presentation['material_mode']=='clay':manifest['style']['applied_features'].append('clay_override')
    for v in selected:
        camera.location=v['location'];target=Vector(v['target']);camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
        ortho=v.get('type')=='ORTHO';camera_data.type='ORTHO' if ortho else 'PERSP';camera_data.lens=v.get('lens',25)
        if ortho:camera_data.ortho_scale=v.get('ortho_scale',max(ew,ed)/1000*1.4*presentation['orthographic_margin'])
        full.hide_render=ortho
        active_cut=cut_sets.get(v['name'],cut)
        for collection in cut_sets.values():collection.hide_render=not ortho or collection!=active_cut
        filename=v['name']+'.png';scene.render.filepath=str(out/filename);bpy.ops.render.render(write_still=True)
        manifest['views'].append({**v,'file':filename})
    export_cut=None
    if presentation['material_mode']=='clay':
        default_view=next((v for v in views if v.get('type')=='ORTHO'),None)
        if default_view:
            export_cut=cut_sets.get(default_view['name'],cut)
            camera.location=default_view['location'];camera.rotation_euler=(Vector(default_view['target'])-camera.location).to_track_quat('-Z','Y').to_euler()
            camera_data.type='ORTHO';camera_data.ortho_scale=default_view.get('ortho_scale',max(ew,ed)/1000*1.4*presentation['orthographic_margin'])
    full.hide_render=export_cut is not None;full.hide_viewport=export_cut is not None
    for collection in cut_sets.values():
        collection.hide_render=collection!=export_cut;collection.hide_viewport=collection!=export_cut
    scene.render.filepath='//render.png'
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'interior.blend'))
    bpy.ops.object.select_all(action='DESELECT')
    excluded={environment}
    excluded.update(collection for collection in cut_sets.values() if collection!=export_cut)
    if export_cut is not None:excluded.add(full)
    for o in scene.objects:
        if o.type=='MESH' and not any(collection in excluded for collection in o.users_collection):o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(out/'interior.glb'),use_selection=True,export_format='GLB',export_cameras=False,export_lights=False)
    manifest['outputs']={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in out.iterdir() if f.name in ['interior.blend','interior.glb','render-input.json','resolved-input.json']+[v['file'] for v in manifest['views']]}
    (out/'render-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('RENDER_COMPLETE',len(manifest['views']))
