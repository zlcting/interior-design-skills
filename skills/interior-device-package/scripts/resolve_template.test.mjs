import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {fileURLToPath} from 'node:url';
import {resolveTemplateReference} from './resolve_template.mjs';

const row={id:'8f8d5eaf-0a29-5e14-81f0-7da335a39c30',key:'lighting.light.general',
  sourcePublicationId:'sha256:'+'1'.repeat(64),enabled:true,archived:false};
async function fakeNb(t,data){
  const dir=await fs.mkdtemp(path.join(os.tmpdir(),'template-resolver-'));
  t.after(()=>fs.rm(dir,{recursive:true,force:true}));
  const file=path.join(dir,'nb');
  await fs.writeFile(file,`#!/usr/bin/env node
const fs=require('node:fs');const args=process.argv.slice(2);
if(args.slice(0,3).join(' ')!=='api resource list')process.exit(91);
fs.writeFileSync(${JSON.stringify(path.join(dir,'args.json'))},JSON.stringify(args));
process.stdout.write(${JSON.stringify(JSON.stringify(data))});
`,{mode:0o755});
  return{file,args:()=>fs.readFile(path.join(dir,'args.json'),'utf8').then(JSON.parse)};
}
test('queries an exact key read-only and returns only the portable reference',async t=>{
  const fake=await fakeNb(t,{data:[row],meta:{count:1}});
  assert.deepEqual(await resolveTemplateReference({env:'houzzkit-dev',templateKey:row.key,nbBinary:fake.file}),{
    schema:'houzzkit.device-template-reference.v1',templateId:row.id,templateKey:row.key,
    publicationId:row.sourcePublicationId,purpose:'experienceSimulation',
  });
  const args=await fake.args();
  assert.equal(args[args.indexOf('--resource')+1],'plugins_pm_device_templates');
  assert.deepEqual(JSON.parse(args[args.indexOf('--filter')+1]),{key:row.key});
  assert.equal(args[args.indexOf('--env')+1],'houzzkit-dev');
  assert(!args.includes('--token')&&!args.includes('--api-base-url'));
});
test('resolves a supplied UUID without choosing a similarly named template',async t=>{
  const fake=await fakeNb(t,{data:[row],meta:{count:1}});
  const value=await resolveTemplateReference({env:'houzzkit-dev',templateId:row.id,nbBinary:fake.file});
  assert.equal(value.templateKey,row.key);
  const args=await fake.args();assert.deepEqual(JSON.parse(args[args.indexOf('--filter')+1]),{id:row.id});
});
for(const [name,data,reason] of [
  ['missing',{data:[],meta:{count:0}},/exactly one/],
  ['ambiguous',{data:[row,row],meta:{count:2}},/exactly one/],
  ['disabled',{data:[{...row,enabled:false}]},/disabled/],
  ['archived',{data:[{...row,archived:true}]},/archived/],
  ['unpublished',{data:[{...row,sourcePublicationId:null}]},/published source/],
  ['different key',{data:[{...row,key:'different.key'}]},/different template key/],
  ['permission error',{errors:[{message:'forbidden'}]},/access was denied/],
])test(`rejects ${name} results`,async t=>{
  const fake=await fakeNb(t,data);
  await assert.rejects(resolveTemplateReference({env:'houzzkit-dev',templateKey:row.key,nbBinary:fake.file}),reason);
});
test('requires an explicit environment and an unambiguous selector',async()=>{
  await assert.rejects(resolveTemplateReference({templateKey:row.key}),/explicit nb environment/);
  await assert.rejects(resolveTemplateReference({env:'houzzkit-dev',templateKey:row.key,templateId:row.id}),/exactly one/);
});
test('CLI writes a usable reference when invoked through a symlink',async t=>{
  const fake=await fakeNb(t,{data:[row],meta:{count:1}});
  const dir=path.dirname(fake.file),script=path.join(dir,'resolver.mjs'),output=path.join(dir,'reference.json');
  await fs.symlink(fileURLToPath(new URL('./resolve_template.mjs',import.meta.url)),script);
  const {stdout}=await promisify(execFile)(process.execPath,[script,'--env','houzzkit-dev','--template-key',row.key,'--output',output],{env:{...process.env,NB_BIN:fake.file}});
  const result=JSON.parse(stdout);
  assert.equal(result.templateId,row.id);
  assert.deepEqual(JSON.parse(await fs.readFile(output,'utf8')),result);
});
