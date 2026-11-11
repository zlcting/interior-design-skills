"""Run inside Blender after loading a generated .blend; verify actual mesh bounds/materials."""
import json
import sys
from pathlib import Path
import bpy
from mathutils import Vector
p=Path(sys.argv[sys.argv.index('--')+1])
manifest=json.loads((p/'render-manifest.json').read_text())
model=json.loads((p/'resolved-input.json').read_text())
items={f['id']:f for f in model['furniture']}
deps=bpy.context.evaluated_depsgraph_get();seen=set();meshes=0
for obj in bpy.context.scene.objects:
    oid=obj.get('object_id')
    if oid not in items or obj.type!='MESH':continue
    f=items[oid];x,y,w,d=f['rect'];h=f['height_mm'];seen.add(oid);meshes+=1
    evaluated=obj.evaluated_get(deps)
    for v in evaluated.bound_box:
        pt=evaluated.matrix_world @ Vector(v);xx,yy,zz=[value*1000 for value in pt]
        assert x-.1<=xx<=x+w+.1 and y-.1<=yy<=y+d+.1 and -.1<=zz<=h+.1,(oid,obj.name,tuple(pt))
    assert obj.data.materials,(oid,'missing material')
    expected=manifest['style']['applied_forms'].get(oid)
    if expected:assert obj.get('asset_id')==expected
assert seen==set(items),(set(items)-seen)
for role,profile in manifest['material_profiles'].items():
    material=bpy.data.materials[role]
    bsdf=material.node_tree.nodes.get('Principled BSDF')
    assert abs(bsdf.inputs['Roughness'].default_value-profile['roughness'])<1e-5
    assert abs(bsdf.inputs['Metallic'].default_value-profile['metallic'])<1e-5
    assert material['texture_kind']==profile['texture']
print('STYLE_SCENE_VERIFIED',len(seen),'objects',meshes,'parts')

if manifest.get('presentation',{}).get('material_mode')=='clay':
    assert bpy.context.scene.camera.data.type=='ORTHO'
    assert bpy.data.collections['Full walls'].hide_viewport
    for obj in bpy.context.scene.objects:
        if obj.type!='MESH':continue
        if obj.get('object_id') in items:
            for mat in obj.data.materials:
                assert mat['texture_kind']=='plain',(obj.name,'texture leak')
                if obj.get('material_role')=='detail':
                    assert mat.name=='detail' and max(mat.diffuse_color[:3])-min(mat.diffuse_color[:3])<.2
                else:assert min(mat.diffuse_color[:3])>.6,(obj.name,'dark material leak')
                assert mat.node_tree.nodes['Principled BSDF'].inputs['Metallic'].default_value==0
        assert not obj.name.startswith(('floor joint','tile joint'))
    assert bpy.data.collections['Presentation environment'].objects
    assert bpy.data.materials.get('Presentation glazing')
    for key,limits in manifest['cutaway_wall_heights'].items():
        if key in ('full','default'):continue
        collection=bpy.data.collections['Cutaway '+key]
        for obj in collection.objects:
            oid=obj.get('object_id')
            if oid in limits:
                assert max((obj.matrix_world @ Vector(v)).z*1000 for v in obj.bound_box)<=limits[oid]+.1
    print('WHITE_PRESENTATION_VERIFIED clay, neutral materials, blue environment, camera cutaway')

    if manifest.get('presentation',{}).get('detail_level')=='illustrated':
        assert bpy.data.lights.get('Studio key')
        assert bpy.data.materials['wall'].node_tree.nodes.get('Contact shading')
        expected={d['id'] for d in manifest['illustration_details']['accessories']}
        seen_details={o.get('object_id') for o in bpy.context.scene.objects if o.get('object_id') in expected}
        assert expected==seen_details
        detail_map={d['id']:d for d in manifest['illustration_details']['accessories']}
        for obj in bpy.context.scene.objects:
            if obj.type!='MESH' or obj.get('object_id') not in detail_map:continue
            item=detail_map[obj['object_id']];x,y,w,d=item['rect'];h=item['height_mm']
            evaluated=obj.evaluated_get(deps)
            for vertex in evaluated.bound_box:
                xx,yy,zz=[v*1000 for v in (evaluated.matrix_world @ Vector(vertex))]
                assert x-2<=xx<=x+w+2 and y-2<=yy<=y+d+2 and -2<=zz<=h+2,(obj.name,'accessory exceeds envelope')
        assert any(o.get('part_name')=='toilet bowl' for o in bpy.context.scene.objects)
        print('ILLUSTRATED_DETAILS_VERIFIED',len(expected),'accessories')
        if manifest['presentation'].get('living_refinement'):
            assert bpy.data.materials['Presentation glazing'].node_tree.nodes['Principled BSDF'].inputs['Transmission Weight'].default_value>.9
            lamps=[d for d in detail_map.values() if d['asset_id']=='living-floor-lamp']
            for lamp in lamps:assert bpy.data.lights.get('Warm floor lamp '+lamp['id'])
            assert any(o.get('part_name')=='tailored seat' for o in bpy.context.scene.objects)
            assert any(o.get('part_name','').startswith('broad leaf ') for o in bpy.context.scene.objects)
            print('LIVING_STUDY_VERIFIED transparent glazing, tailored cushions, broad leaves,',len(lamps),'warm lamp')
    if manifest['presentation'].get('hard_edge_bevel_mm') is not None:
        maximum=manifest['presentation']['hard_edge_bevel_mm'];hard=[]
        for obj in bpy.context.scene.objects:
            if 'hard_edge_bevel_mm' not in obj:continue
            hard.append(obj);bevel=obj.modifiers.get('Edge softness')
            assert bevel and bevel.width*1000<=maximum+.001
            assert obj.get('material_role') not in ('upholstery','shade','accent')
        assert hard
        assert abs(bpy.data.lights['Studio key'].angle-manifest['presentation']['studio_key_angle'])<1e-5
        assert abs(bpy.data.lights['Studio key'].energy-manifest['presentation']['studio_key_strength'])<1e-5
        assert abs(bpy.data.lights['Studio fill'].energy-300*manifest['presentation']['studio_fill_scale'])<1e-4
        ao=bpy.data.materials['wall'].node_tree.nodes['Contact shading']
        assert abs(ao.inputs['Distance'].default_value*1000-manifest['presentation']['contact_shadow_distance_mm'])<.01
        assert bpy.data.materials['wall'].diffuse_color[0]>bpy.data.materials['floor'].diffuse_color[0]
        q=manifest['render_quality'];scene=bpy.context.scene
        assert (scene.render.resolution_x,scene.render.resolution_y)==(q['width'],q['height'])
        assert scene.cycles.samples==q['samples'] and scene.cycles.use_denoising==q['denoising']
        assert abs(scene.cycles.filter_width-q['pixel_filter_width'])<1e-5
        assert scene.render.filepath.startswith('//')
        print('CRISP_PRESENTATION_VERIFIED',len(hard),'hard parts, max bevel',maximum,'mm;',q['width'],'x',q['height'])
