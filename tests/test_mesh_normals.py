"""Behavioural tests: bad generated normals rejected, repair preserves other GLB data."""
import copy
import json
import math
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'skills/interior-orchestrator/scripts'))
from mesh_normals import POLICY, KEY, accessor, pack, process, unpack
from illustration_meshes import detailed_mesh


def fixture(marked=True, indexed=True):
    positions = struct.pack('<12f', 0,0,0, 1,0,0, 1,1,0, 0,1,0)
    normals = struct.pack('<12f', *([0,1,0]*4))  # Unit, but perpendicular to the true surface normal.
    colours = struct.pack('<16f', *([.7,.7,.7,1]*4))
    indices = struct.pack('<6H', 0,1,2, 0,2,3)
    binary = positions+normals+colours+indices
    g = {'asset':{'version':'2.0'}, 'buffers':[{'byteLength':len(binary)}],
         'bufferViews':[{'buffer':0,'byteOffset':0,'byteLength':48}, {'buffer':0,'byteOffset':48,'byteLength':48},
                        {'buffer':0,'byteOffset':96,'byteLength':64}, {'buffer':0,'byteOffset':160,'byteLength':12}],
         'accessors':[{'bufferView':0,'componentType':5126,'count':4,'type':'VEC3'},
                      {'bufferView':1,'componentType':5126,'count':4,'type':'VEC3'},
                      {'bufferView':2,'componentType':5126,'count':4,'type':'VEC4'},
                      {'bufferView':3,'componentType':5123,'count':6,'type':'SCALAR'}],
         'meshes':[{'primitives':[{'attributes':{'POSITION':0,'NORMAL':1,'COLOR_0':2},'indices':3,'material':0}]}],
         'nodes':[{'mesh':0, 'translation':[2,3,4], 'extras':{KEY:POLICY} if marked else {}}],
         'materials':[{'name':'keep','doubleSided':True,'pbrMetallicRoughness':{'roughnessFactor':.65}}]}
    if not indexed:
        g['accessors'][0]['count']=g['accessors'][1]['count']=3
        del g['meshes'][0]['primitives'][0]['indices']
    return pack(g,binary)


class MeshNormalsTests(unittest.TestCase):
    def test_unit_but_incorrect_generated_normals_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'differ from final triangles'): process(fixture())

    def test_repair_only_changes_normals_and_is_idempotent(self):
        original=fixture(); before,oldbin=unpack(original)
        fixed,report=process(original,repair=True);after,newbin=unpack(fixed)
        self.assertEqual(newbin[:len(oldbin)],oldbin)
        self.assertEqual(before['materials'],after['materials']);self.assertEqual(before['nodes'],after['nodes'])
        old=before['meshes'][0]['primitives'][0];new=after['meshes'][0]['primitives'][0]
        self.assertEqual(old['indices'],new['indices'])
        self.assertEqual(old['attributes']['POSITION'],new['attributes']['POSITION'])
        self.assertEqual(old['attributes']['COLOR_0'],new['attributes']['COLOR_0'])
        self.assertTrue(all(abs(n[2]-1)<1e-7 for n in accessor(after,newbin,new['attributes']['NORMAL'],True)))
        self.assertEqual(report['regeneratedPrimitives'],1);self.assertTrue(process(fixed)[1]['passed'])
        self.assertEqual(process(fixed,repair=True)[0],fixed)

    def test_unmarked_authored_normals_are_preserved(self):
        raw=fixture(False);fixed,report=process(raw,repair=True)
        self.assertEqual(fixed,raw);self.assertEqual(report['regeneratedPrimitives'],0)
        forced,_=process(raw,repair=True,all_static=True)
        self.assertNotEqual(forced,raw);self.assertTrue(process(forced)[1]['passed'])

    def test_non_indexed_static_triangles_can_be_repaired(self):
        fixed,_=process(fixture(indexed=False),repair=True)
        self.assertTrue(process(fixed)[1]['passed'])

    def test_non_finite_normals_fail_validation_and_can_be_repaired_explicitly(self):
        g,b=unpack(fixture(False));struct.pack_into('<f',b,48,float('nan'));raw=pack(g,b)
        with self.assertRaisesRegex(ValueError,'Non-finite'):process(raw)
        fixed,_=process(raw,repair=True,all_static=True);self.assertTrue(process(fixed)[1]['passed'])

    def test_wrong_count_and_unknown_policy_are_rejected(self):
        g,b=unpack(fixture(False));g['accessors'][1]['count']=3
        with self.assertRaisesRegex(ValueError,'count differs'):process(pack(g,b))
        g,b=unpack(fixture());g['nodes'][0]['extras'][KEY]='future-unimplemented'
        with self.assertRaisesRegex(ValueError,'Unsupported'):process(pack(g,b),repair=True)

    def test_skinned_and_morphing_assets_are_not_silently_regenerated(self):
        for morph in [False,True]:
            g,b=unpack(fixture())
            if morph:g['meshes'][0]['primitives'][0]['targets']=[{'POSITION':0}]
            else:g['nodes'][0]['skin']=0
            with self.assertRaisesRegex(ValueError,'static meshes'):process(pack(g,b),repair=True)

    def test_cushion_poles_are_shared_and_surface_is_closed_without_sliver_faces(self):
        p={'name':'seat','shape':'cushion','rect':[0,0,700,600],'z':0,'height':200,'lean':.1}
        vertices,faces=detailed_mesh(p)
        self.assertTrue(all(len(f)==3 for f in faces));edges={}
        for tri in faces:
            a,b,c=[vertices[i] for i in tri];u=[b[k]-a[k] for k in range(3)];v=[c[k]-a[k] for k in range(3)]
            area=math.sqrt(sum(x*x for x in (u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])))
            self.assertGreater(area,1e-7)
            for i,j in zip(tri,(tri[1],tri[2],tri[0])):edges.setdefault(tuple(sorted((i,j))),[]).append((i,j))
        self.assertTrue(all(len(e)==2 and e[0]==tuple(reversed(e[1])) for e in edges.values()))
        self.assertEqual(sum(abs(p[2])<1e-10 for p in vertices),1)
        self.assertEqual(sum(abs(p[2]-200)<1e-10 for p in vertices),1)


if __name__=='__main__':unittest.main()
