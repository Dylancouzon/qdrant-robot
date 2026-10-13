"""Neck hub, head shaft, and horn disc of the simplified enclosure, in the assembly frame (mm).
Run head.py with build/hardware-layout/venv/bin/python; it calls these builders and checks.
"""

from itertools import pairwise
from math import acos, atan2, cos, degrees, dist, hypot, radians, sin, sqrt, tan

import cadquery as cq
import trimesh
from interface import (
    CABLE_D,
    CABLE_DEG,
    CABLE_FLARE,
    CABLE_HOLE,
    CABLE_R,
    CABLE_XY,
    HEAD_FLOOR_Z,
    HEAD_SCREWS_XY,
    HUB_OD,
    HUB_SCREWS_XY,
    HUB_TOP_Z,
    ROOF_BOTTOM_Z,
    ROOF_TOP_Z,
    SERVO_CASE,
    SERVO_CASE_CENTER_XY,
    SERVO_CASE_TOP_Z,
    SERVO_HORN_TOP_Z,
)

STOCK_MM = (4, 6, 8, 10, 12, 16)
MIN_ENGAGE = 2.5  # mm of screw past the first face of the nut (or into the horn)
MIN_SECTION = 2.4  # wall rule for every floor, plate, and disc section
# 6802-size bearing: bore, outside diameter, width. Race sizes are U until measured.
BORE_D, BEARING_D, BEARING_W = 15.0, 24.0, 5.0
INNER_RACE_OD, OUTER_RACE_ID = 17.5, 21.5
SEAT_D = 24.1  # the coupon decides the final value
SHOULDER_T = 2.4
JOURNAL_D = 14.9
PLAY = (
    0.5  # axial play: the shaft hangs on the upper inner race; the disc ring is 0.5 below the lower
)
RING_D, RING_H = 17.0, 1.7

LOWER_Z = ROOF_TOP_Z  # lower bearing bottom face
FLANGE_BOTTOM_Z = HUB_TOP_Z + RING_H
FLANGE_D = HUB_OD
FLANGE_NUT_TOP_Z = (
    HEAD_FLOOR_Z - 2.4
)  # skin above the nut channel: the screw pulls the nut up to it
DISC_D, DISC_BOTTOM_Z = 31.0, SERVO_HORN_TOP_Z  # 0.7 mm per side in the roof opening
DISC_RING_R, DISC_RING_H = (7.6, 8.6), 0.8  # inside the 17.5 mm inner race OD, outside the bore
DISC_RING_TOP_Z = ROOF_TOP_Z - PLAY
DISC_TOP_Z = DISC_RING_TOP_Z - DISC_RING_H
NUT_AF, NUT_T = 5.7, 2.5  # M3 nut pocket across flats, depth
RIDGE_AT = 2.2  # nut channel ridge crest, past the seated nut's center
LIP_H, LIP_IN = 0.4, 0.3  # the pocket mouth: two lips on opposite flats keep the nut in (U)
DISC_NUT_DEPTH = 3.0  # deeper in the disc, so the center screw tip stops above the horn
NUT_CEILING_Z = DISC_BOTTOM_Z + DISC_NUT_DEPTH
# Square drive: a boss on the disc rises into a socket in the shaft bottom. Its flats face the
# axes, so the corners fall in the horn screw head recesses and leave no thin wall.
BOSS_AF, SOCKET_AF, SOCKET_R, DRIVE_ENGAGE = 7.5, 7.8, 4.6, 3.1
BOSS_TOP_Z = DISC_TOP_Z + DRIVE_ENGAGE
HORN_HOLES = [(sx * 4.95, sy * 4.95) for sx in (-1, 1) for sy in (-1, 1)]
HORN_HEAD_D, HORN_HEAD_H, HORN_CB_R = 5.5, 3.0, 3.2  # head type is U
HORN_CB_FLOOR_Z = LOWER_Z - 0.5 - HORN_HEAD_H  # head tops stay 0.5 mm under the lower bearing
HORN_CB_DEPTH = DISC_TOP_Z - HORN_CB_FLOOR_Z
HORN_RELIEF = HORN_HEAD_H - HORN_CB_DEPTH + 0.2  # pocket in the shaft bottom for the head tops
CENTER_SCREW_L, CENTER_TIP_GAP = 16, 0.5  # tip height above the horn top
CENTER_SCREW_SEAT_Z = SERVO_HORN_TOP_Z + CENTER_TIP_GAP + CENTER_SCREW_L
HUB_CB_DEPTH, HUB_CB_R = 3.0, 2.95
SLOT_R0, SLOT_R1, SLOT_DEPTH = 19.4, 22.6, 3.5
POST_R0, POST_R1, POST_HALF_DEG = 19.8, 22.2, 12.0  # post 2.4 wide, 0.4 mm clear in the slot
POST_TOP_Z = FLANGE_BOTTOM_Z + SLOT_DEPTH - 0.5  # never reaches the slot ceiling
STOP_DEG = 80.0
STOP_CENTER_DEG = 120.0  # clear of the hub screws at 0, 90, and 270 degrees
HUB_R = max(HUB_OD / 2, *(hypot(*xy) + HUB_CB_R + MIN_SECTION for xy in HUB_SCREWS_XY))  # bulges
CABLE_CLEAR = 0.5  # the cable stays this far from the hub and flange
WRAP_R = HUB_R + CABLE_D / 2 + CABLE_CLEAR  # radius of the cable's centerline round the hub


def cyl(r, z0, z1, xy=(0.0, 0.0)):
    return cq.Solid.makeCylinder(r, z1 - z0, cq.Vector(xy[0], xy[1], z0), cq.Vector(0, 0, 1))


def box(sx, sy, z0, z1, xy=(0.0, 0.0)):
    return (
        cq.Workplane("XY")
        .box(sx, sy, z1 - z0, centered=(True, True, False))
        .translate((xy[0], xy[1], z0))
        .val()
    )


def hexprism(af, z0, z1, xy=(0.0, 0.0), rot=0.0):
    """Hexagon with `af` across flats; a corner points along +X when rot is 0."""
    r = af / sqrt(3)
    pts = [
        (xy[0] + r * cos(radians(rot + 60 * k)), xy[1] + r * sin(radians(rot + 60 * k)))
        for k in range(6)
    ]
    return cq.Workplane("XY").workplane(offset=z0).polyline(pts).close().extrude(z1 - z0).val()


def nut_slot(xy, z0, z1, angle, length):
    """M3 nut trap opening toward `angle` (degrees): a hex end at xy plus a channel to `length`.
    A 0.3 mm ridge on each channel wall, 2.2 mm past the seated nut's center where the nut is
    still narrow, makes the nut snap in and stay, as the shell's nut channels do."""
    half, a = NUT_AF / 2, RIDGE_AT
    ridges = [
        cq.Workplane("XY")
        .workplane(offset=z0)
        .polyline([(a - 0.5, s * half), (a + 0.5, s * half), (a, s * (half - 0.3))])
        .close()
        .extrude(z1 - z0)
        .val()
        for s in (-1, 1)
    ]
    base = hexprism(NUT_AF, z0, z1).fuse(box(length, NUT_AF, z0, z1, (length / 2, 0)))
    turned_ = base.cut(*ridges).rotate((0, 0, 0), (0, 0, 1), angle)
    return turned_.translate(cq.Vector(xy[0], xy[1], 0))


def nut_ghost(xy, z0, angle):
    "A real M3 nut (5.5 across flats, 2.4 thick) seated from z0, corners along `angle`."
    return hexprism(5.5, z0, z0 + 2.4, xy, rot=angle)


def sector(r0, r1, a0, a1, z0, z1):
    """Annular sector from angle a0 to a1 (degrees, counter-clockwise from +X)."""
    full = cq.Solid.makeCylinder(r1, z1 - z0, cq.Vector(0, 0, z0), cq.Vector(0, 0, 1), a1 - a0)
    hole = cq.Solid.makeCylinder(r0, z1 - z0, cq.Vector(0, 0, z0), cq.Vector(0, 0, 1), a1 - a0)
    return full.cut(hole).rotate((0, 0, 0), (0, 0, 1), a0)


def hub():
    solid = cyl(HUB_OD / 2, LOWER_Z, HUB_TOP_Z)
    for xy in HUB_SCREWS_XY:  # a 0.35 mm bulge keeps the wall outside each counterbore at 2.4 mm
        solid = solid.fuse(cyl(HUB_CB_R + MIN_SECTION, LOWER_Z, HUB_TOP_Z, xy))
    seat = LOWER_Z + BEARING_W
    solid = solid.cut(cyl(SEAT_D / 2, LOWER_Z - 1, seat))
    solid = solid.cut(cyl(OUTER_RACE_ID / 2, seat - 1, seat + SHOULDER_T + 1))
    solid = solid.cut(cyl(SEAT_D / 2, seat + SHOULDER_T, HUB_TOP_Z + 1))
    for xy in HUB_SCREWS_XY:
        solid = solid.cut(cyl(1.7, LOWER_Z - 1, HUB_TOP_Z + 1, xy))
        solid = solid.cut(cyl(HUB_CB_R, HUB_TOP_Z - HUB_CB_DEPTH, HUB_TOP_Z + 1, xy))
    a = STOP_CENTER_DEG
    return solid.fuse(
        sector(POST_R0, POST_R1, a - POST_HALF_DEG, a + POST_HALF_DEG, HUB_TOP_Z - 0.5, POST_TOP_Z)
    ).clean()


def shaft():
    solid = cyl(JOURNAL_D / 2, DISC_TOP_Z, HUB_TOP_Z)
    solid = solid.fuse(cyl(RING_D / 2, HUB_TOP_Z, FLANGE_BOTTOM_Z))
    solid = solid.fuse(cyl(FLANGE_D / 2, FLANGE_BOTTOM_Z, HEAD_FLOOR_Z))
    for xy in HEAD_SCREWS_XY:  # a 0.6 mm bulge keeps the skin 2.4 mm wide outside each screw hole
        solid = solid.fuse(cyl(1.7 + MIN_SECTION, FLANGE_BOTTOM_Z, HEAD_FLOOR_Z, xy))
    socket = box(SOCKET_AF, SOCKET_AF, DISC_TOP_Z - 1, DISC_TOP_Z + DRIVE_ENGAGE + 0.1)
    solid = solid.cut(socket.intersect(cyl(SOCKET_R, DISC_TOP_Z - 2, HEAD_FLOOR_Z)))
    for xy in HORN_HOLES:  # relief for the horn screw heads under the shaft's bottom face
        solid = solid.cut(cyl(HORN_CB_R, DISC_TOP_Z - 1, DISC_TOP_Z + HORN_RELIEF, xy))
    a = STOP_CENTER_DEG
    half = STOP_DEG + POST_HALF_DEG
    slot = sector(
        SLOT_R0, SLOT_R1, a - half, a + half, FLANGE_BOTTOM_Z - 1, FLANGE_BOTTOM_Z + SLOT_DEPTH
    )
    solid = solid.cut(slot)
    for xy in HEAD_SCREWS_XY:  # nut channel from the rim; the screw pulls the nut up to the skin
        angle = degrees(atan2(xy[1], xy[0]))
        solid = solid.cut(nut_slot(xy, FLANGE_BOTTOM_Z - 1, FLANGE_NUT_TOP_Z, angle, 20))
        solid = solid.cut(cyl(1.7, FLANGE_NUT_TOP_Z - 1, HEAD_FLOOR_Z + 1, xy))
    solid = solid.cut(cyl(1.7, DISC_TOP_Z - 1, HEAD_FLOOR_Z + 1))
    return solid.cut(cyl(3.1, CENTER_SCREW_SEAT_Z, HEAD_FLOOR_Z + 1)).clean()


def disc():
    solid = cyl(DISC_D / 2, DISC_BOTTOM_Z, DISC_TOP_Z)
    ring = cyl(DISC_RING_R[1], DISC_TOP_Z - 0.1, DISC_RING_TOP_Z)
    solid = solid.fuse(ring.cut(cyl(DISC_RING_R[0], DISC_TOP_Z - 1, DISC_RING_TOP_Z + 1)))
    solid = solid.fuse(box(BOSS_AF, BOSS_AF, DISC_TOP_Z - 0.1, BOSS_TOP_Z))
    solid = solid.cut(cyl(1.7, DISC_BOTTOM_Z - 1, BOSS_TOP_Z + 1))
    solid = solid.cut(hexprism(NUT_AF, DISC_BOTTOM_Z - 1, NUT_CEILING_Z, rot=30))
    for side in (-1, 1):  # the nut snaps past these 0.3 mm lips, then sits above them
        x = side * (NUT_AF / 2 - LIP_IN / 2)
        lip = box(LIP_IN, NUT_AF / sqrt(3), DISC_BOTTOM_Z, DISC_BOTTOM_Z + LIP_H, (x, 0))
        solid = solid.fuse(lip)
    for xy in HORN_HOLES:  # head recesses also trim the boss corners
        solid = solid.cut(cyl(1.7, DISC_BOTTOM_Z - 1, DISC_TOP_Z + 1, xy))
        solid = solid.cut(cyl(HORN_CB_R, HORN_CB_FLOOR_Z, BOSS_TOP_Z + 1, xy))
    return solid.clean()


def cable_hole(z0, z1, surface_z, material_below):
    """Cutter for one camera cable hole: a rectangle from z0 to z1 with a 46 degree flare on the
    face at surface_z, so the cable meets a chamfer and not an edge."""
    w, h = CABLE_HOLE
    flare_dz = (-1 if material_below else 1) * CABLE_FLARE * tan(radians(46))
    flare = (
        cq.Workplane("XY")
        .workplane(offset=surface_z)
        .rect(w + 2 * CABLE_FLARE, h + 2 * CABLE_FLARE)
        .workplane(offset=flare_dz)
        .rect(w, h)
        .loft(combine=True)
        .val()
    )
    hole = box(w, h, z0, z1).fuse(flare)
    return hole.rotate((0, 0, 0), (0, 0, 1), CABLE_DEG + 90).translate((*CABLE_XY, 0))


def cable_path(yaw):
    """Taut camera cable centerline at `yaw` degrees, from the roof hole plane to the head floor
    hole plane: vertical for CABLE_D in each hole, then straight if that clears the hub and
    otherwise wrapped around it. Points are (x, y, z)."""
    polar = lambda deg, r: (r * cos(radians(deg)), r * sin(radians(deg)))  # noqa: E731
    start, end = CABLE_DEG, CABLE_DEG + yaw
    reach = degrees(acos(WRAP_R / CABLE_R))  # angle from a hole to the wrap circle's tangent point
    flat = [polar(start, CABLE_R), polar(end, CABLE_R)]
    if abs(yaw) > 2 * reach:
        a0, a1 = start + reach * (1 if yaw > 0 else -1), end - reach * (1 if yaw > 0 else -1)
        steps = int(abs(a1 - a0) / 2) + 1
        arc = [polar(a0 + (a1 - a0) * i / steps, WRAP_R) for i in range(steps + 1)]
        flat = [flat[0], *arc, flat[1]]
    along = [0.0]
    for p, q in pairwise(flat):
        along.append(along[-1] + hypot(q[0] - p[0], q[1] - p[1]))
    z0, z1 = ROOF_TOP_Z + CABLE_D, HEAD_FLOOR_Z - CABLE_D
    mid = [
        (x, y, z0 + (z1 - z0) * s / (along[-1] or 1.0))
        for (x, y), s in zip(flat, along, strict=True)
    ]
    return [(*flat[0], ROOF_TOP_Z), *mid, (*flat[-1], HEAD_FLOOR_Z)]


def path_length(points):
    return sum(dist(p, q) for p, q in pairwise(points))


def cable_solid(points):
    "The cable as a chain of cylinders along `points`."
    segments = []
    for p, q in pairwise(points):
        v = cq.Vector(*q) - cq.Vector(*p)
        if v.Length > 1e-9:
            segments.append(cq.Solid.makeCylinder(CABLE_D / 2, v.Length, cq.Vector(*p), v))
    return cq.Compound.makeCompound(segments)


def bearing(z0):
    "Both races of one bearing as ghosts; the balls and cage stay out."
    inner = cyl(INNER_RACE_OD / 2, z0, z0 + BEARING_W).cut(cyl(BORE_D / 2, z0 - 1, z0 + 9))
    outer = cyl(BEARING_D / 2, z0, z0 + BEARING_W).cut(cyl(OUTER_RACE_ID / 2, z0 - 1, z0 + 9))
    return inner, outer


def servo_ghosts():
    x, y = SERVO_CASE_CENTER_XY
    sx, sy, sz = SERVO_CASE
    return box(sx, sy, SERVO_CASE_TOP_Z - sz, SERVO_CASE_TOP_Z, (x, y)), cyl(
        10.0, SERVO_CASE_TOP_Z, SERVO_HORN_TOP_Z
    )


# One entry per screw group: name, XY positions, head seat Z, length, first face Z, direction.
# The first face is where the thread first meets the nut or the horn; it sets the engagement.
NECK_SCREWS = [
    ("center", [(0.0, 0.0)], CENTER_SCREW_SEAT_Z, CENTER_SCREW_L, NUT_CEILING_Z, False),
    ("hub", HUB_SCREWS_XY, HUB_TOP_Z - HUB_CB_DEPTH, 16, ROOF_BOTTOM_Z, False),  # nut: body roof
    ("horn", HORN_HOLES, HORN_CB_FLOOR_Z, 6, SERVO_HORN_TOP_Z, False),
]


def screw_ghosts(specs):
    "Each screw as two cylinders: shank and head."
    out = {}
    for name, xys, seat, length, _, up in specs:
        for i, xy in enumerate(xys):
            tip = seat + length if up else seat - length
            head0 = seat - HORN_HEAD_H if up else seat
            shank = cyl(1.5, min(seat, tip), max(seat, tip), xy)
            out[f"{name} screw {i}"] = shank.fuse(
                cyl(HORN_HEAD_D / 2, head0, head0 + HORN_HEAD_H, xy)
            )
    return out


def screw_report(specs):
    "Assert stock length and 2.5 mm of engagement past the first face for every screw."
    out = []
    for name, xys, seat, length, first, up in specs:
        tip = seat + length if up else seat - length
        engaged = tip - first if up else first - tip
        assert length in STOCK_MM and engaged >= MIN_ENGAGE - 1e-9, (name, engaged)
        out.append(
            f"{name} x{len(xys)}: M3 x {length}, head seat Z {seat:.1f}, tip Z {tip:.1f}, "
            f"{engaged:.1f} mm past the first nut or horn face (Z {first:.1f})"
        )
    return out


def to_print_mesh(solid, matrix):
    "Tessellate, turn into print orientation with `matrix`, then rest on Z 0 centered in XY."
    vertices, faces = solid.tessellate(0.02, 0.1)
    mesh = trimesh.Trimesh([v.toTuple() for v in vertices], faces)
    mesh.merge_vertices()
    mesh.apply_transform(matrix)
    lo, hi = mesh.bounds
    mesh.apply_translation([-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]])
    assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume > 0
    return mesh


def overlap(a, b):
    return a.intersect(b).Volume()


def turned(solid, deg):
    return solid.rotate((0, 0, 0), (0, 0, 1), deg)


def wall_outside(solid, angle, r_start, z, step=0.02):
    "Material thickness met going outward along `angle` from radius r_start at height z."
    ux, uy = cos(radians(angle)), sin(radians(angle))
    t = 0.0
    while t < 8 and solid.isInside(
        cq.Vector(ux * (r_start + t + 0.005), uy * (r_start + t + 0.005), z)
    ):
        t += step
    return t


def neck_checks(parts):
    """Contact, play, stop, yaw sweep, and section checks for the neck parts. Raises on failure."""
    hub_, shaft_, disc_ = parts["hub"], parts["head shaft"], parts["horn disc"]
    lo_in, lo_out = bearing(LOWER_Z)
    up_in, up_out = bearing(HUB_TOP_Z - BEARING_W)
    out = {}
    assert LOWER_Z + 2 * BEARING_W + SHOULDER_T == HUB_TOP_Z, (
        "bearing stack must match interface.py"
    )
    assert all(hub_.distance(r) < 1e-6 for r in (lo_out, up_out)), "shoulder must touch outer races"
    assert all(hub_.distance(r) > 1.5 for r in (lo_in, up_in)), "hub must not touch inner races"
    ring = shaft_.intersect(cyl(RING_D / 2, HUB_TOP_Z, HUB_TOP_Z + 0.1).cut(cyl(7.6, 0, 300)))
    assert ring.distance(up_in) < 1e-6 and shaft_.distance(up_out) > 1.5, "ring: inner race only"
    assert shaft_.distance(lo_out) > 1.5 and shaft_.distance(lo_in) > 0.04
    lifted = turned(disc_, 0).translate(cq.Vector(0, 0, PLAY + 0.1))  # head lifted past the play
    assert abs(disc_.distance(lo_in) - PLAY) < 1e-6 and disc_.distance(lo_out) >= 0.5
    assert overlap(lifted, lo_in) > 0.1 and overlap(lifted, lo_out) < 1e-6
    out["bearing contact"] = (
        "shoulder touches both outer races (inner races 2.0 mm away); shaft ring touches the "
        "upper inner race only (outer race 2.25 mm away); lifted 0.6 mm, the disc ring reaches "
        f"the lower inner race and the outer race stays {disc_.distance(lo_out):.1f} mm away"
    )
    out["axial play"] = (
        f"{disc_.distance(lo_in) + ring.distance(up_in):.2f} mm, ring on race, disc ring below"
    )
    for sign in (-1, 1):  # stops meet at exactly 80.0 degrees and not before
        at = turned(shaft_, sign * STOP_DEG)
        assert hub_.distance(at) < 1e-6 and overlap(hub_, at) < 1e-6
        assert overlap(hub_, turned(shaft_, sign * (STOP_DEG + 0.5))) > 1.0
    low = shaft_.translate(cq.Vector(0, 0, -(SLOT_DEPTH - (POST_TOP_Z - FLANGE_BOTTOM_Z)) + 0.05))
    assert overlap(hub_, low) < 1e-6 and overlap(hub_, low.translate(cq.Vector(0, 0, -0.1))) > 0.01
    for deg in range(-80, 81):
        moving = (turned(shaft_, deg), turned(disc_, deg))
        assert all(overlap(hub_, m) < 1e-6 for m in moving), deg
    out["stops"] = (
        "shaft, flange, and disc clear the hub and posts at 161 yaw angles; the post meets the "
        "slot end at +80.0 and -80.0 and stays 0.5 mm under the slot ceiling"
    )
    sections = {
        "bearing shoulder": SHOULDER_T,
        "flange over the slot": HEAD_FLOOR_Z - FLANGE_BOTTOM_Z - SLOT_DEPTH,
        "disc under the screw head recesses": HORN_CB_FLOOR_Z - DISC_BOTTOM_Z,
    }
    for xy in HUB_SCREWS_XY:
        angle = degrees(atan2(xy[1], xy[0]))
        wall = wall_outside(hub_, angle, hypot(*xy) + HUB_CB_R, HUB_TOP_Z - HUB_CB_DEPTH / 2)
        sections["hub wall outside the counterbores"] = min(
            wall, sections.get("hub wall outside the counterbores", 9)
        )
    for xy in HEAD_SCREWS_XY:
        angle = degrees(atan2(xy[1], xy[0]))
        wall = wall_outside(shaft_, angle, hypot(*xy) + 1.7, HEAD_FLOOR_Z - 1.2)
        sections["flange skin outside the head screw holes"] = min(
            wall, sections.get("flange skin outside the head screw holes", 9)
        )
    assert all(v >= MIN_SECTION - 0.03 for v in sections.values()), sections
    # The boss wall at the screw bore is the one section below 2.4: socket 7.8 and the horn head
    # recesses leave 2.05 to 2.1 mm, and printcheck accepts 2.0.
    boss = min(wall_outside(disc_, a, 1.7, DISC_TOP_Z + 1.5) for a in (0, 45, 90))
    assert boss >= 2.0 - 0.03, boss
    sections["disc boss wall at the screw bore (exception)"] = boss
    out["sections"] = {k: round(v, 2) for k, v in sections.items()}
    out["drive"] = f"square drive, {DRIVE_ENGAGE} mm engagement, disc ring {DISC_RING_H} mm tall"
    nut = nut_ghost((0, 0), NUT_CEILING_Z - 2.4, 30)
    assert overlap(disc_, nut) < 1e-3
    assert overlap(disc_, nut.translate(cq.Vector(0, 0, -0.5))) > 0.01
    out["disc nut"] = (
        f"two {LIP_IN} mm lips at the pocket mouth hold the seated nut; a nut pushed down 0.5 mm "
        "meets them"
    )
    out |= cable_checks(hub_, shaft_, disc_)
    return out


def cable_checks(hub_, shaft_, disc_):
    """The two cable holes clear the neck parts, and the taut cable clears them at every yaw."""
    column = cable_hole(ROOF_BOTTOM_Z - 1, HEAD_FLOOR_Z + 8, ROOF_TOP_Z, True).fuse(
        cable_hole(ROOF_BOTTOM_Z - 1, HEAD_FLOOR_Z + 8, HEAD_FLOOR_Z, False)
    )
    nearest = min(column.distance(p) for p in (hub_, shaft_, disc_))
    assert nearest >= 1.0 - 1e-6, nearest
    flat = 2 * degrees(acos(WRAP_R / CABLE_R))
    worst = 9.0
    for yaw in range(-80, 81, 10):
        cable = cable_solid(cable_path(yaw))
        moving = (turned(shaft_, yaw), turned(disc_, yaw))
        worst = min(worst, cable.distance(hub_), *(cable.distance(m) for m in moving))
    assert worst >= CABLE_CLEAR - 0.01, worst
    base = path_length(cable_path(0))
    turn = max(path_length(cable_path(d)) for d in (-80, 80))
    return {
        "cable holes": (
            f"{CABLE_HOLE[0]:.0f} x {CABLE_HOLE[1]:.0f} mm at radius {CABLE_R:.0f}, "
            f"{CABLE_DEG:.0f} deg from +X, 1 mm 46 deg flare; {nearest:.1f} mm from the hub, "
            "flange, disc, and posts"
        ),
        "cable path": (
            f"taut {CABLE_D} mm cable, straight to +-{flat:.0f} deg of yaw and wrapped round the "
            f"hub beyond, stays {worst:.2f} mm from every neck part over -80 to +80 deg in 10 deg "
            f"steps; length {base:.1f} mm at yaw 0 and {turn:.1f} mm at 80 deg, {turn - base:.1f} "
            "mm more"
        ),
    }
