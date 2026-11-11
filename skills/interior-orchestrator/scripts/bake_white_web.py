"""Run in Blender: preserve flat-colour white geometry, bake contact AO for realtime GLB."""
import bpy,sys,json,math,hashlib,struct,argparse
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
from exchange_validation import signature,verify_roundtrip
arg=argparse.ArgumentParser();arg.add_argument('--input',type=Path,required=True);arg.add_argument('--output',type=Path,required=True);arg.add_argument('--config',type=Path,required=True);arg.add_argument('--report',type=Path,required=True)
a=arg.parse_args(sys.argv[sys.argv.index('--')+1:]);config=json.loads(a.config.read_text());ao=config['contactAO']
raw=a.input.read_bytes();n=struct.unpack_from('<I',raw,12)[0];source=json.loads(raw[20:20+n])
if source.get('textures'):raise ValueError('当前白模烘焙只验证了无纹理的单色PBR材质；不要静默丢弃纹理')
materials={}
for item in source.get('materials',[]):
 name=item.get('name')
 if not name or name in materials:raise ValueError('白模材质需要稳定且唯一的名称')
 if item.get('alphaMode','OPAQUE')!='OPAQUE':raise ValueError('当前白模烘焙未验证 alphaMode 材质；透射玻璃使用 transmission')
 unsupported=set(item.get('extensions',{}))-{'KHR_materials_transmission','KHR_materials_ior','KHR_materials_emissive_strength'}
 if unsupported:raise ValueError('当前白模烘焙未验证材质扩展：'+', '.join(sorted(unsupported)))
 materials[name]=item
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(a.input))
objects=[o for o in bpy.context.scene.objects if o.type=='MESH'];bpy.context.view_layer.update();graph=bpy.context.evaluated_depsgraph_get();expected={o.name:signature(o,graph) for o in objects}
# Replace imported material graphs with the original flat glTF factors. This also
# removes any prior vertex-AO multiplier, so regenerating never double-bakes AO.
original_materials={m:m.name for o in objects for m in o.data.materials};converted={}
for old,name in original_materials.items():
 if name not in materials:raise ValueError('无法追踪原始白模材质：'+name)
 definition=materials[name];pbr=definition.get('pbrMetallicRoughness',{});ext=definition.get('extensions',{});old.name='source '+name
 fresh=bpy.data.materials.new(name);fresh.use_nodes=True;b=fresh.node_tree.nodes.get('Principled BSDF')
 color=pbr.get('baseColorFactor',[1,1,1,1]);fresh.diffuse_color=tuple(color);b.inputs['Base Color'].default_value=color;b.inputs['Roughness'].default_value=pbr.get('roughnessFactor',1);b.inputs['Metallic'].default_value=pbr.get('metallicFactor',1)
 b.inputs['Transmission Weight'].default_value=ext.get('KHR_materials_transmission',{}).get('transmissionFactor',0);b.inputs['IOR'].default_value=ext.get('KHR_materials_ior',{}).get('ior',1.5)
 b.inputs['Emission Color'].default_value=(*definition.get('emissiveFactor',[0,0,0]),1);b.inputs['Emission Strength'].default_value=ext.get('KHR_materials_emissive_strength',{}).get('emissiveStrength',1)
 fresh.use_backface_culling=not definition.get('doubleSided',False);converted[old]=fresh
vertices=[];faces=[];glass={}
for obj in objects:
 mesh=bpy.data.meshes.new_from_object(obj.evaluated_get(graph),preserve_all_data_layers=True,depsgraph=graph);obj.data=mesh;obj.modifiers.clear()
 for i,old in enumerate(list(mesh.materials)):mesh.materials[i]=converted[old]
 glass[obj.name]=any(m.node_tree.nodes.get('Principled BSDF').inputs['Transmission Weight'].default_value>.5 for m in mesh.materials)
 if glass[obj.name]:continue
 start=len(vertices);vertices.extend(obj.matrix_world@v.co for v in mesh.vertices);mesh.calc_loop_triangles();faces.extend(tuple(start+i for i in tri.vertices) for tri in mesh.loop_triangles)
bvh=BVHTree.FromPolygons(vertices,faces,all_triangles=True) if faces else None;stats=[]
for obj in objects:
 mesh=obj.data;normal_matrix=obj.matrix_world.to_3x3().inverted().transposed();values=[]
 for vertex in mesh.vertices:
  normal=(normal_matrix@vertex.normal).normalized();point=obj.matrix_world@vertex.co+normal*.0015;axis=Vector((0,0,1)) if abs(normal.z)<.9 else Vector((1,0,0));u=normal.cross(axis).normalized();v=normal.cross(u).normalized();occlusion=0
  if bvh and not glass[obj.name]:
   for i in range(ao['samples']):
    z=math.sqrt((i+.5)/ao['samples']);radius=math.sqrt(1-z*z);angle=i*2.399963;direction=normal*z+u*(radius*math.cos(angle))+v*(radius*math.sin(angle));hit,_,_,distance=bvh.ray_cast(point,direction,ao['distanceM'])
    if hit is not None:occlusion+=max(0,1-distance/ao['distanceM'])
  values.append(1-ao['strength']*occlusion/ao['samples'])
 for attribute in list(mesh.color_attributes):mesh.color_attributes.remove(attribute)
 colors=mesh.color_attributes.new(name='WhiteContactAO',type='FLOAT_COLOR',domain='CORNER');mesh.color_attributes.active_color_index=0
 for loop in mesh.loops:colors.data[loop.index].color=(values[loop.vertex_index],)*3+(1,)
 obj['exchange_source_id']=obj.name;stats.append({'id':obj.name,'vertices':len(values),'min':min(values),'max':max(values)})
bpy.ops.object.select_all(action='DESELECT')
for obj in objects:obj.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(a.output),use_selection=True,export_format='GLB',export_apply=True,export_extras=True,export_vertex_color='NAME',export_vertex_color_name='WhiteContactAO',export_cameras=False,export_lights=False)
report=verify_roundtrip(a.output,expected);report.update(apply_modifiers=True,source_geometry_preserved=True,input_glb_sha256=hashlib.sha256(raw).hexdigest(),profile_id=config['profileId'],profile_sha256=config['profileSha256'],ao=ao,ao_objects=stats,previous_vertex_colors='replaced from original flat material factors; no cumulative AO',blender_version=bpy.app.version_string)
a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('WHITE_CONTACT_AO_VERIFIED',len(objects),flush=True)
