#!/usr/bin/env node
/** Read-only authoring check. The application's importer/compiler and the official SDK own all semantics. */
import { readFile } from 'node:fs/promises';
import { resolve, join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';

async function main() {
  const args = process.argv.slice(2), options = {};
  const allowed = new Set(['business-root', 'home3d', 'yaml', 'scene-version', 'context', 'output']);
  for (let i = 0; i < args.length; i++) {
    const key = args[i].replace(/^--/, '');
    if (args[i] === '--sdk-only') { options.sdkOnly = true; continue; }
    if (!args[i].startsWith('--') || !allowed.has(key) || !args[i + 1] || args[i + 1].startsWith('--'))
      throw new Error('Invalid arguments. See references/sdk-preflight.md.');
    options[key] = args[++i];
  }
  for (const key of ['business-root', 'home3d', 'yaml', 'scene-version'])
    if (!options[key]) throw new Error('Missing --' + key);
  if (Boolean(options.context) === Boolean(options.sdkOnly))
    throw new Error('Choose exactly one: --context <target-context.json> or --sdk-only.');
  const root = resolve(options['business-root']);
  const shared = join(root, 'packages/plugins/@nocobase/plugin-solution-management/src');
  // Run through this repository's tsx loader, as documented, to import its canonical TypeScript.
  const { importExperienceDocument } = await import(pathToFileURL(join(shared, 'shared/experience-yaml.ts')).href);
  const { authoringIssues } = await import(pathToFileURL(join(shared, 'shared/experience-source.ts')).href);
  const { validateExperience } = await import(pathToFileURL(join(shared, 'shared/experience.ts')).href);
  const { preflightSdkDeviceProgram } = await import(pathToFileURL(join(shared, 'server/sdk-device-program.ts')).href);
  const require = createRequire(join(root, 'package.json'));
  const { HOME3D_PACKAGE_SDK: sdk } = require(join(root, 'packages/plugins/@nocobase/plugin-home3d-editor/dist/server/home3d-runtime.cjs'));
  const bytes = new Uint8Array(await readFile(resolve(options.home3d)));
  const content = await readFile(resolve(options.yaml), 'utf8');
  const { experience } = importExperienceDocument(content, options['scene-version']);
  let context, businessIssues = authoringIssues(experience, content, options['scene-version']);
  if (options.context) {
    context = JSON.parse(await readFile(resolve(options.context), 'utf8'));
    if (context.sceneVersionId !== options['scene-version']) throw new Error('Context does not match the confirmed target scene version.');
    businessIssues.push(...validateExperience(experience, context, context.narrationAudio || []));
  } else {
    const pkg = await sdk.readPackage(bytes);
    context = { sceneVersionId: options['scene-version'], floors: [], rooms: [], templates: {}, models: {},
      devices: pkg.devices.instances.map((device) => ({ id: device.instanceId })) };
  }
  const checked = await preflightSdkDeviceProgram(bytes, experience, context, sdk);
  const issues = [...new Map([...businessIssues, ...checked.issues].map((issue) => [issue.path + ':' + issue.key, issue])).values()];
  const result = { ok: issues.length === 0 && checked.applicable, scope: options.sdkOnly ? 'sdk-only' : 'business-and-sdk',
    businessValidation: options.sdkOnly ? 'not-run' : 'checked', sdkApplicable: checked.applicable,
    sceneVersionId: options['scene-version'], sourceDigest: sdk.digest(bytes), issues };
  if (options.output) {
    const target = resolve(options.output);
    if ([options.home3d, options.yaml, options.context].filter(Boolean).some((file) => resolve(file) === target))
      throw new Error('Output must not overwrite an input.');
    const { writeFile } = await import('node:fs/promises');
    await writeFile(target, JSON.stringify(result, null, 2) + '\n', { flag: 'wx' });
  }
  console.log(JSON.stringify(result, null, 2));
  process.exitCode = result.ok ? 0 : 1;
}
main().catch((error) => {
  console.error(JSON.stringify({ ok: false, error: error instanceof Error ? error.message : String(error) }));
  process.exitCode = 2;
});
