"""Printability checker for STL parts that are already in print orientation (mm, FDM).

Reports overhang area, floating islands, and thin-wall area per part, so designs compare by number.
Run `python hardware/printcheck.py <stl or dir> [...] [--json out.json]` or `--selftest`.
"""

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import trimesh
from scipy import ndimage

PITCH_MM = 0.4  # voxel size in X and Y
LAYER_MM = 0.2
OVERHANG_NORMAL_Z = -np.sin(np.radians(45)) - 1e-4  # flatter than 45 degrees; exact 45 passes
CEILING_NORMAL_Z = -0.98
BED_Z_MM = 0.1
THIN_MM = 2.0
THIN_SAMPLES = 20000  # minimum; large parts get one sample per mm2
EDGE_BAND_MM = 1.0  # chamfers and fillets thin out near sharp edges; skip that band
SHARP_DEG = 30
MIN_ISLAND_MM2 = 2.0  # ponytail: smaller regions flicker with the 0.4 mm grid offset
RAY_BATCH = 4_000_000  # triangle-by-sample pairs per numpy batch
JITTER_MM = np.array([0.0137, 0.0291])  # unequal, so rays miss shared edges and the x = y diagonal
GROUPS = ("Required", "Optional")


def _occupancy(mesh):
    """Voxel grid (layer, x, y) from vertical ray parity; layers are sampled at mid height."""
    tri = mesh.triangles
    lo = mesh.bounds[0, :2]
    nx, ny = np.ceil(mesh.extents[:2] / PITCH_MM).astype(int) + 1
    nk = int(np.ceil(mesh.extents[2] / LAYER_MM))
    ax, ay, az = tri[:, 0].T
    bx, by, bz = tri[:, 1].T
    cx, cy, cz = tri[:, 2].T
    # z of the face normal: negative where a ray going up enters the solid, positive where it leaves
    det = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
    xs, ys = tri[:, :, 0], tri[:, :, 1]

    def cell(v, axis):  # column index (fractional) of coordinate v
        return (v - lo[axis] - JITTER_MM[axis]) / PITCH_MM - 0.5

    i0, i1 = np.ceil(cell(xs.min(1), 0)).astype(int), np.floor(cell(xs.max(1), 0)).astype(int)
    j0, j1 = np.ceil(cell(ys.min(1), 1)).astype(int), np.floor(cell(ys.max(1), 1)).astype(int)
    i0, j0 = np.maximum(i0, 0), np.maximum(j0, 0)
    i1, j1 = np.minimum(i1, nx - 1), np.minimum(j1, ny - 1)
    width = np.maximum(j1 - j0 + 1, 0)
    count = np.where(np.abs(det) > 1e-12, np.maximum(i1 - i0 + 1, 0) * width, 0)
    done = np.cumsum(count)
    diff = np.zeros((nk + 1, nx * ny), np.int8)
    start = 0
    while start < len(tri):
        end = max(
            np.searchsorted(done, done[start] - count[start] + RAY_BATCH, side="right"), start + 1
        )
        s = slice(start, end)
        start = end
        n = count[s]
        if n.sum() == 0:
            continue
        t = np.repeat(np.arange(s.start, s.stop), n)
        local = np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n)
        ix = i0[t] + local // width[t]
        iy = j0[t] + local % width[t]
        px = lo[0] + (ix + 0.5) * PITCH_MM + JITTER_MM[0]
        py = lo[1] + (iy + 0.5) * PITCH_MM + JITTER_MM[1]
        u = ((px - ax[t]) * (cy[t] - ay[t]) - (py - ay[t]) * (cx[t] - ax[t])) / det[t]
        v = ((bx[t] - ax[t]) * (py - ay[t]) - (by[t] - ay[t]) * (px - ax[t])) / det[t]
        hit = (u >= 0) & (v >= 0) & (u + v <= 1)
        t, u, v, ix, iy = t[hit], u[hit], v[hit], ix[hit], iy[hit]
        z = az[t] + u * (bz[t] - az[t]) + v * (cz[t] - az[t])
        layer = np.clip(np.floor(z / LAYER_MM - 0.5).astype(int) + 1, 0, nk)
        np.add.at(diff, (layer, ix * ny + iy), -np.sign(det[t]).astype(np.int8))
    return (np.cumsum(diff[:-1], axis=0, dtype=np.int8) > 0).reshape(nk, nx, ny)


def _floating_islands(occ):
    """Areas (mm2) and layer bottoms (mm) of 2D regions with nothing below them."""
    areas, zs = [], []
    for k in range(1, len(occ)):
        labels, n = ndimage.label(occ[k], structure=np.ones((3, 3)))
        if n == 0:
            continue
        floating = np.ones(n + 1, bool)
        floating[np.unique(labels[occ[k - 1]])] = False
        floating[0] = False
        sizes = np.bincount(labels.ravel(), minlength=n + 1)[floating]
        sizes = sizes[sizes * PITCH_MM**2 >= MIN_ISLAND_MM2]
        areas += list(sizes * PITCH_MM**2)
        zs += [k * LAYER_MM] * len(sizes)
    return areas, zs


def _inward_thickness(mesh, points, normals):
    """Distance from each surface point to the first wall met along the reversed normal."""
    tri = mesh.triangles
    v0, e1, e2 = tri[:, 0], tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
    out = np.full(len(points), np.inf)
    step = max(1, RAY_BATCH // len(tri))
    for s in range(0, len(points), step):
        d = -normals[s : s + step]
        o = points[s : s + step] + 1e-3 * d  # start just inside so the origin face is not hit
        p = np.cross(d[:, None, :], e2)
        det = np.einsum("fk,sfk->sf", e1, p)
        inv = 1 / np.where(np.abs(det) > 1e-12, det, np.inf)
        tv = o[:, None, :] - v0
        q = np.cross(tv, e1)
        u = np.einsum("sfk,sfk->sf", tv, p) * inv
        v = np.einsum("sk,sfk->sf", d, q) * inv
        dist = np.einsum("fk,sfk->sf", e2, q) * inv
        hit = (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9) & (dist > 1e-6)
        out[s : s + step] = np.where(hit, dist, np.inf).min(axis=1) + 1e-3
    return out


def _edge_distance(mesh, points):
    """Distance from each point to the nearest sharp mesh edge."""
    sharp = mesh.face_adjacency_angles > np.radians(SHARP_DEG)
    a, b = (mesh.vertices[i] for i in mesh.face_adjacency_edges[sharp].T)
    ab = b - a
    length2 = np.maximum((ab * ab).sum(1), 1e-12)
    out = np.full(len(points), np.inf)
    step = max(1, RAY_BATCH // max(len(a), 1))
    for s in range(0, len(points) if len(a) else 0, step):
        ap = points[s : s + step, None, :] - a
        t = np.clip((ap * ab).sum(2) / length2, 0, 1)
        out[s : s + step] = np.linalg.norm(ap - t[..., None] * ab, axis=2).min(1)
    return out


def analyze(mesh):
    """Printability numbers for one mesh already in print orientation."""
    if not (mesh.is_watertight and mesh.is_winding_consistent and mesh.volume > 0):
        raise ValueError("mesh must be closed, consistently wound, and outward facing")
    mesh = mesh.copy()
    mesh.apply_translation([0, 0, -mesh.bounds[0, 2]])
    nz = mesh.face_normals[:, 2]
    off_bed = mesh.triangles[:, :, 2].max(axis=1) > BED_Z_MM
    overhang = off_bed & (nz < OVERHANG_NORMAL_Z)
    ceiling = off_bed & (nz < CEILING_NORMAL_Z)
    area = mesh.area_faces
    islands, island_z = _floating_islands(_occupancy(mesh))
    count = max(THIN_SAMPLES, int(mesh.area))
    points, face = trimesh.sample.sample_surface(mesh, count, seed=0)
    away = _edge_distance(mesh, points) > EDGE_BAND_MM
    if away.mean() < 0.5:  # ponytail: a part that is mostly edges is a small feature; judge it raw
        away[:] = True
    depth = _inward_thickness(mesh, points[away], mesh.face_normals[face[away]])
    thin = np.round(depth, 2) < THIN_MM  # rounding keeps nominal 2.0 mm walls out
    worst = int(np.argmax(islands)) if islands else None
    return {
        "overhang_mm2": round(float(area[overhang].sum()), 1),
        "ceiling_mm2": round(float(area[ceiling].sum()), 1),
        "floating_islands": len(islands),
        "island_max_mm2": round(float(islands[worst]), 2) if islands else 0.0,
        "island_max_z_mm": round(island_z[worst], 1) if islands else None,
        "thin_mm2": round(float(mesh.area * thin.sum() / count), 1),
        "min_thickness_mm": round(float(depth.min()), 2) if len(depth) else None,
        "volume_mm3": round(float(mesh.volume)),
        "bbox_mm": [round(float(x), 1) for x in mesh.extents],
        "face_count": len(mesh.faces),
    }


def _totals(rows):
    return {
        "parts": len(rows),
        "overhang_mm2": round(sum(r["overhang_mm2"] for r in rows), 1),
        "floating_islands": sum(r["floating_islands"] for r in rows),
        "thin_mm2": round(sum(r["thin_mm2"] for r in rows), 1),
    }


def _print_table(rows, totals):
    cols = [
        "part",
        "overhang",
        "ceiling",
        "islands",
        "isl_max",
        "isl_z",
        "thin_mm2",
        "min_t",
        "volume",
        "bbox",
    ]
    print(f"{cols[0]:<48}" + "".join(f"{c:>10}" for c in cols[1:9]) + "  " + cols[9])
    for r in rows:
        values = [
            r["overhang_mm2"],
            r["ceiling_mm2"],
            r["floating_islands"],
            r["island_max_mm2"],
            r["island_max_z_mm"] if r["floating_islands"] else "-",
            r["thin_mm2"],
            r["min_thickness_mm"],
            r["volume_mm3"],
        ]
        print(
            f"{r['part']:<48}"
            + "".join(f"{v!s:>10}" for v in values)
            + "  "
            + "x".join(map(str, r["bbox_mm"]))
        )
    for group, t in totals.items():
        print(
            f"TOTAL {group}: {t['parts']} parts, overhang {t['overhang_mm2']} mm2, "
            f"floating islands {t['floating_islands']}, thin {t['thin_mm2']} mm2"
        )


def selftest():
    def box(x, y, z, at=(0, 0, 0)):
        return trimesh.creation.box(
            (x, y, z), transform=trimesh.transformations.translation_matrix(at)
        )

    cube = analyze(box(20, 20, 20, (0, 0, 10)))
    assert cube["overhang_mm2"] == 0 and cube["floating_islands"] == 0 and cube["thin_mm2"] == 0, (
        cube
    )

    floating = analyze(
        trimesh.util.concatenate([box(10, 10, 10, (0, 0, 5)), box(10, 10, 10, (0, 0, 25))])
    )
    assert floating["floating_islands"] == 1 and floating["island_max_z_mm"] == 20, floating

    # T profile in XY (y becomes Z after the turn): slab 40 wide on a post 10 wide, 40 deep
    profile = np.array(
        [(-5, 0), (5, 0), (5, 10), (20, 10), (20, 14), (-20, 14), (-20, 10), (-5, 10)], float
    )
    faces = [(0, 1, 2), (0, 2, 7), (5, 6, 7), (5, 7, 2), (5, 2, 3), (5, 3, 4)]
    tee = trimesh.creation.extrude_triangulation(profile, faces, 40)
    tee.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    tee = analyze(tee)
    assert abs(tee["overhang_mm2"] - 30 * 40) < 0.05 * 30 * 40 and tee["floating_islands"] == 0, tee

    h = 10 * np.tan(np.radians(50))  # underside slopes 50 degrees from horizontal
    corners = [
        (sx * r, sy * r, z) for r, z in ((5, 0), (15, h)) for sx in (-1, 1) for sy in (-1, 1)
    ]
    chamfer = analyze(trimesh.Trimesh(corners).convex_hull)
    assert chamfer["overhang_mm2"] == 0 and chamfer["floating_islands"] == 0, chamfer

    plate = analyze(box(50, 50, 1, (0, 0, 0.5)))
    assert (
        abs(plate["thin_mm2"] - 2 * 50 * 50) < 0.1 * 2 * 50 * 50 and plate["min_thickness_mm"] == 1
    ), plate
    # A 0.5 mm stem centred on the x = y diagonal once lost its voxels to edge hits
    stem = analyze(
        trimesh.util.concatenate(
            [box(10, 10, 10, (0, 0, 5)), box(0.5, 0.5, 2, (0, 0, 11)), box(10, 10, 10, (0, 0, 17))]
        )
    )
    assert stem["floating_islands"] == 0, stem

    wedge = trimesh.Trimesh(  # underside exactly 45 degrees
        [(0, 0, 0), (10, 0, 0), (0, 0, 10), (10, 0, 10), (0, 10, 10), (10, 10, 10)]
    ).convex_hull
    assert analyze(wedge)["overhang_mm2"] == 0, analyze(wedge)

    inverted = box(10, 10, 10, (0, 0, 5))
    inverted.invert()
    try:
        analyze(inverted)
        raise AssertionError("inverted mesh accepted")
    except ValueError:
        pass
    key = analyze(box(1.3, 1.2, 10, (0, 0, 0.6)))  # Concept A head key section
    assert key["thin_mm2"] > 0, key
    print("selftest passed")


def _collect(paths):
    return sorted(f for p in map(Path, paths) for f in ([p] if p.is_file() else p.rglob("*.stl")))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="STL files or directories")
    parser.add_argument("--json", help="write rows and totals to this file")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    files = _collect(args.paths)
    if not files:
        sys.exit("no STL files given")
    rows = []
    for f in files:
        group = next((g for g in GROUPS if g in f.parts), "all")
        rows.append({"part": f.stem, "group": group} | analyze(trimesh.load(f, force="mesh")))
    totals = {
        g: _totals([r for r in rows if r["group"] == g])
        for g in dict.fromkeys(r["group"] for r in rows)
    }
    _print_table(rows, totals)
    if args.json:
        repo = Path(__file__).resolve().parent
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
        ).stdout.strip()
        meta = {
            "revision": revision,
            "date": datetime.date.today().isoformat(),
            "pitch_mm": PITCH_MM,
            "layer_mm": LAYER_MM,
            "thin_mm": THIN_MM,
            "thin_samples": THIN_SAMPLES,
        }
        Path(args.json).write_text(
            json.dumps({"meta": meta, "totals": totals, "parts": rows}, indent=1) + "\n"
        )


if __name__ == "__main__":
    main()
