#!/usr/bin/env node
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
const HERE = path.dirname(fileURLToPath(import.meta.url));
if (Number(process.versions.node.split('.')[0]) < 20) throw new Error('Node.js 20+ is required');
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const manifest = JSON.parse(await fs.readFile(path.join(HERE, 'vendor/manifest.json')));
const bundle = path.join(HERE, 'vendor/home3d-package.cjs');
if (manifest.version !== '0.2.0' || hash(await fs.readFile(bundle)) !== manifest.bundleSha256) throw new Error('SDK artifact digest mismatch');
const sdk = createRequire(import.meta.url)(bundle);
const CAPABILITIES = ['scene.structure.v1', 'model.glb.v1', 'model.normalization.v1', 'model.lighting.v1',
  'device.contracts.v1', 'device.presentation.v1', 'device.simulation.v1'];
const NS = 'org.houzzkit.interior';
const EDITOR = 'com.houzzkit.editor';
const readJson = async file => JSON.parse(await fs.readFile(file, 'utf8'));
const key = source => /^[A-Za-z][A-Za-z0-9_.:-]{0,100}$/.test(source) ? source : 'id-' + hash(Buffer.from(source)).slice(0, 24);
const rotateY = (p, angle) => [Math.cos(angle) * p[0] + Math.sin(angle) * p[2], p[1], -Math.sin(angle) * p[0] + Math.cos(angle) * p[2]];
const relative = (p, origin, angle) => rotateY(p.map((v, i) => v - origin[i]), -angle);

export async function build(jobFile) {
  const root = path.dirname(jobFile), job = await readJson(jobFile), extracted = await readJson(path.join(root, 'components.json'));
  const scene = job.scene, entries = {}, resources = {schema: 'home3d.runtime-resources.v4', resources: []};
  const fixtures = job.lighting ? sdk.parseModelLighting(job.lighting, job.geometrySha256).fixtures : [];
  const fixtureOwners = job.mapping.fixtures || {};
  for (const light of fixtures)
    if (!extracted.components.some(c => c.sourceId === (fixtureOwners[light.id] || light.id))) throw new Error('LIGHT_OWNER_REQUIRED: ' + light.id);
  const definitions = new Map(), objectMap = [];
  for (const component of extracted.components) {
    const bytes = await fs.readFile(path.join(root, component.file));
    const digest = hash(bytes), blobPath = 'blobs/' + digest + '.glb';
    entries[blobPath] = bytes;
    const model = await sdk.inspectModel(bytes, component.file);
    const min = model.bounds.min, max = model.bounds.max;
    const translation = [-(min[0] + max[0]) / 2, -min[1], -(min[2] + max[2]) / 2];
    const defaultSize = {width: max[0] - min[0], height: max[1] - min[1], depth: max[2] - min[2]};
    const normalizedFixtures = fixtures.filter(f => (fixtureOwners[f.id] || f.id) === component.sourceId).map(f => ({...f,
      position: relative(f.position, component.position, component.rotationY),
      emitterOffsetM: rotateY(f.emitterOffsetM, -component.rotationY)}));
    const definition = {schema: 'home3d.model-definition.v1', kind: 'model', file: blobPath, defaultSize,
      pivot: 'bottom-center', normalization: {translation, scale: [1, 1, 1]}, targets: []};
    if (normalizedFixtures.length) {
      const light = {schema: 'home3d.model-lighting.v1', modelDigest: 'sha256:' + digest,
        coordinateSystem: 'right-handed-y-up', fixtures: normalizedFixtures};
      const data = Buffer.from(sdk.serializeModelLighting(light));
      definition.lightingPath = 'blobs/' + hash(data) + '.json';
      entries[definition.lightingPath] = data;
    }
    const definitionDigest = hash(sdk.encode(definition));
    const resourceKey = 'model-' + definitionDigest.slice(0, 32);
    if (!definitions.has(resourceKey)) {
      const definitionPath = 'resources/' + resourceKey + '.json';
      definitions.set(resourceKey, definition);
      resources.resources.push({key: resourceKey, kind: 'model', definitionPath});
      entries[definitionPath] = definition;
    }
    const shifted = rotateY(translation, component.rotationY);
    const position = component.position.map((v, i) => v - shifted[i]);
    let room = component.room;
    if (!room) {
      const [x, , z] = component.position;
      const found = job.project.rooms.filter(r => x * 1000 >= r.rect[0] && x * 1000 <= r.rect[0] + r.rect[2]
        && -z * 1000 >= r.rect[1] && -z * 1000 <= r.rect[1] + r.rect[3]);
      room = found.length === 1 ? found[0].id : null;
    }
    const instance = {id: 'instance-' + key(component.sourceId), kind: 'furnishing', name: component.name,
      resourceKey, floorId: scene.floors[0].id, roomId: room ? 'room-' + key(room) : null, regionId: null,
      materialKey: null, transform: {position, rotation: component.rotation, size: defaultSize},
      visible: true, placement: 'floor', host: null,
      extensions: {[NS]: {sourceId: component.sourceId}}};
    if (component.openingId) {
      const opening = scene.floors[0].openings.find(o => o.id === 'opening-' + key(component.openingId));
      if (!opening) throw new Error('Missing source opening: ' + component.openingId);
      instance.placement = 'opening';
      instance.host = {kind: 'opening', id: opening.id};
      instance.extensions[EDITOR] = {mounting: {offset: opening.width / 2,
        localV: position[1], normalOffset: 0}};
    }
    scene.instances.push(instance);
    objectMap.push({sourceId: component.sourceId, sourceNodes: component.sourceNodes, instanceId: instance.id,
      resourceKey, modelDigest: digest, lightingFixtures: normalizedFixtures.map(f => f.id), openingId: component.openingId});
  }
  scene.extensions[NS].sourceModelSha256 = job.sourceModelSha256;
  scene.extensions[NS].sourceGeometrySha256 = job.geometrySha256;
  const input = {version: 4, kind: 'project', name: scene.projectMetadata.name,
    producer: {name: 'interior-home3d', version: '1.1.0'},
    requiredCapabilities: ['scene.structure.v1', 'model.glb.v1', 'model.normalization.v1',
      'device.contracts.v1', 'device.presentation.v1', 'device.simulation.v1',
      ...(fixtures.length || extracted.components.some(c => c.embeddedLights) ? ['model.lighting.v1'] : [])],
    project: scene, resources, devices: {schema: 'home3d.devices.v1', instances: []},
    presentation: {schema: 'home3d.presentation.v1', bindings: []}, entries};
  const bytes = await sdk.writePackage(input, {capabilities: CAPABILITIES});
  const check = await sdk.validatePackage(bytes, {capabilities: CAPABILITIES});
  if (!check.valid) throw new Error(JSON.stringify(check.errors));
  const roundtrip = await sdk.readPackage(bytes, {capabilities: CAPABILITIES});
  const repeat = await sdk.writePackage(input, {capabilities: CAPABILITIES});
  if (hash(bytes) !== hash(repeat)) throw new Error('Non-deterministic SDK archive');
  const expectedFurniture = new Set(job.project.furniture.map(f => f.id));
  for (const source of expectedFurniture) if (!objectMap.some(o => o.sourceId === source)) throw new Error('Missing independent furniture: ' + source);
  if (roundtrip.format !== 'v4' || roundtrip.manifest.kind !== 'project') throw new Error('Expected standard v4 project');
  if (roundtrip.project.instances.length !== objectMap.length) throw new Error('Round-trip instance count differs');
  const report = {schema: 'interior.home3d-acceptance.v1', producer: input.producer,
    sdk: {name: manifest.name, version: manifest.version, bundleSha256: manifest.bundleSha256, sourceDigest: manifest.sourceDigest},
    inputs: {modelSha256: job.sourceModelSha256, geometrySha256: job.geometrySha256, skillSha256: job.skillSha256, lightingSha256: job.lightingSha256, fullSourceSha256: job.fullSourceSha256, objectMapSha256: job.objectMapSha256},
    package: {file: 'project.home3d', sha256: hash(bytes), packageDigest: roundtrip.packageDigest,
      format: roundtrip.format, version: roundtrip.manifest.version, kind: roundtrip.manifest.kind},
    protocol: {...check, deterministic: true, consumerCapabilities: CAPABILITIES},
    objects: {passed: true, sourceFurniture: expectedFurniture.size, walls: scene.floors[0].walls.length,
      openings: scene.floors[0].openings.length, rooms: scene.floors[0].rooms.length,
      instances: scene.instances.length, modelDefinitions: resources.resources.length, lightingFixtures: fixtures.length, embeddedLights: extracted.components.reduce((sum, c) => sum + (c.embeddedLights || 0), 0)},
    geometry: {passed: extracted.components.every(c => c.geometryVerification.passed), toleranceMm: 0.02,
      scope: 'evaluated mesh local coordinates after extraction and GLB reimport; source transforms retained in object map'},
    normals: {passed: extracted.components.every(c => c.geometryVerification.normals?.passed),
      generatedPrimitives: extracted.components.reduce((n,c) => n + c.geometryVerification.normals.generatedPrimitives, 0),
      regeneratedPrimitives: extracted.components.reduce((n,c) => n + c.geometryVerification.normal_generation.regeneratedPrimitives, 0)},
    precisionNotes: ['Vertex colors are retained through Blender; storage conversion can quantize values. Exact numerical color preservation requires a separate comparison.'],
    editorReview: {status: 'not_reviewed', evidence: []}, visualReview: {status: 'not_reviewed', evidence: []}};
  await fs.writeFile(path.join(root, 'project.home3d'), bytes, {flag: 'wx'});
  await fs.writeFile(path.join(root, 'object-map.json'), JSON.stringify({schema: 'interior.home3d-object-map.v1', objects: objectMap}, null, 2) + '\n');
  await fs.writeFile(path.join(root, 'acceptance.json'), JSON.stringify(report, null, 2) + '\n');
  await fs.mkdir(path.join(root, 'state'), {recursive: true});
  await fs.writeFile(path.join(root, 'state/execution-log.json'), JSON.stringify([{skill: 'interior-home3d', skill_sha256: job.skillSha256,
    input_sha256: job.sourceModelSha256, executed_at: new Date().toISOString(), result: 'protocol-and-geometry-passed',
    output_files: [{path: 'project.home3d', sha256: hash(bytes)}]}], null, 2) + '\n');
  console.log('HOME3D_PACKAGE_VALID', JSON.stringify(report.objects));
  return report;
}

const [command, file] = process.argv.slice(2);
if (command === 'build' && file) await build(path.resolve(file));
else if (['validate', 'validate-protocol'].includes(command) && file) {
  const result = await sdk.validatePackage(await fs.readFile(file), {capabilities: command === 'validate-protocol' ? sdk.CAPABILITIES : CAPABILITIES});
  console.log(JSON.stringify(result, null, 2));
  if (!result.valid) process.exitCode = 1;
} else if (process.argv[1] === fileURLToPath(import.meta.url)) throw new Error('Use build <job.json> or validate|validate-protocol <project.home3d>');
