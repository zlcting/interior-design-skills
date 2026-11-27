/** Source-package helpers. SDK owns state and validates compiled Home3D programs. */
function check(value,message='Invalid device state definition'){if(!value)throw Error(message);}
const REF_KEYS=['capabilityKey','controlObjectId','outputId'];
export function capabilityRef(ref){
  check(ref&&typeof ref==='object'&&!Array.isArray(ref),'Missing local capability reference');
  check(Object.keys(ref).every(k=>REF_KEYS.includes(k)),'Use a local capability reference without deviceId');
  check(typeof ref.capabilityKey==='string'&&ref.capabilityKey,'Missing capabilityKey');
  for(const key of ['controlObjectId','outputId'])if(Object.hasOwn(ref,key))check(typeof ref[key]==='string'&&ref[key],'Invalid scope');
  return {...ref};
}
function find(contract,ref){
  capabilityRef(ref);
  const scope=contract.scopes.find(s=>s.controlObjectId===ref.controlObjectId&&s.outputId===ref.outputId);
  const cap=scope?.capabilities.find(c=>c.key===ref.capabilityKey);
  check(cap,'Unknown capability or scope: '+JSON.stringify(ref));return cap;
}
export function validateStateDescription(contract,description){
  check(description?.schema==='home3d.device-state-description.v1','Invalid state description schema');
  check(description.mode==='simulation','Only simulation state is supported');
  check(description.readableRefs?.length,'Declare readableRefs for current device state');
  const seen=new Set();
  for(const ref of description.readableRefs){
    const cap=find(contract,ref),key=JSON.stringify([ref.controlObjectId??null,ref.outputId??null,ref.capabilityKey]);
    check(!seen.has(key),'Duplicate readable reference');seen.add(key);
    check(cap.behavior==='property'&&['read','read-write'].includes(cap.access),'State must reference a readable property');
  }
  for(const ref of [description.summaryRef,...(description.qualityRef?[description.qualityRef]:[])]){
    find(contract,ref);
    check(seen.has(JSON.stringify([ref.controlObjectId??null,ref.outputId??null,ref.capabilityKey])),'Summary/quality must be a declared readable state');
  }
}
export function instantiateBehavior(template,deviceId,contract){
  check(template?.schema==='home3d.device-behavior-template.v1','Invalid behavior template schema');
  check(template.version===1,'Unsupported behavior version');check(template.mode==='simulation','Only simulation behavior is supported');check(Array.isArray(template.rules));
  check(Object.keys(template).every(k=>['schema','version','mode','rules','note'].includes(k)),'Unexpected behavior template fields');
  const ids=new Set();
  return template.rules.map(rule=>{
    check(typeof rule.id==='string'&&rule.id&&!ids.has(rule.id),'Duplicate/missing behavior rule id');ids.add(rule.id);
    check(Object.keys(rule).every(k=>['id','when','actions'].includes(k)),'Unexpected behavior rule fields');
    check(rule.when&&Object.keys(rule.when).every(k=>['target','value'].includes(k)),'Unexpected behavior condition');
    const ref=capabilityRef(rule.when.target);find(contract,ref);
    check(Array.isArray(rule.actions)&&rule.actions.length,'Rule needs actions');
    const actions=rule.actions.map(action=>{
      check(Object.keys(action).every(k=>[...REF_KEYS,'operation','value','sample','transitionMs'].includes(k)),'Unexpected behavior action fields');
      const target=Object.fromEntries(REF_KEYS.filter(k=>Object.hasOwn(action,k)).map(k=>[k,action[k]]));find(contract,target);
      return {...action,deviceId};
    });
    return{id:deviceId+'--'+rule.id,when:{target:{...ref,deviceId},value:rule.when.value},actions};
  });
}
export function readDeviceState(runtime,deviceId,contract,description){
  validateStateDescription(contract,description);
  const sample=ref=>runtime.read({...ref,deviceId});
  return{deviceId,mode:description.mode,summary:sample(description.summaryRef),quality:description.qualityRef?sample(description.qualityRef):null,
    values:description.readableRefs.map(ref=>({ref:{...ref},...sample(ref)}))};
}
