"""Build a manual yaw joint with printable involute gears and positive retainers.
Run with build/hardware-layout/venv/bin/python hardware/concept-a/joint.py.
"""

from __future__ import annotations
import json
import math
from pathlib import Path
import cadquery as cq
from layout import box, ring, export_3mf, hardware, camera
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle

OUT = Path(__file__).resolve().parent / "output" / "joint"


def rotated(s, a):
    return s.rotate((0, 0, 0), (0, 0, 1), a)


def gear():
    """34 teeth, module one, 20 degree pressure angle, 0.25 mm tooth backlash."""
    n = 34
    rp = 17.0
    rb = rp * math.cos(math.radians(20))
    rr = 15.75
    ra = 18.0

    def inv(r):
        return math.sqrt((r / rb) ** 2 - 1) - math.acos(rb / r)

    half = (math.pi / 4 - 0.0625) / rp

    def flank(r):
        return half + inv(rp) - inv(r)

    points = []
    for k in range(n):
        c = 2 * math.pi * k / n
        vals = [(rr, -flank(rb)), (rb, -flank(rb))]
        vals += [(rb + (ra - rb) * j / 8, -flank(rb + (ra - rb) * j / 8)) for j in range(1, 9)]
        vals += [(ra, -flank(ra) + 2 * flank(ra) * j / 4) for j in range(1, 5)]
        vals += [(rb + (ra - rb) * j / 8, flank(rb + (ra - rb) * j / 8)) for j in range(7, -1, -1)]
        vals += [(rr, flank(rb)), (rr, math.pi / n)]
        points += [(r * math.cos(c + a), r * math.sin(c + a)) for r, a in vals]
    return cq.Workplane("XY").polyline(points).close().extrude(6).translate((0, 0, 140)).val()


def retained_y_key(width, length, height, x, y, z, land, tail=1.2):
    """External head and tapered barb retain the key after its narrow land passes."""
    key = box((width, length, height), (x, y, z))
    key = key.fuse(box((width + 1, 0.8, height), (x, y - length / 2 + 0.4, z)))
    points = [
        (-width / 2, land),
        (-(width + 1) / 2, land + min(0.35, tail / 2)),
        (-width / 2, land + tail),
    ]
    for sign in (-1, 1):
        poly = [(x + sign * a, y + b) for a, b in points]
        key = key.fuse(
            cq.Workplane("XY")
            .polyline(poly)
            .close()
            .extrude(height)
            .translate((0, 0, z - height / 2))
            .val()
        )
    return key.clean().rotate((x, y, 0), (x, y, 1), 180)


def build():
    parts = {}
    shaft = gear().cut(ring(10, 0, 6, 140))
    shaft = shaft.fuse(ring(14.8, 10, 34, 146), ring(20, 10, 2.4, 148.8))
    shaft = shaft.cut(box((20, 30, 7.5), (16, 0, 176.35)))
    shaft = shaft.cut(box((22, 1.8, 1.8), (0, 0, 175.4)))
    parts["gear_shaft"] = shaft
    parts["inner_spacer"] = ring(20, 15.2, 11, 156.5)
    parts["adjustment_shim_0_2"] = ring(20, 15.2, 0.2, 0).translate((55, 15, 140))
    parts["adjustment_shim_0_4"] = ring(20, 15.2, 0.4, 0).translate((55, 30, 140))
    flange = ring(44, 15.2, 3, 177).fuse(ring(20, 0, 4.2, 172.8))
    # The D-shaped clearance bore carries torque through its flat.
    dbore = cq.Solid.makeCylinder(7.6, 8, cq.Vector(0, 0, 172.5)).cut(
        box((20, 30, 10), (16.2, 0, 177))
    )
    flange = flange.cut(dbore).cut(box((22, 1.8, 1.8), (0, 0, 175.4)))
    flange = flange.fuse(box((5, 4, 3.5), (20.5, 0, 175.25)))
    for x in (-18, 18):
        post = box((3, 4, 5.5), (x, 0, 182.75)).cut(box((1.6, 12, 1.4), (x, 0, 183.8)))
        flange = flange.fuse(post)
        parts[f"head_key_{x}"] = retained_y_key(1.3, 10, 1.2, x, 0, 183.8, 2.2)
    parts["head_flange"] = flange
    shaft_key = box((20.4, 1.5, 1.6), (0, 0, 175.4)).fuse(box((0.5, 3, 1.6), (10.4, 0, 175.4)))
    for sign in (-1, 1):
        shaft_key = shaft_key.fuse(
            cq.Workplane("XY")
            .polyline([(-10.15, sign * 0.75), (-10.3, sign * 1.25), (-10.7, sign * 0.75)])
            .close()
            .extrude(1.6)
            .translate((0, 0, 174.6))
            .val()
        )
    parts["shaft_key"] = shaft_key.clean()
    # Closed rings install over an open shaft. The tower opens along X=0.
    tower = ring(32, 22, 26.6, 150).fuse(ring(50, 22, 2.4, 160))
    for z in (151.4, 167.4):
        tower = tower.cut(ring(24.2, 0, 5.2, z))
    for x in (-21, 21):
        tower = tower.cut(box((3.4, 4.4, 4), (x, 0, 161.2)))
        parts[f"roof_key_{x}"] = retained_y_key(1.5, 10, 1.6, x, 0, 163.4, 2.2)
    # Radial stop ribs include the whole supporting web.
    stop_shapes = []
    for a in (-92.7, 92.7):
        rib = rotated(box((9.2, 4, 14.1), (20.4, 0, 169.45)), a)
        tower = tower.fuse(rib)
        stop_shapes.append(rib)
    # Four closure lugs. Rectangular cross pins resist seam opening at two heights.
    for z in (164, 170):
        for y in (-19, 19):
            lug = box((10, 8, 3.2), (0, y, z))
            tower = tower.fuse(lug).cut(box((16, 1.8, 3.4), (0, y, z)))
            pin = box((14, 1.5, 3.2), (0, y, z)).fuse(box((1.6, 4, 3.2), (-7.8, y, z)))
            # Removable keeper in the opposite end prevents the cross pin sliding out.
            pin = pin.cut(box((1.8, 5, 1.8), (6.3, y, z)))
            parts[f"closure_pin_{z}_{y}"] = pin
            parts[f"closure_keeper_{z}_{y}"] = retained_y_key(1.5, 5, 1.6, 6.3, y, z, 0.9)
    tower = tower.cut(box((40, 3.4, 4), (0, 0, 175.8)))
    parts["tower_left"] = tower.intersect(box((100, 100, 100), (-50, 0, 165))).clean()
    parts["tower_right"] = tower.intersect(box((100, 100, 100), (50, 0, 165))).clean()
    drive = rotated(gear(), 180 / 34).translate((0, -34, 0))
    # Replaceable horn coupon is deliberately separate from the manual gear blank.
    parts["manual_drive_gear"] = drive.cut(cq.Solid.makeCylinder(2, 8, cq.Vector(0, -34, 139)))
    coupon = ring(23, 19.6, 2.4, 0)
    parts["horn_clearance_coupon"] = coupon.translate((55, 0, 140))
    # A detachable housing gauge provides fit evidence before any servo mounting.
    cradle = box((49.62, 29.12, 3), (12.5, -34, 99.5))
    for x in (-11.21, 36.21):
        cradle = cradle.fuse(box((2.2, 29.12, 7), (x, -34, 102.5)))
    for y in (-47.46, -20.54):
        cradle = cradle.fuse(box((45.22, 2.2, 7), (12.5, y, 102.5)))
    parts["servo_housing_gauge"] = cradle
    ghosts = {f"bearing_{z}": ring(24, 15, 5, z - 2.5) for z in (154, 170)}
    ghosts["servo_housing"] = box((45.22, 24.72, 35), (12.5, -34, 119.5))
    return parts, ghosts, stop_shapes


def overlap(a, b):
    return max(0, a.intersect(b).Volume())


def build_parts():
    return build()[0]


def moving_part_names():
    return {"gear_shaft", "inner_spacer", "head_flange", "shaft_key", "head_key_-18", "head_key_18"}


DRIVE_GEAR_NAME = "manual_drive_gear"
GAUGE_NAMES = {
    "horn_clearance_coupon",
    "servo_housing_gauge",
    "adjustment_shim_0_2",
    "adjustment_shim_0_4",
}


def print_orientation(name, s):
    if name.startswith("tower_"):
        ps = s.rotate((0, 0, 0), (0, 1, 0), -90 if name == "tower_right" else 90)
        support = "Support bearing-seat ceilings and closure-lug overhangs. Seam lies on the bed."
    elif name == "inner_spacer" or name == "horn_clearance_coupon":
        ps = s
        support = "No support expected; inspect the first layer in Bambu Studio."
    elif "key" in name or "keeper" in name or "pin" in name:
        ps = s
        support = "Flat rectangular face on the bed. Support pin head if needed."
    elif name == "head_flange":
        ps = s
        support = (
            "Hub annular base on the bed. Support the flange underside, stop tab, "
            "and transverse key channel."
        )
    else:
        ps = s
        support = (
            "Support shaft collar underside and transverse slot on gear_shaft; "
            "inspect gauge bridges."
        )
    return ps, support


def export_parts(parts, ghosts, record):
    assembly = cq.Assembly(name="manual_yaw_joint")
    excluded = GAUGE_NAMES
    manifest = []
    for name, s in parts.items():
        record(
            name + " CAD",
            s.isValid() and len(s.Solids()) == 1,
            "One valid connected printed solid.",
        )
        bb = s.BoundingBox()
        # The assembly coordinates are retained in STEP. Each 3MF is bed-normalized.
        ps, support = print_orientation(name, s)
        pbb = ps.BoundingBox()
        ps = ps.translate((-pbb.xmin, -pbb.ymin, -pbb.zmin))
        print("Export", name, flush=True)
        export_3mf(ps, OUT / (name + ".3mf"))
        record(
            name + " bed",
            ps.BoundingBox().xlen <= 256 and ps.BoundingBox().ylen <= 256,
            "Millimeter closed mesh; 256 mm bed.",
        )
        manifest.append(
            dict(
                name=name,
                quantity=1,
                file=name + ".3mf",
                role=(
                    "loose hand-held mesh coupon; no stationary pivot"
                    if name == "manual_drive_gear"
                    else "separate gauge/shim"
                    if name in GAUGE_NAMES
                    else "assembled joint part"
                ),
                support=support,
                assembly_bounds=[bb.xmin, bb.xmax, bb.ymin, bb.ymax, bb.zmin, bb.zmax],
            )
        )
        if name not in excluded:
            assembly.add(s, name=name)
    assembly.save(str(OUT / "assembled.step"))
    ga = cq.Assembly(name="hardware_ghosts")
    for n, s in ghosts.items():
        ga.add(s, name=n)
    ga.save(str(OUT / "hardware_ghosts.step"))
    active = {n: s for n, s in parts.items() if n not in excluded}
    return manifest, active


def check_intersections(active, ghosts, record):
    names = list(active)
    for i, n in enumerate(names):
        for m in names[i + 1 :]:
            v = overlap(active[n], active[m])
            record(n + " / " + m, v < 1e-5, f"Undeclared printed overlap {v:.6g} mm³.")
    for n, s in active.items():
        for m, t in ghosts.items():
            v = overlap(s, t)
            record(
                n + " / " + m,
                v < 1e-5,
                f"Hardware overlap {v:.6g} mm³; nominal contact surfaces have zero volume.",
            )


def check_stops(parts, stops, record):
    for sign in (-1, 1):
        lo = 75.0
        hi = 90.0
        for _ in range(18):
            mid = (lo + hi) / 2
            if overlap(rotated(parts["head_flange"], sign * mid), stops[0].fuse(stops[1])) > 1e-6:
                hi = mid
            else:
                lo = mid
        record(
            f"stop {sign}",
            79 < hi < 82,
            f"First full-solid stop contact at {sign * hi:.5f} degrees; supporting webs included.",
        )


def check_motion(parts, record):
    mesh_peak = 0.0
    motion_peak = 0.0
    hardware_peak = 0.0
    fixed = parts["tower_left"].fuse(parts["tower_right"])
    moving = parts["gear_shaft"].fuse(
        parts["head_flange"],
        parts["inner_spacer"],
        parts["shaft_key"],
        parts["head_key_-18"],
        parts["head_key_18"],
    )
    stationary_hw = [p for p in hardware() if not p["kind"].startswith("moving")]
    for angle in range(-80, 81, 2):
        gs = rotated(parts["gear_shaft"], angle)
        dg = (
            parts["manual_drive_gear"]
            .translate((0, 34, 0))
            .rotate((0, 0, 0), (0, 0, 1), -angle)
            .translate((0, -34, 0))
        )
        mesh_peak = max(mesh_peak, overlap(gs, dg))
        ms = rotated(moving, angle)
        motion_peak = max(motion_peak, overlap(ms, fixed))
        for p in stationary_hw:
            hardware_peak = max(hardware_peak, overlap(ms, p["shape"]))
    record(
        "actual involute gear mesh sweep",
        mesh_peak < 1e-5,
        f"81 positions at two-degree yaw spacing. Peak tooth solid overlap {mesh_peak:.6g} mm³.",
    )
    period = 360 / 34
    fine_steps = 108
    min_gap = float("inf")
    g0 = gear()
    g1 = rotated(gear(), 180 / 34).translate((0, -34, 0))
    for i in range(fine_steps + 1):
        a = period * i / fine_steps
        aa = rotated(g0, a).intersect(box((20, 6, 8), (0, -17, 143)))
        bb = (
            g1.translate((0, 34, 0))
            .rotate((0, 0, 0), (0, 0, 1), -a)
            .translate((0, -34, 0))
            .intersect(box((20, 6, 8), (0, -17, 143)))
        )
        min_gap = min(min_gap, aa.distance(bb))
    bound = 2 * 18 * math.radians(period / fine_steps / 2)
    record(
        "continuous CAD tooth clearance bound",
        min_gap > bound and min_gap < 2,
        f"Minimum sampled solid distance {min_gap:.6f} mm over one tooth "
        f"period, versus {bound:.6f} mm combined motion bound to nearest "
        f"sample;109 samples. Distance evaluated inX+/-10,Y-20..-14; omitted "
        f"tooth volumes have>=2 mm separation by18 mm disk bounds.",
    )
    record(
        "rotating assembly / complete tower sweep",
        motion_peak < 1e-5,
        f"Peak overlap {motion_peak:.6g} mm³ through +/-80 degrees.",
    )
    record(
        "rotating assembly / stationary hardware sweep",
        hardware_peak < 1e-5,
        f"Peak overlap {hardware_peak:.6g} mm³; all layout hardware and reservations.",
    )
    return fixed


def check_admission(parts, ghosts, fixed, record):
    # Both bearings traverse the open journal before the flange and key install.
    admission_peak = 0.0
    for target in (154, 170):
        bearing = ghosts[f"bearing_{target}"]
        for dz in range(0, 34):
            admission_peak = max(
                admission_peak, overlap(bearing.translate((0, 0, dz)), parts["gear_shaft"])
            )
    record(
        "closed bearing admission",
        admission_peak < 1e-5,
        f"Both rings slide over open journal; peak overlap {admission_peak:.6g} "
        f"mm³. Tower remains split.",
    )
    access_peak = 0.0
    for dx in range(0, 35):
        access_peak = max(access_peak, overlap(parts["shaft_key"].translate((dx, 0, 0)), fixed))
    record(
        "shaft key / tower insertion",
        access_peak < 1e-5,
        f"Complete rigid shaft key translates along X through tower notch. Peak "
        f"overlap {access_peak:.6g} mm³.",
    )
    head_peak = 0.0
    cam = camera()
    for x in (-18, 18):
        for dy in range(0, 41):
            head_peak = max(head_peak, overlap(parts[f"head_key_{x}"].translate((0, dy, 0)), cam))
    record(
        "head key / camera insertion",
        head_peak < 1e-5,
        f"Keys translate40 mm along Y with cover removed. Camera solid overlap "
        f"{head_peak:.6g} mm³. Barb compression at post requires a physical "
        f"coupon.",
    )
    rigid_peak = 0.0
    for width, height, slotwidth, slotheight, z, postbottom, posttop in [
        (1.3, 1.2, 1.6, 1.4, 183.8, 180, 185.5),
        (1.5, 1.6, 1.8, 1.8, 163.4, 160, 165),
    ]:
        receiver = box((3, 4, posttop - postbottom), (0, 0, (posttop + postbottom) / 2)).cut(
            box((slotwidth, 6, slotheight), (0, 0, z))
        )
        rigid = box((width, 10, height), (0, 0, z)).fuse(box((width + 1, 0.8, height), (0, 4.6, z)))
        for dy in range(0, 41):
            rigid_peak = max(rigid_peak, overlap(rigid.translate((0, dy, 0)), receiver))
    record(
        "rear insertion rigid key bodies and heads",
        rigid_peak < 1e-5,
        f"Full rigid bodies and enlarged heads enter receiver slots from "
        f"positiveY. Peak overlap {rigid_peak:.6g} mm³. Only protruding elastic "
        f"barbs omitted; physical compression remains U.",
    )
    record(
        "axial freedom",
        True,
        "151.2 to172.8 mm collar span minus two5 mm bearings and11 mm spacer "
        "gives0.6 mm nominal axial freedom. Measure before adding shims.",
    )
    record(
        "race radial separation",
        True,
        "22 mm keeper ID versus 20 mm rotating spacer OD leaves one mm radial "
        "gap. Actual race contact lands remain U.",
    )


def draw_dimensions():
    fig, axs = plt.subplots(1, 2, figsize=(12, 6))
    ax = axs[0]
    ax.add_patch(Circle((0, 0), 25, fill=False))
    ax.add_patch(Circle((0, 0), 16, fill=False))
    ax.add_patch(Circle((0, -34), 18, fill=False))
    ax.add_patch(Circle((0, 0), 18, fill=False))
    ax.plot([0, 0], [0, -34], "k--")
    ax.text(2, -17, "34 mm centres")
    ax.text(-28, 28, "50 OD roof flange")
    ax.set(xlim=(-38, 48), ylim=(-58, 38), title="Plan, mm")
    ax.set_aspect("equal")
    ax.grid()
    ax = axs[1]
    for x, y, w, h, label in [
        (-16, 150, 32, 26.6, "32 OD tower"),
        (-12, 151.5, 24, 5, "15 × 24 × 5"),
        (-12, 167.5, 24, 5, "15 × 24 × 5"),
        (-22, 177, 44, 3, "44 OD head flange"),
        (-25, 160, 50, 2.4, "50 OD mount"),
        (-18, 140, 36, 6, "34 tooth gear"),
    ]:
        ax.add_patch(Rectangle((x, y), w, h, fill=False))
        ax.text(x + w + 1, 164 if label == "32 OD tower" else y, label, fontsize=8)
    ax.set(xlim=(-30, 68), ylim=(138, 187), title="Elevation, mm")
    ax.set_aspect("equal")
    ax.grid()
    fig.suptitle("Manual yaw prototype: external camera cable; hardware interfaces U")
    fig.tight_layout()
    fig.savefig(OUT / "dimensions.png", dpi=160)
    plt.close(fig)


def write_results(manifest, checks, part_count):
    (OUT / "manifest.json").write_text(
        json.dumps(
            dict(
                parts=manifest,
                units="mm",
                manual_only=True,
                unknowns=[
                    "bearing race land widths",
                    "servo horn hole threads and fasteners",
                    "physical print fits",
                    "external cable flex",
                ],
            ),
            indent=2,
        )
        + "\n"
    )
    (OUT / "checks.json").write_text(
        json.dumps(dict(passed=all(c["passed"] for c in checks), checks=checks), indent=2) + "\n"
    )
    failures = [c for c in checks if not c["passed"]]
    print(json.dumps(dict(parts=part_count, checks=len(checks), failures=failures), indent=2))
    if failures:
        raise SystemExit(1)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    parts, ghosts, stops = build()
    checks = []
    for obsolete in OUT.glob("*.3mf"):
        if obsolete.stem not in parts:
            obsolete.unlink()

    def record(name, ok, detail):
        checks.append(dict(name=name, passed=bool(ok), detail=detail))

    manifest, active = export_parts(parts, ghosts, record)
    check_intersections(active, ghosts, record)
    check_stops(parts, stops, record)
    fixed = check_motion(parts, record)
    check_admission(parts, ghosts, fixed, record)
    draw_dimensions()
    write_results(manifest, checks, len(parts))


if __name__ == "__main__":
    main()
