#!/usr/bin/env node
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';

const HERE=path.dirname(fileURLToPath(import.meta.url));
const sha=b=>'sha256:'+createHash('sha256').update(b).digest('hex');
const read=async p=>JSON.parse(await fs.readFile(p,'utf8'));
const NS='org.houzzkit.interior-device';
const CORE=['scene.structure.v1','model.glb.v1','model.normalization.v1','device.contracts.v1','device.presentation.v1','device.simulation.v1'];
const CHANNELS=new Set(['node.visible','node.position.x','node.position.y','node.position.z','node.scale.x','node.scale.y','node.scale.z','material.opacity','material.emissiveIntensity','light.intensity']);
const FEATURES=new Set(['device.static','light.power','light.brightness','curtain.position','curtain.stop']);

export async function loadSdk(directory){
  assert(Number(process.versions.node.split('.')[0])>=20,'Node 20+ required');
  const dir=directory?path.resolve(directory):path.resolve(HERE,'../../interior-home3d/scripts/vendor');
  const manifest=await read(path.join(dir,'manifest.json')),file=path.join(dir,'home3d-package.cjs');
  assert.equal(manifest.version,'0.3.0','SDK version mismatch');
  assert.equal(sha(await fs.readFile(file)),'sha256:'+manifest.bundleSha256,'SDK artifact digest mismatch');
  const sdk=createRequire(import.meta.url)(file);assert.equal(sdk.VERSION,manifest.version);
  return{sdk,manifest};
}

function relative(name){
  assert(typeof name==='string'&&!path.isAbsolute(name)&&!name.includes('\\')&&name.split('/').every(p=>p&&p!=='.'&&p!=='..'),'Unsafe asset path: '+name);
  return name;
}
async function inventory(directory){
  const files=new Map();
  async function walk(dir,prefix=''){
    for(const row of (await fs.readdir(dir,{withFileTypes:true})).sort((a,b)=>a.name.localeCompare(b.name,'en'))){
      const name=relative(prefix+row.name),file=path.join(dir,row.name);
      assert(!row.isSymbolicLink(),'Symlink not allowed: '+name);
      if(row.isDirectory())await walk(file,name+'/');
      else{assert(row.isFile(),'Not a regular asset file: '+name);files.set(name,await fs.readFile(file));}
    }
  }
  assert(!(await fs.lstat(directory)).isSymbolicLink(),'Asset root cannot be a symlink');
  await walk(directory);return files;
}
export async function seal(directory){
  const files=await inventory(directory),meta=JSON.parse(files.get('device-asset.json'));
  assert.equal(meta.schema,'home3d.device-asset.v1','Migrate demo format explicitly before sealing');
  meta.files=[...files].filter(([p])=>p!=='device-asset.json').sort(([a],[b])=>a<b?-1:a>b?1:0)
    .map(([p,b])=>({path:p,byteSize:b.length,digest:sha(b)}));
  await fs.writeFile(path.join(directory,'device-asset.json'),JSON.stringify(meta,null,2)+'\n');
  return{status:'sealed-not-validated',files:meta.files.length};
}
export async function loadAsset(directory){
  const files=await inventory(directory),raw=files.get('device-asset.json');assert(raw,'Missing device-asset.json');
  const meta=JSON.parse(raw);assert.equal(meta.schema,'home3d.device-asset.v1');assert.equal(meta.specVersion,'1.0.0-draft');
  assert(/^[A-Za-z][A-Za-z0-9_.:-]{0,127}$/.test(meta.id),'Invalid asset id');assert(/^\d+\.\d+\.\d+$/.test(meta.version),'Invalid version');
  assert(typeof meta.name==='string'&&meta.name.trim()&&typeof meta.deviceType==='string'&&meta.deviceType.trim(),'Missing name/deviceType');
  assert.equal(meta.geometryKind,'fixed','BLOCKED: procedural/path generator not implemented by this tool');
  assert.equal(meta.target?.packageVersion,4);assert.equal(meta.target?.sdkVersion,'0.3.0');assert.equal(meta.target?.profile,'core-v4');
  assert(Array.isArray(meta.target.requiredCapabilities));assert(Array.isArray(meta.requiredFeatures));
  for(const f of meta.requiredFeatures)assert(FEATURES.has(f.id)&&f.version===1,'BLOCKED: unsupported required feature '+f.id);
  const scope=await read(path.join(HERE,'../references/scope.json')),ref=meta.requirementRef;
  assert(ref&&typeof ref==='object','Missing requirementRef');
  if(ref.scopeStatus==='experimental')assert(typeof ref.reason==='string'&&ref.reason.trim(),'Experimental scope needs reason');
  else assert(scope.forms.some(v=>v.modelTypeId===ref.modelTypeId&&v.templateKey===ref.templateKey&&v.geometryKind===meta.geometryKind),'Shape is outside active scope');
  const declared=new Set();assert(Array.isArray(meta.files));
  for(const row of meta.files){
    relative(row.path);assert(row.path!=='device-asset.json'&&!declared.has(row.path),'Duplicate or self-referencing inventory');
    const bytes=files.get(row.path);assert(bytes,'Missing declared file: '+row.path);
    assert(Number.isSafeInteger(row.byteSize)&&row.byteSize>=0);assert.equal(row.byteSize,bytes.length,'Size mismatch: '+row.path);
    assert.equal(row.digest,sha(bytes),'Digest mismatch: '+row.path);declared.add(row.path);
  }
  assert.deepEqual([...declared].sort(),[...files.keys()].filter(p=>p!=='device-asset.json').sort(),'Unlisted asset files');
  const json=name=>{relative(name);assert(declared.has(name),'Undeclared entry: '+name);return JSON.parse(files.get(name));};
  for(const key of ['model','contract','bindings','rig','statePolicy','effects','sources','preview']){relative(meta.entries?.[key]);assert(declared.has(meta.entries[key]),'Missing entry '+key);}
  assert(files.has('README.md'),'Missing README.md');
  const model=json(meta.entries.model),contract=json(meta.entries.contract),template=json(meta.entries.bindings),rig=json(meta.entries.rig),policy=json(meta.entries.statePolicy),effects=json(meta.entries.effects),sources=json(meta.entries.sources);
  assert.equal(template.schema,'home3d.presentation-template.v1');assert(Array.isArray(template.bindings));
  for(const b of template.bindings)assert.deepEqual(Object.keys(b).sort(),['slot','target']);
  assert.equal(rig.schema,'home3d.device-rig.v1');assert.equal(rig.coordinateSpace,'normalized-model');assert.deepEqual(rig.front,[0,0,-1]);
  assert(rig.mounting?.allowedSurfaces?.length&&rig.mounting.allowedSurfaces.every(s=>['floor','wall','ceiling'].includes(s)),'Unsupported mounting');
  assert(rig.mounting.attachmentPoint?.length===3&&rig.mounting.attachmentPoint.every(Number.isFinite),'Invalid mounting point');
  assert.equal(policy.schema,'home3d.device-state-policy.v1');assert.equal(policy.mode,'simulation','BLOCKED: real-state adapter not implemented');
  assert.equal(effects.schema,'home3d.device-effects.v1');assert(Array.isArray(effects.effects));
  for(const e of effects.effects)assert(['point','curtain'].includes(e.groupId)&&e.groupVersion===1,'BLOCKED: unsupported effect group '+e.groupId);
  assert.equal(sources.schema,'home3d.device-sources.v1');for(const key of ['requirements','product','capabilityMappings','tools'])assert(Object.hasOwn(sources,key),'Missing source '+key);
  for(const e of contract.presentation?.effects||[])assert(CHANNELS.has(e.channel),'BLOCKED: unsupported consumer channel '+e.channel);
  assert(declared.has(model.file),'Missing model file');
  const lighting=model.lightingPath?json(model.lightingPath):null;
  const preview=files.get(meta.entries.preview);assert(preview.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10])),'Preview must be PNG');
  return{meta,raw,files,model,contract,template,rig,lighting,contractBytes:files.get(meta.entries.contract)};
}

export function testProject(name){
  return{schema:'home3d.floorplan-scene.v5',id:'device-test',revision:1,parentDigest:null,unit:'m',coordinateSystem:'right-handed-y-up',
    projectMetadata:{name,activeFloorId:'floor-test',mainRoomId:'room-test'},presentation:{profile:{id:'white-home3d-v1',version:1}},
    floors:[{id:'floor-test',name:'测试层',elevation:0,height:3,walls:[],openings:[],rooms:[{id:'room-test',name:'设备测试房间',boundary:[{x:-3,z:-2},{x:3,z:-2},{x:3,z:2},{x:-3,z:2}],materialKey:null}],regions:[],dividers:[]}],instances:[],extensions:{}};
}

export async function assemble(asset,job,sdk){
  const capabilities=job.consumerCapabilities||sdk.CAPABILITIES;
  const source=job.basePackage?await sdk.readPackage(await fs.readFile(job.basePackage),{capabilities}):null;
  if(source)assert.equal(source.format,'v4','Only standard v4 base projects supported');
  const project=structuredClone(source?.project||testProject(job.name||asset.meta.name+' · 测试'));
  const resources=structuredClone(source?.resources||{schema:'home3d.runtime-resources.v4',resources:[]});
  const devices=structuredClone(source?.devices||{schema:'home3d.devices.v1',instances:[]});
  const presentation=structuredClone(source?.presentation||{schema:'home3d.presentation.v1',bindings:[]});
  const reserved=new Set(['package.json','project.json','resources.json','devices.json','presentation.json','experience.json','rendering.json']);
  const entries=Object.fromEntries(Object.entries(source?.entries||{}).filter(([p])=>!reserved.has(p)));
  assert(job.placements?.length,'At least one explicit placement required');
  const def=structuredClone(asset.model),glb=asset.files.get(def.file);def.file='blobs/'+sha(glb).slice(7)+'.glb';entries[def.file]=glb;
  if(def.lightingPath){const bytes=asset.files.get(def.lightingPath);def.lightingPath='blobs/'+sha(bytes).slice(7)+'.json';entries[def.lightingPath]=bytes;}
  const definition=sdk.encode(def),resourceKey='model-'+sha(definition).slice(7,39),definitionPath='resources/'+resourceKey+'.json';
  const existing=resources.resources.find(r=>r.key===resourceKey);
  if(existing)assert.deepEqual(entries[existing.definitionPath],definition,'Resource collision');
  else{resources.resources.push({key:resourceKey,kind:'model',definitionPath});entries[definitionPath]=definition;}
  const digest=sha(asset.contractBytes),contractPath='contracts/'+digest.slice(7)+'.json';entries[contractPath]=asset.contractBytes;
  const additions=[];
  for(const place of job.placements){
    assert(['floor','wall','ceiling'].includes(place.placement)&&asset.rig.mounting.allowedSurfaces.includes(place.placement),'Placement not allowed');
    assert(!project.instances.some(i=>i.id===place.instanceId),'Duplicate instance id');
    const deviceId=place.deviceId||'device-'+place.instanceId;assert(!devices.instances.some(d=>d.id===deviceId),'Duplicate device id');
    project.instances.push({id:place.instanceId,name:place.name||asset.meta.name,kind:'device',resourceKey,floorId:place.floorId,roomId:place.roomId??null,regionId:null,materialKey:null,
      transform:{position:place.position,rotation:place.rotation||[0,0,0,1],size:place.size||def.defaultSize},visible:true,placement:place.placement,host:null,
      extensions:{[NS]:{assetId:asset.meta.id,assetVersion:asset.meta.version}}});
    devices.instances.push({id:deviceId,name:place.name||asset.meta.name,instanceId:place.instanceId,contractPath,contractDigest:digest,manualControlEnabled:true});
    for(const b of asset.template.bindings)presentation.bindings.push({deviceId,...structuredClone(b)});
    additions.push({instanceId:place.instanceId,deviceId});
  }
  if(source){project.revision+=1;project.parentDigest=sha(source.entries['project.json']);if(job.name)project.projectMetadata.name=job.name;}
  const input={version:4,kind:'project',name:project.projectMetadata.name,producer:{name:'interior-device-package',version:'1.0.0'},project,resources,devices,presentation,entries,
    requiredCapabilities:[...new Set([...CORE,...(source?.manifest.requiredCapabilities||[]),...asset.meta.target.requiredCapabilities,...(asset.lighting?['model.lighting.v1']:[])])]};
  if(source?.experience)input.experience={...structuredClone(source.experience),projectDigest:sha(sdk.encode(project))};
  if(source?.rendering){
    const rendering=structuredClone(source.rendering),inspected=await sdk.inspectModel(glb,asset.model.file);
    const lights=asset.lighting?asset.lighting.fixtures.map(f=>f.id):(inspected.document.nodes||[]).filter((n,i)=>n.extensions?.KHR_lights_punctual&&inspected.reachableNodes.has(i)).map(n=>n.name);
    for(const add of additions)for(const lightId of lights)rendering.modelLightShadows.push({instanceId:add.instanceId,lightId,shadow:{enabled:false}});
    input.rendering=sdk.bindRenderingToProject(rendering,project);
  }
  const bytes=await sdk.writePackage(input,{capabilities});
  const validation=await sdk.validatePackage(bytes,{capabilities});assert(validation.valid,JSON.stringify(validation.errors));
  const parsed=await sdk.readPackage(bytes,{capabilities});assert.equal(sha(bytes),sha(await sdk.writePackage(input,{capabilities})),'Non-deterministic Home3D');
  if(source){
    assert.deepEqual(parsed.project.floors,source.project.floors);
    assert.deepEqual(parsed.project.instances.slice(0,source.project.instances.length),source.project.instances);
    for(const[p,b]of Object.entries(source.entries))if(!reserved.has(p))assert.deepEqual(parsed.entries[p],b,'Original payload changed: '+p);
    assert.deepEqual(parsed.devices.instances.slice(0,source.devices.instances.length),source.devices.instances);
    assert.deepEqual(parsed.presentation.bindings.slice(0,source.presentation.bindings.length),source.presentation.bindings);
    if(source.experience)assert.equal(sha(sdk.encode({...parsed.experience,projectDigest:source.experience.projectDigest})),sha(sdk.encode(source.experience)));
    if(source.rendering)assert.deepEqual(parsed.rendering.modelLightShadows.slice(0,source.rendering.modelLightShadows.length),source.rendering.modelLightShadows);
    if(source.rendering)for(const k of Object.keys(source.rendering))if(!['projectDigest','modelLightShadows'].includes(k))assert.deepEqual(parsed.rendering[k],source.rendering[k]);
  }
  let isolation='not-reviewed',isolationChecks=0;
  if(additions.length>=2)for(const scope of asset.contract.scopes)for(const c of scope.capabilities){
    if(c.behavior!=='property'||!['write','read-write'].includes(c.access)||c.initialValue===undefined)continue;
    const r={...(scope.controlObjectId!==undefined?{controlObjectId:scope.controlObjectId}:{}),...(scope.outputId!==undefined?{outputId:scope.outputId}:{}),capabilityKey:c.key};
    let value=c.value.type==='boolean'?!c.initialValue:c.value.type==='number'?(c.initialValue===c.value.minimum?c.value.maximum:c.value.minimum):c.value.enum?.find(v=>v!==c.initialValue);
    if(value===undefined||value===c.initialValue)continue;
    const runtime=sdk.createDemoRuntime(parsed),before=additions.slice(1).map(a=>runtime.read({deviceId:a.deviceId,...r}));
    runtime.dispatch({deviceId:additions[0].deviceId,...r,operation:'write',value});runtime.advance(60000);
    assert.deepEqual(additions.slice(1).map(a=>runtime.read({deviceId:a.deviceId,...r})),before,'Device state leaked');isolationChecks++;
  }
  if(isolationChecks)isolation='passed';
  for(const scenario of job.scenarios||[]){const runtime=sdk.createDemoRuntime(parsed);for(const step of scenario.steps){
    if(step.action)runtime.dispatch(step.action);
    if(step.advanceMs!==undefined)runtime.advance(step.advanceMs);
    if(step.expect)assert.deepEqual(runtime.read(step.expect.ref),{known:true,value:step.expect.value},'Scenario failed: '+scenario.name);
  }}
  return{bytes,parsed,report:{schema:'home3d.device-acceptance.v1',assetId:asset.meta.id,version:asset.meta.version,entryDigest:sha(asset.raw),packageFileDigest:sha(bytes),packageDigest:parsed.packageDigest,
    protocol:'passed',deterministic:true,scope:'fixed geometry, simulation, core-v4 primitives',sourcePreservation:source?'passed':'not-requested',stateIsolation:isolation,stateIsolationChecks:isolationChecks,
    scenarios:(job.scenarios||[]).map(s=>({name:s.name,status:'passed'})),consumerCapabilityCheck:job.consumerCapabilities?'passed':'not-reviewed',
    materialIsolation:'not-reviewed',geometryReview:'not-reviewed',editorReview:'not-reviewed',onlineSave:'not-reviewed',realHardware:'not-reviewed',additions}};
}

export async function build(jobFile,sdkInfo){
  const base=path.dirname(path.resolve(jobFile)),job=await read(jobFile);
  const resolve=v=>path.resolve(base,v);job.assetDir=resolve(job.assetDir);job.outputDir=resolve(job.outputDir);
  if(job.basePackage)job.basePackage=resolve(job.basePackage);
  const realAsset=await fs.realpath(job.assetDir);
  job.outputDir=path.join(await fs.realpath(path.dirname(job.outputDir)),path.basename(job.outputDir));
  assert(job.outputDir!==realAsset&&!job.outputDir.startsWith(realAsset+path.sep),'Output cannot be inside asset source');
  const asset=await loadAsset(job.assetDir),result=await assemble(asset,job,sdkInfo.sdk);
  await fs.mkdir(job.outputDir); // EEXIST is deliberate: never replace a delivery.
  const zip=path.join(job.outputDir,asset.meta.id+'-'+asset.meta.version+'.device.zip');
  execFileSync('python3',[path.join(HERE,'archive_asset.py'),job.assetDir,zip,sha(asset.raw)],{stdio:'pipe'});
  await fs.writeFile(path.join(job.outputDir,'validation.home3d'),result.bytes,{flag:'wx'});
  result.report.sourceZipDigest=sha(await fs.readFile(zip));result.report.sdk={version:sdkInfo.sdk.VERSION,bundleSha256:sdkInfo.manifest.bundleSha256};
  await fs.writeFile(path.join(job.outputDir,'acceptance.json'),JSON.stringify(result.report,null,2)+'\n',{flag:'wx'});
  return result.report;
}

if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  try{
    const args=process.argv.slice(2),index=args.indexOf('--sdk-dir');let sdkDir;
    if(index>=0){sdkDir=args[index+1];assert(sdkDir,'Missing --sdk-dir value');args.splice(index,2);}
    const[command,file]=args;assert(file&&args.length===2,'Use seal|check <source-dir> or build <job.json> [--sdk-dir <vendor>]');
    let report;
    if(command==='seal')report=await seal(path.resolve(file));
    else{const info=await loadSdk(sdkDir);
      if(command==='build')report=await build(path.resolve(file),info);
      else if(command==='check'){
        const asset=await loadAsset(path.resolve(file));assert(asset.rig.mounting.allowedSurfaces.includes('floor')||asset.rig.mounting.allowedSurfaces.includes('ceiling'),'Wall models require explicit build placements');
        const placement=asset.rig.mounting.allowedSurfaces[0];report=(await assemble(asset,{placements:[{instanceId:'check-a',floorId:'floor-test',roomId:'room-test',placement,position:[0,0,0]}]},info.sdk)).report;
      }else throw Error('Unknown command');
    }
    console.log(JSON.stringify(report,null,2));
  }catch(error){console.error(error.stack||String(error));process.exitCode=1;}
}
