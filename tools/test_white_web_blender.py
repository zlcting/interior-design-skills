"""Integration regression with synthetic data: geometry, materials and AO regeneration."""
import argparse,json,subprocess,sys,tempfile,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SCRIPTS=ROOT/'skills/interior-orchestrator/scripts';sys.path.insert(0,str(SCRIPTS))
from white_render_profile import build_config

def content(path):
 raw=path.read_bytes();size=struct.unpack_from('<I',raw,12)[0];return json.loads(raw[20:20+size])
def run(blender,script,args,log):
 with log.open('w') as output:subprocess.run([blender,'--background','--python',str(script),'--',*map(str,args)],stdout=output,stderr=subprocess.STDOUT,check=True)
def main(blender):
 with tempfile.TemporaryDirectory(prefix='white-web-regression-') as folder:
  d=Path(folder);source=d/'source.glb';fixture=d/'fixture.py'
  fixture.write_text('''import bpy,sys
bpy.ops.wm.read_factory_settings(use_empty=True)
def material(name,color,transmission=0,emission=0):
 m=bpy.data.materials.new(name);m.use_nodes=True;b=m.node_tree.nodes.get('Principled BSDF');b.inputs['Base Color'].default_value=(*color,1);b.inputs['Roughness'].default_value=.65;b.inputs['Transmission Weight'].default_value=transmission;b.inputs['Emission Color'].default_value=(*color,1);b.inputs['Emission Strength'].default_value=emission;return m
white=material('white',(.8,.82,.85));glass=material('glass',(.7,.8,.9),1);glow=material('glow',(1,.8,.4),0,2)
for name,loc,scale,mat in [('seat',(2,3,.208),(1.4,.8,.4),white),('floor',(2,3,-.02),(4,4,.04),white),('glass',(3,3,.6),(.008,1,1.2),glass),('emitter',(2,2,1),(.2,.2,.02),glow)]:
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.scale=scale;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(mat)
 if name=='seat':
  b=o.modifiers.new('bevel','BEVEL');b.width=.06;b.segments=3
bpy.ops.export_scene.gltf(filepath=sys.argv[-1],export_format='GLB',export_apply=True,export_extras=True,export_cameras=False,export_lights=False)
''')
  run(blender,fixture,[source],d/'fixture.log')
  config=build_config({'revision':'fixture','rooms':[{'id':'R1','name':'room','rect':[0,0,4000,4000]}]}, {'style':{'id':'white-minimal'},'furniture':[],'accessories':[]});(d/'config.json').write_text(json.dumps(config))
  current=source;reports=[];outputs=[]
  for index in [1,2]:
   target=d/f'pass-{index}.glb';report=d/f'pass-{index}.json'
   run(blender,SCRIPTS/'bake_white_web.py',['--input',current,'--output',target,'--config',d/'config.json','--report',report],d/f'pass-{index}.log')
   result=json.loads(report.read_text());assert result['passed'] and result['source_geometry_preserved'];reports.append(result);outputs.append(content(target));current=target
  src=content(source)
  def factors(j):return {m['name']:{k:v for k,v in m.items() if k!='name'} for m in j['materials']}
  assert factors(src)==factors(outputs[0])==factors(outputs[1]),'flat material/IOR/transmission/emission changed'
  assert all('COLOR_0' in p['attributes'] for j in outputs for m in j['meshes'] for p in m['primitives'])
  lows=[min(item['min'] for item in r['ao_objects']) for r in reports]
  assert min(lows)<.99,'no contact AO was produced';assert lows[1]>=lows[0]-.03,'AO accumulated across regeneration'
  assert all(.61<=item['min']<=item['max']<=1.00001 for r in reports for item in r['ao_objects'])
  unsupported=content(source);unsupported['materials'][0].setdefault('extensions',{})['KHR_materials_clearcoat']={'clearcoatFactor':1};raw=source.read_bytes();size=struct.unpack_from('<I',raw,12)[0];encoded=json.dumps(unsupported).encode();encoded+=b' '*((-len(encoded))%4);body=struct.pack('<II',len(encoded),0x4e4f534a)+encoded+raw[20+size:];bad=d/'unsupported.glb';bad.write_bytes(struct.pack('<4sII',b'glTF',2,len(body)+12)+body)
  with (d/'unsupported.log').open('w') as log:result=subprocess.run([blender,'--background','--python',str(SCRIPTS/'bake_white_web.py'),'--','--input',str(bad),'--output',str(d/'bad-output.glb'),'--config',str(d/'config.json'),'--report',str(d/'bad-report.json')],stdout=log,stderr=subprocess.STDOUT)
  assert result.returncode!=0 or 'ValueError' in (d/'unsupported.log').read_text();assert not (d/'bad-output.glb').exists() and not (d/'bad-report.json').exists()
  return {'unsupported_material_extension_rejected':True,'passed':True,'geometry_roundtrip_passes':2,'material_factors_transmission_emission_preserved':True,'contact_ao_present':True,'repeated_generation_no_cumulative_darkening':True,'ao_min_values':lows}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--blender',required=True);a=p.parse_args();print(json.dumps(main(a.blender),indent=2))
