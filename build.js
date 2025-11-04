// Minimal build script: bundle frontend JS with esbuild and copy static files to dist/
const { build } = require('esbuild');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname);
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
