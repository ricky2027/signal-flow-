// Verifies installed and locked versions against this audit's explicit targets.
// It does not replace a current npm audit of the complete dependency graph.
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {join} from 'node:path';
const root=fileURLToPath(new URL('../',import.meta.url));
const target=JSON.parse(readFileSync(join(root,'security/targets.json'),'utf8'));
const lock=JSON.parse(readFileSync(join(root,'package-lock.json'),'utf8'));
let failures=0;
for(const [name,version] of Object.entries({...target.dependencies,...target.devDependencies})){
  let installed;
  try {installed=JSON.parse(readFileSync(join(root,'node_modules',name,'package.json'),'utf8')).version;}
  catch {installed='missing';}
  const locked=lock.packages[`node_modules/${name}`]?.version;
  if(installed!==version||locked!==version){console.error(`${name}: installed=${installed}, locked=${locked}, checked target=${version}`);failures++;}
}
for(const [path,pkg] of Object.entries(lock.packages)){
  if(path.endsWith('/postcss')&&pkg.version!==target.devDependencies.postcss){console.error(`${path}: old PostCSS ${pkg.version} remains`);failures++;}
}
if(failures){console.error('Security upgrade is incomplete. Do not deploy.');process.exitCode=1;}
else console.log('Installed/locked targets match. A successful full npm audit and application/browser acceptance are still required.');
