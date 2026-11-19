#!/usr/bin/env node
// Exercise the target editor's real import/save/export runtime in an isolated workspace.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';

const [packageFile, editorSource, outputDirectory] = process.argv.slice(2);
if (!outputDirectory) throw new Error('Use <project.home3d> <Home3D source directory> <new review directory>');
const source = path.resolve(editorSource), output = path.resolve(outputDirectory);
await mkdir(output); // Do not overwrite an earlier review.
const moduleAt = relative => import(pathToFileURL(path.join(source, relative)).href);
const sdk = await moduleAt('packages/home3d-package/src/index.mjs');
const { createOnlineWorkspaceRuntime } = await moduleAt('scripts/lib/online-workspace-runtime.mjs');
const { readUnifiedProjection } = await moduleAt('scripts/lib/unified-project-workspace.mjs');
const bundled = createRequire(import.meta.url)('../skills/interior-home3d/scripts/vendor/home3d-package.cjs');
const bytes = await readFile(packageFile), before = await bundled.readPackage(bytes);
assert.equal(before.format, 'v4');
assert.equal(before.manifest.kind, 'project');
let runtime = createOnlineWorkspaceRuntime({directory: path.join(output, 'workspace')});
async function request(endpoint, method, body = new Uint8Array(), query = '') {
  const response = await runtime.execute({endpoint, method, query, headers: {}, body,
    expectedRevision: await runtime.revision()});
  assert.equal(response.status, 200, Buffer.from(response.body).toString());
  return response;
}
const imported = JSON.parse(Buffer.from((await request('project-package', 'POST', bytes)).body).toString());
const root = path.join(output, 'workspace/projects', imported.projectId);
const view = await readUnifiedProjection(root, imported.projectId), project = view.project;
const furnishing = project.furniture.find(f => !f.surfaceHost);
assert.ok(furnishing, 'Need an independent furniture instance');
const floor = project.floors[0], wall = floor.layout.walls[0], opening = floor.layout.openings[0];
assert.ok(opening, 'Need an opening to test host preservation');
furnishing.position[1] += 0.1;
furnishing.rotationY += 12 * Math.PI / 180;
wall.height += 0.01;
opening.width -= 0.05;
assert.ok(opening.width > 0);
project.revision++;
await request('project-repository', 'PUT', Buffer.from(JSON.stringify({schema: 'home3d.project-repository.v1',
  version: 1, activeProjectId: imported.projectId, projects: [project]})));
// Reopen storage through a new runtime, as a page refresh would do.
runtime = createOnlineWorkspaceRuntime({directory: path.join(output, 'workspace')});
const refreshed = (await readUnifiedProjection(root, imported.projectId)).project;
assert.deepEqual(refreshed.furniture.find(f => f.id === furnishing.id).position, furnishing.position);
assert.equal(refreshed.furniture.find(f => f.id === furnishing.id).rotationY, furnishing.rotationY);
assert.equal(refreshed.floors[0].layout.walls[0].height, wall.height);
assert.equal(refreshed.floors[0].layout.openings[0].width, opening.width);
const exported = await request('project-package', 'GET', new Uint8Array(),
  new URLSearchParams({projectId: imported.projectId, format: 'unified'}).toString());
assert.equal(exported.headers['x-home3d-package-version'], '4');
const after = await bundled.readPackage(exported.body);
assert.equal(after.format, 'v4');
const original = before.project.instances.find(i => i.id === furnishing.id);
const edited = after.project.instances.find(i => i.id === furnishing.id);
assert.ok(Math.abs(edited.transform.position[1] - original.transform.position[1] - .1) < 1e-8);
const yaw = 2 * Math.atan2(original.transform.rotation[1], original.transform.rotation[3]) + 12 * Math.PI / 180;
const expectedRotation = [0, Math.sin(yaw / 2), 0, Math.cos(yaw / 2)];
assert.ok(Math.abs(edited.transform.rotation.reduce((sum, v, i) => sum + v * expectedRotation[i], 0)) > 1 - 1e-8);
assert.ok(Math.abs(after.project.floors[0].walls[0].height - before.project.floors[0].walls[0].height - .01) < 1e-8);
assert.ok(Math.abs(after.project.floors[0].openings[0].width - before.project.floors[0].openings[0].width + .05) < 1e-8);
assert.equal(after.project.floors[0].openings[0].wallId, before.project.floors[0].openings[0].wallId);
assert.deepEqual(after.project.instances.map(i => i.id).sort(), before.project.instances.map(i => i.id).sort());
assert.deepEqual(after.devices, before.devices);
assert.deepEqual(after.presentation, before.presentation);
assert.deepEqual(after.project.presentation, before.project.presentation);
for (const [key, data] of Object.entries(before.entries))
  if (key.startsWith('blobs/')) assert.deepEqual(after.entries[key], data, 'Geometry or lighting blob changed: ' + key);
const reimported = JSON.parse(Buffer.from((await request('project-package', 'POST', exported.body)).body).toString());
const reexport = await request('project-package', 'GET', new Uint8Array(),
  new URLSearchParams({projectId: reimported.projectId, format: 'unified'}).toString());
const final = await bundled.readPackage(reexport.body);
assert.deepEqual(final.project, after.project);
assert.deepEqual(final.devices, after.devices);
assert.deepEqual(final.presentation, after.presentation);
assert.equal((await sdk.validatePackage(reexport.body)).valid, true);
await writeFile(path.join(output, 'edited-v4.home3d'), exported.body);
await writeFile(path.join(output, 'reimported-v4.home3d'), reexport.body);
const sha = data => createHash('sha256').update(data).digest('hex');
const report = {schema: 'interior.home3d-editor-runtime-review.v1', status: 'passed',
  scope: 'real target editor runtime import/save/reopen/export/reimport; UI and visual review recorded separately',
  recordedAt: new Date().toISOString(), inputSha256: sha(bytes), editorSdkVersion: sdk.VERSION,
  editedSha256: sha(exported.body), reimportedSha256: sha(reexport.body),
  edits: {furnitureId: furnishing.id, position: furnishing.position, rotationY: furnishing.rotationY,
    wallId: wall.id, height: wall.height, openingId: opening.id, width: opening.width},
  checks: {savedValues: true, independentInstances: true, openingHost: true,
    geometryAndLightingBlobsUnchanged: true, devicesAndPresentationUnchanged: true, v4Reimport: true},
  uiReview: 'not_reviewed', visualReview: 'not_reviewed'};
await writeFile(path.join(output, 'acceptance.json'), JSON.stringify(report, null, 2) + '\n');
console.log('HOME3D_EDITOR_ROUNDTRIP_PASSED', JSON.stringify(report.checks));
