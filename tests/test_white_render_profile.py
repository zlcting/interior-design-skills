import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'skills/interior-orchestrator/scripts'))
from white_render_profile import build_config,load_profile
from style_library import get_style
from style_plan import resolve_plan
MODEL=json.loads((ROOT/'projects/STYLE-LAB-096/model/project.json').read_text())
class WhiteRenderProfileTests(unittest.TestCase):
 def config(self,model=None):
  model=model or copy.deepcopy(MODEL);return build_config(model,resolve_plan(model,get_style('white-minimal')))
 def test_existing_home3d_lighting_calibration_is_retained(self):
  c=self.config();self.assertEqual(c['renderer']['exposure'],.85);self.assertEqual(c['studio']['keyIntensity'],1.5);self.assertEqual(c['studio']['fillIntensity'],.7);self.assertEqual(c['shadows']['mapSize'],2048);self.assertEqual(c['contactAO']['samples'],12)
 def test_translated_negative_project_moves_rig_and_cameras_together(self):
  model=copy.deepcopy(MODEL);a=self.config(model);dx,dy=18000,-24000
  for r in model['rooms']:r['rect'][0]+=dx;r['rect'][1]+=dy
  for f in model['furniture']:f['rect'][0]+=dx;f['rect'][1]+=dy
  b=self.config(model)
  for key in ['keyPosition','fillPosition','target']:
   self.assertAlmostEqual(b['studio'][key][0]-a['studio'][key][0],18);self.assertAlmostEqual(b['studio'][key][2]-a['studio'][key][2],24)
  for key in a['views']:
   self.assertAlmostEqual(b['views'][key]['target'][0]-a['views'][key]['target'][0],18);self.assertEqual(a['views'][key]['width'],b['views'][key]['width'])
 def test_unknown_profile_and_invalid_focus_are_rejected(self):
  m=copy.deepcopy(MODEL);m['visualization']['white_render_profile']='missing';p=resolve_plan(m,get_style('white-minimal'))
  with self.assertRaises(ValueError):build_config(m,p)
  m['visualization'].pop('white_render_profile')
  with self.assertRaises(ValueError):build_config(m,p,'MISSING')
 def test_nonwhite_does_not_silently_receive_white_profile(self):
  m=copy.deepcopy(MODEL)
  with self.assertRaises(ValueError):build_config(m,resolve_plan(m,get_style('japanese-natural')))
 def test_source_geometry_cameras_and_presets_are_not_mutated(self):
  m=copy.deepcopy(MODEL);before=copy.deepcopy(m);profile=load_profile();c=self.config(m);c['studio']['keyIntensity']=99
  self.assertEqual(m,before);self.assertEqual(load_profile(),profile);self.assertEqual(self.config()['studio']['keyIntensity'],1.5)
 def test_basic_choice_keeps_geometry_choice_and_does_not_invent_lamps(self):
  m=copy.deepcopy(MODEL);m['visualization']['furniture_detail']='basic';p=resolve_plan(m,get_style('white-minimal'));c=build_config(m,p)
  self.assertEqual(c['fixtures'],[]);self.assertEqual(c['furnitureDetail'],'basic');self.assertNotIn('refined_objects',p)
 def test_no_sofa_uses_overview_without_guessing_a_room(self):
  m=copy.deepcopy(MODEL);p=resolve_plan(m,get_style('white-minimal'));p['furniture']=[f for f in p['furniture'] if f['furniture_type']!='sofa'];c=build_config(m,p)
  self.assertEqual(c['defaultView'],'overview');self.assertIsNone(c['focusRoomId']);self.assertNotIn('focus',c['views'])
 def test_incompatible_units_are_rejected(self):
  m=copy.deepcopy(MODEL);m['units']='m'
  with self.assertRaises(ValueError):self.config(m)
 def test_configuration_never_claims_visual_approval(self):
  c=self.config();self.assertFalse(c['review']['configurationMatchIsVisualPass']);self.assertEqual(c['review']['visualApproval'],'human_review_required')
if __name__=='__main__':unittest.main()
