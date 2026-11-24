#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {fileURLToPath} from 'node:url';

const execute=promisify(execFile);
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Resolve only catalog facts through the operator's configured nb environment. */
export async function resolveTemplateReference({env,templateKey,templateId,nbBinary=process.env.NB_BIN||'nb'}){
  assert(typeof env==='string'&&/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(env),'An explicit nb environment is required');
  assert(Boolean(templateKey)!==Boolean(templateId),'Provide exactly one templateKey or templateId');
  if(templateKey)assert(typeof templateKey==='string'&&templateKey.length<=200&&templateKey.trim()===templateKey,'Invalid templateKey');
  if(templateId)assert(typeof templateId==='string'&&uuid.test(templateId),'Invalid templateId');
  const filter=templateKey?{key:templateKey}:{id:templateId};
  const args=['api','resource','list','--resource','plugins_pm_device_templates','--filter',JSON.stringify(filter),
    '--fields',JSON.stringify(['id','key','name','sourcePublicationId','enabled','archived']),
    '--page-size','2','--env',env,'--yes','-j'];
  let stdout;
  try{
    ({stdout}=await execute(nbBinary,args,{timeout:30000,maxBuffer:2*1024*1024,encoding:'utf8'}));
  }catch(error){
    const detail=error.code==='ENOENT'?'nb CLI was not found':`nb lookup failed (${error.code||error.message})`;
    throw new Error(`${detail}. Check nb environment/login and template read permission; no reference was generated.`);
  }
  let result;
  try{result=JSON.parse(stdout);}catch{throw new Error('nb did not return JSON; no reference was generated');}
  assert(Array.isArray(result.data),'Template list response is unavailable or access was denied');
  assert(result.data.length===1&&Number(result.meta?.count??1)===1,'Expected exactly one accessible template; none or multiple found');
  const row=result.data[0];
  assert(row&&typeof row.id==='string'&&uuid.test(row.id),'Template UUID is missing');
  assert(typeof row.key==='string'&&row.key.length>0&&row.key.length<=200,'Template key is missing');
  assert(!templateKey||row.key===templateKey,'Server returned a different template key');
  assert(!templateId||row.id.toLowerCase()===templateId.toLowerCase(),'Server returned a different template UUID');
  assert(row.enabled===true&&row.archived===false,'Template is disabled, archived, or its status is inaccessible');
  assert(typeof row.sourcePublicationId==='string'&&/^sha256:[0-9a-f]{64}$/.test(row.sourcePublicationId),'Template has no valid published source');
  return{schema:'houzzkit.device-template-reference.v1',templateId:row.id,templateKey:row.key,
    publicationId:row.sourcePublicationId,purpose:'experienceSimulation'};
}

const invokedFile=process.argv[1]?await fs.realpath(path.resolve(process.argv[1])).catch(()=>null):null;
if(invokedFile===fileURLToPath(import.meta.url)){
  try{
    const values={};const names={'--env':'env','--template-key':'templateKey','--template-id':'templateId','--output':'output'};
    for(let i=2;i<process.argv.length;i+=2){
      const key=names[process.argv[i]],value=process.argv[i+1];
      assert(key&&value&&!Object.hasOwn(values,key),'Use --env <nb-env> and --template-key <key> or --template-id <uuid> [--output <new.json>]');
      values[key]=value;
    }
    const reference=await resolveTemplateReference(values),json=JSON.stringify(reference,null,2)+'\n';
    if(values.output)await fs.writeFile(path.resolve(values.output),json,{flag:'wx'});
    process.stdout.write(json);
  }catch(error){console.error(error.message||String(error));process.exitCode=1;}
}
