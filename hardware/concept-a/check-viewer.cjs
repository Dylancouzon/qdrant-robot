/* Check offline viewer interactions and finite drawing coordinates without a browser. */
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, 'output/layout-viewer.html'), 'utf8');
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1];
let width = 736, height = 570, drawings = 0;
const coordinates = [];
const context2d = {};
for (const name of ['setTransform', 'fillRect', 'beginPath', 'closePath', 'fill', 'stroke',
                     'fillText', 'setLineDash']) context2d[name] = () => { if (name === 'fillRect') drawings++; };
for (const name of ['moveTo', 'lineTo', 'arc']) context2d[name] = (...args) => {
  assert(args.every(Number.isFinite), 'Drawing coordinates must be finite');
  coordinates.push(args);
};
function element() {
  return {dataset: {}, style: {}, children: [], textContent: '',
          append(...items) { this.children.push(...items); },
          setAttribute(name, value) { this[name] = value; }};
}
const ids = Object.fromEntries([...source.matchAll(/id="([^"]+)"/g)].map(m => [m[1], element()]));
ids.scene.getContext = () => context2d;
ids.scene.getBoundingClientRect = () => ({width, height});
const views = ['iso', 'front', 'side', 'top'].map(view => Object.assign(element(), {dataset: {view}}));
const document = {
  documentElement: element(),
  getElementById(id) { assert(ids[id], `Missing element ${id}`); return ids[id]; },
  createElement: element,
  createTextNode: value => value,
  querySelectorAll(selector) {
    if (selector === '[data-view]') return views;
    if (selector === '#components button') return ids.components.children;
    throw Error(`Unrecognized selector ${selector}`);
  }
};
const context = vm.createContext({document, console, devicePixelRatio: 2,
  getComputedStyle: () => ({colorScheme: 'light'}),
  matchMedia: () => ({matches: false, addEventListener() {}}),
  ResizeObserver: class { constructor(callback) { this.callback = callback; }
    observe() { this.callback(); } }});
vm.runInContext(script, context, {timeout: 5000});
for (const dimensions of [[320, 440], [736, 570], [1200, 570]]) {
  [width, height] = dimensions;
  for (const view of views) {
    view.onclick();
    assert.equal(views.filter(v => v['aria-pressed'] === 'true').length, 1);
    for (const angle of [-80, 0, 80]) {
      ids.yaw.oninput({target: {value: String(angle)}});
      assert.equal(ids['yaw-value'].textContent, angle + '°');
    }
  }
}
for (const button of ids.components.children) {
  button.onclick();
  assert.equal(ids['selected-name'].textContent, button.dataset.name);
  assert.equal(ids.components.children.filter(b => b['aria-pressed'] === 'true').length, 1);
}
ids.spaces.onchange({target: {checked: false}});
ids.spaces.onchange({target: {checked: true}});
assert(ids['check-summary'].textContent.includes('packaging checks pass'));
assert(ids['open-items'].children.length >= 5);
assert(drawings >= 40 && coordinates.length > 1000);
console.log(`Viewer logic passed: ${drawings} draws, three widths, four views, yaw limits, all selections. Browser appearance remains unverified.`);
