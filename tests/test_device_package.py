"""Real SDK/device archive behavior; no Blender or live service required."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile
from test_home3d import ROOT, NODE, SCRIPT, glb, project
from test_home3d_rendering import white_config, white_document

SKILL=ROOT/'skills/interior-device-package'
TOOL=SKILL/'scripts/device_package.mjs'
SDK=SCRIPT/'vendor/home3d-package.cjs'

@unittest.skipUnless(NODE,'Node 20+ required')
class DevicePackageTests(unittest.TestCase):
    def fixture(self,root):
        asset=root/'source';asset.mkdir();(asset/'assets').mkdir()
        raw=glb();(asset/'assets/model.glb').write_bytes(raw)
        self.write(asset/'model.json',{'schema':'home3d.model-definition.v1','kind':'model','file':'assets/model.glb','defaultSize':{'width':1.5,'height':1,'depth':.5},'pivot':'bottom-center','normalization':{'translation':[-1.5,0,1],'scale':[1,1,1]},'targets':[{'kind':'node','name':'FURN_A'}]})
        contract={'schema':'home3d.device-contract.v1','id':'test.fixture','version':'1.0.0','name':'Test device','scopes':[{'capabilities':[{'key':'power','behavior':'property','access':'read-write','value':{'type':'boolean'},'initialValue':False}]}],
          'presentation':{'controls':[{'id':'power','label':'Power','widget':'toggle','source':{'capabilityKey':'power'}}],'effects':[{'id':'visibility','source':{'capabilityKey':'power'},'slot':'body','channel':'node.visible','mapping':{'kind':'cases','cases':[{'value':False,'output':False},{'value':True,'output':True}]}}]},'simulation':{'behavior':'state-transition.v1','transitions':[],'commands':[]}}
        self.write(asset/'device-contract.json',contract)
        self.write(asset/'bindings.template.json',{'schema':'home3d.presentation-template.v1','bindings':[{'slot':'body','target':{'kind':'node','name':'FURN_A'}}]})
        self.write(asset/'rig.json',{'schema':'home3d.device-rig.v1','coordinateSpace':'normalized-model','front':[0,0,-1],'mounting':{'allowedSurfaces':['floor'],'attachmentPoint':[0,0,0]}})
        self.write(asset/'state-policy.json',{'schema':'home3d.device-state-policy.v1','mode':'simulation'})
        self.write(asset/'effects.json',{'schema':'home3d.device-effects.v1','effects':[]})
        self.write(asset/'sources.json',{'schema':'home3d.device-sources.v1','requirements':{'scope':'automated fixture'},'product':{'status':'test geometry, not a product'},'capabilityMappings':[],'tools':{'test':'1'}})
        _,image,_=white_document(white_config(project(),raw));(asset/'preview.png').write_bytes(image)
        (asset/'README.md').write_text('Test geometry only; not a manufactured product.\n')
        self.write(asset/'device-asset.json',{'schema':'home3d.device-asset.v1','specVersion':'1.0.0-draft','id':'test-device','version':'1.0.0','name':'Test device','deviceType':'fixture','geometryKind':'fixed',
          'requirementRef':{'scopeStatus':'experimental','reason':'SDK regression fixture; not part of first batch'},'entries':{'model':'model.json','contract':'device-contract.json','bindings':'bindings.template.json','rig':'rig.json','statePolicy':'state-policy.json','effects':'effects.json','sources':'sources.json','preview':'preview.png'},
          'target':{'packageVersion':4,'sdkVersion':'0.3.0','profile':'core-v4','requiredCapabilities':['scene.structure.v1','model.glb.v1','model.normalization.v1','device.contracts.v1','device.presentation.v1','device.simulation.v1']},'requiredFeatures':[{'id':'device.static','version':1}],'files':[]})
        self.run_tool('seal',asset)
        return asset

    def write(self,file,data):file.write_text(json.dumps(data))
    def run_tool(self,command,file,ok=True):
        p=subprocess.run([NODE,str(TOOL),command,str(file)],capture_output=True,text=True)
        self.assertEqual(p.returncode==0,ok,p.stdout+p.stderr)
        return json.loads(p.stdout)if ok else p.stderr

    def job(self,root,out='out',**extra):
        job={'assetDir':'source','outputDir':out,'placements':[{'instanceId':i,'floorId':'floor-test','roomId':'room-test','placement':'floor','position':[x,0,0]}for i,x in [('a',-1),('b',1)]],**extra}
        file=root/(out+'.json');self.write(file,job);return file

    def test_build_is_deterministic_roundtrips_and_isolates_states(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);asset=self.fixture(root)
            scenario=[{'name':'switch independence','steps':[{'action':{'deviceId':'device-a','capabilityKey':'power','operation':'write','value':True}},{'expect':{'ref':{'deviceId':'device-a','capabilityKey':'power'},'value':True}},{'expect':{'ref':{'deviceId':'device-b','capabilityKey':'power'},'value':False}}]}]
            report=self.run_tool('build',self.job(root,scenarios=scenario))
            self.assertEqual(report['stateIsolation'],'passed');self.assertEqual(report['editorReview'],'not-reviewed')
            with zipfile.ZipFile(root/'out/test-device-1.0.0.device.zip')as z:z.extractall(root/'unpacked')
            self.run_tool('build',self.job(root,'again',assetDir='unpacked',scenarios=scenario))
            for name in ['validation.home3d','test-device-1.0.0.device.zip']:
                self.assertEqual((root/'out'/name).read_bytes(),(root/'again'/name).read_bytes())
            with zipfile.ZipFile(root/'out/test-device-1.0.0.device.zip')as z:
                self.assertIn('device-asset.json',z.namelist())
                self.assertEqual(set(z.namelist()),{str(p.relative_to(asset))for p in asset.rglob('*')if p.is_file()})
            original=(root/'out/validation.home3d').read_bytes()
            self.run_tool('build',self.job(root),False)
            self.assertEqual(original,(root/'out/validation.home3d').read_bytes())

    def test_merge_preserves_rendering_experience_and_original_payloads(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);self.fixture(root);self.run_tool('build',self.job(root,'first'))
            rendering,image,_=white_document(white_config(project(),glb()))
            (root/'environment.png').write_bytes(image);self.write(root/'rendering.json',rendering)
            code="""const s=require(process.argv[1]),f=require('fs');(async()=>{const p=await s.readPackage(f.readFileSync(process.argv[2]));const entries=Object.fromEntries(Object.entries(p.entries).filter(([k])=>!['package.json',...Object.values(p.manifest.entries)].includes(k)));const r=JSON.parse(f.readFileSync(process.argv[3]));entries[r.environment.file]=f.readFileSync(process.argv[4]);const experience={schema:'home3d.device-program.v1',projectDigest:s.digest(s.encode(p.project)),initialState:[],scenes:[],rules:[]};const b=await s.writePackage({version:4,kind:'project',name:'base',project:p.project,resources:p.resources,devices:p.devices,presentation:p.presentation,entries,rendering:s.bindRenderingToProject(r,p.project),experience,requiredCapabilities:[...p.manifest.requiredCapabilities,...s.RENDERING_CAPABILITIES,'experience.references.v1']});f.writeFileSync(process.argv[5],b)})().catch(e=>{console.error(e);process.exit(1)})"""
            cp=subprocess.run([NODE,'-e',code,str(SDK),str(root/'first/validation.home3d'),str(root/'rendering.json'),str(root/'environment.png'),str(root/'base.home3d')],capture_output=True,text=True)
            self.assertEqual(cp.returncode,0,cp.stderr)
            original=(root/'base.home3d').read_bytes()
            places=[{'instanceId':'new-'+i,'floorId':'floor-test','roomId':'room-test','placement':'floor','position':[x,0,1]}for i,x in [('a',-1),('b',1)]]
            report=self.run_tool('build',self.job(root,'merged',basePackage='base.home3d',placements=places))
            self.assertEqual(report['sourcePreservation'],'passed');self.assertEqual((root/'base.home3d').read_bytes(),original)
            with zipfile.ZipFile(root/'base.home3d')as a,zipfile.ZipFile(root/'merged/validation.home3d')as b:
                for name in a.namelist():
                    if name.startswith(('blobs/','resources/','contracts/')):self.assertEqual(a.read(name),b.read(name))
                old,new=json.loads(a.read('rendering.json')),json.loads(b.read('rendering.json'))
                self.assertEqual(old['lights'],new['lights']);self.assertNotEqual(old['projectDigest'],new['projectDigest'])
                self.assertEqual(json.loads(b.read('experience.json'))['projectDigest'],new['projectDigest'])

    def test_curtain_intermediate_position_stop_and_second_instance(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);asset=self.fixture(root)
            contract=json.loads((asset/'device-contract.json').read_text())
            contract['scopes']=[{'capabilities':[{'key':'position','behavior':'property','access':'read-write','value':{'type':'number','minimum':0,'maximum':100,'unit':'%'},'initialValue':0},{'key':'stop','behavior':'command','access':'write','value':{'type':'null'}}]}]
            contract['presentation']={'controls':[{'id':'position','label':'Position','widget':'slider','source':{'capabilityKey':'position'}},{'id':'stop','label':'Stop','widget':'button','source':{'capabilityKey':'stop'}}],'effects':[{'id':'gather','source':{'capabilityKey':'position'},'slot':'body','channel':'node.scale.x','mapping':{'kind':'linear','input':[0,100],'output':[1,.14]}}]}
            contract['simulation']={'behavior':'state-transition.v1','transitions':[{'target':{'capabilityKey':'position'},'durationMs':2400}],'commands':[{'source':{'capabilityKey':'stop'},'effects':[{'operation':'stop','target':{'capabilityKey':'position'}}]}]}
            self.write(asset/'device-contract.json',contract);self.run_tool('seal',asset)
            scenarios=[{'name':'half open and stop','steps':[{'action':{'deviceId':'device-a','capabilityKey':'position','operation':'write','value':100}},{'advanceMs':1200},{'expect':{'ref':{'deviceId':'device-a','capabilityKey':'position'},'value':50}},{'action':{'deviceId':'device-a','capabilityKey':'stop','operation':'execute','value':None}},{'advanceMs':5000},{'expect':{'ref':{'deviceId':'device-a','capabilityKey':'position'},'value':50}},{'expect':{'ref':{'deviceId':'device-b','capabilityKey':'position'},'value':0}}]}]
            report=self.run_tool('build',self.job(root,scenarios=scenarios));self.assertEqual(report['scenarios'][0]['status'],'passed')

    def test_corruption_unlisted_files_symlinks_and_bad_paths_are_rejected(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);asset=self.fixture(root)
            (asset/'README.md').write_text('tampered');self.run_tool('check',asset,False)
            self.run_tool('seal',asset);(asset/'extra.txt').write_text('unlisted');self.run_tool('check',asset,False)
            (asset/'extra.txt').unlink();(asset/'link').symlink_to(root/'outside');self.run_tool('seal',asset,False);(asset/'link').unlink()
            meta=json.loads((asset/'device-asset.json').read_text());meta['entries']['model']='../outside.json';self.write(asset/'device-asset.json',meta);self.run_tool('check',asset,False)

    def test_unsupported_modes_features_and_geometry_block_without_output(self):
        for kind in ['real','airflow','procedural']:
            with self.subTest(kind=kind),tempfile.TemporaryDirectory()as tmp:
                root=Path(tmp);asset=self.fixture(root)
                file=asset/('state-policy.json'if kind=='real'else'device-asset.json');data=json.loads(file.read_text())
                if kind=='real':data['mode']='real'
                elif kind=='airflow':data['requiredFeatures']=[{'id':'airflow','version':1}]
                else:data['geometryKind']='procedural'
                self.write(file,data);self.run_tool('seal',asset)
                self.assertIn('BLOCKED',self.run_tool('build',self.job(root),False));self.assertFalse((root/'out').exists())

    def test_sdk_rejects_broken_targets_and_forged_contract_values(self):
        for kind in ['target','value']:
            with self.subTest(kind=kind),tempfile.TemporaryDirectory()as tmp:
                root=Path(tmp);asset=self.fixture(root)
                file=asset/('bindings.template.json'if kind=='target'else'device-contract.json');data=json.loads(file.read_text())
                if kind=='target':data['bindings'][0]['target']['name']='MISSING'
                else:data['scopes'][0]['capabilities'][0]['initialValue']='not-a-boolean'
                self.write(file,data);self.run_tool('seal',asset);self.run_tool('build',self.job(root),False);self.assertFalse((root/'out').exists())

    def test_missing_consumer_capability_and_failed_scenario_do_not_publish(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);self.fixture(root)
            self.run_tool('build',self.job(root,consumerCapabilities=['scene.structure.v1','model.glb.v1']),False)
            self.assertFalse((root/'out').exists())
            bad=[{'name':'wrong expected value','steps':[{'expect':{'ref':{'deviceId':'device-a','capabilityKey':'power'},'value':True}}]}]
            self.run_tool('build',self.job(root,'bad',scenarios=bad),False);self.assertFalse((root/'bad').exists())

    def test_output_inside_source_is_rejected_even_through_parent_symlink(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);asset=self.fixture(root);(root/'alias').symlink_to(asset,target_is_directory=True)
            self.run_tool('build',self.job(root,'alias/delivery'),False);self.assertFalse((asset/'delivery').exists())
