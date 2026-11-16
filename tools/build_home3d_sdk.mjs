#!/usr/bin/env node
// Build the installed skill's offline SDK from the canonical package, never a copied validator.
import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
const position = process.argv.indexOf('--sdk-source');
if (position < 0 || !process.argv[position + 1]) throw new Error('Use --sdk-source <canonical home3d-package directory>');
const source = path.resolve(process.argv[position + 1]);
const pkg = JSON.parse(await fs.readFile(path.join(source, 'package.json')));
if (pkg.name !== '@houzzkit/home3d-package' || pkg.version !== '0.1.0') throw new Error('Expected locked SDK @houzzkit/home3d-package@0.1.0');
const require = createRequire(path.join(source, 'package.json'));
const { build, version: buildVersion } = require('esbuild');
if (buildVersion !== '0.20.2') throw new Error('Expected reproducible SDK builder esbuild@0.20.2');
const out = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../skills/interior-home3d/scripts/vendor');
await fs.mkdir(out, { recursive: true });
const built = await build({absWorkingDir: source, metafile: true, stdin: {contents: 'export * from "./src/index.mjs"; export * from "./src/lighting.mjs";', resolveDir: source, loader: 'js'},
  outfile: path.join(out, 'home3d-package.cjs'), bundle: true, format: 'cjs', platform: 'node', target: 'node20', legalComments: 'inline'});
const hash = data => createHash('sha256').update(data).digest('hex');
const files = {};
for (const directory of ['src', 'schemas'])
  for (const entry of (await fs.readdir(path.join(source, directory))).sort())
    files[directory + '/' + entry] = hash(await fs.readFile(path.join(source, directory, entry)));
files['package.json'] = hash(await fs.readFile(path.join(source, 'package.json')));
const notices = [];
const dependencies = {};
const bundledPackages = new Set(Object.keys(pkg.dependencies));
for (const input of Object.keys(built.metafile.inputs)) {
  if (!input.includes('node_modules')) continue;
  let directory = path.dirname(path.resolve(source, input));
  while (directory !== path.dirname(directory)) {
    const data = await fs.readFile(path.join(directory, 'package.json'), 'utf8').then(JSON.parse).catch(() => null);
    if (data?.name) {bundledPackages.add(data.name); break;}
    directory = path.dirname(directory);
  }
}
for (const name of [...bundledPackages].sort()) {
  let dependency;
  try {dependency = require.resolve(name + '/package.json');}
  catch {
    let directory = path.dirname(require.resolve(name));
    while (!(await fs.stat(path.join(directory, 'package.json')).catch(() => null))) directory = path.dirname(directory);
    dependency = path.join(directory, 'package.json');
  }
  const data = JSON.parse(await fs.readFile(dependency));
  dependencies[name] = {version: data.version, license: data.license || null};
  for (const file of ['LICENSE', 'LICENSE.md', 'LICENSE.txt', 'LICENSE-MIT']) {
    const text = await fs.readFile(path.join(path.dirname(dependency), file), 'utf8').catch(() => null);
    if (text) {notices.push('## ' + name + '@' + data.version + '\n\n' + text); break;}
  }
}
const manifest = {schema: 'interior.home3d-sdk-artifact.v1', name: pkg.name, version: pkg.version,
  node: '>=20', builder: {name: 'esbuild', version: buildVersion}, sourceFiles: files, sourceDigest: hash(JSON.stringify(files)), dependencies,
  bundleSha256: hash(await fs.readFile(path.join(out, 'home3d-package.cjs')))};
await fs.writeFile(path.join(out, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
await fs.writeFile(path.join(out, 'THIRD-PARTY-NOTICES.md'), '# Offline SDK dependency notices\n\n' + notices.join('\n\n'));
console.log('SDK_BUNDLED', manifest.version, manifest.bundleSha256);
