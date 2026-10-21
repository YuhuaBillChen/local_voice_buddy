// Runs inside a pinned upstream checkout. No upstream source is overwritten.
import * as esbuild from 'esbuild';
import fs from 'node:fs';
import path from 'node:path';
const [entry,out] = process.argv.slice(2);
fs.mkdirSync(out,{recursive:true});
// The answer runs in a sandbox without same-origin access, where reading localStorage throws.
// Components only use it for preferences, so give them a per-page store before any module runs.
const storage='(()=>{for(const name of ["localStorage","sessionStorage"]){try{window[name].length}catch(e){const m=new Map();'+
 'Object.defineProperty(window,name,{configurable:true,value:{getItem:k=>m.has(k)?m.get(k):null,setItem:(k,v)=>m.set(String(k),String(v)),'+
 'removeItem:k=>m.delete(k),clear:()=>m.clear(),key:i=>[...m.keys()][i]??null,get length(){return m.size}}})}}})();';
await esbuild.build({entryPoints:[entry],outfile:path.join(out,'buddy-openui.js'),bundle:true,minify:true,banner:{js:storage},
 format:'iife',target:'es2020',jsx:'automatic',alias:{'@':path.resolve('src')},
 nodePaths:[path.resolve('node_modules')],define:{'process.env.NODE_ENV':'"production"','process.env.NEXT_PUBLIC_BASE_PATH':'""'},
 loader:{'.svg':'dataurl','.png':'dataurl','.woff2':'dataurl','.woff':'empty','.ttf':'empty'},
 plugins:[{name:'local-map-worker',setup(build){build.onLoad({filter:/components\/map\/basemap\.ts$/},async args=>{
  const original=await fs.promises.readFile(args.path,'utf8');
  const site='new URL("maplibre-gl/dist/maplibre-gl-worker.mjs", import.meta.url).toString()';
  if(original.split(site).length!==2)throw Error('upstream map worker site changed');
  return {contents:original.replace(site,'new URL("map-worker.js", document.querySelector("script[data-buddy-openui]").src).href'),loader:'ts',resolveDir:path.dirname(args.path)};
 });build.onLoad({filter:/components\/map\/use-street-route\.ts$/},async args=>{
  const original=await fs.promises.readFile(args.path,'utf8');
  const site='withBase(`/api/street-route?coords=${encodeURIComponent(routingKey)}`)';
  const points='data.points ?? []';
  if(original.split(site).length!==2||original.split(points).length!==2)throw Error('upstream map routing sites changed');
  return {contents:original.replace(site,'`https://router.project-osrm.org/route/v1/driving/${routingKey}?overview=full&geometries=geojson`')
   .replace('const data: { points?: unknown[] }','const data: any').replace(points,'data.routes?.[0]?.geometry?.coordinates?.map((p: number[]) => [p[1],p[0]]) ?? []'),loader:'ts',resolveDir:path.dirname(args.path)};
 });}}]});
fs.copyFileSync('node_modules/maplibre-gl/dist/maplibre-gl-worker.mjs',path.join(out,'map-worker.js'));
// Use the pinned upstream generated reference, keeping only supported components.
const prompt=fs.readFileSync('src/generated/system-prompt.txt','utf8');
const lines=prompt.split('\n').map(l=>l.startsWith('Image(')?'Image(src: string, alt: string, aspectRatio?: number, radius?: number, fit?: "cover" | "contain") — Display a supplied HTTPS image URL. No image search or automatic fallback.':l).filter(l=>! /^(SearchImage|HtmlView|YouTube)\(/.test(l));
fs.writeFileSync(path.join(out,'reference.txt'),lines.join('\n'));
fs.copyFileSync('LICENSE',path.join(out,'LICENSE-open-intelligent-ui.txt'));
const notices=['Open Intelligent UI (MIT)\n'+fs.readFileSync('LICENSE','utf8')];
// esbuild retains bundled legal comments. Also include installed package notices
// in a separately downloadable file, including packages without /*! comments.
const seen=new Set();function walk(dir){for(const item of fs.readdirSync(dir,{withFileTypes:true})){
 if(!item.isDirectory()||item.name.startsWith('.'))continue;const p=path.join(dir,item.name);
 if(item.name.startsWith('@')){walk(p);continue;}
 const pkg=path.join(p,'package.json');if(!fs.existsSync(pkg))continue;
 const meta=JSON.parse(fs.readFileSync(pkg,'utf8'));const key=meta.name+'@'+meta.version;if(seen.has(key))continue;seen.add(key);
 for(const file of fs.readdirSync(p).filter(n=>/^(licen[cs]e|copying|notice)(\.|$)/i.test(n))){const target=path.join(p,file);if(fs.statSync(target).isFile())notices.push(key+' — '+file+'\n'+fs.readFileSync(target,'utf8'));}
 if(fs.existsSync(path.join(p,'node_modules')))walk(path.join(p,'node_modules'));
}}walk('node_modules');
fs.writeFileSync(path.join(out,'THIRD_PARTY_NOTICES.txt'),notices.join('\n\n---\n\n'));
fs.writeFileSync(path.join(out,'upstream.json'),JSON.stringify({repository:'https://github.com/thesysdev/open-intelligent-ui',commit:'03213439358bf3408ad61a46ec9e3230c5572e48',license:'MIT'},null,2));

fs.copyFileSync(path.join(path.dirname(entry),'host.js'),path.join(out,'host.js'));
