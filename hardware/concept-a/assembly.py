"""Integrate the actual removable casing and manual joint for CAD fit checks.
Run with build/hardware-layout/venv/bin/python hardware/concept-a/assembly.py.
"""

from __future__ import annotations

import json
import math
from html import escape
from pathlib import Path

import cadquery as cq
import numpy as np
import trimesh
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import casing
import joint
import layout
from enclosure_geometry import body_envelopes, head_envelopes

OUT = Path(__file__).resolve().parent / "output" / "assembly"


def parts():
    case = casing.build_parts()
    mechanism = {
        n: s
        for n, s in joint.build_parts().items()
        if n not in joint.GAUGE_NAMES and n != joint.DRIVE_GEAR_NAME
    }
    shapes = case | mechanism
    meta = casing.metadata() | {
        n: dict(
            color="#25272b", moving=n in joint.moving_part_names(), removable=False, kind="joint"
        )
        for n in mechanism
    }
    return shapes, meta


def compound(shapes):
    return cq.Compound.makeCompound(list(shapes))


def yaw(shape, angle):
    return shape.rotate((0, 0, 0), (0, 0, 1), angle)


def rotation_clearance(moving, fixed):
    bb = moving.BoundingBox()
    radius = max(math.hypot(x, y) for x in (bb.xmin, bb.xmax) for y in (bb.ymin, bb.ymax))
    cache = {}

    def distance(angle):
        if angle not in cache:
            cache[angle] = yaw(moving, angle).distance(fixed)
        return cache[angle]

    intervals = [(-80.0, 80.0)]
    failed = []
    proven = 0
    while intervals:
        lo, hi = intervals.pop()
        mid = (lo + hi) / 2
        gap = distance(mid)
        bound = radius * math.radians((hi - lo) / 2)
        if gap > bound + 1e-6:
            proven += 1
        elif hi - lo <= 0.05:
            failed.append(dict(lo=lo, hi=hi, distance=gap, motion_bound=bound))
        else:
            intervals.extend([(lo, mid), (mid, hi)])
    return not failed, dict(
        samples=len(cache),
        proven_intervals=proven,
        radius_mm=radius,
        minimum_sample_gap_mm=min(cache.values()),
        method=(
            "Exact midpoint solid distance exceeds maximum angular point travel "
            "through each interval."
        ),
        unresolved=failed,
    )


def checks(shapes, meta):
    rows = []

    def record(name, passed, detail):
        rows.append(dict(name=name, passed=bool(passed), detail=detail))

    case = {n: s for n, s in shapes.items() if meta[n]["kind"] == "casing"}
    mechanism = {n: s for n, s in shapes.items() if meta[n]["kind"] == "joint"}
    for n, a in case.items():
        for m, b in mechanism.items():
            volume = a.intersect(b).Volume()
            record(
                f"{n} / {m}",
                volume < 1e-5,
                f"Assembled overlap {volume:.6g} mm³. Designed boundary contacts have zero volume.",
            )
    stationary = compound(s for n, s in shapes.items() if not meta[n]["moving"])
    moving_case = compound(s for n, s in case.items() if meta[n]["moving"])
    moving_joint = compound(s for n, s in mechanism.items() if meta[n]["moving"])
    fixed_case = compound(s for n, s in case.items() if not meta[n]["moving"])
    # Gear mesh and joint stops have their own checks in joint.py. Here, adaptive
    # solid distances bound every intermediate rotation against the other group.
    for label, moving, fixed in [
        ("head casing / stationary assembly", moving_case, stationary),
        ("moving joint / fixed casing", moving_joint, fixed_case),
    ]:
        passed, detail = rotation_clearance(moving, fixed)
        record(label, passed, detail)
    # Head keys enter from the open rear. Use the full key bounding prism as
    # a conservative continuous path. The retaining barb flex is tested separately.
    access_case = compound(s for n, s in case.items() if meta[n]["moving"] and n != "head-rear")
    for x in (-18, 18):
        key = shapes[f"head_key_{x}"]
        bb = key.BoundingBox()
        prism = layout.box(
            (bb.xlen, bb.ylen + 55, bb.zlen),
            ((bb.xmin + bb.xmax) / 2, (bb.ymin + bb.ymax) / 2 + 27.5, (bb.zmin + bb.zmax) / 2),
        )
        overlap = prism.intersect(access_case).Volume() + prism.intersect(layout.camera()).Volume()
        record(
            f"head key {x} rear access",
            overlap < 1e-5,
            f"Continuous 55 mm bounding-prism path versus head and camera: {overlap:.6g} mm³.",
        )
    core = {
        n: s
        for n, s in mechanism.items()
        if n in {"gear_shaft", "inner_spacer", "tower_left", "tower_right"}
        or n.startswith("closure_")
    }
    rows.extend(casing.check_joint_admission(case, core))
    rows.append(casing.check_neck_admission(case, mechanism))
    return rows


def mesh(shape):
    """Use whole-solid triangles and angle-weighted normals without smoothing sharp edges."""
    vertices, faces = shape.tessellate(0.06, 0.12)
    mesh = trimesh.Trimesh(vertices=[v.toTuple() for v in vertices], faces=faces, process=False)
    mesh.merge_vertices(digits_vertex=7)
    mesh.update_faces(mesh.area_faces > 1e-12)
    mesh.remove_unreferenced_vertices()
    triangles = mesh.vertices[mesh.faces]
    normals = mesh.face_normals
    angles = mesh.face_angles
    incident = [[] for _ in mesh.vertices]
    for face_index, indices in enumerate(mesh.faces):
        for corner, index in enumerate(indices):
            incident[index].append((face_index, corner))
    smooth = np.empty_like(triangles)
    threshold = np.cos(np.radians(35))
    for face_index, indices in enumerate(mesh.faces):
        for corner, index in enumerate(indices):
            entries = [
                (f, c) for f, c in incident[index] if normals[f] @ normals[face_index] >= threshold
            ]
            normal = sum((normals[f] * angles[f, c] for f, c in entries), np.zeros(3))
            smooth[face_index, corner] = normal / max(np.linalg.norm(normal), 1e-12)
    return triangles, smooth


def raster(shapes, meta, angle, width=720, height=1040):
    """Render actual triangles with a depth buffer so holes show the correct surfaces."""
    canvas = np.full((height, width, 3), [0.894, 0.91, 0.929])
    depth = np.full((height, width), np.inf)
    rotation = math.radians(angle)
    elevation = math.radians(16)
    c, s = math.cos(rotation), math.sin(rotation)
    ce, se = math.cos(elevation), math.sin(elevation)
    scale = height / 270
    light = np.array([0.3, -0.7, 0.8])
    light /= np.linalg.norm(light)
    for name, shape in shapes.items():
        triangles, normals = mesh(shape)
        base = np.array(matplotlib.colors.to_rgb(meta[name]["color"]))
        points = triangles.copy()
        points[:, :, 2] -= 115
        x = c * points[:, :, 0] - s * points[:, :, 1]
        y = s * points[:, :, 0] + c * points[:, :, 1]
        z = points[:, :, 2]
        screen = np.stack(
            [width / 2 + x * scale, height / 2 - (ce * z + se * y) * scale, ce * y - se * z], axis=2
        )
        for triangle, vertex_normals in zip(screen, normals, strict=True):
            x0, y0, d0 = triangle[0]
            x1, y1, d1 = triangle[1]
            x2, y2, d2 = triangle[2]
            den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
            if abs(den) < 1e-8:
                continue
            left = max(0, int(np.floor(triangle[:, 0].min())))
            right = min(width - 1, int(np.ceil(triangle[:, 0].max())))
            top = max(0, int(np.floor(triangle[:, 1].min())))
            bottom = min(height - 1, int(np.ceil(triangle[:, 1].max())))
            if left > right or top > bottom:
                continue
            xx, yy = np.meshgrid(np.arange(left, right + 1) + 0.5, np.arange(top, bottom + 1) + 0.5)
            a = ((y1 - y2) * (xx - x2) + (x2 - x1) * (yy - y2)) / den
            b = ((y2 - y0) * (xx - x2) + (x0 - x2) * (yy - y2)) / den
            third = 1 - a - b
            distance = a * d0 + b * d1 + third * d2
            patch = depth[top : bottom + 1, left : right + 1]
            visible = (a >= -1e-8) & (b >= -1e-8) & (third >= -1e-8) & (distance < patch)
            patch[visible] = distance[visible]
            interpolated = (
                a[..., None] * vertex_normals[0]
                + b[..., None] * vertex_normals[1]
                + third[..., None] * vertex_normals[2]
            )
            interpolated /= np.maximum(np.linalg.norm(interpolated, axis=2)[..., None], 1e-12)
            brightness = 0.5 + 0.5 * np.maximum(0, interpolated @ light)
            canvas[top : bottom + 1, left : right + 1][visible] = base * brightness[visible, None]
    return canvas


def render(shapes, meta):
    # Display the full source camera and speaker envelope to fill their real openings.
    display = shapes | {"camera": layout.camera(), "speaker": layout.hardware()[1]["shape"]}
    colors = meta | {"camera": dict(color="#20252b"), "speaker": dict(color="#33373c")}
    fig, axes = plt.subplots(1, 2, figsize=(12, 9), facecolor="#e4e8ed")
    for ax, angle, title in zip(axes, (-25, 155), ("Front / right", "Rear / left"), strict=True):
        ax.imshow(raster(display, colors, angle))
        ax.set_axis_off()
        ax.set_title(title)
    fig.suptitle("Concept A | actual casing and manual joint | 236 mm tall", fontsize=16)
    fig.text(
        0.5,
        0.025,
        (
            "CAD preview with source camera and speaker envelope. Physical fit, cable movement, "
            "cooling, and powered mounting remain U."
        ),
        ha="center",
        fontsize=9,
    )
    fig.subplots_adjust(left=0, right=1, bottom=0.06, top=0.93, wspace=0)
    fig.savefig(OUT / "robot-preview.png", dpi=170)
    plt.close(fig)


def exact_size(shape):
    """Measure CAD surfaces without cached tessellation or added shape tolerance."""
    bounds = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape.wrapped, bounds, False, False)
    low_x, low_y, low_z, high_x, high_y, high_z = bounds.Get()
    return high_x - low_x, high_y - low_y, high_z - low_z


def printed_inventory(shapes, meta):
    """Build an offline inventory from the installed printed part metadata."""
    joint_count = sum(meta[name]["kind"] == "joint" for name in shapes)
    summary = (
        f"The installed preview contains {len(shapes)} printed pieces: "
        f"{len(shapes) - joint_count} casing pieces and {joint_count} joint pieces. "
        "Bearings and reference hardware are separate."
    )
    rows = "".join(
        f"<li>{escape(name.replace('-', ' ').replace('_', ' ').capitalize())}: one.</li>"
        for name in shapes
    )
    return summary, rows


def viewer(
    shapes, meta, hardware_entries=None, destination=None, study_name=None, model_envelopes=None
):
    """Export an offline triangle viewer with component and assembly metadata."""
    payload = []
    entries = [(name, shape, meta[name]) for name, shape in shapes.items()]
    if hardware_entries is None:
        entries += [(p["name"], p["shape"], p) for p in layout.hardware()]
        entries += [
            (
                name,
                shape,
                dict(
                    kind="moving hardware",
                    color="#7299ab",
                    moving=True,
                    note=(
                        "E: 15 × 24 × 5 mm bearing envelope. Actual race contact and fit remain U."
                    ),
                ),
            )
            for name, shape in joint.build()[1].items()
            if name.startswith("bearing_")
        ]
        entries += [
            (
                "Complete camera",
                layout.camera(),
                dict(
                    kind="moving hardware",
                    color="#477967",
                    moving=True,
                    note=(
                        "E: complete source board, optics, heatsink, and connectors. "
                        "Physical support and cable motion remain U."
                    ),
                ),
            )
        ]
    else:
        entries += [(p["name"], p["shape"], p) for p in hardware_entries]
    for name, shape, data in entries:
        triangles, normals = mesh(shape)
        size = exact_size(shape)
        hardware = name not in shapes
        moving = data.get("moving", data["kind"].startswith("moving"))
        reservation = data["kind"].endswith("reservation")
        exterior = name in {
            "body-front",
            "body-rear",
            "body-right",
            "body-roof",
            "head-front",
            "head-rear",
            "head-visor",
            "speaker-grille",
            "neck-cover",
        }
        cover = name in {"body-rear", "body-right", "head-rear", "head-visor"}
        if hardware:
            group = "reservation" if reservation else "hardware"
            stage = 3 if name.startswith("bearing_") else 5 if moving else 1
        elif data["kind"] == "joint":
            group, stage = "joint", 5 if name.startswith("head_key") else 3
        elif moving:
            group, stage = "head", 5
        else:
            group, stage = "body", int(name.endswith("retaining-key") or name == "audio-cradle")
        if name == "body-roof":
            stage = 2
        if name.startswith("roof-bridge") or name == "neck-cover":
            stage = 4
        if cover or name == "speaker-grille":
            stage = 2 if name.startswith("body-") or name == "speaker-grille" else 6
        payload.append(
            dict(
                name=name,
                label=name.replace("-", " ").replace("_", " ").capitalize()
                if not hardware
                else name,
                vertices=np.round(triangles.reshape(-1, 3), 4).tolist(),
                normals=np.round(normals.reshape(-1, 3), 5).tolist(),
                color=list(matplotlib.colors.to_rgb(data["color"])),
                moving=moving,
                removable=data.get("removable", False),
                hardware=hardware,
                reservation=reservation,
                group=group,
                stage=stage,
                cover=cover,
                exterior=exterior,
                service_removed=(
                    cover
                    or moving
                    or group == "joint"
                    or name == "body-roof"
                    or name.startswith("roof-bridge")
                    or name == "neck-cover"
                ),
                size=[round(value, 1) for value in size],
                note=data.get(
                    "note", "E: modeled printed geometry. Physical fit and retention remain U."
                ),
            )
        )
    template = Path(__file__).with_name("assembly-viewer.html").read_text()
    model_envelopes = model_envelopes or dict(body=body_envelopes()[0], head=head_envelopes()[0])
    body = exact_size(model_envelopes["body"])
    head = exact_size(model_envelopes["head"])
    overall = exact_size(compound([model_envelopes["body"], model_envelopes["head"]]))

    def dimensions(values):
        return " × ".join(f"{round(v, 1):g}" for v in values)

    model_info = (
        "Enclosure study · actual CAD triangles · "
        f"body {dimensions(body)} mm · head {dimensions(head)} mm · "
        f"overall {round(overall[2], 1):g} mm."
    )
    inventory_summary, inventory_rows = printed_inventory(shapes, meta)
    target = Path(destination) if destination else OUT / "robot-viewer.html"
    target.write_text(
        template.replace("__PART_DATA__", json.dumps(payload, separators=(",", ":")))
        .replace("__MODEL_INFO__", model_info)
        .replace("__PRINTED_SUMMARY__", inventory_summary)
        .replace("__PRINTED_ROWS__", inventory_rows)
        .replace("__STUDY_MODE__", "true" if study_name else "false")
        .replace(
            "__STUDY_NOTE__",
            (
                (
                    f"{study_name}: preliminary silhouette and component packing. "
                    "Ports, mounts, seams, joint interfaces, admission, cooling, "
                    "and physical fit remain U."
                )
                if study_name
                else "Mechanical prototype. Physical fit and powered mounting remain U."
            ),
        )
    )


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    shapes, meta = parts()
    rows = checks(shapes, meta)
    (OUT / "checks.json").write_text(
        json.dumps(dict(passed=all(r["passed"] for r in rows), checks=rows), indent=2) + "\n"
    )
    failures = [r for r in rows if not r["passed"]]
    if failures:
        print(json.dumps(failures, indent=2))
        raise SystemExit(1)
    assembled = cq.Assembly(name="Concept_A_manual_prototype")
    for n, s in shapes.items():
        assembled.add(s, name=n, color=layout.color(meta[n]["color"]))
    assembled.export(str(OUT / "robot-assembled.step"))
    render(shapes, meta)
    viewer(shapes, meta)
    print(f"{len(rows)} integrated checks pass; {len(shapes)} actual printed assembly parts.")


if __name__ == "__main__":
    main()
