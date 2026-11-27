import assert from 'node:assert/strict';

export const VISUAL_CYCLE_CAPABILITY='device.visual-cycles.v1';
export const SUPPORTED_SDK_VERSIONS=['0.3.0','0.3.1','0.3.2','0.3.3','0.3.4'];
export function sdkAtLeast(actual,minimum){
  const a=actual.split('.').map(Number),b=minimum.split('.').map(Number);
  for(let i=0;i<3;i++){if(a[i]!==b[i])return a[i]>b[i];}
  return true;
}
const key=ref=>JSON.stringify([ref.deviceId??null,ref.controlObjectId??null,ref.outputId??null,ref.capabilityKey]);

/** Authoring requirements only; the official SDK remains the contract validator. */
export function checkContinuousAsset(meta,contract,stateful){
  const cycles=contract.simulation?.visualCycles||[];
  if(!cycles.length)return;
  assert(stateful,'Continuous effects require device.state-simulation and a state description');
  assert(sdkAtLeast(meta.target.sdkVersion,'0.3.4'),'Continuous effects require target SDK 0.3.4 or later');
  assert(meta.target.requiredCapabilities.includes(VISUAL_CYCLE_CAPABILITY),'Declare '+VISUAL_CYCLE_CAPABILITY);
  for(const cycle of cycles) {
    assert(contract.presentation.effects.some(effect=>key(effect.source)===key(cycle.target)&&
      effect.mapping?.kind==='linear'&&effect.mapping.output[0]!==effect.mapping.output[1]),
      'Continuous phase needs a changing linear model effect: '+cycle.id);
  }
}

/** Synthetic gate samples exercise SDK lifecycle without replaying business rules. */
export function verifyContinuousEffects(pkg,sdk){
  const checks=[];
  for(const device of pkg.deviceIndex.values())for(const cycle of device.contract.simulation.visualCycles||[]) {
    const runtime=sdk.createDemoRuntime(pkg);
    assert(typeof runtime.hasBlockingTransitions==='function','Continuous effects require SDK lifecycle queries');
    const target={...cycle.target,deviceId:device.id},gate={...cycle.when.target,deviceId:device.id};
    const snapshot=JSON.parse(JSON.stringify(runtime.exportStableState()));
    const row=ref=>{const found=snapshot.values.find(v=>key(v.target)===key(ref));assert(found,'Missing scoped state');return found;};
    row(gate).state={known:true,value:cycle.when.value};row(target).state={known:true,value:cycle.from};
    runtime.importStableState(snapshot);
    assert.equal(runtime.hasPendingTransitions(),true,'Continuous effect did not request device frames');
    assert.equal(runtime.hasBlockingTransitions(),false,'Visual phase blocks finite playback');
    runtime.resume();runtime.startGuidedScene({id:'visual-check',actions:[{...gate,operation:'observe',sample:true,value:cycle.when.value}]});
    const frame=runtime.guidedSceneProgress();
    assert.equal(frame.status,'awaiting-presentation','Continuous effect blocks guided completion');
    runtime.advance(cycle.durationMs/2);
    assert.notEqual(runtime.read(target).value,cycle.from,'Visual phase did not advance');
    assert.equal(runtime.guidedSceneProgress().finalFrameId,frame.finalFrameId,'Visual progress invalidated the final-frame receipt');
    assert.equal(runtime.acknowledgeGuidedFrame(frame.finalFrameId),true);
    const state=JSON.parse(JSON.stringify(runtime.exportStableState())),next=sdk.createDemoRuntime(pkg);
    next.importStableState(state);
    assert.deepEqual(next.exportStableState(),state,'Stable handoff changed device properties');
    assert.deepEqual(next.effects(),runtime.effects(),'Stable handoff changed projected effects');
    const before=next.read(target).value;next.advance(cycle.durationMs/4);
    assert.notEqual(next.read(target).value,before,'Visual effect did not continue after handoff');
    const stopped=JSON.parse(JSON.stringify(next.exportStableState()));
    stopped.values.find(v=>key(v.target)===key(gate)).state={known:false};
    next.importStableState(stopped);next.advance(cycle.durationMs/2);
    assert.equal(next.read(target).value,cycle.from,'Unknown gate did not stop/reset its visual phase');
    checks.push({deviceId:device.id,cycleId:cycle.id,target,gate,sample:'synthetic gate; no rule replay',
      phaseAdvance:'passed',guidedCompletion:'passed',stableHandoff:'passed',unknownGateStop:'passed'});
  }
  return{status:checks.length?'passed':'not-declared',checks};
}
