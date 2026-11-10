"""Style selection, semantic portability, dimensions, and rejection behavior."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'skills/interior-orchestrator/scripts'
sys.path.insert(0,str(SCRIPTS))
from style_library import load_styles, load_catalog, validate_style, read_json, COLORS
from style_plan import resolve_plan, digest
from furniture_library import build_parts, validate_parts, world_xy
from style_presentation import presentation_settings, cutaway_wall_height, presentation_camera
MODEL=json.loads((ROOT/'projects/STYLE-LAB-096/model/project.json').read_text())
CATALOG=load_catalog();STYLES=load_styles()

class StyleTests(unittest.TestCase):
    def test_crisp_edges_preserve_soft_bodies_and_authored_bounds(self):
        from style_presentation import presentation_part
        settings=presentation_settings(STYLES['white-minimal'])
        hard={'name':'door','shape':'box','role':'wood','rect':[0,0,600,20],'z':0,'height':2200,'radius':30,'bevel_mm':8}
        original=copy.deepcopy(hard);result=presentation_part(hard,settings)
        self.assertEqual(hard,original);self.assertEqual(result['rect'],hard['rect'])
        self.assertLessEqual(result['radius'],settings['hard_edge_bevel_mm']*4)
        self.assertLessEqual(result['bevel_mm'],settings['hard_edge_bevel_mm'])
        for shape,role in [('cushion','upholstery'),('box','upholstery'),('ellipsoid','wood')]:
            soft={**hard,'shape':shape,'role':role}
            self.assertEqual(presentation_part(soft,settings),soft)
        wall={k:v for k,v in hard.items() if k!='role'}
        self.assertTrue(presentation_part(wall,settings,'wall')['hard_edge_applied'])
        for name in ('japanese-natural','italian-modern','mid-century'):
            self.assertEqual(presentation_part(hard,presentation_settings(STYLES[name])),hard)

    def test_style_quality_defaults_and_explicit_overrides(self):
        from style_presentation import render_quality
        self.assertEqual(render_quality(STYLES['white-minimal']),(2400,128))
        self.assertEqual(render_quality(STYLES['white-minimal'],1000,24),(1000,24))
        self.assertEqual(render_quality(None),(1200,32))
        for name in ('japanese-natural','italian-modern','mid-century'):
            self.assertEqual(render_quality(STYLES[name]),(1200,32))
        for width,samples in [(200,32),(8001,32),(1000,0),(True,32),(1000,1.5)]:
            with self.assertRaises(ValueError):render_quality(STYLES['white-minimal'],width,samples)

    def test_invalid_clarity_settings_are_rejected(self):
        for key,value in [('hard_edge_bevel_mm',0),('studio_key_strength',float('nan')),('studio_key_angle',2),('studio_fill_scale',-1),('pixel_filter_width',.1),('default_render_width',2400.5),('default_render_samples',True)]:
            style=copy.deepcopy(STYLES['white-minimal']);style['presentation'][key]=value
            with self.assertRaises(ValueError):presentation_settings(style)

    def test_living_refinement_is_limited_to_the_coffee_table_group(self):
        source=copy.deepcopy(MODEL);style=copy.deepcopy(STYLES['white-minimal'])
        new=resolve_plan(source,style);style['presentation']['living_refinement']=False
        old=resolve_plan(source,style);old_items={f['id']:f for f in old['furniture']}
        refined=[f for f in new['furniture'] if (f.get('refinement') or '').startswith('living-')]
        self.assertEqual({f['furniture_type'] for f in refined},{'sofa','coffee_table'})
        for item in new['furniture']:
            if item not in refined:self.assertEqual(item,old_items[item['id']])
            self.assertEqual(item['rect'],old_items[item['id']]['rect'])
        self.assertEqual(source,MODEL)

    def test_detailed_surfaces_fit_actual_envelopes_in_all_facings(self):
        from illustration_meshes import detailed_mesh
        shapes={'cushion','piping','botanical_leaf','botanical_stem','shade_shell'}
        for facing in ('north','east','south','west'):
            model=copy.deepcopy(MODEL)
            for f in model['furniture']:
                if f['furniture_type']=='sofa':f['facing']=facing
            plan=resolve_plan(model,STYLES['white-minimal'])
            for item in plan['furniture']+plan['accessories']:
                x,y,w,d=item['rect']
                for part in item['parts']:
                    if part['shape'] not in shapes:continue
                    vertices,faces=detailed_mesh(part)
                    self.assertGreater(len(faces),40)
                    for u,v,z in vertices:
                        xx,yy=world_xy(item,u,v)
                        self.assertTrue(x-.01<=xx<=x+w+.01 and y-.01<=yy<=y+d+.01)
                        self.assertTrue(-.01<=z<=item['height_mm']+.01)

    def test_floor_lamp_is_anchored_clear_of_furniture_and_optional(self):
        plan=resolve_plan(MODEL,STYLES['white-minimal'])
        lamps=[d for d in plan['accessories'] if d['asset_id']=='living-floor-lamp']
        self.assertEqual(len(lamps),1)
        for lamp in lamps:
            x,y,w,d=lamp['rect'];self.assertTrue(lamp['presentation_only'])
            self.assertIn(lamp['source_object'],{f['id'] for f in plan['furniture']})
            for f in plan['furniture']:
                if f['furniture_type']=='rug':continue
                fx,fy,fw,fd=f['rect']
                self.assertFalse(x<fx+fw and x+w>fx and y<fy+fd and y+d>fy)
        from living_details import living_accessories
        blocked=copy.deepcopy(MODEL)
        blocked['rooms'][0]['rect']=[2600,650,900,2600]
        details=living_accessories(blocked,plan['furniture'],[])
        self.assertFalse(any(d['asset_id']=='living-floor-lamp' for d in details))

    def test_detail_camera_is_derived_without_mutating_project_views(self):
        from style_presentation import presentation_views
        plan=resolve_plan(MODEL,STYLES['white-minimal']);before=copy.deepcopy(plan['resolved_model'])
        views=presentation_views(plan);study=next(v for v in views if v['name']=='living-detail')
        self.assertEqual(study['type'],'ORTHO');self.assertTrue(study['presentation_only'])
        self.assertEqual(before,plan['resolved_model'])
        self.assertEqual(len(views),len(MODEL['visualization']['cameras'])+2)

    def test_illustrated_equipment_and_bedding_are_not_boxes(self):
        p=resolve_plan(MODEL,STYLES['white-minimal'])
        refinements=set(p['refined_objects'].values())
        self.assertTrue({'refrigerator','washer_stack','toilet','bedding'}<=refinements)
        self.assertEqual(len(p['basic_objects']),4)
        toilet=next(f for f in p['furniture'] if f.get('refinement')=='toilet')
        self.assertIn('toilet bowl',{x['name'] for x in toilet['parts']})
        self.assertTrue(any(x['shape']=='ellipsoid' for x in toilet['parts']))
    def test_accessories_are_anchored_and_explicitly_recorded(self):
        p=resolve_plan(MODEL,STYLES['white-minimal']);items={f['id']:f for f in p['furniture']}
        ids=[d['id'] for d in p['accessories']];self.assertEqual(len(ids),len(set(ids)))
        types={d['asset_id'] for d in p['accessories']}
        self.assertTrue({'potted-plant','cooktop','sink','shower','vanity-basin','television'}<=types)
        for d in p['accessories']:
            validate_parts(d,d['parts'])
            if d['asset_id']=='potted-plant':
                f=items[d['source_object']];x,y,w,h=f['rect'];dx,dy,dw,dh=d['rect']
                self.assertTrue(x<=dx and y<=dy and dx+dw<=x+w and dy+dh<=y+h)
                self.assertGreaterEqual(min(p['z'] for p in d['parts']),f['height_mm'])
    def test_shower_enclosure_uses_authoritative_model(self):
        p=resolve_plan(MODEL,STYLES['white-minimal'])
        shower=next(x for x in p['accessories'] if x['asset_id']=='shower')
        self.assertEqual(shower['rect'],MODEL['shower']['rect'])
        self.assertEqual(shower['height_mm'],MODEL['shower']['glass_height_mm'])
    def test_accessories_can_be_disabled_without_changing_layout(self):
        s=copy.deepcopy(STYLES['white-minimal']);s['presentation']['accessories']=False
        p=resolve_plan(MODEL,s);self.assertEqual(p['accessories'],[])
        self.assertEqual(p['resolved_model'],MODEL)
    def test_unrecognized_equipment_keeps_basic_geometry(self):
        m=copy.deepcopy(MODEL)
        f=next(f for f in m['furniture'] if f['furniture_type']=='equipment');f['name']='Unknown device';f['equipment_type']='unknown'
        p=resolve_plan(m,STYLES['white-minimal']);obj=next(x for x in p['furniture'] if x['id']==f['id'])
        self.assertEqual(obj['mode'],'basic');self.assertEqual(len(obj['parts']),1)
    def test_conical_pendant_is_bounded_and_has_warm_bulb(self):
        p=resolve_plan(MODEL,STYLES['white-minimal']);light=p['pendants'][0]
        self.assertEqual(light['asset_id'],'cone-shade')
        self.assertTrue(any(part['shape']=='frustum' for part in light['parts']))
        self.assertTrue(any(part['role']=='warm_glow' for part in light['parts']))
    def test_illustration_controls_validate_and_default_off(self):
        for name in ('japanese-natural','italian-modern','mid-century'):
            p=presentation_settings(STYLES[name]);self.assertEqual(p['detail_level'],'basic');self.assertEqual(p['lighting_rig'],'daylight');self.assertEqual(p['contact_shadow_strength'],0)
        for key,value in [('contact_shadow_strength',2),('contact_shadow_distance_mm',-1),('lighting_rig','none'),('detail_level','bad'),('accessories','yes')]:
            s=copy.deepcopy(STYLES['white-minimal']);s['presentation'][key]=value
            with self.assertRaises(ValueError):validate_style(s,CATALOG)
    def test_white_framing_is_reversible_and_does_not_change_project_camera(self):
        source=copy.deepcopy(MODEL['visualization']['cameras'][0]);before=copy.deepcopy(source)
        result=presentation_camera(source,presentation_settings(STYLES['white-minimal']))
        self.assertEqual(source,before)
        self.assertGreater(result['ortho_scale'],source['ortho_scale'])
        self.assertGreater(result['target'][2],source['target'][2])
        for name in ('japanese-natural','italian-modern','mid-century'):
            self.assertEqual(presentation_camera(source,presentation_settings(STYLES[name])),source)
    def test_white_style_is_selectable_and_matte(self):
        style=STYLES['white-minimal'];p=presentation_settings(style)
        self.assertEqual(p['material_mode'],'clay')
        self.assertFalse(p['floor_joints']);self.assertTrue(p['ground_plane'])
        for role in COLORS:
            profile=style['surfaces'][role]
            self.assertEqual(CATALOG['material_profiles'][profile]['texture'],'plain')
            self.assertEqual(CATALOG['material_profiles'][profile]['metallic'],0)
            color=style['colors'][role]
            self.assertGreaterEqual(min(int(color[i:i+2],16) for i in (1,3,5)),210)
    def test_white_does_not_change_layout(self):
        p=resolve_plan(MODEL,STYLES['white-minimal'])
        self.assertEqual(p['resolved_model'],MODEL)
        self.assertEqual([f['rect'] for f in p['furniture']],[f['rect'] for f in MODEL['furniture']])
    def test_original_styles_keep_default_presentation(self):
        for name in ('japanese-natural','italian-modern','mid-century'):
            p=presentation_settings(STYLES[name])
            self.assertEqual(p['material_mode'],'project')
            self.assertEqual(p['cutaway_mode'],'uniform')
            self.assertEqual(p['cutaway_height_mm'],1050)
            self.assertTrue(p['floor_joints']);self.assertFalse(p['ground_plane'])
    def test_camera_cutaway_keeps_far_exterior_walls(self):
        p=presentation_settings(STYLES['white-minimal']);walls={w['id']:w for w in MODEL['walls']}
        view={'location':[17,-17,20]}
        for wid in ('W02','W03'):self.assertEqual(cutaway_wall_height(walls[wid],MODEL,view,p),2700)
        for wid in ('W01','W04','W05'):self.assertEqual(cutaway_wall_height(walls[wid],MODEL,view,p),1250)
        reverse={'location':[-17,17,20]}
        for wid in ('W01','W04'):self.assertEqual(cutaway_wall_height(walls[wid],MODEL,reverse,p),2700)
        for wid in ('W02','W03','W05'):self.assertEqual(cutaway_wall_height(walls[wid],MODEL,reverse,p),1250)
    def test_cutaway_respects_actual_wall_height(self):
        wall=copy.deepcopy(MODEL['walls'][1]);wall['height']=700
        self.assertEqual(cutaway_wall_height(wall,MODEL,{'location':[17,-17,20]},presentation_settings(STYLES['white-minimal'])),700)
    def test_invalid_presentation_is_rejected(self):
        for key,value in [('background_color','blue'),('material_mode','unknown'),('cutaway_mode','unknown'),('cutaway_height_mm',float('nan')),('ground_plane','yes'),('glazing_transmission',2),('extra_field',True)]:
            style=copy.deepcopy(STYLES['white-minimal']);style['presentation'][key]=value
            with self.assertRaises(ValueError):validate_style(style,CATALOG)
    def test_every_style_resolves_complete_families(self):
        for s in STYLES.values():
            p=resolve_plan(MODEL,s)
            self.assertIsNone(p['legacy_adapter'])
            self.assertEqual({f['furniture_type'] for f in p['furniture'] if f['mode']=='styled'},{'sofa','coffee_table','chair','cabinet_front'})
            self.assertEqual(len(p['pendants']),1)
    def test_variants_have_different_geometry(self):
        plans=[resolve_plan(MODEL,STYLES[name]) for name in ('japanese-natural','italian-modern','mid-century')]
        for family in ('sofa','coffee_table','chair','cabinet_front'):
            shapes=[digest(next(i['parts'] for i in p['furniture'] if i['furniture_type']==family)) for p in plans]
            self.assertEqual(len(set(shapes)),3,family)
        self.assertEqual(len({digest(p['pendants'][0]['parts']) for p in plans}),3)
    def test_all_parts_fit_all_facings_and_source_is_unchanged(self):
        source=copy.deepcopy(MODEL)
        for s in STYLES.values():
            for facing in ('south','north','west','east'):
                m=copy.deepcopy(MODEL)
                for f in m['furniture']:f['facing']=facing
                p=resolve_plan(m,s)
                for item in p['furniture']:
                    validate_parts(item,item['parts'])
                    x,y,w,d=item['rect']
                    for part in item['parts']:
                        u,v,pw,pd=part['rect']
                        for a,b in ((u,v),(u+pw,v+pd)):
                            xx,yy=world_xy(item,a,b)
                            self.assertTrue(x-.001<=xx<=x+w+.001 and y-.001<=yy<=y+d+.001)
        self.assertEqual(MODEL,source)
    def test_arbitrary_ids_and_negative_translation(self):
        m=copy.deepcopy(MODEL)
        for i,f in enumerate(m['furniture']):
            f['id']='MY-ITEM-'+str(i);f['rect'][0]-=25000;f['rect'][1]+=4000
        p=resolve_plan(m,STYLES['mid-century'])
        self.assertTrue(all(i['id'].startswith('MY-ITEM-') for i in p['furniture']))
    def test_missing_semantics_is_rejected_for_new_projects(self):
        m=copy.deepcopy(MODEL);m['furniture'][0].pop('furniture_type')
        with self.assertRaisesRegex(ValueError,'furniture_type'):resolve_plan(m,STYLES['mid-century'])
    def test_missing_asset_is_rejected(self):
        s=copy.deepcopy(STYLES['mid-century']);s['forms']['sofa']='missing'
        with self.assertRaisesRegex(ValueError,'资产'):validate_style(s,CATALOG)
    def test_wrong_asset_family_is_rejected(self):
        m=copy.deepcopy(MODEL);m['furniture'][0]['asset_id']='oval-wood'
        with self.assertRaisesRegex(ValueError,'类型不符'):resolve_plan(m,STYLES['mid-century'])
    def test_explicit_asset_override(self):
        m=copy.deepcopy(MODEL);m['furniture'][0]['asset_id']='low-wide-modular'
        p=resolve_plan(m,STYLES['mid-century'])
        self.assertEqual(p['furniture'][0]['asset_id'],'low-wide-modular')
    def test_new_variant_in_existing_builder_needs_no_renderer_change(self):
        c=copy.deepcopy(CATALOG);c['assets']['my-new-sofa']=copy.deepcopy(c['assets']['low-wood-frame'])
        c['assets']['my-new-sofa']['parameters']['seat_count']=2
        s=copy.deepcopy(STYLES['japanese-natural']);s['forms']['sofa']='my-new-sofa'
        p=resolve_plan(MODEL,s,c)
        self.assertEqual(p['furniture'][0]['asset_id'],'my-new-sofa')
        self.assertEqual(sum(part['name']=='seat' for part in p['furniture'][0]['parts']),2)
    def test_unimplemented_geometry_parameter_is_rejected(self):
        c=copy.deepcopy(CATALOG)
        c['assets']['low-wood-frame']['parameters']['legs']='unknown-shape'
        with self.assertRaisesRegex(ValueError,'不支持参数'):
            resolve_plan(MODEL,STYLES['japanese-natural'],c)
    def test_height_overrun_is_rejected(self):
        c=copy.deepcopy(CATALOG)
        c['assets']['low-wood-frame']['parameters']['back_h']=.99
        with self.assertRaisesRegex(ValueError,'外包尺寸'):
            resolve_plan(MODEL,STYLES['japanese-natural'],c)
    def test_invalid_color_role_and_path_id(self):
        for key,val in [('wall','bad'),('wood','#GGGGGG')]:
            s=copy.deepcopy(STYLES['mid-century']);s['colors'][key]=val
            with self.assertRaises(ValueError):validate_style(s,CATALOG)
        s=copy.deepcopy(STYLES['mid-century']);s['id']='../escape'
        with self.assertRaises(ValueError):validate_style(s,CATALOG)
    def test_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.json';p.write_text('{"id":1,"id":2}')
            with self.assertRaisesRegex(ValueError,'重复'):read_json(p)
    def test_check_only_has_no_side_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'not-created'
            r=subprocess.run([sys.executable,'-B',str(SCRIPTS/'render_project.py'),str(ROOT/'projects/STYLE-LAB-096'),'--check-only','--out',str(out),'--style','italian-modern'],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr);self.assertFalse(out.exists())
    def test_failure_does_not_create_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'not-created'
            r=subprocess.run([sys.executable,'-B',str(SCRIPTS/'render_project.py'),str(ROOT/'projects/STYLE-LAB-096'),'--check-only','--out',str(out),'--style','unknown'],capture_output=True,text=True)
            self.assertNotEqual(r.returncode,0);self.assertFalse(out.exists())
    def test_legacy_demo_adaptation(self):
        m=json.loads((ROOT/'projects/DEMO-APT-096/model/project.json').read_text())
        p=resolve_plan(m,STYLES['mid-century'])
        self.assertEqual(p['legacy_adapter'],'DEMO-APT-096')
        self.assertEqual(p['furniture'][0]['facing'],'west')
    def test_tiny_invalid_furniture_is_rejected(self):
        m=copy.deepcopy(MODEL);m['furniture'][0]['rect'][2]=0
        with self.assertRaises(ValueError):resolve_plan(m,STYLES['mid-century'])
    def test_unsafe_camera_names_rejected(self):
        m=copy.deepcopy(MODEL);m['visualization']['cameras'][0]['name']='../escape'
        with self.assertRaises(ValueError):resolve_plan(m,STYLES['mid-century'])

if __name__=='__main__':unittest.main()
