"""Simplified body: roof-down shell (A1), base plate, port panel and speaker grille, in mm.
Run with `build/hardware-layout/venv/bin/python`; every run rebuilds, asserts the checks and
writes STL, STEP, PNG and body-checks.json to hardware/enclosure/output/.
"""

import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from math import atan, atan2, cos, degrees, radians, sin, sqrt, tan
from pathlib import Path

import cadquery as cq
import numpy as np
import trimesh

HARDWARE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HARDWARE)]
import interface as ifc  # noqa: E402
import neck  # noqa: E402
import printcheck  # noqa: E402
from geometry import (  # noqa: E402
    BAND_Y, BODY_SECTIONS, BUS_T, JETSON_PARTS, PLUG_FLOOR_Z, SLOT_GAP, SLOT_WALL, WALL,
    body_envelopes, hardware,
)  # fmt: skip

OUT = Path(__file__).resolve().parent / "output"
HEIGHT = BODY_SECTIONS[-1][0]
BASE_ROLL, SHOULDER_ROLL = BODY_SECTIONS[0][3], BODY_SECTIONS[-1][3]
NECK_R = ifc.ROOF_HOLE_D / 2
LIP_DEG = 46  # 45 degree limit plus 1 degree so tessellation noise stays off printcheck's threshold
P1S_MM = 256
SUPPORT_DEG = 50  # underside slope of every feature that hangs from a wall, steeper than 45
K_SUPPORT = tan(radians(SUPPORT_DEG))

# Seat: the shell is cut at CUT_Z; the cavity outline of OPEN_Z is kept straight below OPEN_Z so the
# seat has a 1.3 mm vertical inner wall and is 3.1 mm wide (a cut at OPEN_Z left a knife edge).
CUT_Z = 7.6
CORNER = (52.5, 41.8)  # centre of the plan corner arcs, measured on the body sections (mm)
SCREW_RHO = 9.5  # plate screw distance from the corner centre, on the diagonal
M3_CLEAR, NUT_AF, NUT_T = 3.4, 5.7, 2.4  # M3 nut: 5.5 mm across flats in a 5.7 mm pocket
HUB_BOSS_Z, NUT_FLOOR = 152.0, 2.0  # hub boss bottom; the nut sits on a 2 mm floor above it
HUB_NUT_Z = (HUB_BOSS_Z + NUT_FLOOR, ifc.ROOF_BOTTOM_Z)  # nut channel floor and ceiling
CORNER_NUT_Z = (CUT_Z + NUT_FLOOR, CUT_Z + NUT_FLOOR + NUT_T + 0.4)
HUB_SCREW_TIP_Z = 153.4  # neck.py: M3 x 16 screws seat at Z 169.4
BLOCK_W, BLOCK_RHO = 10.6, 5.8  # plate screw boss width; its start from the corner centre
SERVO_WALL, SERVO_GUSSET = 3.2, 6.0  # servo pocket wall thickness; gusset leg into the roof
HORN_R = 15.5  # the 31 mm horn disc
PLATE_SCREW_LEN, TIP_CLEAR_Z = 10.0, 14.5  # M3 x 10; hole above the nut clears the tip
CB_D, CB_DEPTH = 6.5, 3.2  # plate screw counterbore: socket, button, pan, or flat M3 head
PANEL_CB_D, PANEL_CB_DEPTH = (
    6.0,
    3.0,
)  # panel counterbore, in the 3.2 mm plug: 6.0 keeps 2 mm to its edge
WALL_FRONT, WALL_SIDE = (0.0, -65.0), (76.0, 0.0)  # outer wall planes at Z 0 (front -Y, side +X)
LEAN_FRONT = degrees(atan((BODY_SECTIONS[0][2] - BODY_SECTIONS[-1][2]) / 2 / HEIGHT))
LEAN_SIDE = degrees(atan((BODY_SECTIONS[0][1] - BODY_SECTIONS[-1][1]) / 2 / HEIGHT))
POCKET_GAP, POCKET_WALL = 1.0, 2.4
NUT_AF_MAX = 5.5  # M3 nut across flats
RIDGE_H, RIDGE_BACK = 0.3, 2.2  # detent height; crest this far behind the seated nut's centre
WINDOW_Y, WINDOW_TOP, PANEL_GAP = (-18.0, 30.0), 117.0, 0.5  # port window, inner top in wall frame
SIDE_TAPER, TOP_TAPER = tan(radians(20)), 0.0  # window wider outside; the top edge is straight
SPEAKER_SHIFT = 2.0  # the 100 x 45 x 21 speaker front (Y -56) is deeper than the 110.3 mm opening
GRILLE_ZC = 47.5 / cos(radians(LEAN_FRONT))
WALL_BOTTOM = 124.0  # servo pocket walls end here
SKIRT_TOP = 24.5  # the roll of the +X wall below this height belongs to the plate (port skirt)
PORT_NOTCH = (-1.5, 22.5)  # power and cable exit in the skirt top edge, Y range
PANEL_SCREW = (-12.5, 32.0 / cos(radians(LEAN_SIDE)))  # y and z in the side wall frame
PANEL_BOSS = (10.0, 5.0)  # diameter and height inside the panel
PANEL_NUT_X, PANEL_SCREW_LEN = (59.4, 62.2), 12.0  # nut slot in the plate ear; M3 x 12
GRILLE_WINDOW, GRILLE_RECESS = (96.0, 44.0), (102.0, 50.0)  # rounded-end window and its seat
GRILLE_FLANGE, GRILLE_PLUG = (101.2, 49.2), (94.8, 42.8)  # insert: rear flange; plug 0.6 mm clear
SEAT_D, FACE_D, BACK_D = 2.4, 0.5, 4.8  # depths from the outer face: seat, grille face, flange back
SLOT_GRIP, SLOT_TOP = 8.0, 48.0  # slot grips 8 of the strip's 10 mm (Dylan); walls reach Z 48
RIM_H = 10.0  # the shallow pocket's far wall rises this far above the Jetson's bottom edge


# Helpers shared with study.py ----------------------------------------------------------------


def box(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))


def cyl(x, y, r, z0, z1, axis=(0, 0, 1)):
    return cq.Solid.makeCylinder(r, z1 - z0, cq.Vector(x, y, z0), cq.Vector(*axis))


def keep_z(solid, z0, z1):
    return solid.intersect(box(-300, 300, -300, 300, z0, z1))


def flip(solid):
    "Turn the body over so the roof lies on the bed."
    return solid.rotate((0, 0, 0), (1, 0, 0), 180).translate((0, 0, HEIGHT))


def chain(wire):
    "Edges of a closed wire as (edge, forward) in connected order."
    left = list(wire.Edges())
    edge = left.pop(0)
    out, end = [(edge, True)], edge.endPoint()
    while left:
        for i, edge in enumerate(left):
            if (edge.startPoint() - end).Length < 1e-3:
                fwd = True
            elif (edge.endPoint() - end).Length < 1e-3:
                fwd = False
            else:
                continue
            out.append((left.pop(i), fwd))
            end = edge.endPoint() if fwd else edge.startPoint()
            break
        else:
            raise RuntimeError("open wire")
    return out


def offset_wire(wire, dist, dz, samples=40):
    "Inward offset of a convex closed wire, as one spline per edge (same edge count as the input)."
    c = wire.Center()
    runs = []
    for edge, fwd in chain(wire):
        pts = []
        for t in np.linspace(0, 1, samples):
            p, tg = edge.positionAt(t if fwd else 1 - t), edge.tangentAt(t if fwd else 1 - t)
            n = np.array([tg.y, -tg.x]) / np.hypot(tg.x, tg.y)
            if n @ [c.x - p.x, c.y - p.y] < 0:
                n = -n
            pts.append(cq.Vector(p.x + n[0] * dist, p.y + n[1] * dist, p.z + dz))
        runs.append(pts)
    for i, run in enumerate(runs):
        run[-1] = runs[(i + 1) % len(runs)][0]
    return cq.Wire.assembleEdges([cq.Edge.makeSpline(run) for run in runs])


def chamfer_bed(solid, roll_r):
    """Replace the bed-side arc of a roll with a LIP_DEG chamfer tangent to the rest of the arc.
    The solid sits on Z 0. The chamfer only adds material, never removes it."""
    zp = roll_r * (1 - cos(radians(LIP_DEG)))
    upper = keep_z(solid, zp, 400)
    ring = cq.Workplane(obj=upper).faces("<Z").val().outerWire()
    wedge = cq.Solid.makeLoft([offset_wire(ring, zp / tan(radians(LIP_DEG)), -zp), ring], True)
    out = upper.fuse(wedge).clean()
    assert out.isValid() and len(out.Solids()) == 1
    return out


def base_roll_cut(cut_deg):
    "Real-frame Z where the cavity roll (radius ROLL - WALL, centre Z ROLL) has turned cut_deg."
    return BASE_ROLL - (BASE_ROLL - WALL) * cos(radians(cut_deg))


def to_print_mesh(solid, deflection=0.05, angle=0.2):
    "Tessellate, then centre on X and Y and put the lowest point on the bed."
    vertices, faces = solid.tessellate(deflection, angle)
    mesh = trimesh.Trimesh([v.toTuple() for v in vertices], faces)
    mesh.merge_vertices()
    mesh.apply_translation(-mesh.bounds[0] - [mesh.extents[0] / 2, mesh.extents[1] / 2, 0])
    return mesh


OPEN_Z = base_roll_cut(LIP_DEG)


def outer_shell():
    "Outer envelope with the roof edge chamfered (the A1 variant of the study), assembly frame."
    return flip(chamfer_bed(flip(body_envelopes()[0]), SHOULDER_ROLL))


def shell_blank():
    "A1 shell, assembly frame: cavity kept straight from OPEN_Z down to the seat, roof hole cut."
    inner = body_envelopes()[1]
    face = cq.Workplane(obj=keep_z(inner, OPEN_Z, OPEN_Z + 0.01)).faces("<Z").val()
    lip = cq.Solid.extrudeLinear(face, cq.Vector(0, 0, -OPEN_Z - 1))
    cavity = inner.fuse(lip)
    blank = outer_shell().cut(cavity).cut(cyl(0, 0, NECK_R, -1, HEIGHT + 1))
    return keep_z(blank, CUT_Z, HEIGHT + 1)


# Wall frames: x outward, y along the wall (side) or inward (front), z up along the wall ---------


def side_to_world(solid):
    return solid.rotate((0, 0, 0), (0, 1, 0), -LEAN_SIDE).translate((*WALL_SIDE, 0))


def world_to_side(solid):
    return solid.translate((-WALL_SIDE[0], 0, 0)).rotate((0, 0, 0), (0, 1, 0), LEAN_SIDE)


def front_to_world(solid):
    "Front wall frame: x = X, y = depth inward from the outer plane, z = up along the wall."
    return solid.rotate((0, 0, 0), (1, 0, 0), -LEAN_FRONT).translate((0, WALL_FRONT[1], 0))


def hex_pocket(x, y, z0, z1, rot=0.0, af=NUT_AF):
    "Hex nut pocket with a vertex on the direction rot (degrees), so flats are tangent to it."
    pocket = (
        cq.Workplane("XY", origin=(0, 0, z0))
        .polygon(6, af / cos(radians(30)))
        .extrude(z1 - z0)
        .val()
    )
    return pocket.rotate((0, 0, 0), (0, 0, 1), rot).translate((x, y, 0))


def screw_hole(x, y, z0, z1):
    return cyl(x, y, M3_CLEAR / 2, z0, z1)


def plate_screws():
    c = cos(radians(45))
    return [
        (sx * (CORNER[0] + SCREW_RHO * c), sy * (CORNER[1] + SCREW_RHO * c))
        for sx in (-1, 1)
        for sy in (-1, 1)
    ]


# Shell ---------------------------------------------------------------------------------------


def at_corner(solid, sx, sy):
    "Move a solid built along +X from the corner centre onto the diagonal of corner (sx, sy)."
    turned = solid.rotate((0, 0, 0), (0, 0, 1), degrees(atan2(sy, sx)))
    return turned.translate((sx * CORNER[0], sy * CORNER[1], 0))


def corner_block(sx, sy, outer):
    """Screw boss for the base plate: a 10.6 mm block on the corner diagonal, tallest at the wall.
    Its underside in print orientation is a 50 degree cone, so it hangs from the wall without
    support."""
    top, r_wall = CUT_Z + 23.5, 18.6  # r_wall: cavity radius about the corner centre above the roll
    block = at_corner(box(BLOCK_RHO, 24, -BLOCK_W / 2, BLOCK_W / 2, CUT_Z, top), sx, sy)
    h = r_wall * K_SUPPORT  # cone with its apex on the corner centre axis and its base at the wall
    cone = cq.Solid.makeCone(
        0.01, r_wall, h, cq.Vector(sx * CORNER[0], sy * CORNER[1], top - h), cq.Vector(0, 0, 1)
    )
    return block.cut(cone).intersect(outer)


def servo_walls():
    """Two 3.2 mm walls on the long sides of the servo, 1 mm clear, hanging from the roof with a
    gusset on the outer side. They stop at the roof hole edge (a wall cut by the hole would leave
    a thin sliver)."""
    c, case, gap = ifc.SERVO_CASE_CENTER_XY, ifc.SERVO_CASE, ifc.POCKET_CLEARANCE
    x0, x1 = c[0] - case[0] / 2 - gap, -sqrt(NECK_R**2 - (case[1] / 2 + gap) ** 2) - 0.5
    y_in, z1 = case[1] / 2 + gap, ifc.ROOF_BOTTOM_Z + 0.5
    y_out, g = y_in + SERVO_WALL, SERVO_GUSSET
    tri = [(y_out - 0.5, z1), (y_out + g, z1), (y_out - 0.5, z1 - (g + 0.5) * K_SUPPORT)]
    gusset = cq.Workplane("YZ", origin=(x0, 0, 0)).polyline(tri).close().extrude(x1 - x0).val()
    out = []
    for side in (-1, 1):
        wall = box(x0, x1, y_in, y_out, WALL_BOTTOM, z1)
        piece = wall.fuse(gusset)
        out.append(piece if side > 0 else piece.mirror("XZ"))
    return out


def detent_ridges(r_nut, z0, z1):
    """Triangular ridge on each wall of a nut channel (radial along +x, nut centre at r_nut).
    The nut's flats fit 0.4 mm inside the ridges, so it snaps past them and cannot slide back
    out. The crest sits where the seated nut is still narrow, so the nut can move back 0.5 mm."""
    r, h, half = r_nut - RIDGE_BACK, RIDGE_H, NUT_AF / 2
    out = []
    for side in (-1, 1):
        pts = [(r - 0.5, side * half), (r + 0.5, side * half), (r, side * (half - h))]
        prism = cq.Workplane("XY", origin=(0, 0, z0)).polyline(pts).close().extrude(z1 - z0)
        out.append(prism.val())
    return out


def hub_bosses():
    return [cyl(x, y, 6, HUB_BOSS_Z, ifc.ROOF_BOTTOM_Z + 0.5) for x, y in ifc.HUB_SCREWS_XY]


def hub_cuts():
    """Screw hole and a nut slot above a 2 mm floor, entered from the roof hole side. The slot
    walls stop the nut turning and the floor stops it falling out when the shell is roof up."""
    z0, z1 = HUB_NUT_Z
    cuts = []
    for x, y in ifc.HUB_SCREWS_XY:
        r, angle = np.hypot(x, y), degrees(atan2(y, x))
        channel = box(0, r, -NUT_AF / 2, NUT_AF / 2, z0, z1).cut(*detent_ridges(r, z0, z1))
        channel = channel.rotate((0, 0, 0), (0, 0, 1), angle)
        cuts += [
            screw_hole(x, y, HUB_BOSS_Z - 1, ifc.ROOF_TOP_Z + 1),
            hex_pocket(x, y, z0, z1, angle),
        ]
        cuts.append(channel)
    return cuts


def corner_cuts():
    """Plate screw hole through a 2 mm floor at the seat, and a nut slot above it that opens toward
    the corner centre, so the nut slides in from inside the opening and the floor holds it."""
    z0, z1 = CORNER_NUT_Z
    cuts = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            hole = at_corner(cyl(SCREW_RHO, 0, M3_CLEAR / 2, CUT_Z - 1, TIP_CLEAR_Z), sx, sy)
            pocket = at_corner(hex_pocket(SCREW_RHO, 0, z0, z1), sx, sy)
            channel = box(BLOCK_RHO - 2, SCREW_RHO, -NUT_AF / 2, NUT_AF / 2, z0, z1)
            slot_in = at_corner(channel.cut(*detent_ridges(SCREW_RHO, z0, z1)), sx, sy)
            cuts += [hole, pocket, slot_in]
    return cuts


def window_cutter(inset=0.0):
    """Port window as a loft in the side wall frame (t = 0 outer face, t = -WALL inner face). It is
    wider outside, so the panel cannot fall in, and taller inside, so the top edge hooks."""

    def rect(t):
        y0 = WINDOW_Y[0] - (t + WALL) * SIDE_TAPER + inset
        y1 = WINDOW_Y[1] + (t + WALL) * SIDE_TAPER - inset
        z1 = WINDOW_TOP - (t + WALL) * TOP_TAPER - inset
        pts = [(t, y0, -40), (t, y1, -40), (t, y1, z1), (t, y0, z1)]
        return cq.Wire.makePolygon([cq.Vector(*p) for p in pts], close=True)

    return side_to_world(cq.Solid.makeLoft([rect(1.0), rect(-15.0)], True))


def slot(cx, cz, face, width=3.0, length=32.0):
    "Vertical slot with pointed ends, so no end is a flat bridge in print orientation."
    h, w, rise = length / 2, width / 2, 0.55 * width
    pts = [(cx - w, cz + h), (cx, cz + h + rise), (cx + w, cz + h)]
    pts += [(cx + w, cz - h), (cx, cz - h - rise), (cx - w, cz - h)]
    if face == "-x":  # profile in (Y, Z), cut through the -X wall
        return cq.Workplane("YZ", origin=(-80, 0, 0)).polyline(pts).close().extrude(30).val()
    origin = (0, 80 if face == "+y" else -50, 0)  # profile in (X, Z), cut along Y
    return cq.Workplane("XZ", origin=origin).polyline(pts).close().extrude(30).val()


INTAKE_X = list(np.arange(-45.0, 36.0, 6.0))  # rear vents over the fan intake reservation
OUTLET_Y = list(np.arange(-4.5, 27.0, 6.0))  # left vents over the outlet reservation
VENT_ROWS = (44.0, 86.0)


def vent_cutters():
    rear = [slot(x, z, "+y") for x in INTAKE_X for z in VENT_ROWS]
    left = [slot(y, z, "-x") for y in OUTLET_Y for z in VENT_ROWS]
    return rear, left


def mic_hole(x, z):
    "Teardrop with its point down (up in print orientation), cut along Y through the front wall."
    wp = cq.Workplane("XZ", origin=(0, -40, 0))
    hole = wp.center(x, z).circle(1.7).extrude(40).val()
    tip = wp.polyline([(x - 1.2, z - 1.2), (x, z - 2.8), (x + 1.2, z - 1.2)]).close().extrude(40)
    return hole.fuse(tip.val())


MIC_X, MIC_Z = (-19.0, 19.0), 15.0


def stadium(w, h, z0, z1):
    "Window outline with fully rounded ends, as a prism in a print-like frame (z from z0 to z1)."
    return cq.Workplane("XY", origin=(0, 0, z0)).slot2D(w, h).extrude(z1 - z0).val()


def in_front_frame(solid, d0):
    "Solid built with z = depth and y = -height, placed at depth d0 in the front wall frame."
    local = solid.rotate((0, 0, 0), (1, 0, 0), -90).translate((0, d0, GRILLE_ZC))
    return front_to_world(local)


def grille_cutters():
    """Front window (one bridge across its top edge in print orientation, the single named
    overhang) and the seat behind it, which widens toward the cavity so it needs no support."""
    window = stadium(*GRILLE_WINDOW, 0, 4.0)
    w, h = GRILLE_RECESS
    lo = cq.Workplane(obj=stadium(w, h, 0, 1)).faces("<Z").val().outerWire()
    hi = cq.Workplane(obj=stadium(w + 4.5, h + 4.5, 0, 1)).faces("<Z").val().outerWire()
    recess = cq.Solid.makeLoft([lo, hi.translate(cq.Vector(0, 0, 2.1))], True)
    return [in_front_frame(window, -1.0), in_front_frame(recess, SEAT_D)]


def roof_hole():
    "Camera cable hole through the roof behind the hub, flared on the outside."
    return neck.cable_hole(ifc.ROOF_BOTTOM_Z - 1, ifc.ROOF_TOP_Z + 1, ifc.ROOF_TOP_Z, True)


def build_shell():
    outer = outer_shell()
    adds = (
        hub_bosses()
        + servo_walls()
        + [corner_block(sx, sy, outer) for sx in (-1, 1) for sy in (-1, 1)]
    )
    pre = shell_blank().fuse(*adds).cut(cyl(0, 0, NECK_R, -1, HEIGHT + 1))
    rear, left = vent_cutters()
    cuts = hub_cuts() + corner_cuts() + rear + left + grille_cutters()
    cuts += [mic_hole(x, MIC_Z) for x in MIC_X] + [window_cutter(), roof_hole()]
    return pre, pre.cut(*cuts)


# Components and base plate ---------------------------------------------------------------------


def reservation(item):
    b = item["shape"].BoundingBox()
    return (b.xmin, b.xmax, b.ymin, b.ymax, b.zmin, b.zmax)


def components():
    "Placed hardware boxes (x0, x1, y0, y1, z0, z1), from geometry.py or moved to the plate here."
    res = {i["name"]: reservation(i) for i in hardware()}
    sx0, sx1, sy0, sy1, sz0, sz1 = res["One speaker"]
    return {n: res[n] for n in JETSON_PARTS} | {
        "Speaker": (sx0, sx1, sy0 + SPEAKER_SHIFT, sy1 + SPEAKER_SHIFT, sz0, sz1),
        "USB audio case": (-26.5, 26.5, -54.9, -31.4, CUT_Z, CUT_Z + 14.6),
        "Bus board": res["Bus interface"],  # 42 x 13 x 32 on a long edge, on the plate
    }


def risers():
    "Everything that stands on the plate above CUT_Z, as named boxes (x0, x1, y0, y1, z0, z1)."
    comp = components()
    t, ports = comp["Jetson tray and board"], comp["Jetson ports"]
    s, a, bus = comp["Speaker"], comp["USB audio case"], comp["Bus board"]
    g, w, z = POCKET_GAP, POCKET_WALL, CUT_Z
    bus_l, bus_r = bus[0] - g - w, bus[1] + g + w  # bus end ribs' outer X
    back_x, grip_x = t[0] - SLOT_GAP, t[0] + SLOT_GRIP  # slot: inside of its back wall, open end
    y_out = (t[2] - SLOT_GAP - SLOT_WALL, t[3] + SLOT_GAP + SLOT_WALL)  # slot walls' outer faces
    front = (a[0] - g - w, a[1] + g + w, a[3] + g, a[3] + g + w)  # wall behind the audio case
    out = {
        "jetson sill": (t[0], t[1], t[2], t[3], z, t[4]),
        "jetson slot back wall": (back_x - SLOT_WALL, back_x, y_out[0], y_out[1], z, SLOT_TOP),
        "jetson slot wall -": (back_x, grip_x, y_out[0], t[2] - SLOT_GAP, z, SLOT_TOP),
        "jetson slot wall +": (back_x, grip_x, t[3] + SLOT_GAP, y_out[1], z, SLOT_TOP),
        "jetson back wall": (grip_x, bus_r, y_out[0], t[2] - g, z, SLOT_TOP),  # bus rear wall too
        "jetson rim": (grip_x, ports[0] - g, t[3] + g, y_out[1], z, t[4] + RIM_H),
        "audio side wall -": (a[0] - g - w, a[0] - g, a[2], front[3], z, z + 12.0),
        "audio side wall +": (a[1] + g, a[1] + g + w, a[2], front[3], z, z + 12.0),
        "audio and bus wall": (*front, z, z + 30.0),
        "bus end rib -": (bus_l, bus[0] - g, front[3], y_out[0], z, PLUG_FLOOR_Z),
        "bus end rib +": (bus[1] + g, bus_r, front[3], y_out[0], z, PLUG_FLOOR_Z),
        "panel ear": (56.0, 64.8, -19.9, -7.1, z, 40.0),
    }
    for side in (-1, 1):
        edge, outer = side * (s[1] + g), side * (s[1] + g + w)
        x0, x1 = sorted((side * (s[1] - 11.0), outer))
        out[f"speaker rail {side}"] = (x0, x1, s[2] + 6.0, s[3], z, s[4])
        out[f"speaker end wall {side}"] = (
            *sorted((edge, outer)),
            s[2] + 6.0,
            s[3] + g + w,
            z,
            s[4] + 20.0,
        )
        out[f"speaker rear wall {side}"] = (x0, x1, s[3] + g, s[3] + g + w, z, s[4] + 20.0)
    return out


def teardrop_hole(y, z, length):
    "Screw hole along -x in the side wall frame with its point up, so it is no bridge in print."
    r = M3_CLEAR / 2
    pts = [(y - r * 0.707, z + r * 0.707), (y, z + r * 1.65), (y + r * 0.707, z + r * 0.707)]
    wp = cq.Workplane("YZ", origin=(5, 0, 0))
    hole = wp.center(y, z).circle(r).extrude(-length).val()
    return hole.fuse(wp.polyline(pts).close().extrude(-length).val())


def panel_ear_cuts():
    "Screw hole along the panel screw axis and a vertical nut slot open at the top."
    y, zc = PANEL_SCREW
    slot_box = box(*PANEL_NUT_X, y - 3.0, y + 3.0, zc - 4.0, 40.0)
    return [side_to_world(teardrop_hole(y, zc, 40)), slot_box]


def build_plate(outer, skirt):
    face = cq.Workplane(obj=keep_z(outer, CUT_Z, CUT_Z + 0.01)).faces("<Z").val()
    plate = cq.Solid.extrudeLinear(face, cq.Vector(0, 0, -CUT_Z))
    plate = plate.fuse(skirt, *[box(*b) for b in risers().values()])
    cuts = panel_ear_cuts()
    for x, y in plate_screws():
        cuts += [cyl(x, y, CB_D / 2, -1, CB_DEPTH), screw_hole(x, y, -1, CUT_Z + 1)]
    return plate.cut(*cuts)


# Port panel and grille ---------------------------------------------------------------------------


def build_skirt(plug):
    """Roll part of the +X wall under the window. It prints on the plate (the roll curves away from
    the bed if it prints with the panel). The notch in its top edge is the edge-open cable exit."""
    notch = box(60, 80, *PORT_NOTCH, CUT_Z - 1, SKIRT_TOP + 1)
    return keep_z(plug, CUT_Z - 1, SKIRT_TOP).cut(notch)


def build_panel(plug):
    "Flat window plug above the skirt, 0.5 mm smaller than the window, with one screw boss."
    panel = world_to_side(keep_z(plug, SKIRT_TOP, HEIGHT))
    y, zc = PANEL_SCREW
    d, h = PANEL_BOSS
    boss = cq.Solid.makeCylinder(d / 2, h + 0.5, cq.Vector(-WALL - h, y, zc), cq.Vector(1, 0, 0))
    hole = cq.Solid.makeCylinder(M3_CLEAR / 2, 20, cq.Vector(5, y, zc), cq.Vector(-1, 0, 0))
    bore = cq.Solid.makeCylinder(
        PANEL_CB_D / 2, 1 + PANEL_CB_DEPTH, cq.Vector(1, y, zc), cq.Vector(-1, 0, 0)
    )
    return panel.fuse(boss).cut(hole, bore)


def grille_holes():
    "Hole centres on a 5.2 mm grid inside the plug outline, 2.6 mm from its edge."
    w, h = GRILLE_PLUG
    half, r = (w - h) / 2, h / 2 - 2.6 - 1.4
    pitch = 5.2
    pts = []
    for x in np.arange(-9, 10) * pitch:
        for z in np.arange(-4, 5) * pitch:
            if np.hypot(max(abs(x) - half, 0.0), z) <= r:
                pts.append((float(x), float(z)))
    return pts


def build_grille():
    """Black insert from inside: a plug fills the window with its face 0.5 mm below the outside,
    and a rear flange covers the window edge from behind. Prints back down (no overhang)."""
    plug = stadium(*GRILLE_PLUG, 0, BACK_D - FACE_D)
    flange = stadium(*GRILLE_FLANGE, SEAT_D - FACE_D, BACK_D - FACE_D)
    thick = BACK_D - FACE_D
    holes = cq.Workplane("XY").pushPoints(grille_holes()).circle(1.4).extrude(thick).val()
    insert = plug.fuse(flange).cut(holes)
    flat = insert.rotate((0, 0, 0), (1, 0, 0), 180).translate((0, 0, thick))
    return flat, in_front_frame(insert, FACE_D)


def build_all():
    "Every part in the assembly frame, plus the print orientation of each."
    outer = outer_shell()
    pre, shell = build_shell()
    plug = pre.intersect(window_cutter(PANEL_GAP))
    skirt = build_skirt(plug)
    plate = build_plate(outer, skirt)
    panel_side = build_panel(plug)
    grille_print, grille = build_grille()
    return {
        "outer": outer,
        "pre": pre,
        "skirt": skirt,
        "assembly": {
            "body-shell": shell,
            "base-plate": plate,
            "port-panel": side_to_world(panel_side),
            "speaker-grille": grille,
        },
        "print": {
            "Required/White/body-shell": flip(shell),
            "Required/White/base-plate": plate,
            "Required/White/port-panel": panel_side.rotate((0, 0, 0), (0, 1, 0), 90),
            "Required/Black/speaker-grille": grille_print,
        },
    }


# Checks ----------------------------------------------------------------------------------------
# Each check asserts and returns the numbers that go into body-checks.json.

KEEP_RESERVATIONS = {  # geometry.py items that stay where they are; the others are placed above
    *JETSON_PARTS, "Bus interface", "Bus power plug space",
    "Bus USB plug space -", "Bus USB plug space +", "Jetson USB/power plugs", "Fan intake space",
    "Camera cable slack loop", "Outlet space", "Camera rear cable space",
}  # fmt: skip
TOL_MM3 = 1e-3


def vol(a, b):
    "Common volume of two solids, zero when their bounding boxes miss each other."
    ba, bb = a.BoundingBox(), b.BoundingBox()
    apart = (
        ba.xmax <= bb.xmin or bb.xmax <= ba.xmin or ba.ymax <= bb.ymin
        or bb.ymax <= ba.ymin or ba.zmax <= bb.zmin or bb.zmax <= ba.zmin
    )  # fmt: skip
    return 0.0 if apart else a.intersect(b).Volume()


def reservations():
    boxes = {i["name"]: box(*reservation(i)) for i in hardware() if i["name"] in KEEP_RESERVATIONS}
    moved = ("Speaker", "USB audio case")  # the two reservations that body.py moves
    return boxes | {f"{k} (placed)": box(*v) for k, v in components().items() if k in moved}


def check_meshes(meshes):
    out = {}
    for name, m in meshes.items():
        assert m.is_watertight and m.is_winding_consistent and m.volume > 0, name
        assert max(m.extents) <= P1S_MM, name
        out[name] = {"bbox_mm": [round(float(x), 1) for x in m.extents], "watertight": True}
    return out


def check_envelope(parts, outer):
    ob = outer.BoundingBox()
    worst = 0.0
    for name, solid in parts.items():
        b = solid.BoundingBox()
        over = max(
            ob.xmin - b.xmin, b.xmax - ob.xmax, ob.ymin - b.ymin, b.ymax - ob.ymax, b.zmax - ob.zmax
        )
        assert over < 0.02, (name, over)
        worst = max(worst, over)
    return {
        "max_outside_A1_bounds_mm": round(worst, 3),
        "A1_bounds_mm": [round(ob.xlen, 1), round(ob.ylen, 1)],
    }


def check_overlaps(parts):
    "No part touches a reservation, and no two parts touch each other."
    res, out = reservations(), {}
    for name, solid in parts.items():
        for rname, rbox in res.items():
            v = vol(solid, rbox)
            assert v < TOL_MM3, (name, rname, v)
    names = list(parts)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            v = vol(parts[a], parts[b])
            assert v < TOL_MM3, (a, b, v)
            out[f"{a} / {b}"] = round(v, 4)
    return {"reservations_checked": len(res), "part_pairs_mm3": out}


def check_sweeps(shell, skirt):
    """Everything on the plate moves straight up into the shell. The swept box of each riser and
    component, and the skirt shifted up in steps, must miss the shell (which has the window)."""
    worst = {}
    boxes = dict(risers()) | {f"component {k}": v for k, v in components().items()}
    for name, b in boxes.items():
        sweep = box(b[0], b[1], b[2], b[3], CUT_Z, b[5])
        v = vol(sweep, shell)
        assert v < TOL_MM3, (name, v)
        worst[name] = round(v, 4)
    for dz in range(-int(SKIRT_TOP - CUT_Z) - 1, 1, 2):  # the skirt rises its own height
        v = vol(skirt.translate((0, 0, dz)), shell)
        assert v < TOL_MM3, ("skirt", dz, v)
    return {
        "swept_boxes_vs_shell_mm3": worst,
        "skirt_rise_steps_mm": "0 to its height below seated, 2 mm",
    }


def check_cable(shell):
    """The roof hole clears the hub bosses, their nut channels and the servo pocket walls, with
    solid roof round it. The slack loop sits under it and touches the plug space, which leads to
    the Jetson USB ports. The bus pocket band matches the walls that bound it."""
    cutter = roof_hole()
    near = {
        "hub bosses": hub_bosses(),
        "hub nut channels and screw holes": hub_cuts(),
        "servo pocket walls": servo_walls(),
    }
    gaps = {k: min(cutter.distance(s) for s in v) for k, v in near.items()}
    assert min(gaps.values()) >= 1.0, gaps
    hx, hy = ifc.CABLE_XY
    w, h = neck.CABLE_HOLE
    assert not probe(shell, hx, hy, 158.4)  # open at the middle of the roof
    tx, ty = -sin(radians(ifc.CABLE_DEG)), cos(radians(ifc.CABLE_DEG))  # the hole's long side
    for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)):  # solid roof 1 mm outside the straight hole
        along, across = a * (w / 2 + 1.0), b * (h / 2 + 1.0)
        assert probe(shell, hx + tx * along + ty * across, hy + ty * along - tx * across, 158.4)
    res = {i["name"]: box(*reservation(i)) for i in hardware()}
    loop, plugs = res["Camera cable slack loop"], res["Jetson USB/power plugs"]
    lb = loop.BoundingBox()
    margin = min(hx - lb.xmin, lb.xmax - hx, hy - lb.ymin, lb.ymax - hy)
    assert margin >= neck.CABLE_D and ifc.ROOF_BOTTOM_Z - lb.zmax >= 10.0, margin
    shared = vol(loop.translate((0, 0, -0.5)), plugs) / 0.5  # mm2 of face the two spaces share
    assert shared >= 100.0, shared
    risers_ = risers()
    front, back = risers_["audio and bus wall"], risers_["jetson back wall"]
    assert abs(front[3] - BAND_Y[0]) < 1e-6 and abs(back[2] - BAND_Y[1]) < 1e-6, (front, back)
    bus = components()["Bus board"]
    rear = BAND_Y[1] - bus[3]
    assert bus[2] - BAND_Y[0] >= POCKET_GAP and rear >= POCKET_GAP, (bus, BAND_Y)
    return {
        "roof_hole_to_nearest_mm": {k: round(v, 2) for k, v in gaps.items()},
        "slack_loop_mm": [round(lb.xlen), round(lb.ylen), round(lb.zlen)],
        "hole_center_to_loop_edge_mm": round(margin, 1),
        "loop_to_plug_space_shared_face_mm2": round(shared),
        "bus_front_gap_mm": round(bus[2] - BAND_Y[0], 2),
        "bus_rear_gap_mm": round(rear, 2),
        "bus_front_gap_most_mm": round(BAND_Y[1] - BAND_Y[0] - BUS_T - POCKET_GAP, 2),
    }


def check_servo(shell):
    case = ifc.SERVO_CASE
    cx, cy = ifc.SERVO_CASE_CENTER_XY
    z1 = ifc.SERVO_CASE_TOP_Z
    servo = box(
        cx - case[0] / 2, cx + case[0] / 2, cy - case[1] / 2, cy + case[1] / 2, z1 - case[2], z1
    )
    gap = servo.distance(shell)
    assert gap >= ifc.POCKET_CLEARANCE - 0.01, gap
    horn = cyl(
        0, 0, HORN_R, ifc.SERVO_HORN_TOP_Z, 159.8
    )  # the 31 mm disc turns inside the roof hole
    horn_gap = horn.distance(shell)
    assert vol(horn, shell) < TOL_MM3 and horn_gap >= 0.5, horn_gap
    inner = body_envelopes()[1]
    y_in = case[1] / 2 + ifc.POCKET_CLEARANCE
    for w in servo_walls():
        lower = w.intersect(box(-100, 100, -100, 100, 0, ifc.ROOF_BOTTOM_Z))
        assert lower.cut(inner).Volume() < TOL_MM3
        assert w.distance(servo) >= ifc.POCKET_CLEARANCE - 0.01
    for s in (-1, 1):  # real thickness and gusset, probed in the finished shell
        assert probe(shell, -20, s * (y_in + SERVO_WALL - 0.05), 140.0)
        assert not probe(shell, -20, s * (y_in + SERVO_WALL + 0.05), 140.0)
        assert probe(shell, -20, s * (y_in + SERVO_WALL + 2.0), ifc.ROOF_BOTTOM_Z - 1.0)
    boss_gap = min(
        cyl(x, y, 6, HUB_BOSS_Z, ifc.ROOF_BOTTOM_Z).distance(servo) for x, y in ifc.HUB_SCREWS_XY
    )
    assert boss_gap >= ifc.POCKET_CLEARANCE, boss_gap
    return {
        "servo_to_shell_min_mm": round(gap, 2),
        "wall_to_servo_mm": ifc.POCKET_CLEARANCE,
        "servo_wall_mm": SERVO_WALL,
        "hub_boss_to_servo_mm": round(boss_gap, 2),
        "horn_disc_r15.5_to_shell_mm": round(horn_gap, 2),
    }


def probe(solid, x, y, z):
    return solid.isInside(cq.Vector(x, y, z), 1e-4)


def side_point(x, y, z):
    return (
        cq.Vertex.makeVertex(x, y, z)
        .rotate((0, 0, 0), (0, 1, 0), -LEAN_SIDE)
        .translate((*WALL_SIDE, 0))
        .toTuple()
    )


def nut_channels():
    "Every nut channel as (r_nut, z0, z1, place); place(x, y) maps channel coordinates to world."
    out = []
    for x, y in ifc.HUB_SCREWS_XY:
        c, s = np.array([x, y]) / np.hypot(x, y)
        place = lambda u, v, c=c, s=s: (c * u - s * v, s * u + c * v)  # noqa: E731
        out.append((np.hypot(x, y), *HUB_NUT_Z, place))
    for sx in (-1, 1):
        for sy in (-1, 1):
            c, s = np.array([sx, sy]) / np.hypot(sx, sy)

            def place(u, v, c=c, s=s, sx=sx, sy=sy):
                return c * u - s * v + sx * CORNER[0], s * u + c * v + sy * CORNER[1]

            out.append((SCREW_RHO, *CORNER_NUT_Z, place))
    return out


def check_detents(shell):
    """Each channel has a ridge on both walls in the finished shell. A seated nut clears them, and
    a nut that moves back 1 mm hits them, so it cannot slide out before the screw goes in."""
    half, channels = NUT_AF / 2, nut_channels()
    for r_nut, z0, z1, place in channels:
        r, zm = r_nut - RIDGE_BACK, (z0 + z1) / 2
        for side in (-1, 1):
            assert probe(shell, *place(r, side * (half - RIDGE_H / 2)), zm)
            assert not probe(shell, *place(r, side * (half - RIDGE_H - 0.15)), zm)
        ridges = detent_ridges(r_nut, z0, z1)
        nut = hex_pocket(r_nut, 0, z0 + 0.05, z0 + 0.05 + NUT_T, 0, NUT_AF_MAX)
        assert all(vol(nut, ridge) < TOL_MM3 for ridge in ridges), "seated nut touches a ridge"
        back = [sum(vol(nut.translate((-d, 0, 0)), r) for r in ridges) for d in (0.6, 1.0)]
        assert min(back) > 0.05, back
    return {"nut_channels": len(channels), "ridge_mm": RIDGE_H, "nut_play_before_ridge_mm": 0.5}


def check_alignment(shell, plate, panel):
    "Screw holes line up with nut pockets, nuts have floors, and screws engage at least 2.5 mm."
    floor_top, ceiling = CUT_Z + NUT_FLOOR, CUT_Z + NUT_FLOOR + NUT_T + 0.4
    seat = CB_DEPTH  # the head seats on the counterbore floor
    for x, y in plate_screws():
        assert not probe(plate, x, y, 1.0) and not probe(plate, x + CB_D / 2 - 0.2, y, 1.0)
        assert probe(plate, x + CB_D / 2 + 0.3, y, 1.0)  # counterbore wall
        assert not probe(plate, x + 1.5, y, CB_DEPTH + 0.5) and probe(
            plate, x + 2.0, y, CB_DEPTH + 0.5
        )
        assert not probe(shell, x, y, CUT_Z + 1.0) and probe(
            shell, x + 2.4, y, CUT_Z + 1.0
        )  # floor
        assert not probe(shell, x, y, floor_top + 1.2)  # nut pocket
        assert not probe(shell, x, y, TIP_CLEAR_Z - 0.2) and probe(shell, x, y, TIP_CLEAR_Z + 1.0)
        assert probe(shell, x + 2.4, y, ceiling + 0.5)  # solid ceiling beside the screw hole
    tip = seat + PLATE_SCREW_LEN
    engage = tip - floor_top  # thread past the nut's first face (its lower face)
    assert engage >= 2.5 and tip <= TIP_CLEAR_Z, (tip, floor_top)
    hub_top = HUB_BOSS_Z + NUT_FLOOR + NUT_T
    hub_engage = hub_top - HUB_SCREW_TIP_Z
    assert hub_engage >= 2.5, hub_engage
    for x, y in ifc.HUB_SCREWS_XY:
        tx = -y / np.hypot(x, y) * 2.6, x / np.hypot(x, y) * 2.6  # sideways, inside the floor ring
        assert not probe(shell, x, y, HUB_BOSS_Z + 1.0) and probe(
            shell, x + tx[0], y + tx[1], HUB_BOSS_Z + 1.0
        )
        assert not probe(shell, x, y, hub_top - 1.0)  # nut space
        assert not probe(shell, x, y, ifc.ROOF_BOTTOM_Z + 0.5)  # screw hole through the roof
    y, zc = PANEL_SCREW
    x0, x10 = side_point(0, y, zc)[0], side_point(-10, y, zc)[0]
    first = (x0 - PANEL_NUT_X[1]) / ((x0 - x10) / 10)  # depth of the nut's first face on the axis
    panel_engage = PANEL_CB_DEPTH + PANEL_SCREW_LEN - first
    assert panel_engage >= 2.5, panel_engage
    ear = side_point(-10.5, y, zc)  # in the ear wall between the panel boss and the nut slot
    assert not probe(plate, *ear) and probe(plate, ear[0], ear[1] + 2.6, ear[2])
    face = side_point(-1.0, y, zc)
    assert not probe(panel, *face) and probe(panel, face[0], face[1] + 3.8, face[2])
    return {
        "plate_screws": f"{len(plate_screws())} x M3 x {PLATE_SCREW_LEN:.0f}",
        "plate_screw_engagement_mm": round(engage, 1),
        "plate_screw_tip_past_nut_mm": round(tip - (floor_top + NUT_T), 1),
        "hub_screw_engagement_mm": round(hub_engage, 1),
        "panel_screw": f"1 x M3 x {PANEL_SCREW_LEN:.0f}",
        "panel_screw_engagement_mm": round(panel_engage, 1),
        "panel_screw_y_z": [round(v, 1) for v in PANEL_SCREW],
    }


def jetson_envelope():
    "Bounds of the three Jetson boxes (x0, x1, y0, y1, z0, z1)."
    boxes = [components()[n] for n in JETSON_PARTS]
    return tuple(f(b[i] for b in boxes) for i, f in enumerate((min, max) * 3))


def slot_area(solids):
    "Total open area of vent slots, from the cutter volumes (each is 30 mm deep)."
    return sum(v.Volume() for v in solids) / 30.0


def check_openings(shell):
    "Vent slots sit over their reservations and are open; the mic holes are open and clear."
    jet = jetson_envelope()
    rear, left = vent_cutters()
    r = [v.BoundingBox() for v in rear]
    assert min(b.xmin for b in r) >= jet[0] and max(b.xmax for b in r) <= jet[1]
    assert min(b.zmin for b in r) >= jet[4] and max(b.zmax for b in r) <= jet[5]
    out = [v.BoundingBox() for v in left]
    assert min(b.ymin for b in out) >= jet[2] and max(b.ymax for b in out) <= jet[3]
    assert min(b.zmin for b in out) >= jet[4] and max(b.zmax for b in out) <= jet[5]
    for z in VENT_ROWS:
        y_mid = 65.0 - 0.0625 * z - 1.6
        for x in INTAKE_X:
            assert not probe(shell, x, y_mid, z) and probe(shell, x + 3.0, y_mid, z)
        x_mid = -(76.0 - 0.075 * z - 1.6)
        for y in OUTLET_Y:
            assert not probe(shell, x_mid, y, z) and probe(shell, x_mid, y + 3.0, z)
    window = in_front_frame(stadium(*GRILLE_WINDOW, 0, 4.0), -1.0)
    mic_gap = min(mic_hole(x, MIC_Z).distance(window) for x in MIC_X)
    assert mic_gap >= 5.0, mic_gap
    for (
        x
    ) in MIC_X:  # the whole hole: ring of points inside the circle and the tip, through the wall
        spots = [(0, 0), (1.2, 0), (-1.2, 0), (0, 1.2), (0, -1.2), (0, -2.2)]
        for dx, dz in spots:
            for y in (-59.9, -60.8, -61.7, -62.5):  # roll wall at Z 15 spans Y -63.0 to -59.8
                assert not probe(shell, x + dx, y, MIC_Z + dz), (x, dx, dz, y)
        assert probe(shell, x, -61.0, MIC_Z + 3.4) and probe(shell, x + 3.0, -61.0, MIC_Z)
    y_win = -65.0 + 0.0625 * 47.5 + 1.6
    half = GRILLE_WINDOW[0] / 2
    assert not probe(shell, 0, y_win, 47.5) and not probe(shell, half - 4, y_win, 47.5)
    assert probe(shell, half + 1.5, y_win, 47.5) and probe(shell, 0, y_win, 47.5 + 24.0)
    return {
        "intake_open_mm2": round(slot_area(rear)),
        "outlet_open_mm2": round(slot_area(left)),
        "mic_holes": len(MIC_X),
        "grille_window_mm": list(GRILLE_WINDOW),
        "grille_holes": len(grille_holes()),
        "mic_hole_to_window_mm": round(mic_gap, 1),
    }


WALL_GAPS = {  # wall: {part: smallest gap}. The bus band holds 17 mm for the 13 mm board.
    "jetson slot back wall": {"Jetson tray and board": SLOT_GAP},
    "jetson slot wall -": {"Jetson tray and board": SLOT_GAP},
    "jetson slot wall +": {"Jetson tray and board": SLOT_GAP},
    "jetson back wall": {"Jetson tray and board": POCKET_GAP, "Bus board": POCKET_GAP},
    "jetson rim": {"Jetson tray and board": POCKET_GAP},
    "audio side wall -": {"USB audio case": POCKET_GAP},
    "audio side wall +": {"USB audio case": POCKET_GAP},
    "audio and bus wall": {"USB audio case": POCKET_GAP, "Bus board": POCKET_GAP},
    "bus end rib -": {"Bus board": POCKET_GAP},
    "bus end rib +": {"Bus board": POCKET_GAP},
}


def check_pockets(grille):
    "Pocket walls keep their gaps to their parts, and no riser cuts into a component."
    comp = {k: box(*v) for k, v in components().items()}
    gaps = {}
    for name, b in risers().items():
        rb = box(*b)
        assert all(vol(rb, c) < TOL_MM3 for c in comp.values()), name
        for part, least in WALL_GAPS.get(name, {}).items():
            gap = rb.distance(comp[part])
            assert gap >= least - 0.01, (name, part, gap)
            gaps[f"{name} / {part}"] = round(gap, 2)
    speaker_gap = grille.distance(comp["Speaker"])
    assert speaker_gap >= POCKET_GAP
    return {"wall_to_part_mm": gaps, "grille_to_speaker_mm": round(speaker_gap, 2)}


def check_jetson_slot(plate, shell):
    """The Jetson slides straight down into its slot and up out of it without touching the plate.
    With the shell on, it cannot rise far enough to leave the slot when the robot tips."""
    comp = components()
    t = comp["Jetson tray and board"]
    boxes = [comp[n] for n in JETSON_PARTS]
    walls = [box(*b) for b in risers().values()]
    for dz in range(0, 61, 2):  # 60 mm covers the slot height
        for b in boxes:
            moved = box(b[0], b[1], b[2], b[3], b[4] + dz, b[5] + dz)
            assert all(vol(moved, w) < TOL_MM3 for w in walls), dz
    x, z = t[0] + SLOT_GRIP / 2, CUT_Z + 20.0  # probes in the finished plate, inside the slot
    for y, step in ((t[2] - SLOT_GAP, -1), (t[3] + SLOT_GAP, 1)):
        assert not probe(plate, x, y - 0.05 * step, z) and probe(plate, x, y + 0.05 * step, z)
        assert probe(plate, x, y + step * (SLOT_WALL - 0.05), z)
        assert not probe(plate, x, y + step * (SLOT_WALL + 0.05), z)
    engage = SLOT_TOP - t[4]  # strip length in the slot at rest

    def blocked(lift):
        prisms = (box(b[0], b[1], b[2], b[3], b[5], b[5] + lift) for b in boxes)
        return any(vol(prism, shell) > TOL_MM3 for prism in prisms)

    lo, hi = 0.0, engage
    assert blocked(hi), "the Jetson could lift out of its slot"
    for _ in range(7):
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if blocked(mid) else (mid, hi)
    return {
        "slot_width_mm": round(t[3] - t[2] + 2 * SLOT_GAP, 2),
        "slot_grip_mm": SLOT_GRIP,
        "slot_height_above_plate_mm": round(SLOT_TOP - CUT_Z, 1),
        "slot_engagement_at_rest_mm": round(engage, 1),
        "max_lift_with_shell_mm": round(hi, 1),
        "engagement_left_at_max_lift_mm": round(engage - hi, 1),
    }


def check_band(plate, outer):
    "Base plate band stays inside the A1 plan bounds and sticks out of the rolled base under 6 mm."
    ob, b = outer.BoundingBox(), plate.BoundingBox()
    assert b.xmax <= ob.xmax + 0.02 and b.ymax <= ob.ymax + 0.02 and b.ymin >= ob.ymin - 0.02
    sect = keep_z(outer, CUT_Z, CUT_Z + 0.01).BoundingBox()
    band = plate.intersect(box(-300, 62, -300, 300, -1, CUT_Z))  # away from the skirt
    reach = max(v.distance(outer) for v in band.Vertices() if v.Z < 0.01)
    assert reach < 6.0, reach
    return {
        "band_half_x_y_mm": [round(sect.xmax, 1), round(sect.ymax, 1)],
        "a1_half_x_y_mm": [round(ob.xmax, 1), round(ob.ymax, 1)],
        "band_corner_beyond_rolled_a1_surface_mm": round(reach, 1),
    }


def check_panel_removal(parts):
    """Take the panel straight out along the wall normal, the way the one screw leaves it free:
    it must clear the shell, plate and grille at every 2 mm step."""
    shell, plate, grille = (parts[n] for n in ("body-shell", "base-plate", "speaker-grille"))
    panel = parts["port-panel"]
    ux, uz = cos(radians(LEAN_SIDE)), sin(radians(LEAN_SIDE))  # wall normal, outward and up
    worst = 0.0
    for d in range(0, 41, 2):
        moved = panel.translate((d * ux, 0, d * uz))
        for other in (shell, plate, grille):
            v = vol(moved, other)
            assert v < TOL_MM3, ("panel", d, v)
            worst = max(worst, v)
    return {"panel_pull_out_steps_mm": "0 to 40, 2 mm", "max_overlap_mm3": worst}


def run_printcheck(meshes):
    with ProcessPoolExecutor() as pool:
        futures = {n: pool.submit(printcheck.analyze, m) for n, m in meshes.items()}
        rows = {n: f.result() for n, f in futures.items()}
    for n, r in rows.items():
        assert r["floating_islands"] == 0 and r["thin_mm2"] == 0, (n, r)
    return rows


# Outputs ---------------------------------------------------------------------------------------

WHITE, GREY, BLACK = (0.93, 0.93, 0.92), (0.72, 0.74, 0.76), (0.1, 0.1, 0.11)


def write_meshes(meshes):
    for name, m in meshes.items():
        path = OUT / "print" / f"{name}.stl"
        path.parent.mkdir(parents=True, exist_ok=True)
        m.export(path)


def write_step(parts):
    colors = {"base-plate": GREY, "speaker-grille": BLACK}
    asm = cq.Assembly(name="body")
    for name, solid in parts.items():
        asm.add(solid, name=name, color=cq.Color(*colors.get(name, WHITE)))
    asm.save(str(OUT / "body-assembly.step"))
    hw = cq.Assembly(name="hardware")
    for name, solid in reservations().items():
        hw.add(solid, name=name, color=cq.Color(0.4, 0.55, 0.8, 0.5))
    hw.save(str(OUT / "body-hardware.step"))


def polydata(mesh, color):
    import vtk
    from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray

    points = vtk.vtkPoints()
    points.SetData(numpy_to_vtk(np.asarray(mesh.vertices, float)))
    n = len(mesh.faces)
    cells = vtk.vtkCellArray()
    cells.SetCells(
        n,
        numpy_to_vtkIdTypeArray(
            np.hstack([np.full((n, 1), 3), mesh.faces]).ravel().astype(np.int64)
        ),
    )
    poly = vtk.vtkPolyData()
    poly.SetPoints(points)
    poly.SetPolys(cells)
    normals = vtk.vtkPolyDataNormals()
    normals.SetInputData(poly)
    normals.SetFeatureAngle(35)
    normals.Update()
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(normals.GetOutput())
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    actor.GetProperty().SetColor(*color)
    return actor


def snapshot(actors, eye, focus, path, size=(900, 800)):
    import vtk

    ren = vtk.vtkRenderer()
    ren.SetBackground(1, 1, 1)
    for a in actors:
        ren.AddActor(a)
    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.AddRenderer(ren)
    win.SetSize(*size)
    cam = ren.GetActiveCamera()
    cam.SetPosition(*eye)
    cam.SetFocalPoint(*focus)
    cam.SetViewUp(0, 0, 1)
    ren.ResetCameraClippingRange()
    win.Render()
    grab = vtk.vtkWindowToImageFilter()
    grab.SetInput(win)
    grab.Update()
    writer = vtk.vtkPNGWriter()
    writer.SetFileName(str(path))
    writer.SetInputConnection(grab.GetOutputPort())
    writer.Write()


def render(parts, print_meshes):
    from PIL import Image

    colors = {"base-plate": GREY, "speaker-grille": BLACK}
    actors = [polydata(to_print_mesh_world(s), colors.get(n, WHITE)) for n, s in parts.items()]
    tmp = [OUT / "_front.png", OUT / "_rear.png"]
    snapshot(actors, (-230, -420, 330), (0, 0, 70), tmp[0])
    snapshot(actors, (260, 420, 330), (0, 0, 70), tmp[1])
    images = [Image.open(t) for t in tmp]
    sheet = Image.new("RGB", (sum(i.width for i in images), images[0].height), "white")
    sheet.paste(images[0], (0, 0))
    sheet.paste(images[1], (images[0].width, 0))
    sheet.save(OUT / "body-assembled.png")
    x, laid = 0.0, []
    for name, m in print_meshes.items():
        m = m.copy()
        m.apply_translation([x + m.extents[0] / 2, 0, 0])
        x += m.extents[0] + 15
        laid.append(polydata(m, BLACK if "Black" in name else WHITE))
    snapshot(laid, (x / 2, -520, 380), (x / 2, 0, 45), tmp[0], size=(1800, 700))
    Image.open(tmp[0]).save(OUT / "body-print-parts.png")
    for t in tmp:
        t.unlink()


def to_print_mesh_world(solid):
    "Tessellate in place (no re-centring) for the assembled picture."
    vertices, faces = solid.tessellate(0.1, 0.3)
    mesh = trimesh.Trimesh([v.toTuple() for v in vertices], faces)
    mesh.merge_vertices()
    return mesh


def main():
    start = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    built = build_all()
    parts = built["assembly"]
    shell = parts["body-shell"]
    report = {  # geometry checks first: tessellating a solid widens its bounding box
        "envelope": check_envelope(parts, built["outer"]),
        "overlaps": check_overlaps(parts),
        "sweeps": check_sweeps(shell, built["skirt"]),
        "servo_pocket": check_servo(shell),
        "camera_cable": check_cable(shell),
        "alignment": check_alignment(shell, parts["base-plate"], parts["port-panel"]),
        "nut_detents": check_detents(shell),
        "openings": check_openings(shell),
        "pockets": check_pockets(parts["speaker-grille"]),
        "panel_removal": check_panel_removal(parts),
        "jetson_slot": check_jetson_slot(parts["base-plate"], shell),
        "plate_band": check_band(parts["base-plate"], built["outer"]),
    }
    meshes = {n: to_print_mesh(s) for n, s in built["print"].items()}
    report["meshes"] = check_meshes(meshes)
    write_meshes(meshes)
    rows = run_printcheck(meshes)
    report["printcheck"] = rows
    report["printcheck_total_overhang_mm2"] = round(
        sum(r["overhang_mm2"] for r in rows.values()), 1
    )
    write_step(parts)
    render(parts, meshes)
    report["runtime_s"] = round(time.time() - start, 1)
    (OUT / "body-checks.json").write_text(json.dumps(report, indent=1) + "\n")
    print(f"all body checks passed in {report['runtime_s']} s")


if __name__ == "__main__":
    main()
