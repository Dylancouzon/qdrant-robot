"""Offline robot viewer: output/robot-viewer.html shows the assembled robot with a head turn
control, the printed parts, the fasteners, and the assembly steps. Run bambu.py first (it supplies
times and grams), then run this with build/hardware-layout/venv/bin/python. Check it with
check-viewer.cjs.
"""

import base64
import json
import re
import sys
from html import escape
from pathlib import Path

import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent)]
import body  # noqa: E402
import head  # noqa: E402

OUT = HERE / "output" / "robot-viewer.html"
WHITE, BLACK = "#e8e6df", "#2b2b2e"
# stem: (color, print orientation); print order is the table order
PARTS = {
    "body-shell": ("White", "Upside down, roof on the bed"),
    "base-plate": ("White", "Flat, underside on the bed"),
    "port-panel": ("White", "Outside face on the bed"),
    "head-shell": ("White", "Rear face on the bed"),
    "visor": ("Black", "Front face on the bed"),
    "speaker-grille": ("Black", "Inside face on the bed"),
    "neck-hub": ("Black", "Lower face on the bed"),
    "head-shaft": ("Black", "Flange on the bed"),
    "horn-disc": ("Black", "Flat on the bed"),
}
# screw group: (what it holds, nut, tool); counts and lengths come from the CAD constants
SCREWS = {
    "hub": ("Hub to the roof", True, "2.5 mm hex key from above"),
    "center": ("Shaft to the horn disc", True, "2.5 mm hex key from above"),
    "horn": ("Horn disc to the servo horn", False, "2.5 mm hex key through the disc"),
    "head": ("Head to the shaft flange", True, "2.5 mm ball-end key through the front, about 20°"),
    "visor": ("Visor to the head", True, "2.5 mm short-arm L-key from below"),
    "plate": ("Base plate to the shell", True, "2.5 mm hex key from below"),
    "panel": ("Port panel to the plate ear", True, "2.5 mm hex key from outside"),
}
GHOSTS = {  # name: color; every ghost is a translucent reference part
    "Jetson": "#477967",
    "Speaker": "#555960",
    "USB audio case": "#767a84",
    "Bus board": "#9a8d66",
    "Servo regulator": "#b29664",
    "servo case": "#74738f",
    "servo horn": "#a6a2b6",
    "bearing lower": "#8fa3b8",
    "bearing upper": "#8fa3b8",
    "camera board": "#3d6a9e",
    "camera lens holder": "#3d6a9e",
    "camera heatsink": "#3d6a9e",
    "camera connector": "#3d6a9e",
}
SHELLS = {"body-shell", "port-panel", "head-shell", "visor"}  # hidden by the cutaway control
MOVING = {"head-shell", "visor", "head-shaft", "horn-disc", "servo horn"}  # turn with the head


STEMS = {  # head.build() names to part names
    "head shell": "head-shell",
    "visor": "visor",
    "hub": "neck-hub",
    "head shaft": "head-shaft",
    "horn disc": "horn-disc",
}


def mesh_of(solid):
    vertices, faces = solid.tessellate(0.1, 0.3)
    mesh = trimesh.Trimesh([v.toTuple() for v in vertices], faces)
    mesh.merge_vertices()
    return mesh


def encode(array):
    return base64.b64encode(np.ascontiguousarray(array).tobytes()).decode()


def entry(name, label, color, ghost, solid):
    mesh = mesh_of(solid)
    return dict(
        name=name,
        label=label,
        color=color,
        ghost=ghost,
        shell=name in SHELLS,
        moving=name in MOVING or name.startswith("camera"),
        vertices=encode(mesh.vertices.astype(np.float32)),
        indices=encode(mesh.faces.astype(np.uint32)),
    )


def scene():
    "Every drawn mesh as JSON: base64 float32 vertices and uint32 triangle indices."
    solids = body.build_all()["assembly"] | {STEMS[k]: v for k, v in head.build()[0].items()}
    ghosts = {k: body.box(*b) for k, b in body.components().items()} | head.ghost_solids()
    out = [
        entry(n, n, WHITE if PARTS[n][0] == "White" else BLACK, False, solid)
        for n, solid in solids.items()
    ]
    return out + [entry(n, n[0].upper() + n[1:], GHOSTS[n], True, s) for n, s in ghosts.items()]


def fastener_rows():
    "(screw, length, count, nut, holds, tool) per group, from the CAD constants."
    counts = {name: (len(xys), length) for name, xys, _, length, _, _ in head.SCREWS}
    counts["plate"] = (len(body.plate_screws()), body.PLATE_SCREW_LEN)
    counts["panel"] = (1, body.PANEL_SCREW_LEN)
    rows = []
    for name, (holds, nut, tool) in SCREWS.items():
        count, length = counts[name]
        rows.append(("M3", int(length), count, nut, holds, tool))
    return rows + [("M2", head.M2_LENGTH, 4, False, "Camera to the visor posts", "M2 driver")]


def steps():
    "Numbered steps of the Assemble section in ASSEMBLY.md, as HTML."
    text = (HERE / "ASSEMBLY.md").read_text().split("## Assemble")[1].split("\n## ")[0]
    rows = re.findall(r"^\d+\. (.*)$", text, re.M)
    assert len(rows) == 12, rows
    bold = re.compile(r"[*][*](.*?)[*][*]")
    return "".join(f"<li>{bold.sub(r'<strong>\1</strong>', escape(r))}</li>" for r in rows)


def parts_table():
    slices = {
        Path(r["part"]).name: r
        for r in json.loads((HERE / "output" / "bambu" / "slice-checks.json").read_text())["parts"]
        if r["part"].startswith("Required")
    }
    assert set(slices) == set(PARTS), set(slices) ^ set(PARTS)
    rows = ""
    for stem, (color, orientation) in PARTS.items():
        s = slices[stem]
        size = " × ".join(f"{v:g}" for v in s["size_mm"])
        button = f'<button type="button" data-part="{stem}">{stem}</button>'
        rows += (
            f"<tr><td>{button}</td><td>{color}</td><td>{orientation}</td><td>{size}</td>"
            f"<td>{s['seconds'] / 3600:.1f} h</td><td>{s['grams']:.0f} g</td></tr>"
        )
    hours = sum(s["seconds"] for s in slices.values()) / 3600
    grams = sum(s["grams"] for s in slices.values())
    return rows, f"{hours:.1f} h and {grams:.0f} g of PLA in total"


def fastener_table():
    rows = fastener_rows()
    html = "".join(
        f"<tr><td>{s} × {n}</td><td>{length} mm</td><td>{'yes' if nut else 'no'}</td>"
        f"<td>{holds}</td><td>{tool}</td></tr>"
        for s, length, n, nut, holds, tool in rows
    )
    m3 = sum(n for s, _, n, _, _, _ in rows if s == "M3")
    nuts = sum(n for _, _, n, nut, _, _ in rows if nut)
    return html, f"{m3} M3 screws, 4 M2 screws, and {nuts} M3 nuts"


def main():
    data = scene()
    part_rows, print_total = parts_table()
    fastener_rows_html, fastener_total = fastener_table()
    html = (
        TEMPLATE.replace("__DATA__", json.dumps(data, separators=(",", ":")))
        .replace("__PART_ROWS__", part_rows)
        .replace("__PRINT_TOTAL__", print_total)
        .replace("__FASTENER_ROWS__", fastener_rows_html)
        .replace("__FASTENER_TOTAL__", fastener_total)
        .replace("__STEPS__", steps())
    )
    OUT.write_text(html)
    print(f"{OUT.name}: {len(html) / 1e6:.2f} MB, {len(data)} meshes; {fastener_total}")


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Robot viewer</title>
<style>
:root{--bg:#f4f2ec;--fg:#282b30;--card:#fffdf7;--line:#d6d2c8;--accent:#275c71;--muted:#5d6168}
@media(prefers-color-scheme:dark){:root{--bg:#1b1d21;--fg:#e6e4de;--card:#25282d;--line:#3a3e45;--accent:#8fc3d8;--muted:#a3a7ae}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif}
main{max-width:1100px;margin:auto;padding:24px 16px}
h1{font-size:26px;margin:0 0 8px}h2{margin-top:32px}
a{color:var(--accent)}
canvas{width:100%;height:600px;display:block;border-radius:16px;background:#dfe3e8;touch-action:none}
.controls{display:flex;flex-wrap:wrap;gap:12px 24px;align-items:center;margin:12px 0}
.controls label{display:flex;gap:8px;align-items:center}
button{border:1px solid var(--line);background:var(--card);color:inherit;border-radius:8px;padding:8px 12px;cursor:pointer;font:inherit}
button[aria-pressed=true]{background:var(--fg);color:var(--bg)}
canvas:focus-visible,button:focus-visible,input:focus-visible{outline:3px solid var(--accent);outline-offset:3px}
.wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:14px}
th,td{text-align:left;vertical-align:top;padding:8px 12px;border-bottom:1px solid var(--line)}
li{margin:10px 0}.note{font-size:14px;color:var(--muted)}#error{color:#b03030}
@media(max-width:720px){canvas{height:420px}}
</style></head><body><main>
<h1>Robot enclosure</h1>
<p>Nine printed parts, white and black, around the reference hardware. Drag to turn the view, scroll to zoom, and use the arrow keys when the view has focus. Translucent parts are hardware, not printed.</p>
<nav class="controls" aria-label="Page sections"><a href="#printed-parts">Printed parts</a><a href="#fasteners">Fasteners</a><a href="#assembly">Assembly steps</a></nav>
<canvas id="scene" tabindex="0" aria-label="Interactive 3D view of the assembled robot"></canvas>
<p id="error" role="alert"></p>
<div class="controls">
<span role="group" aria-label="View"><button data-view="three" aria-pressed="true">3D</button> <button data-view="front" aria-pressed="false">Front</button> <button data-view="rear" aria-pressed="false">Rear</button> <button data-view="side" aria-pressed="false">Port side</button></span>
<label for="yaw">Head turn <input id="yaw" type="range" min="-80" max="80" value="0" step="1"> <output id="yaw-value">0°</output></label>
<label><input id="shells" type="checkbox" checked> Show shells</label>
<label><input id="ghosts" type="checkbox" checked> Show hardware</label>
<span id="count" class="note"></span>
</div>
<section id="printed-parts"><h2>Printed parts</h2>
<p>Select a part name to highlight it in orange. All parts print in PLA with a 0.4 mm nozzle, 0.2 mm layers, and no supports.</p>
<div class="wrap"><table><caption class="note">Print orientation, size, and the Bambu Studio estimate for the P1S</caption><thead><tr><th scope="col">Part</th><th scope="col">Color</th><th scope="col">Orientation</th><th scope="col">Size (mm)</th><th scope="col">Time</th><th scope="col">PLA</th></tr></thead><tbody>__PART_ROWS__</tbody></table></div>
<p class="note">Estimate: __PRINT_TOTAL__. Print the coupon plate first.</p></section>
<section id="fasteners"><h2>Fasteners</h2>
<div class="wrap"><table><caption class="note">__FASTENER_TOTAL__</caption><thead><tr><th scope="col">Screw</th><th scope="col">Length</th><th scope="col">M3 nut</th><th scope="col">Holds</th><th scope="col">Tool</th></tr></thead><tbody>__FASTENER_ROWS__</tbody></table></div></section>
<section id="assembly"><h2>Assembly steps</h2>
<ol>__STEPS__</ol>
<p>Service is the same steps in reverse. The full guide is in ASSEMBLY.md.</p></section>
</main><script>
'use strict';
const parts = __DATA__;
const $ = id => document.getElementById(id);
const canvas = $('scene');
const gl = canvas.getContext('webgl', {antialias: true});
const VIEWS = {three: [35, 18], front: [0, 0], rear: [180, 0], side: [90, 0]};
const TARGET = [0, 0, 118];
const state = {az: 35, el: 18, dist: 640, yaw: 0, shells: true, ghosts: true, selected: ''};
const rad = deg => deg * Math.PI / 180;
if (!gl) {
  $('error').textContent = 'This browser cannot display WebGL. The lists below still work.';
} else {
  start();
}

function decode(text, Type) {
  const bin = atob(text), bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Type(bytes.buffer);
}

// Flat shading: expand the indexed mesh so every triangle carries its own normal.
function expand(part) {
  const v = decode(part.vertices, Float32Array), idx = decode(part.indices, Uint32Array);
  const pos = new Float32Array(idx.length * 3), nor = new Float32Array(idx.length * 3);
  for (let t = 0; t < idx.length; t += 3) {
    const a = [0, 1, 2].map(k => idx[t + k] * 3);
    const u = [0, 1, 2].map(i => v[a[1] + i] - v[a[0] + i]);
    const w = [0, 1, 2].map(i => v[a[2] + i] - v[a[0] + i]);
    const n = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]];
    const len = Math.hypot(...n) || 1;
    for (let k = 0; k < 3; k++) for (let i = 0; i < 3; i++) {
      pos[(t + k) * 3 + i] = v[a[k] + i];
      nor[(t + k) * 3 + i] = n[i] / len;
    }
  }
  return {pos, nor, count: idx.length};
}

function perspective(fovy, aspect, near, far) {
  const f = 1 / Math.tan(fovy / 2), nf = 1 / (near - far);
  return [f / aspect, 0, 0, 0, 0, f, 0, 0, 0, 0, (far + near) * nf, -1, 0, 0, 2 * far * near * nf, 0];
}

function lookAt(eye, target) {
  const sub = (a, b) => a.map((x, i) => x - b[i]);
  const norm = a => a.map(x => x / Math.hypot(...a));
  const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const z = norm(sub(eye, target)), x = norm(cross([0, 0, 1], z)), y = cross(z, x);
  return [x[0], y[0], z[0], 0, x[1], y[1], z[1], 0, x[2], y[2], z[2], 0, -dot(x, eye), -dot(y, eye), -dot(z, eye), 1];
}

function multiply(a, b) {
  const out = new Array(16).fill(0);
  for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++) for (let k = 0; k < 4; k++) out[c * 4 + r] += a[k * 4 + r] * b[c * 4 + k];
  return out;
}

function start() {
  const vs = `attribute vec3 position;attribute vec3 normal;uniform mat4 viewProj;uniform float yaw;uniform vec3 light;varying float shade;
void main(){float c=cos(yaw),s=sin(yaw);mat3 r=mat3(c,s,0.,-s,c,0.,0.,0.,1.);
gl_Position=viewProj*vec4(r*position,1.);shade=0.4+0.6*abs(dot(r*normal,light));}`;
  const fs = `precision mediump float;uniform vec4 color;varying float shade;void main(){gl_FragColor=vec4(color.rgb*shade,color.a);}`;
  const compile = (type, source) => {
    const s = gl.createShader(type);
    gl.shaderSource(s, source);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw Error(gl.getShaderInfoLog(s));
    return s;
  };
  const program = gl.createProgram();
  gl.attachShader(program, compile(gl.VERTEX_SHADER, vs));
  gl.attachShader(program, compile(gl.FRAGMENT_SHADER, fs));
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw Error(gl.getProgramInfoLog(program));
  gl.useProgram(program);
  const attribute = name => gl.getAttribLocation(program, name);
  const uniform = Object.fromEntries(['viewProj', 'yaw', 'light', 'color'].map(k => [k, gl.getUniformLocation(program, k)]));
  for (const part of parts) {
    const mesh = expand(part);
    part.count = mesh.count;
    part.rgb = [1, 3, 5].map(i => parseInt(part.color.slice(i, i + 2), 16) / 255);
    for (const [key, data] of [['posBuffer', mesh.pos], ['norBuffer', mesh.nor]]) {
      part[key] = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, part[key]);
      gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
    }
    delete part.vertices;
    delete part.indices;
  }

  function draw() {
    const box = canvas.getBoundingClientRect(), ratio = Math.min(devicePixelRatio || 1, 2);
    canvas.width = Math.round(box.width * ratio);
    canvas.height = Math.round(box.height * ratio);
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.clearColor(0.875, 0.89, 0.91, 1);
    gl.enable(gl.DEPTH_TEST);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    gl.depthMask(true);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    const az = rad(state.az), el = rad(state.el), d = state.dist;
    const eye = [TARGET[0] + d * Math.sin(az) * Math.cos(el), TARGET[1] - d * Math.cos(az) * Math.cos(el), TARGET[2] + d * Math.sin(el)];
    const matrix = multiply(perspective(rad(30), canvas.width / canvas.height, 50, 2000), lookAt(eye, TARGET));
    const light = [eye[0] - TARGET[0], eye[1] - TARGET[1], eye[2] - TARGET[2] + 0.4 * d].map((x, _, a) => x / Math.hypot(...a));
    gl.uniformMatrix4fv(uniform.viewProj, false, new Float32Array(matrix));
    gl.uniform3fv(uniform.light, light);
    let shown = 0;
    for (const ghostPass of [false, true]) {
      gl.depthMask(!ghostPass);
      for (const part of parts) {
        if (part.ghost !== ghostPass || (part.ghost ? !state.ghosts : part.shell && !state.shells)) continue;
        const alpha = part.ghost ? 0.4 : 1;
        gl.uniform1f(uniform.yaw, part.moving ? rad(state.yaw) : 0);
        gl.uniform4fv(uniform.color, part.name === state.selected ? [1, 0.48, 0.14, 1] : [...part.rgb, alpha]);
        for (const [name, key] of [['position', 'posBuffer'], ['normal', 'norBuffer']]) {
          gl.bindBuffer(gl.ARRAY_BUFFER, part[key]);
          gl.vertexAttribPointer(attribute(name), 3, gl.FLOAT, false, 0, 0);
          gl.enableVertexAttribArray(attribute(name));
        }
        gl.drawArrays(gl.TRIANGLES, 0, part.count);
        shown++;
      }
    }
    $('count').textContent = shown + ' parts shown';
  }

  const views = document.querySelectorAll('[data-view]');
  for (const button of views) {
    button.onclick = () => {
      [state.az, state.el] = VIEWS[button.dataset.view];
      for (const b of views) b.setAttribute('aria-pressed', String(b === button));
      draw();
    };
  }
  for (const button of document.querySelectorAll('[data-part]')) {
    button.onclick = () => {
      state.selected = state.selected === button.dataset.part ? '' : button.dataset.part;
      draw();
    };
  }
  $('yaw').oninput = e => {
    state.yaw = Number(e.target.value);
    $('yaw-value').textContent = state.yaw + '°';
    draw();
  };
  for (const id of ['shells', 'ghosts']) {
    $(id).onchange = e => {
      state[id] = e.target.checked;
      draw();
    };
  }
  let drag = null;
  canvas.onpointerdown = e => { drag = [e.clientX, e.clientY]; };
  canvas.onpointerup = canvas.onpointercancel = () => { drag = null; };
  canvas.onpointermove = e => {
    if (!drag) return;
    state.az -= (e.clientX - drag[0]) * 0.5;
    state.el = Math.max(-80, Math.min(80, state.el + (e.clientY - drag[1]) * 0.5));
    drag = [e.clientX, e.clientY];
    draw();
  };
  canvas.onwheel = e => {
    e.preventDefault();
    state.dist = Math.max(260, Math.min(1000, state.dist * (e.deltaY > 0 ? 1.1 : 0.9)));
    draw();
  };
  canvas.onkeydown = e => {
    const turn = {ArrowLeft: [-10, 0], ArrowRight: [10, 0], ArrowUp: [0, 10], ArrowDown: [0, -10]}[e.key];
    if (!turn) return;
    e.preventDefault();
    state.az += turn[0];
    state.el = Math.max(-80, Math.min(80, state.el + turn[1]));
    draw();
  };
  new ResizeObserver(draw).observe(canvas);
  draw();
}
</script></body></html>
"""  # noqa: E501

if __name__ == "__main__":
    main()
