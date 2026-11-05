import {execFileSync} from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
const dir=fs.mkdtempSync(path.join(os.tmpdir(),'survey-css-'));
try {
 const output=path.join(dir,'design.css');
 execFileSync(process.execPath,['node_modules/@tailwindcss/cli/dist/index.mjs','-i','scripts/design.source.css','-o',output,'--minify'],{stdio:'inherit'});
 if(fs.readFileSync(output,'utf8')!==fs.readFileSync('scripts/design.css','utf8'))throw new Error('Compiled design.css is stale; run npm run design:build');
 console.log('Compiled Tailwind stylesheet matches source');
} finally {fs.rmSync(dir,{recursive:true,force:true});}
