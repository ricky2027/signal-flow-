/** Resolve the complete target lockfile before changing the working dependency tree.
 * No --force, peer bypass, fake integrity hashes, cache-only "latest", or deployment.
 */
import {mkdtempSync, readFileSync, writeFileSync, rmSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {spawnSync} from 'node:child_process';
const root=fileURLToPath(new URL('../',import.meta.url));
const targets=JSON.parse(readFileSync(join(root,'security/targets.json'),'utf8'));
const manifest=JSON.parse(readFileSync(join(root,'package.json'),'utf8'));
manifest.dependencies={...manifest.dependencies,...targets.dependencies};
manifest.devDependencies={...manifest.devDependencies,...targets.devDependencies};
manifest.engines={...manifest.engines,...targets.engines};
const staging=mkdtempSync(join(tmpdir(),'signalflow-security-resolve-'));
const npm=process.platform==='win32'?'npm.cmd':'npm';
try {
  writeFileSync(join(staging,'package.json'),JSON.stringify(manifest,null,2)+'\n');
  writeFileSync(join(staging,'package-lock.json'),readFileSync(join(root,'package-lock.json')));
  console.log(`Resolving checked targets from ${targets.checked_at}:`,targets.dependencies);
  const result=spawnSync(npm,['install','--package-lock-only','--prefer-online','--ignore-scripts','--no-audit','--no-fund','--fetch-retries=0','--fetch-timeout=10000'],{cwd:staging,encoding:'utf8'});
  writeFileSync(join(root,'audit/security/target-resolution.txt'),(result.stdout||'')+(result.stderr||'')+(result.error?String(result.error):''));
  if(result.status!==0){
    console.error(result.stderr||result.error||'Dependency resolution failed');
    console.error('Upgrade not applied: the project manifest, lockfile and node_modules were preserved.');
    process.exitCode=1;
  } else {
    const resolved=JSON.parse(readFileSync(join(staging,'package-lock.json'),'utf8'));
    for(const [name,version] of Object.entries({...targets.dependencies,...targets.devDependencies})){
      if(resolved.packages[`node_modules/${name}`]?.version!==version)throw new Error(`Unexpected resolution for ${name}`);
    }
    writeFileSync(join(root,'package.json'),JSON.stringify(manifest,null,2)+'\n');
    writeFileSync(join(root,'package-lock.json'),readFileSync(join(staging,'package-lock.json')));
    const installed=spawnSync(npm,['ci','--prefer-online','--no-audit','--no-fund'],{cwd:root,stdio:'inherit'});
    if(installed.status!==0)throw new Error('Target lockfile resolved, but installation failed. Run npm ci to finish; do not deploy.');
    console.log('Target versions installed. Run security:check, audit, typecheck, build and every test suite before deployment.');
  }
} finally {rmSync(staging,{recursive:true,force:true});}
