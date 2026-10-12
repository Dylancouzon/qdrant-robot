/* Check the offline viewer's data, lists, and controls without a browser or graphics driver. */
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');

const source = fs.readFileSync(process.argv[2] || path.join(__dirname, 'output/robot-viewer.html'), 'utf8');
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1];
const parts = JSON.parse(source.match(/const parts = (.*);\n/)[1]);

// Data: nine printed parts plus the hardware ghosts, in white and black.
const printed = parts.filter(p => !p.ghost);
assert.equal(printed.length, 9);
assert.equal(printed.filter(p => p.color === '#e8e6df').length, 4);
assert.equal(printed.filter(p => p.color === '#2b2b2e').length, 5);
assert(parts.filter(p => p.ghost).length >= 10);
assert(printed.every(p => p.moving === ['head-shell', 'visor', 'head-shaft', 'horn-disc'].includes(p.name)));
assert(source.length < 8e6, 'page is over 8 MB');

// Lists: printed parts, fasteners, and the twelve assembly steps.
for (const id of ['printed-parts', 'fasteners', 'assembly']) {
  assert(source.includes(`id="${id}"`) && source.includes(`href="#${id}"`));
}
for (const p of printed) assert(source.includes(`data-part="${p.name}"`));
assert(source.includes('17 M3 screws, 4 M2 screws, and 13 M3 nuts'));
assert.equal((source.match(/<li>/g) || []).length, 12);
assert(source.includes('2.5 mm short-arm L-key from below') && source.includes('ball-end key'));

// Controls, with a mock WebGL context that rejects non-finite or empty draws.
const ids = Object.fromEntries([...source.matchAll(/id="([^"]+)"/g)].map(m => [m[1], {textContent: ''}]));
let width = 800, height = 600, draws = 0, buffers = 0, yawValues = new Set();
const gl = {};
for (const name of ['createShader', 'createProgram', 'createBuffer', 'getUniformLocation']) gl[name] = () => ({});
for (const name of ['shaderSource', 'compileShader', 'attachShader', 'linkProgram', 'useProgram', 'bindBuffer',
  'viewport', 'clearColor', 'enable', 'blendFunc', 'depthMask', 'clear', 'vertexAttribPointer', 'enableVertexAttribArray']) gl[name] = () => {};
gl.getShaderParameter = gl.getProgramParameter = () => true;
gl.getAttribLocation = () => 0;
gl.bufferData = (target, data) => { assert(data.length > 0 && data.every(Number.isFinite)); buffers++; };
gl.uniform1f = (target, value) => { assert(Number.isFinite(value)); yawValues.add(Math.round(value * 1000)); };
for (const name of ['uniform3fv', 'uniform4fv', 'uniformMatrix4fv']) gl[name] = (...args) => assert(Array.from(args.at(-1)).every(Number.isFinite));
gl.drawArrays = (mode, offset, count) => { assert(count > 0 && count % 3 === 0); draws++; };
ids.scene.getContext = () => gl;
ids.scene.getBoundingClientRect = () => ({width, height});
const views = ['three', 'front', 'rear', 'side'].map(view => ({dataset: {view}, setAttribute(name, value) { this[name] = value; }}));
const buttons = printed.map(p => ({dataset: {part: p.name}}));
const document = {
  getElementById: id => { assert(ids[id], id); return ids[id]; },
  querySelectorAll: selector => selector === '[data-view]' ? views : buttons,
};
const context = {document, atob: s => Buffer.from(s, 'base64').toString('binary'), devicePixelRatio: 2, ResizeObserver: class { constructor(cb) { this.cb = cb; } observe() { this.cb(); } }};
vm.runInNewContext(script, context, {timeout: 30000});
vm.runInNewContext(script, {...context, document: {...document, getElementById: id => id === 'scene' ? {getContext: () => null} : ids[id]}});
assert(ids.error.textContent.includes('cannot display WebGL'));
assert(buffers === 2 * parts.length);
const drawsOf = action => { const before = draws; action(); return draws - before; };
assert.equal(drawsOf(() => views[0].onclick()), parts.length, 'a frame draws every part');
for (const [w, h] of [[320, 420], [800, 600], [1100, 600]]) {
  [width, height] = [w, h];
  for (const view of views) {
    view.onclick();
    assert.equal(views.filter(v => v['aria-pressed'] === 'true').length, 1);
  }
}
for (const angle of [-80, 0, 80]) {
  ids.yaw.oninput({target: {value: String(angle)}});
  assert.equal(ids['yaw-value'].textContent, angle + '°');
}
assert(yawValues.has(Math.round(80 * Math.PI / 180 * 1000)) && yawValues.has(Math.round(-80 * Math.PI / 180 * 1000)));
assert.equal(drawsOf(() => ids.shells.onchange({target: {checked: false}})), parts.length - parts.filter(p => p.shell).length);
assert.equal(drawsOf(() => ids.ghosts.onchange({target: {checked: false}})), printed.length - parts.filter(p => p.shell).length);
ids.shells.onchange({target: {checked: true}});
ids.ghosts.onchange({target: {checked: true}});
for (const button of buttons) button.onclick();
let dragged = {preventDefault() {}};
ids.scene.onpointerdown({clientX: 10, clientY: 10});
ids.scene.onpointermove({clientX: 60, clientY: 40});
ids.scene.onpointerup();
ids.scene.onwheel({deltaY: 100, ...dragged});
ids.scene.onkeydown({key: 'ArrowLeft', ...dragged});
console.log(`Viewer check passed: ${parts.length} meshes (${printed.length} printed), ${(source.length / 1e6).toFixed(2)} MB, ` +
  'lists, head turn at -80 and 80 degrees, view, cutaway, highlight, and drag controls. Browser pixels remain unverified.');
