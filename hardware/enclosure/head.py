"""Head shell and visor of the simplified enclosure, plus the combined neck and head build.
Run with build/hardware-layout/venv/bin/python hardware/enclosure/head.py: builds all five parts,
runs every check, and writes STLs, a STEP, the checks JSON, and two PNGs to output/.
"""

import datetime
import json
import sys
from math import atan2, cos, degrees, radians, sin, sqrt, tan
from pathlib import Path

import cadquery as cq
import matplotlib
import numpy as np
import trimesh
from interface import CABLE_DEG, CABLE_XY, HEAD_FLOOR_Z, HEAD_SCREWS_XY

import neck

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.collections import PolyCollection  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent)]
import printcheck  # noqa: E402
from geometry import head_envelopes  # noqa: E402

OUT = HERE / "output"
HEAD_Z0, HEAD_Z1, HEAD_W, HEAD_R = HEAD_FLOOR_Z, 236.0, 116.0, 22.0
HEAD_CZ = (HEAD_Z0 + HEAD_Z1) / 2  # 208, also the camera height
REAR_Y, RIM_Y, FRONT_Y = (
    40.0,
    -37.0,
    -40.0,
)  # head rear, shell rim (the visor sits on it), visor front
WALL, FLOOR = 3.2, 5.4
REAR_CHAMFER = (2.93, 2.83)  # 46 degrees: tangent to the approved 5 mm rear fillet, prints clean
FLOOR_CB_DEPTH = 3.0
CAMERA_XZ = (-24.0, HEAD_CZ)  # camera position in geometry.py
BOARD, BOARD_T, LENS_D, LENS_L = 38.0, 1.6, 15.0, 23.0
# Camera holes: Arducam lists a 34 x 34 mm pattern for the B0200, and it fit the test piece after
# 32.3 and 33.76 missed (Dylan, 2026-10-15).
STANDOFF_PITCH = 34.0
PILOT_D = 2.1  # M2 pilot that fit the test piece; 1.7 and 1.9 printed too tight
VISOR_T, LENS_RECESS, LENS_HOLE_D = 3.0, 0.5, 19.0
LENS_TIP_Y = FRONT_Y + LENS_RECESS
BOARD_FRONT_Y = LENS_TIP_Y + LENS_L
M2_LENGTH, PILOT_DEPTH = 8, 7.0
EYE_X, EYE_R = 22.0, 11.0  # second eye: the approved concept circle, as a groove in the visor face
EYE_GROOVE_W, EYE_GROOVE_DEPTH = 1.2, 0.6
FOV_HALF_DEG = 50.0  # about 100 degrees diagonal
CAVITY_W = HEAD_W - 2 * WALL
CAVITY_Z0, CAVITY_Z1 = HEAD_Z0 + FLOOR, HEAD_Z1 - WALL
# Visor retention: two M3 screws go up from below through the floor into nut slots in two tabs.
VISOR_SCREWS_XY = ((-24.0, -30.0), (24.0, -30.0))
VISOR_CB_DEPTH = 3.0
TAB_W, TAB_END_Y = 14.0, -24.0
TAB_BASE = neck.MIN_SECTION  # tab under the nut: the nut pulls down on it
TAB_SLOT_Z0 = CAVITY_Z0 + TAB_BASE
TAB_SLOT_Z1 = TAB_SLOT_Z0 + neck.NUT_T
TAB_TOP_Z = TAB_SLOT_Z1 + neck.MIN_SECTION
HEAD_SCREW_L, VISOR_SCREW_L = 8, 8
SCREWS = neck.NECK_SCREWS + [
    # head screws: thread meets the nut at the flange skin; visor screws: at the tab slot floor
    (
        "head",
        HEAD_SCREWS_XY,
        CAVITY_Z0 - FLOOR_CB_DEPTH,
        HEAD_SCREW_L,
        neck.FLANGE_NUT_TOP_Z,
        False,
    ),
    ("visor", VISOR_SCREWS_XY, HEAD_Z0 + VISOR_CB_DEPTH, VISOR_SCREW_L, TAB_SLOT_Z0, True),
]


def plane(y):
    "XZ workplane at Y = y; extrude() then runs toward -Y."
    return cq.Workplane("XZ").workplane(offset=-y)


def rounded(y, width, z0, z1, radius, depth):
    "Rounded rectangle in X and Z from Y = y, extruded `depth` toward -Y."
    return (
        plane(y)
        .center(0, (z0 + z1) / 2)
        .rect(width, z1 - z0)
        .extrude(depth)
        .edges("|Y")
        .fillet(radius)
    )


def teardrop(r, xy, z0, z1, toward=-1):
    "Vertical hole with a 45 degree point toward Y = `toward` (the print-up side): no support."
    x, y = xy
    k = r / sqrt(2)
    tri = (
        cq.Workplane("XY")
        .workplane(offset=z0)
        .polyline([(x - k, y + toward * k), (x, y + toward * r * sqrt(2)), (x + k, y + toward * k)])
        .close()
        .extrude(z1 - z0)
        .val()
    )
    return neck.cyl(r, z0, z1, xy).fuse(tri)


def head_shell():
    outer = rounded(REAR_Y, HEAD_W, HEAD_Z0, HEAD_Z1, HEAD_R, REAR_Y - RIM_Y)
    outer = outer.faces(">Y").edges().chamfer(*REAR_CHAMFER)
    inner = rounded(
        REAR_Y - WALL, CAVITY_W, CAVITY_Z0, CAVITY_Z1, HEAD_R - WALL, REAR_Y - WALL - RIM_Y + 1
    )
    solid = outer.cut(inner).val()
    for (
        xy
    ) in HEAD_SCREWS_XY:  # flange screws: hole and counterbore, reached through the front opening
        solid = solid.cut(teardrop(1.7, xy, HEAD_Z0 - 1, CAVITY_Z0 + 1))
        solid = solid.cut(teardrop(3.2, xy, CAVITY_Z0 - FLOOR_CB_DEPTH, CAVITY_Z0 + 1))
    for xy in VISOR_SCREWS_XY:  # visor screws: hole and counterbore, reached from below the head
        solid = solid.cut(teardrop(1.7, xy, HEAD_Z0 - 1, CAVITY_Z0 + 1))
        solid = solid.cut(teardrop(3.2, xy, HEAD_Z0 - 1, HEAD_Z0 + VISOR_CB_DEPTH))
    return solid.cut(cable_hole()).clean()  # the camera cable leaves through the floor


def cable_hole():
    return neck.cable_hole(HEAD_Z0 - 1, CAVITY_Z0 + 1, HEAD_Z0, False)


def standoff_xz():
    h = STANDOFF_PITCH / 2
    return [(CAMERA_XZ[0] + sx * h, CAMERA_XZ[1] + sz * h) for sx in (-1, 1) for sz in (-1, 1)]


def eye_groove():
    "Ring groove on the visor front face; printed face down, its ceiling is a 1.2 mm bridge."
    start = cq.Vector(EYE_X, FRONT_Y - 1, HEAD_CZ)
    outer = cq.Solid.makeCylinder(EYE_R, 1 + EYE_GROOVE_DEPTH, start, cq.Vector(0, 1, 0))
    return outer.cut(cq.Solid.makeCylinder(EYE_R - EYE_GROOVE_W, 3, start, cq.Vector(0, 1, 0)))


def visor():
    plate = rounded(RIM_Y, HEAD_W - 4, HEAD_Z0 + 2, HEAD_Z1 - 2, HEAD_R - 2, VISOR_T)
    plate = plate.faces("<Y").edges().chamfer(1.0).val()  # 45 degrees keeps the bed edge printable
    ring = rounded(RIM_Y, CAVITY_W - 0.4, CAVITY_Z0 + 0.2, CAVITY_Z1 - 0.2, HEAD_R - WALL - 0.2, -3)
    ring = ring.cut(
        rounded(
            RIM_Y, CAVITY_W - 0.4 - 4.8, CAVITY_Z0 + 2.6, CAVITY_Z1 - 2.6, HEAD_R - WALL - 2.6, -3
        )
    )
    solid = plate.fuse(ring.val())  # the ring is the locating lip inside the head opening
    along_y = cq.Vector(0, 1, 0)
    for x, z in standoff_xz():  # four 7 mm posts carry the camera on M2 screws
        post = cq.Solid.makeCylinder(
            3.5, BOARD_FRONT_Y - RIM_Y + 0.5, cq.Vector(x, RIM_Y - 0.5, z), along_y
        )
        solid = solid.fuse(post)
        pilot = cq.Vector(x, BOARD_FRONT_Y - PILOT_DEPTH, z)
        solid = solid.cut(cq.Solid.makeCylinder(PILOT_D / 2, PILOT_DEPTH + 0.5, pilot, along_y))
    lens_hole = cq.Vector(CAMERA_XZ[0], FRONT_Y - 1, CAMERA_XZ[1])
    solid = solid.cut(cq.Solid.makeCylinder(LENS_HOLE_D / 2, 5, lens_hole, along_y))
    solid = solid.cut(eye_groove())
    for x, y in VISOR_SCREWS_XY:  # screw tab above the floor, nut slot open to the rear
        tab_y0 = RIM_Y - 0.5
        tab = neck.box(
            TAB_W, TAB_END_Y - tab_y0, CAVITY_Z0, TAB_TOP_Z, (x, (tab_y0 + TAB_END_Y) / 2)
        )
        slot = neck.nut_slot((x, y), TAB_SLOT_Z0, TAB_SLOT_Z1, 90, 12)
        solid = (
            solid.fuse(tab).cut(slot).cut(teardrop(1.7, (x, y), CAVITY_Z0 - 1, TAB_TOP_Z + 1, 1))
        )
    return solid.clean()


def camera_ghosts():
    "Measured camera: 38 mm board, 15 x 23 mm lens holder, 6 mm heatsink, 4 mm connector."
    x, z = CAMERA_XZ
    back = BOARD_FRONT_Y + BOARD_T

    def box(size, center):
        return cq.Workplane("XY").box(*size).translate(center).val()

    return {
        "camera board": box((BOARD, BOARD_T, BOARD), (x, BOARD_FRONT_Y + BOARD_T / 2, z)),
        "camera lens holder": cq.Solid.makeCylinder(
            LENS_D / 2, LENS_L, cq.Vector(x, LENS_TIP_Y, z), cq.Vector(0, 1, 0)
        ),
        "camera heatsink": box((26, 6, 26), (x, back + 3, z)),
        "camera connector": box((14, 4, 10), (x, back + 2, z + BOARD / 2 - 8)),
    }


def view_cone():
    "100 degree diagonal view cone from the lens front face, 60 mm long."
    length = 60.0
    return cq.Solid.makeCone(
        LENS_D / 2,
        LENS_D / 2 + length * tan(radians(FOV_HALF_DEG)),
        length,
        cq.Vector(CAMERA_XZ[0], LENS_TIP_Y, CAMERA_XZ[1]),
        cq.Vector(0, -1, 0),
    )


def nut_ghosts():
    "Real M3 nuts in their traps, pulled against the load face by the screw."
    out = {}
    flange_z0 = neck.FLANGE_NUT_TOP_Z - 2.4
    for i, xy in enumerate(HEAD_SCREWS_XY):
        out[f"flange nut {i}"] = neck.nut_ghost(xy, flange_z0, degrees(atan2(xy[1], xy[0])))
    for i, xy in enumerate(VISOR_SCREWS_XY):
        out[f"tab nut {i}"] = neck.nut_ghost(xy, TAB_SLOT_Z0, 90)
    out["disc nut"] = neck.nut_ghost((0, 0), neck.NUT_CEILING_Z - 2.4, 30)
    return out


def head_checks(parts, neck_parts):
    "Overlap, seating, screw, camera, and section checks. Raises on failure."
    shell, vis = parts["head shell"], parts["visor"]
    everything = parts | neck_parts
    cam = camera_ghosts()
    ghosts = dict(cam) | nut_ghosts() | neck.screw_ghosts(SCREWS)
    ghosts["lower inner race"], ghosts["lower outer race"] = neck.bearing(neck.LOWER_Z)
    ghosts["upper inner race"], ghosts["upper outer race"] = neck.bearing(
        neck.HUB_TOP_Z - neck.BEARING_W
    )
    servo = dict(zip(("servo case", "servo horn"), neck.servo_ghosts(), strict=True))
    ghosts |= servo
    out = {}
    names = list(everything)
    for i, a in enumerate(names):
        assert everything[a].isValid() and len(everything[a].Solids()) == 1, a
        for b in names[i + 1 :]:
            assert neck.overlap(everything[a], everything[b]) < 1e-3, (a, b)
        bad = [g for g, s in ghosts.items() if neck.overlap(everything[a], s) > 1e-3]
        assert not bad, (a, bad)
    clash = [
        g
        for g, s in ghosts.items()
        if "screw" in g and not g.startswith("horn")
        for v in servo.values()
        if neck.overlap(s, v) > 1e-3
    ]
    assert not clash, clash
    out["no overlap"] = (
        f"five parts against each other and {len(ghosts)} ghosts (bearing races, servo, camera, "
        "every screw, every nut): all below 0.001 mm3"
    )
    assert vis.distance(shell) < 1e-6 and neck_parts["head shaft"].distance(shell) < 1e-6
    out["seating"] = (
        "visor sits on the shell rim, its tabs on the floor, the shaft flange on the head floor"
    )
    out["screws"] = neck.screw_report(SCREWS)
    nuts = nut_ghosts()  # each nut touches the face the screw pulls it against
    assert (
        nuts["tab nut 0"].distance(vis) < 1e-6
        and nuts["flange nut 0"].distance(neck_parts["head shaft"]) < 1e-6
    )
    assert nuts["disc nut"].distance(neck_parts["horn disc"]) < 1e-6
    angles = {
        f"flange nut {i}": ("head shaft", atan2(xy[1], xy[0]))
        for i, xy in enumerate(HEAD_SCREWS_XY)
    }
    angles |= {f"tab nut {i}": ("visor", radians(90)) for i in range(len(VISOR_SCREWS_XY))}
    for name, (owner, angle) in angles.items():  # 1 mm toward the mouth meets a ridge
        back = nuts[name].translate(cq.Vector(cos(angle), sin(angle), 0))
        assert neck.overlap(back, everything[owner]) > 0.01, name
    out["visor retention"] = (
        "two M3 x 8 screws up through the floor lip into nut slots in two visor tabs; the "
        "spigot ring locates the visor; no flexing part"
    )
    groove = eye_groove()
    y, z = FRONT_Y + EYE_GROOVE_DEPTH / 2, HEAD_CZ
    assert not vis.isInside(cq.Vector(EYE_X + EYE_R - 0.6, y, z), 1e-3)  # groove is empty
    assert vis.isInside(cq.Vector(EYE_X, y, z), 1e-3)  # circle inside it stays solid
    assert vis.isInside(cq.Vector(EYE_X + EYE_R - 0.6, FRONT_Y + 1.0, z), 1e-3)  # floor remains
    eye_gaps = [groove.distance(g) for g in cam.values()]
    assert min(eye_gaps) >= 10
    out["second eye"] = (
        f"{2 * EYE_R:.0f} mm circle groove at X {EYE_X:.0f}, {EYE_GROOVE_W} wide, "
        f"{EYE_GROOVE_DEPTH} deep: {min(eye_gaps):.0f} mm from camera"
    )
    cone = view_cone()
    assert neck.overlap(cone, vis) < 1e-3 and neck.overlap(cone, shell) < 1e-3
    assert neck.overlap(cone, neck_parts["head shaft"]) < 1e-3
    out["camera view"] = (
        f"100 deg cone from the lens front clears visor, shell, and shaft; lens tip "
        f"{LENS_RECESS} mm behind the visor face, opening {LENS_HOLE_D} mm"
    )
    h = STANDOFF_PITCH / 2
    assert all(abs(abs(x - CAMERA_XZ[0]) - h) < 1e-9 for x, _ in standoff_xz())
    m2_tip = BOARD_FRONT_Y - (M2_LENGTH - BOARD_T)  # tip depth in the post, measured along Y
    assert BOARD_FRONT_Y - m2_tip >= 5 and m2_tip >= BOARD_FRONT_Y - PILOT_DEPTH
    out["camera mount"] = (
        f"4 M2 x {M2_LENGTH} screws into 7 mm posts with {PILOT_D} mm pilots, "
        f"{STANDOFF_PITCH:.2f} mm square; board "
        f"center Y {BOARD_FRONT_Y + BOARD_T / 2:.1f}, {-4 - BOARD_FRONT_Y - BOARD_T / 2:.1f} mm in "
        "front of the geometry.py position (X and Z unchanged)"
    )
    hx, hy = CABLE_XY
    ux, uy = -sin(radians(CABLE_DEG)), cos(radians(CABLE_DEG))  # tangent; the radial is (uy, -ux)
    w, h = neck.CABLE_HOLE
    for a, b in ((0, 0), (0.45, 0.45), (-0.45, 0.45), (0.45, -0.45), (-0.45, -0.45)):
        x = hx + ux * a * w + uy * b * h  # points inside the hole, at the floor's mid height
        y = hy + uy * a * w - ux * b * h
        assert not shell.isInside(cq.Vector(x, y, HEAD_Z0 + FLOOR / 2), 1e-3)
    rim = 1.0 + neck.CABLE_FLARE  # a ring 1 mm outside the flare is still solid floor
    for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
        x = hx + ux * a * (w / 2 + rim) + uy * b * (h / 2 + rim)
        y = hy + uy * a * (w / 2 + rim) - ux * b * (h / 2 + rim)
        assert shell.isInside(cq.Vector(x, y, HEAD_Z0 + 0.3), 1e-3), (x, y)
    out["cable hole"] = (
        f"{w:.0f} x {h:.0f} mm through the floor at ({hx:.1f}, {hy:.1f}), 1 mm of floor all round "
        "the 1 mm flare on the underside; it replaces the old rear slot"
    )
    outside = shell.cut(head_envelopes()[0]).Volume()
    assert outside < 0.01 * shell.Volume()
    bb = shell.fuse(vis).BoundingBox()
    assert bb.xlen <= HEAD_W + 1e-6 and bb.zlen <= HEAD_Z1 - HEAD_Z0 + 1e-6 and bb.ylen <= 80 + 1e-6
    out["envelope"] = (
        f"{bb.xlen:.0f} x {bb.ylen:.0f} x {bb.zlen:.0f} mm; {outside:.0f} mm3 of the shell lies "
        "outside the approved head (the rear chamfer)"
    )
    sections = {
        "floor under the flange screw recess": FLOOR - FLOOR_CB_DEPTH,
        "floor under the visor screw recess": FLOOR - VISOR_CB_DEPTH,
        "visor plate under the eye groove": VISOR_T - EYE_GROOVE_DEPTH,
        "tab under the nut": TAB_BASE,
        "tab skin over the nut": TAB_TOP_Z - TAB_SLOT_Z1,
        "head wall": WALL,
    }
    assert all(v >= neck.MIN_SECTION - 1e-6 for v in sections.values()), sections
    out["sections"] = {k: round(v, 2) for k, v in sections.items()}
    return out


def rot(*rows):
    m = np.eye(4)
    m[:3, :3] = rows
    return m


# Print orientation: hub and disc as built, shaft flange down, head rear down, visor front down.
FLIP_X = rot((1, 0, 0), (0, -1, 0), (0, 0, -1))
HEAD_TURN = rot((1, 0, 0), (0, 0, 1), (0, -1, 0))  # X, Y, Z -> X, Z, -Y
VISOR_TURN = rot((1, 0, 0), (0, 0, -1), (0, 1, 0))  # X, Y, Z -> X, -Z, Y
PRINT = {  # name: (color folder, file, orientation)
    "head shell": ("White", "head-shell", HEAD_TURN),
    "visor": ("Black", "visor", VISOR_TURN),
    "hub": ("Black", "neck-hub", np.eye(4)),
    "head shaft": ("Black", "head-shaft", FLIP_X),
    "horn disc": ("Black", "horn-disc", np.eye(4)),
}


def build():
    neck_parts = {"hub": neck.hub(), "head shaft": neck.shaft(), "horn disc": neck.disc()}
    parts = {"head shell": head_shell(), "visor": visor()}
    checks = {f"neck {k}": v for k, v in neck.neck_checks(neck_parts).items()}
    checks |= {
        f"head {k}" if k != "screws" else k: v for k, v in head_checks(parts, neck_parts).items()
    }
    return parts | neck_parts, checks


def write_stls(solids):
    meshes, rows = {}, {}
    for name, (folder, stem, matrix) in PRINT.items():
        mesh = neck.to_print_mesh(solids[name], matrix)
        assert max(mesh.extents) < 256 and mesh.extents[2] < 256, name  # P1S bed and height
        dest = OUT / "print" / "Required" / folder / f"{stem}.stl"
        dest.parent.mkdir(parents=True, exist_ok=True)
        mesh.export(dest)
        meshes[name] = mesh
        rows[name] = printcheck.analyze(mesh) | {"file": str(dest.relative_to(OUT.parent.parent))}
    return meshes, rows


COLORS = {"White": "#e8e6df", "Black": "#2b2b2e"}
GHOST = "#8fa3b8"


def ghost_solids():
    lo_in, lo_out = neck.bearing(neck.LOWER_Z)
    up_in, up_out = neck.bearing(neck.HUB_TOP_Z - neck.BEARING_W)
    case, horn = neck.servo_ghosts()
    return {
        "bearing lower": cq.Compound.makeCompound([lo_in, lo_out]),
        "bearing upper": cq.Compound.makeCompound([up_in, up_out]),
        "servo case": case,
        "servo horn": horn,
    } | camera_ghosts()


def write_step(solids):
    assy = cq.Assembly(name="neck-head")
    for name, (folder, _, _) in PRINT.items():
        r, g, b = (int(COLORS[folder][i : i + 2], 16) / 255 for i in (1, 3, 5))
        assy.add(solids[name], name=name, color=cq.Color(r, g, b))
    for name, solid in ghost_solids().items():
        assy.add(solid, name="ghost " + name, color=cq.Color(0.56, 0.64, 0.72, 0.5))
    assy.export(str(OUT / "neck-head-assembly.step"), "STEP")


def tess(solid):
    vertices, faces = solid.tessellate(0.05, 0.2)
    mesh = trimesh.Trimesh([v.toTuple() for v in vertices], faces)
    mesh.merge_vertices()
    return mesh


def view_matrix(yaw, elev):
    "Rotation from Z-up model axes to screen axes (x right, y up, z toward the viewer)."
    a, t = radians(yaw), radians(elev - 90)
    rz = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
    rx = np.array([[1, 0, 0], [0, np.cos(t), -np.sin(t)], [0, np.sin(t), np.cos(t)]])
    return rx @ rz


def shade(ax, items, view):
    "Painter's algorithm: flat-shaded triangles, farthest first, back faces dropped."
    polys, colors, depth = [], [], []
    light = np.array([0.35, 0.55, 0.75])
    light /= np.linalg.norm(light)
    for mesh, color in items:
        tri = (mesh.vertices @ view.T)[mesh.faces]
        n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        keep = n[:, 2] > 0
        base = np.array(matplotlib.colors.to_rgb(color))
        lum = 0.45 + 0.55 * np.clip(n[keep] @ light, 0, 1)
        polys += list(tri[keep][:, :, :2])
        colors += list(np.clip(base * lum[:, None], 0, 1))
        depth += list(tri[keep][:, :, 2].mean(1))
    order = np.argsort(depth)
    ax.add_collection(
        PolyCollection(
            [polys[i] for i in order], facecolors=[colors[i] for i in order], edgecolors="none"
        )
    )
    ax.autoscale()
    ax.set_aspect("equal")
    ax.axis("off")


def section_lines(ax, items, normal, axes):
    for mesh, color in items:
        path = mesh.section(
            plane_origin=[0, 0, 0] if normal[1] else [-24, 0, 0], plane_normal=normal
        )
        for line in path.discrete if path is not None else []:
            ax.plot(line[:, axes[0]], line[:, axes[1]], color=color, lw=1.1)
    ax.set_aspect("equal")
    ax.axis("off")


def render_assembly(solids):
    parts = [(tess(solids[n]), COLORS[PRINT[n][0]]) for n in PRINT]
    ghosts = [(tess(s), GHOST) for s in ghost_solids().values()]
    fig, axs = plt.subplots(1, 3, figsize=(18, 6))
    shade(
        axs[0], [(m, "#c9c9cf") if c == "#2b2b2e" else (m, c) for m, c in parts], view_matrix(0, 0)
    )
    axs[0].set_title("Front, no ghosts (black parts lightened)")
    # Y = 0 plane (through the yaw axis): X across, Z up. X = -24 plane (through the camera): Y, Z.
    section_lines(axs[1], [(m, "#222") for m, _ in parts] + ghosts, [0, 1, 0], (0, 2))
    axs[1].set_title("Section through the yaw axis (Y = 0)")
    section_lines(axs[2], [(m, "#222") for m, _ in parts] + ghosts, [1, 0, 0], (1, 2))
    axs[2].set_title("Section through the camera (X = -24); front is to the left")
    fig.savefig(OUT / "neck-head-assembly.png", dpi=110, bbox_inches="tight")
    plt.close(fig)


def render_print(meshes, rows):
    fig, ax = plt.subplots(figsize=(16, 6))
    view = view_matrix(-35, 35)
    x, items = 0.0, []
    for name, mesh in meshes.items():
        shifted = mesh.copy()
        shifted.apply_translation([x + mesh.extents[0] / 2 - 0, 0, 0])
        items.append((shifted, "#cfcfd6" if PRINT[name][0] == "Black" else "#e8e6df"))
        r = rows[name]
        proj = np.array([x + mesh.extents[0] / 2, 0, 0]) @ view.T
        ax.text(
            proj[0],
            -mesh.extents[1] * 0.45 - 38,
            f"{name}\noverhang {r['overhang_mm2']} mm2",
            ha="center",
            fontsize=8,
        )
        x += mesh.extents[0] + 55
    shade(ax, items, view)
    ax.set_title("Parts in print orientation on the bed (black parts lightened)")
    fig.savefig(OUT / "neck-head-print-orientation.png", dpi=110, bbox_inches="tight")
    plt.close(fig)


def main():
    OUT.mkdir(exist_ok=True)
    solids, checks = build()
    meshes, rows = write_stls(solids)
    write_step(solids)
    render_assembly(solids)
    render_print(meshes, rows)
    totals = {
        k: round(sum(r[k] for r in rows.values()), 1)
        for k in ("overhang_mm2", "floating_islands", "thin_mm2")
    }
    report = {
        "date": datetime.date.today().isoformat(),
        "checks": checks,
        "printcheck": rows,
        "printcheck_totals": totals,
    }
    (OUT / "neck-head-checks.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(totals))


if __name__ == "__main__":
    main()
