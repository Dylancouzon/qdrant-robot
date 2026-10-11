/* Verify offline CAD data and controls without a browser or graphics driver. */
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, 'output/assembly/robot-viewer.html'), 'utf8');
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1];
const ids = Object.fromEntries([...source.matchAll(/id="([^"]+)"/g)].map(m => [m[1], {textContent: ''}]));
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
const document = {getElementById: id => {assert(ids[id]);return ids[id];},querySelectorAll: () => views};
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
assert(buffers >= 60 && draws > 1000);
console.log(`CAD viewer logic passed: ${buffers/2} meshes, ${draws} draws, three widths, four views, head yaw, cover and envelope controls. Browser pixels remain unverified.`);
