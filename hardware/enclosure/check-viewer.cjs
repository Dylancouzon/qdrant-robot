/* Check the offline viewer's data, lists, steps, and controls without a browser or graphics driver. */
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');

const source = fs.readFileSync(process.argv[2] || path.join(__dirname, 'output/robot-viewer.html'), 'utf8');
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1];
const parts = JSON.parse(source.match(/const parts = (.*);\n/)[1]);
const steps = JSON.parse(source.match(/const steps = (.*);\n/)[1]);

// Data: nine printed parts in white and black, hardware boxes, and fasteners.
const printed = parts.filter(p => p.kind === 'printed');
assert.equal(printed.length, 9);
assert.equal(printed.filter(p => p.color === '#e8e6df').length, 4);
assert.equal(printed.filter(p => p.color === '#2b2b2e').length, 5);
assert(parts.filter(p => p.kind === 'ghost').length >= 10);
assert(parts.filter(p => p.kind === 'fastener').length > 0);
assert(parts.every(p => ['printed', 'ghost', 'fastener'].includes(p.kind) && p.label && p.key));
assert(!parts.some(p => /regulator/i.test(p.name)), 'the servo regulator is gone (H5)');
assert(printed.every(p => p.moving === ['head-shell', 'visor', 'head-shaft', 'horn-disc'].includes(p.name)));
assert(source.length < 8e6, 'page is over 8 MB');

// Steps: about 20 to 28, grouped Neck, Head, Body, each with text, new parts, and valid mesh indices.
assert(steps.length >= 20 && steps.length <= 28, `${steps.length} steps`);
assert.deepEqual([...new Set(steps.map(s => s.group))], ['Neck', 'Head', 'Body']);
const valid = i => Number.isInteger(i) && i >= 0 && i < parts.length;
for (const [n, s] of steps.entries()) {
  const at = `step ${n + 1}`;
  assert(s.title && s.text, at);
  assert((s.text.match(/[.!?](\s|$)/g) || []).length <= 3, `${at} has over three sentences`);
  assert(!/[{}]/.test(s.text), `${at} has an unfilled fastener name`);
  assert(s.new.length > 0 && s.new.every(valid) && s.show.every(valid), at);
  assert(s.new.every(i => s.show.includes(i)), `${at} draws a new part that is not shown`);
  assert(Object.keys(s.offsets).every(i => s.show.includes(Number(i))), `${at} moves a part that is not shown`);
  assert(Object.values(s.offsets).every(v => v.length === 3 && v.every(Number.isFinite)), at);
  assert(Number.isFinite(s.tilt) && Math.abs(s.tilt) <= 180, at);
  assert(s.view.length === 3 && s.target.length === 3 && [...s.view, ...s.target].every(Number.isFinite), at);
  assert(!s.cut || s.new.every(i => !parts[i].shell), `${at} cuts away a shell it works on`);
}
const tilted = steps.filter(s => s.tilt);
assert(tilted.length >= 2 && tilted.every(s => Math.abs(s.tilt) > 90 && /rear face|Insert the head shaft/.test(s.title + s.text)), 'the shell lies on its rear face in the servo steps');
assert(new Set(steps.flatMap(s => s.show)).size === parts.length, 'some mesh never appears in a step');
assert(steps.some(s => /rear of the head floor/.test(s.text) && /roof hole/.test(s.text)), 'camera cable route');
assert(steps.some(s => /3 × M3 × 16 screw/.test(s.text)) && steps.some(s => /4 × M2 × 8 screw/.test(s.text)));
assert(/^Check the head turn/.test(steps.at(-1).title), 'the last step checks the head turn by hand');
assert(steps.some(s => /USB-A to 5\.5 × 2\.1 mm barrel cable/.test(s.text)));

// Lists: hardware, printed parts, fasteners, and one list item per step.
for (const id of ['hardware', 'printed-parts', 'fasteners', 'assembly']) {
  assert(source.includes(`id="${id}"`) && source.includes(`href="#${id}"`));
}
for (const p of printed) assert(source.includes(`data-part="${p.name}"`));
for (const name of ['Jetson', 'USB sound card', 'Speaker', 'Servo adapter board', 'Camera', 'Bearings', 'Angled USB cables']) {
  assert(source.includes(`<th scope='row'>${name}`), name);
}
const prose = source.replace(/<script>[\s\S]*<\/script>/, '');
for (const old of ['USB audio', 'bus board', 'Bus board', 'audio case']) assert(!prose.includes(old), `old name in the text: ${old}`);
assert(source.includes('17 M3 screws, 4 M2 screws, and 13 M3 nuts'));
assert.equal((source.match(/data-step="/g) || []).length, steps.length);
assert.equal((source.match(/<li>/g) || []).length, steps.length);
assert(source.includes('2.5 mm short-arm L-key from below') && source.includes('ball-end key'));

// Controls, with a mock WebGL context that rejects non-finite or empty draws.
const ids = Object.fromEntries([...source.matchAll(/id="([^"]+)"/g)].map(m => [m[1], {textContent: ''}]));
let width = 800, height = 600, draws = 0, orange = 0, buffers = 0, color = [], offsets = 0, tilt = 0;
const yawValues = new Set();
const gl = {};
for (const name of ['createShader', 'createProgram', 'createBuffer']) gl[name] = () => ({});
gl.getUniformLocation = (program, name) => ({name});
for (const name of ['shaderSource', 'compileShader', 'attachShader', 'linkProgram', 'useProgram', 'bindBuffer',
  'viewport', 'clearColor', 'enable', 'blendFunc', 'depthMask', 'clear', 'vertexAttribPointer', 'enableVertexAttribArray']) gl[name] = () => {};
gl.getShaderParameter = gl.getProgramParameter = () => true;
gl.getAttribLocation = () => 0;
gl.bufferData = (target, data) => { assert(data.length > 0 && data.every(Number.isFinite)); buffers++; };
gl.uniform1f = (target, value) => {
  assert(Number.isFinite(value));
  if (target.name === 'tilt') tilt = value;
  else yawValues.add(Math.round(value * 1000));
};
gl.uniform3f = (target, ...v) => { assert(v.length === 3 && v.every(Number.isFinite)); if (v.some(x => x !== 0)) offsets++; };
gl.uniform4fv = (target, value) => { assert(Array.from(value).every(Number.isFinite)); color = Array.from(value); };
for (const name of ['uniform3fv', 'uniformMatrix4fv']) gl[name] = (...args) => assert(Array.from(args.at(-1)).every(Number.isFinite));
gl.drawArrays = (mode, offset, count) => {
  assert(count > 0 && count % 3 === 0);
  draws++;
  if (Math.abs(color[0] - 1) < 1e-6 && Math.abs(color[1] - 0.48) < 1e-6) orange++;
};
ids.scene.getContext = () => gl;
ids.scene.getBoundingClientRect = () => ({width, height});
const views = ['three', 'front', 'rear', 'side'].map(view => ({dataset: {view}, setAttribute(name, value) { this[name] = value; }}));
const buttons = printed.map(p => ({dataset: {part: p.name}}));
const stepButtons = steps.map((s, n) => ({dataset: {step: String(n)}}));
const document = {
  getElementById: id => { assert(ids[id], id); return ids[id]; },
  querySelectorAll: selector => ({'[data-view]': views, '[data-part]': buttons, '[data-step]': stepButtons})[selector],
};
const context = {document, atob: s => Buffer.from(s, 'base64').toString('binary'), devicePixelRatio: 2, ResizeObserver: class { constructor(cb) { this.cb = cb; } observe() { this.cb(); } }};
vm.runInNewContext(script, context, {timeout: 30000});
vm.runInNewContext(script, {...context, document: {...document, getElementById: id => id === 'scene' ? {getContext: () => null} : ids[id]}});
assert(ids.error.textContent.includes('cannot display WebGL'));
assert(buffers === 2 * parts.length);
const drawsOf = action => { const before = draws; action(); return draws - before; };
const shellCount = parts.filter(p => p.shell).length;

// Free view draws every part. Next, Previous, and Free view walk the steps.
assert.equal(ids['step-count'].textContent, 'Free view');
assert.equal(drawsOf(() => ids.free.onclick()), parts.length, 'a frame draws every part');
assert(ids.prev.disabled && ids.free.disabled && !ids.next.disabled);
for (const [n, s] of steps.entries()) {
  const expected = s.show.filter(i => !(s.cut && parts[i].shell)).length;
  orange = offsets = 0;
  assert.equal(drawsOf(() => ids.next.onclick()), expected, `step ${n + 1} draws the fitted parts`);
  assert.equal(ids['step-title'].textContent, s.title);
  assert.equal(ids['step-text'].textContent, s.text);
  assert.equal(ids['step-count'].textContent, `${s.group}, step ${n + 1} of ${steps.length}`);
  assert.equal(orange, s.new.length, `step ${n + 1} colors its new parts orange`);
  const moved = Object.keys(s.offsets).filter(i => !(s.cut && parts[i].shell)).length;
  assert.equal(offsets, moved, `step ${n + 1} offsets its moved parts`);
  assert.equal(ids.shells.checked, !s.cut);
  assert(Math.abs(tilt - s.tilt * Math.PI / 180) < 1e-9, `step ${n + 1} sets the scene tilt`);
  assert.equal(ids.prev.disabled, n === 0);
}
assert(ids.next.disabled && !ids.free.disabled);
ids.prev.onclick();
assert.equal(ids['step-title'].textContent, steps.at(-2).title);
stepButtons[3].onclick();
assert.equal(ids['step-title'].textContent, steps[3].title);
assert.equal(drawsOf(() => ids.free.onclick()), parts.length);
assert.equal(tilt, 0, 'the free view is level');
ids.next.onclick();
assert.equal(ids['step-title'].textContent, steps[0].title);
ids.free.onclick();
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
assert.equal(drawsOf(() => ids.shells.onchange({target: {checked: false}})), parts.length - shellCount);
assert.equal(drawsOf(() => ids.ghosts.onchange({target: {checked: false}})), printed.length - shellCount);
ids.shells.onchange({target: {checked: true}});
ids.ghosts.onchange({target: {checked: true}});
for (const button of buttons) button.onclick();
const dragged = {preventDefault() {}};
ids.scene.onpointerdown({clientX: 10, clientY: 10});
ids.scene.onpointermove({clientX: 60, clientY: 40});
ids.scene.onpointerup();
ids.scene.onwheel({deltaY: 100, ...dragged});
ids.scene.onkeydown({key: 'ArrowLeft', ...dragged});
console.log(`Viewer check passed: ${parts.length} meshes (${printed.length} printed), ${steps.length} steps, ${(source.length / 1e6).toFixed(2)} MB, ` +
  'lists, Previous, Next, and Free view, orange new parts, offsets, head turn at -80 and 80 degrees, view, cutaway, highlight, and drag controls. Browser pixels remain unverified.');
