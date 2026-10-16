"""Measure the two open choices in BRIEF.md: body split (printcheck per piece) and servo placement.
Run with `build/hardware-layout/venv/bin/python`; outputs go to build/enclosure-study/.
"""

import json
import sys
import time
from math import cos, radians, sin
from pathlib import Path

import cadquery as cq
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from scipy.spatial import ConvexHull  # noqa: E402

HARDWARE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HARDWARE)]
import printcheck  # noqa: E402
from body import (  # noqa: E402
    BASE_ROLL,
    HEIGHT,
    LEAN_FRONT,
    LIP_DEG,
    NECK_R,
    P1S_MM,
    SHOULDER_ROLL,
    base_roll_cut,
    box,
    chamfer_bed,
    flip,
    keep_z,
    shell_blank,
    to_print_mesh,
)
from geometry import WALL, body_envelopes, hardware  # noqa: E402

OUT = HARDWARE.parent / "build" / "enclosure-study"
LID_CUT_Z = 138  # below the shoulder roll start (about Z 139 on the tapered wall)


def max_outside_mm(new, old, z_max):
    "Largest distance from the new surface (below z_max) to the original solid."
    vertices, _ = new.tessellate(0.02, 0.1)
    pts = [v for v in vertices if v.z <= z_max]
    return max(cq.Vertex.makeVertex(v.x, v.y, v.z).distance(old) for v in pts)


def split_front_rear(shell, side):
    "Half of the shell on one side of Y 0, turned so its exterior face lies on the bed."
    half = shell.intersect(box(-300, 300, *((-300, 0) if side < 0 else (0, 300)), -10, 300))
    return half.rotate((0, 0, 0), (1, 0, 0), -side * (90 + LEAN_FRONT))


def open_bottom_metrics(outer, inner, cut_z):
    slab = box(-300, 300, -300, 300, cut_z, cut_z + 0.01)
    opening, edge = inner.intersect(slab).BoundingBox(), outer.intersect(slab).BoundingBox()
    removed = outer.cut(inner).intersect(box(-300, 300, -300, 300, -1, cut_z)).Volume()
    return {
        "cut_z_mm": round(cut_z, 2),
        "opening_mm": [round(opening.xlen, 1), round(opening.ylen, 1)],
        "outer_at_cut_mm": [round(edge.xlen, 1), round(edge.ylen, 1)],
        "base_roll_height_removed_mm": f"{cut_z:.1f} of {BASE_ROLL}",
        "shell_volume_removed_mm3": round(removed),
    }


def build_pieces():
    """All Study 1 pieces in print orientation, with the extra numbers each variant reports."""
    outer, inner = body_envelopes()
    hole = cq.Solid.makeCylinder(NECK_R, 400, cq.Vector(0, 0, -100))
    cut_z = base_roll_cut(LIP_DEG)
    up_outer, up_inner = flip(outer), flip(inner)
    roof_chamfer = chamfer_bed(up_outer, SHOULDER_ROLL)
    base_chamfer = chamfer_bed(outer, BASE_ROLL)
    dev_roof = max_outside_mm(roof_chamfer, up_outer, 15)
    dev_base = max_outside_mm(base_chamfer, outer, 15)
    open_bottom = open_bottom_metrics(outer, inner, cut_z)

    def a(shape):
        return keep_z(shape.cut(up_inner).cut(hole), -1, HEIGHT - cut_z)

    pieces = {
        "A0 as-is": {"body": (a(up_outer), 0.0)},
        "A1 chamfer": {"body": (flip(shell_blank()), dev_roof)},
        "B shell upright + roof lid": {
            "shell": (keep_z(base_chamfer.cut(inner), -1, LID_CUT_Z), dev_base),
            "lid": (keep_z(roof_chamfer.cut(up_inner).cut(hole), -1, HEIGHT - LID_CUT_Z), dev_roof),
        },
    }
    half_shell = outer.cut(inner).cut(hole)
    pieces["C front/rear halves"] = {
        "front": (split_front_rear(half_shell, -1), 0.0),
        "rear": (split_front_rear(half_shell, 1), 0.0),
    }
    return pieces, {"open_bottom": open_bottom}


def study_split():
    pieces, extra = build_pieces()
    rows, meshes = {}, {}
    for variant, parts in pieces.items():
        for name, (solid, deviation) in parts.items():
            mesh = to_print_mesh(solid, 0.03, 0.1)
            tag = f"{variant.split()[0]}-{name}"
            mesh.export(OUT / f"{tag}.stl")
            meshes[variant, name] = mesh
            row = printcheck.analyze(mesh)
            row["fits_p1s_256"] = bool(max(row["bbox_mm"]) <= P1S_MM)
            row["max_silhouette_deviation_mm"] = round(deviation, 2)
            row["watertight"] = bool(mesh.is_watertight)
            rows.setdefault(variant, {})[name] = row
    return rows | extra, meshes


def render(meshes, rows):
    "One PNG per variant: the section through each piece in print orientation."
    for variant in dict.fromkeys(v for v, _ in meshes):
        parts = {n: m for (v, n), m in meshes.items() if v == variant}
        fig, ax = plt.subplots(figsize=(11, 6))
        x0 = 0
        for name, mesh in parts.items():
            vertical = variant.startswith("C")  # halves are slender in Y, so cut across Y
            normal, axis = ([1, 0, 0], 1) if vertical else ([0, 1, 0], 0)
            section = mesh.section(plane_origin=[0, 0, 0], plane_normal=normal)
            for line in section.discrete:
                ax.plot(line[:, axis] + x0, line[:, 2], color="#1b4f9c", lw=1.2)
            r = rows[variant][name]
            label = f"{name}\noverhang {r['overhang_mm2']} mm2, islands {r['floating_islands']}"
            ax.text(x0, -12, label, ha="center", va="top", fontsize=9)
            x0 += mesh.extents[axis] + 25
        ax.axhline(0, color="#999", lw=1)
        ax.set_aspect("equal")
        ax.set_title(f"{variant}: section in print orientation (bed at Z 0)")
        fig.savefig(OUT / f"{variant.split()[0]}.png", dpi=110, bbox_inches="tight")
        plt.close(fig)


# Study 2 ----------------------------------------------------------------------------------

HOUSING = (45.22, 24.72, 35)
HORN_OFFSET, HORN_D, HORN_H = 10.11, 20, 4
LEADS = (58, 30, 39)
BOSS = 3  # leads and ears reservation extends 3 mm above the housing, 1 mm below
ROOF_UNDERSIDE = HEIGHT - WALL


def pose(rot, axis, z_top, leads_h=LEADS[2], horn_h=HORN_H):
    """Servo stack with the output axis at `axis`; z_top is the top of the leads reservation.
    The horn sits on the reservation top; the housing centre is HORN_OFFSET behind the axis."""
    c = np.array(axis) + HORN_OFFSET * np.array([cos(radians(rot)), sin(radians(rot))])
    leads = cq.Workplane("XY").box(*LEADS[:2], leads_h).rotate((0, 0, 0), (0, 0, 1), rot)
    leads = leads.translate((c[0], c[1], z_top - leads_h / 2)).val()
    horn = cq.Workplane("XY").polygon(48, HORN_D).extrude(horn_h).translate((*axis, z_top)).val()
    return {"leads+housing": leads, "horn": horn}


def corners(shape):
    return np.array([v.toTuple() for v in shape.Vertices()])


def gap(a, b):
    "Distance between two convex solids; negative is the penetration depth."
    d = a.distance(b)
    if d > 1e-6:
        return d
    pa, pb = corners(a), corners(b)
    hull = ConvexHull((pa[:, None, :] - pb[None, :, :]).reshape(-1, 3))
    return float(hull.equations[:, 3].max())


def cavity_clearance(stack, hull):
    "Smallest distance from stack corners to the inner cavity wall (convex), pieces inside only."
    pts = np.vstack([corners(s) for s in stack.values() if s.BoundingBox().zmax <= ROOF_UNDERSIDE])
    return float(-(pts @ hull.equations[:, :3].T + hull.equations[:, 3]).max())


def clearances(stack, items, hull):
    per_item = {
        item["name"]: min(gap(s, item["shape"]) for s in stack.values())
        for item in items
        if item["name"] not in ("STS3215 housing", "Servo ears and leads")
    }
    per_item["body inner cavity"] = cavity_clearance(stack, hull)
    closest = min(per_item, key=per_item.get)
    return {
        "min_clearance_mm": round(per_item[closest], 2),
        "closest": closest,
        "clear_by_2mm": bool(per_item[closest] >= 2),
        "by_reservation_mm": {k: round(v, 1) for k, v in per_item.items()},
    }


def ears(rot, axis):
    "Ear tips at the ends of the 58 mm leads and ears span (U: the ear height on the housing)."
    c = np.array(axis) + HORN_OFFSET * np.array([cos(radians(rot)), sin(radians(rot))])
    u = np.array([cos(radians(rot)), sin(radians(rot))])
    tips = [c + s * LEADS[0] / 2 * u for s in (-1, 1)]
    return [round(float(np.linalg.norm(t - axis)), 1) for t in tips]


def study_servo():
    items = hardware()
    cavity = np.array([v.toTuple() for v in body_envelopes()[1].tessellate(0.05, 0.1)[0]])
    hull = ConvexHull(cavity)
    roof_gap = 2.0
    placements = {"2 mm under roof": ROOF_UNDERSIDE - roof_gap, "highest": HEIGHT - HORN_H}
    result = {"A coaxial": {}, "A sweep (2 mm under roof)": {}}
    for label, z_top in placements.items():
        for rot in (0, 90, 180, 270):
            r = clearances(pose(rot, (0, 0), z_top), items, hull)
            r |= {"z_top_mm": z_top, "ear_tip_distance_from_axis_mm": ears(rot, (0, 0))}
            result["A coaxial"][f"rot {rot}, {label}"] = r
    # U: CAD-measured 45.4 x 24.8 x 28.8 mm case, reservation = case + 1 mm below, horn top 6 mm
    # above the case (same horn top Z as the 39 mm model, so the shaft and hub stay unchanged)
    short_top = placements["2 mm under roof"] + HORN_H - 6
    result["A coaxial, 28.8 mm case (U)"] = {
        f"rot {rot}": clearances(pose(rot, (0, 0), short_top, 28.8 + 1, 6), items, hull)
        | {"case_top_mm": round(short_top, 1), "case_bottom_mm": round(short_top - 28.8, 1)}
        for rot in (0, 90, 180, 270)
    }
    for rot in range(0, 360, 15):
        r = clearances(pose(rot, (0, 0), placements["2 mm under roof"]), items, hull)
        result["A sweep (2 mm under roof)"][f"rot {rot}"] = r["min_clearance_mm"], r["closest"]
    z_b = 140  # Concept A: housing Z 102 to 137, reservation to Z 140
    result["B offset (12.5, -34), Concept A"] = clearances(
        pose(0, (12.5 - HORN_OFFSET, -34), z_b), items, hull
    ) | {"z_top_mm": z_b, "gears": "two-gear drive not modelled"}
    result["notes"] = {
        "roof_hole_radius_mm": NECK_R,
        "horn_to_roof_hole_radial_mm": round(NECK_R - HORN_D / 2, 1),
        "housing_fits_roof_hole": False,
        "ear_height_and_screw_boss": "U: needs the owned servo; roof underside is the only mount",
    }
    return result


def main():
    start = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    split, meshes = study_split()
    render(meshes, split)
    study = {"body_split": split, "servo": study_servo(), "tool": "printcheck.analyze"}
    study["runtime_s"] = round(time.time() - start, 1)
    (OUT / "study.json").write_text(json.dumps(study, indent=1) + "\n")
    print(f"wrote {OUT / 'study.json'} in {study['runtime_s']} s")


if __name__ == "__main__":
    main()
