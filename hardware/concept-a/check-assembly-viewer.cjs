/* Verify offline CAD data and controls without a browser or graphics driver. */
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const source = fs.readFileSync(process.argv[2] || path.join(__dirname, 'output/assembly/robot-viewer.html'), 'utf8');
const isStudy = source.includes('const study=true;');
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1];
const ids = Object.fromEntries([...source.matchAll(/id="([^"]+)"/g)].map(m => [m[1], {textContent: '',children:[],appendChild(child){this.children.push(child);}}]));
let width = 800, height = 650, draws = 0, buffers = 0;
const gl = {};
for (const name of ['createShader','createProgram','createBuffer','getUniformLocation']) gl[name] = () => ({});
for (const name of ['shaderSource','compileShader','attachShader','linkProgram','useProgram','bindBuffer',
  'viewport','clearColor','enable','clear','vertexAttribPointer','enableVertexAttribArray']) gl[name] = () => {};
gl.getShaderParameter = gl.getProgramParameter = () => true;
gl.getAttribLocation = () => 0;
gl.bufferData = (target, data) => {assert(data.length > 0 && Array.from(data).every(Number.isFinite)); buffers++;};
for (const name of ['uniform1f','uniform2f']) gl[name] = (target, ...data) => assert(data.every(Number.isFinite));
for (const name of ['uniform2fv','uniform3fv']) gl[name] = (target, data) => assert(data.every(Number.isFinite));
gl.drawArrays = (mode, offset, count) => {assert(count > 0 && count % 3 === 0); draws++;};
ids.scene.getContext = () => gl;
ids.scene.getBoundingClientRect = () => ({width, height});
const views = ['three','front','rear','side'].map(view => ({dataset: {view}, setAttribute(name,value){this[name]=value;}}));
const document = {createElement: () => ({}),getElementById: id => {assert(ids[id]);return ids[id];},querySelectorAll: selector => selector === '.assembly-only' ? [ids.step,ids.yaw,ids.open,ids.explode] : views};
vm.runInNewContext(script, {document,devicePixelRatio:2,console,ResizeObserver:class{constructor(cb){this.cb=cb;}observe(){this.cb();}}}, {timeout:15000});
for (const dimensions of [[320,460],[800,650],[1200,650]]) {
  [width,height] = dimensions;
  for (const view of views) {
    view.onclick(); assert.equal(views.filter(v=>v['aria-pressed']==='true').length,1);
    for (const angle of [-80,0,80]) {
      ids.yaw.oninput({target:{value:String(angle)}});
      assert.equal(ids['yaw-value'].textContent,angle+'°');
    }
  }
}
for (const open of [true,false]) for (const hardware of [true,false]) {
 ids.open.onchange({target:{checked:open}});ids.hardware.onchange({target:{checked:hardware}});
}
for(const id of ['shell','reservations','explode'])for(const checked of [true,false])ids[id].onchange({target:{checked}});
for(let step=0;step<=6;step++){ids.step.oninput({target:{value:String(step)}});assert(ids['step-note'].textContent);}
assert(ids.part.children.length>(isStudy?10:30));
for(let i=0;i<ids.part.children.length;i++){ids.part.onchange({target:{value:String(i)}});assert(ids['part-detail'].textContent.includes('mm.'));}
ids.part.onchange({target:{value:''}});
ids.step.oninput({target:{value:'6'}});
ids.open.onchange({target:{checked:false}});
ids.hardware.onchange({target:{checked:false}});
ids.reservations.onchange({target:{checked:false}});
const data = JSON.parse(source.match(/const parts=(.*);/)[1]);
if(!isStudy){
assert.equal(data.filter(p=>p.name.startsWith('bearing_')).length,2);
assert(!data.some(p=>p.name==='manual_drive_gear'));
assert(source.includes('overall 236 mm'));
assert(source.includes('head 116 × 80 × 56 mm'));
assert(data.find(p=>p.name==='body-roof').stage < data.find(p=>p.name==='tower_left').stage);
assert(data.find(p=>p.name==='roof-bridge').stage > data.find(p=>p.name==='tower_left').stage);
assert(data.find(p=>p.name==='body-right').stage <= data.find(p=>p.name==='body-roof').stage);
assert(data.find(p=>p.name==='neck-cover').stage < data.find(p=>p.name==='head-front').stage);
for(const name of ['head-front','body-roof','tower_left','neck-cover','roof-bridge'])assert.equal(data.find(p=>p.name===name).service_removed,true);
assert.equal(data.find(p=>p.name==='jetson-cradle').service_removed,false);
}
if(isStudy)for(const id of ['step','yaw','open','explode'])assert.equal(ids[id].hidden,true);
const beforeInterior = draws;
ids.shell.onchange({target:{checked:true}});
assert.equal(draws-beforeInterior,data.filter(p=>!p.hardware&&!p.exterior).length);
if(!isStudy){
const cradleIndex = data.findIndex(p=>p.name==='jetson-cradle');
ids.part.onchange({target:{value:String(cradleIndex)}});
assert.equal(ids.shell.checked,true);
assert(ids['part-detail'].textContent.includes('Jetson cradle'));
}
assert(buffers >= (isStudy?20:60) && draws > (isStudy?200:1000));
const controls = isStudy ? 'candidate limits, hidden assembly controls, interior, reservations, and component inspection' : 'head yaw, assembly stages, separation, interior, covers, reservations, and component inspection';
console.log(`CAD viewer logic passed: ${buffers/2} meshes, ${draws} draws, three widths, four views, ${controls}. Browser pixels remain unverified.`);
