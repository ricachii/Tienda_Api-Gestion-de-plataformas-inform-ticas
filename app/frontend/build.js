// build.js (moved to app/frontend)
// Bundles frontend JS with esbuild and copies static files to root dist/
const { build } = require('esbuild');
const fs = require('fs');
const path = require('path');

// root is repo root (two levels above this file: repoRoot/app/frontend)
const root = path.resolve(__dirname, '..', '..');
const frontend = path.join(root, 'app', 'frontend');
const out = path.join(root, 'dist');

async function run(){
  if(!fs.existsSync(out)) fs.mkdirSync(out);
  // copy static files (html, css)
  fs.copyFileSync(path.join(frontend,'index.html'), path.join(out,'index.html'));
  fs.copyFileSync(path.join(frontend,'css','style.css'), path.join(out,'style.css'));
  // bundle JS
  await build({
    entryPoints: [path.join(frontend,'js','main.js')],
    bundle:true,
    minify:true,
    sourcemap:true,
    outdir: path.join(out,'js')
  });
  console.log('Built frontend ->', out);
}

run().catch(e=>{ console.error(e); process.exit(1); });
