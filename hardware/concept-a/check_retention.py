"""Targeted housing/key capture checks before complete prototype regeneration."""

import json
from pathlib import Path

import cadquery as cq
import numpy as np

import casing
import layout

OUT = Path(__file__).parent / "output" / "retention"


def speaker_checks(parts):  # noqa: C901 - one bounded housing validation report
    rows = []

    def record(name, passed, detail):
        rows.append(dict(name=name, passed=bool(passed), detail=detail))

    key = parts["speaker-retaining-key"]
    cradle = parts["speaker-cradle"]
    speaker = next(h["shape"] for h in layout.hardware() if h["name"] == "One speaker")
    record("speaker key connected", key.isValid() and len(key.Solids()) == 1, key.Volume())
    for name, other in parts.items():
        if name != "speaker-retaining-key":
            volume = key.intersect(other).Volume()
            record("speaker key / " + name, volume < 1e-5, volume)
    for hardware in layout.hardware():
        volume = key.intersect(hardware["shape"]).Volume()
        record("speaker key / " + hardware["name"], volume < 1e-5, volume)
    record("receiver shell connected", len(parts["body-front"].Solids()) == 1, "Actual owner solid")
    for name, first, second in (
        ("initial speaker / cradle", speaker, cradle),
        ("initial cradle / owner", cradle, parts["body-front"]),
    ):
        volume = first.intersect(second).Volume()
        record(name, volume < 1e-5, volume)
    fixed = cradle.fuse(key)
    for axis in range(3):
        for sign in (-1, 1):
            overlaps = []
            for distance in (0.2, 0.5, 1, 2, 5, 10):
                delta = [0, 0, 0]
                delta[axis] = sign * distance
                overlaps.append(speaker.translate(tuple(delta)).intersect(fixed).Volume())
            record(
                f"housing finite escape {'XYZ'[axis]} {sign}",
                max(overlaps) > 1e-5,
                dict(travel_mm=[0.2, 0.5, 1, 2, 5, 10], overlap_mm3=overlaps),
            )
    fixed = parts["body-front"].fuse(key)
    for axis in range(3):
        for sign in (-1, 1):
            overlaps = []
            for distance in (0.2, 0.5, 1, 2, 5, 10):
                delta = [0, 0, 0]
                delta[axis] = sign * distance
                overlaps.append(cradle.translate(tuple(delta)).intersect(fixed).Volume())
            record(f"cradle finite escape {'XYZ'[axis]} {sign}", max(overlaps) > 1e-5, overlaps)
    # These bounded paths test a specific lift/tilt family, not every possible motion.
    for axis in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
        for sign in (-1, 1):
            overlaps = []
            for amount in np.linspace(0, 1, 11)[1:]:
                moved = speaker.rotate(
                    (0, -45.5, 47.5),
                    tuple(np.array((0, -45.5, 47.5)) + np.array(axis)),
                    sign * 10 * amount,
                ).translate((0, 0, 5 * amount))
                overlaps.append(moved.intersect(cradle.fuse(key)).Volume())
            record(f"housing lift/tilt {axis} {sign}", max(overlaps) > 1e-5, overlaps)
    # Model a deflected release beam as a rigid rotation. Real flex requires a coupon.
    flex_mask = casing.B((5, 13, 8), (54.6, -51.1, 21.2))
    spring = key.intersect(flex_mask)
    released = key.cut(flex_mask).fuse(spring.rotate((54.6, -44.6, 19.6), (55.6, -44.6, 19.6), 8.5))
    # Body service removes the head/joint and roof, then the bus module before key withdrawal.
    removed_parts = {
        "speaker-retaining-key",
        "body-right",
        "body-rear",
        "body-roof",
        "head-front",
        "head-rear",
        "head-visor",
        "camera-cradle",
        "neck-cover",
    }
    all_neighbors = [
        shape
        for name, shape in parts.items()
        if name not in removed_parts and not name.startswith("roof-bridge")
    ] + [
        h["shape"]
        for h in layout.hardware()
        if h["name"] != "Bus interface" and not h["kind"].startswith("moving")
    ]
    neighbors = cq.Compound.makeCompound(all_neighbors)
    neutral_block = key.translate((0, 2, 0)).intersect(parts["body-front"]).Volume()
    record(
        "rigid key withdrawal stopped",
        neutral_block > 1e-5,
        dict(overlap_mm3=neutral_block, travel_mm=2, nominal_detent_engagement_mm=0.6),
    )
    collisions = []
    for distance in np.linspace(0, 18, 37):
        volume = released.translate((0, distance, 0)).intersect(neighbors).Volume()
        if volume > 1e-5:
            collisions.append(dict(position_mm=float(distance), volume_mm3=volume))
    record(
        "released key actual neighbor path",
        not collisions,
        dict(
            travel_mm=18,
            spacing_mm=0.5,
            removed=sorted(removed_parts) + ["joint", "roof bridge and pins", "Bus interface"],
            retained="Speaker, audio, Jetson, servo/regulator, plugs and airflow reservations",
            collisions=collisions,
            limitation="Rigid approximation of elastic release; printed flex and finger access U",
        ),
    )
    named_neighbors = {
        name: shape
        for name, shape in parts.items()
        if name not in removed_parts and not name.startswith("roof-bridge")
    }
    named_neighbors.update(
        {
            h["name"]: h["shape"]
            for h in layout.hardware()
            if h["name"] != "Bus interface" and not h["kind"].startswith("moving")
        }
    )

    def path_check(name, shape, poses, obstacles, detail):
        collisions = []
        for index, delta in enumerate(poses):
            moved = shape.translate(delta)
            for other_name, other in obstacles.items():
                volume = moved.intersect(other).Volume()
                if volume > 1e-5:
                    collisions.append(
                        dict(
                            pose=index, translation_mm=delta, neighbor=other_name, volume_mm3=volume
                        )
                    )
        record(
            name,
            not collisions,
            dict(
                **detail,
                collisions=collisions,
                limitation="Sampled actual solids, not continuous clearance proof",
            ),
        )

    poses = [(0, float(y), 0) for y in np.linspace(0, 18, 37)]
    poses += [(float(x), 18, 0) for x in range(0, 141, 2)]
    path_check(
        "complete released key extraction",
        released,
        poses,
        named_neighbors,
        dict(segments="18 mm rear at 0.5 mm, then 140 mm right at 2 mm"),
    )
    path_check(
        "reverse key insertion",
        released,
        list(reversed(poses)),
        named_neighbors,
        dict(segments="Same complete route reversed, detent held released"),
    )
    final = released.translate((140, 18, 0))
    record(
        "key completely outside enclosure",
        final.intersect(casing.body_envelopes()[0]).Volume() < 1e-5,
        "Actual complete key at final extraction pose",
    )
    # Remove Jetson and its tray before withdrawing the speaker through the rear.
    service_neighbors = {
        n: v
        for n, v in named_neighbors.items()
        if n
        not in {
            "Jetson",
            "jetson-cradle",
            "speaker-cradle",
            "One speaker",
            "Jetson USB/power plugs",
            "Fan intake space",
            "Outlet space",
        }
    }
    speaker_poses = [(0, float(y), 0) for y in range(0, 201, 2)]
    path_check(
        "speaker full rear removal",
        speaker,
        speaker_poses,
        dict(service_neighbors, **{"speaker-cradle": cradle}),
        dict(
            additional_removals=[
                "Jetson (unplugged, with fan and associated reservations)",
                "jetson-cradle",
            ],
            travel_mm=200,
        ),
    )
    cradle_poses = [(0, 0, float(z)) for z in np.linspace(0, 3, 31)]
    cradle_poses += [(0, float(y), 3) for y in range(0, 201, 2)]
    path_check(
        "speaker cradle complete removal",
        cradle,
        cradle_poses,
        service_neighbors,
        dict(
            additional_removals=[
                "Jetson (unplugged, with fan and associated reservations)",
                "jetson-cradle",
                "One speaker",
            ],
            segments="3 mm lift at 0.1 mm, then 200 mm rear at 2 mm",
        ),
    )
    access = casing.B((18, 2, 1), (63.8, -53.8, 21))
    record(
        "release tool access",
        access.intersect(neighbors).Volume() < 1e-5,
        "2 mm blunt tip enters from removed right panel; printed release force remains U",
    )
    for mask in layout.speaker_contact_regions():
        projected = key.translate((0, 0, -1)).intersect(mask["shape"]).Volume()
        record(mask["name"] + " projected upper stop", projected > 1e-5, projected)
    vent_tools = [
        casing.B((28, 3, 6), (-68, y, z)) for y in range(-34, 45, 6) for z in range(21, 108, 10)
    ]
    blocked = [key.intersect(tool).Volume() for tool in vent_tools]
    record("speaker key clear of every outlet ray", max(blocked) < 1e-5, max(blocked))
    return rows


def audio_checks(parts):  # noqa: C901 - bounded audio retention report
    rows = []

    def record(name, passed, detail):
        rows.append(dict(name=name, passed=bool(passed), detail=detail))

    key = parts["audio-retaining-key"]
    cradle = parts["audio-cradle"]
    housing = next(h["shape"] for h in layout.hardware() if h["name"] == "USB audio case")
    record("audio key connected", key.isValid() and len(key.Solids()) == 1, key.Volume())
    record(
        "audio cradle connected", cradle.isValid() and len(cradle.Solids()) == 1, cradle.Volume()
    )
    for n, other in parts.items():
        if n != "audio-retaining-key":
            v = key.intersect(other).Volume()
            record("audio key / " + n, v < 1e-5, v)
    for h in layout.hardware():
        v = key.intersect(h["shape"]).Volume()
        record("audio key / " + h["name"], v < 1e-5, v)
        v = cradle.intersect(h["shape"]).Volume()
        record("audio cradle / " + h["name"], v < 1e-5, v)
    for n, a, b in (
        ("audio housing / cradle", housing, cradle),
        ("audio cradle / shell", cradle, parts["body-front"]),
    ):
        v = a.intersect(b).Volume()
        record(n, v < 1e-5, v)
    if any(not r["passed"] for r in rows):
        return rows
    for name, moving, fixed in (
        ("audio housing", housing, cradle.fuse(key)),
        ("audio cradle", cradle, parts["body-front"].fuse(key)),
    ):
        for axis in range(3):
            for sign in (-1, 1):
                overlaps = []
                for distance in (0.2, 0.5, 1, 2, 5, 10):
                    delta = [0, 0, 0]
                    delta[axis] = sign * distance
                    overlaps.append(moving.translate(tuple(delta)).intersect(fixed).Volume())
                record(f"{name} finite escape {'XYZ'[axis]} {sign}", max(overlaps) > 1e-5, overlaps)
        for axis in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
            for sign in (-1, 1):
                overlaps = []
                for amount in np.linspace(0, 1, 11)[1:]:
                    moved = moving.rotate(
                        (-27, -40, 88),
                        tuple(np.array((-27, -40, 88)) + np.array(axis)),
                        sign * 10 * amount,
                    ).translate((0, 0, 5 * amount))
                    overlaps.append(moved.intersect(fixed).Volume())
                record(f"{name} lift/tilt {axis} {sign}", max(overlaps) > 1e-5, overlaps)
    # The housing, tray, and key leave together; only docking feet flex.
    released = key
    for x in (-44, -8):
        mask = casing.B((8, 4, 9.1), (x, -55, 75.85))
        spring = key.intersect(mask)
        released = released.cut(mask).fuse(
            spring.rotate((x - 0.4, -54.5, 80.4), (x - 0.4, -53.5, 80.4), 6)
        )
    module = cradle.fuse(housing, key)
    released_module = cradle.fuse(housing, released)
    for direction in ((0, 0, 1), (0, 1, 0)):
        v = key.translate(direction).intersect(parts["body-front"]).Volume()
        record(f"audio unreleased dock stopped {direction}", v > 1e-5, v)
    removed = {
        "audio-retaining-key",
        "speaker-retaining-key",
        "audio-cradle",
        "jetson-cradle",
        "body-right",
        "body-rear",
        "body-roof",
        "head-front",
        "head-rear",
        "head-visor",
        "camera-cradle",
        "neck-cover",
    }
    neighbors = {
        n: v for n, v in parts.items() if n not in removed and not n.startswith("roof-bridge")
    }
    excluded_hardware = {
        "USB audio case",
        "Jetson",
        "Jetson USB/power plugs",
        "Fan intake space",
        "Outlet space",
        "Bus interface",
        "Audio USB extension",
    }
    neighbors.update(
        {
            h["name"]: h["shape"]
            for h in layout.hardware()
            if h["name"] not in excluded_hardware and not h["kind"].startswith("moving")
        }
    )

    def path(name, moving, poses, fixed):
        collisions = []
        for index, delta in enumerate(poses):
            moved = moving.translate(delta)
            for n, v in fixed.items():
                box, other = moved.BoundingBox(), v.BoundingBox()
                if (
                    box.xmax < other.xmin
                    or box.xmin > other.xmax
                    or box.ymax < other.ymin
                    or box.ymin > other.ymax
                    or box.zmax < other.zmin
                    or box.zmin > other.zmax
                ):
                    continue
                overlap = moved.intersect(v).Volume()
                if overlap > 1e-5:
                    collisions.append(
                        dict(pose=index, translation_mm=delta, neighbor=n, volume_mm3=overlap)
                    )
        record(
            name,
            not collisions,
            dict(
                collisions=collisions,
                limitation="Actual solids sampled; elastic release and holding force unverified",
            ),
        )

    poses = [(0, 0, float(z)) for z in np.linspace(0, 0.5, 6)]
    poses += [(0, float(y), 0.5) for y in np.linspace(0, 200, 401)]
    path("audio complete module removal", released_module, poses, neighbors)
    # Reverse insertion uses identical released solids, obstacles, and poses.
    forward = rows[-1]
    record(
        "audio reverse module insertion",
        forward["passed"],
        dict(forward["detail"], rationale="Same service state and poses in reverse order"),
    )
    v = released_module.translate((0, 200, 0.5)).intersect(casing.body_envelopes()[0]).Volume()
    record("audio module completely outside body", v < 1e-5, v)
    outside_poses = [(0, 0, float(z)) for z in np.linspace(0, 100, 201)]
    path(
        "audio key removal outside enclosure",
        key,
        outside_poses,
        {"audio housing": housing, "audio cradle": cradle},
    )
    rows.extend(audio_release_tool_checks(parts))
    # Installed module clearance includes every actual joint solid.
    import joint

    joints = joint.build_parts()
    for n, solid in joints.items():
        if n in joint.GAUGE_NAMES or n == joint.DRIVE_GEAR_NAME:
            continue
        v = module.intersect(solid).Volume()
        record("audio installed module / joint " + n, v < 1e-5, v)

    return rows


def audio_release_tool_checks(parts):
    """Rear-entered blunt shafts load only named flexible beam contact bands."""
    rows = []
    key = parts["audio-retaining-key"]
    released = key
    for x in (-44, -8):
        mask = casing.B((8, 4, 9.1), (x, -55, 75.85))
        released = released.cut(mask).fuse(
            key.intersect(mask).rotate((x - 0.4, -54.5, 80.4), (x - 0.4, -53.5, 80.4), 6)
        )
    removed = {
        "audio-retaining-key",
        "speaker-retaining-key",
        "jetson-cradle",
        "body-right",
        "body-rear",
        "body-roof",
        "head-front",
        "head-rear",
        "head-visor",
        "camera-cradle",
        "neck-cover",
    }
    fixed = {n: v for n, v in parts.items() if n not in removed and not n.startswith("roof-bridge")}
    excluded = {
        "Jetson",
        "Jetson USB/power plugs",
        "Fan intake space",
        "Outlet space",
        "Bus interface",
        "Audio USB extension",
    }
    fixed.update(
        {
            h["name"]: h["shape"]
            for h in layout.hardware()
            if h["name"] not in excluded and not h["kind"].startswith("moving")
        }
    )

    def record(name, passed, detail):
        rows.append(dict(name=name, passed=bool(passed), detail=detail))

    def hits(shape, neighbors):
        return {
            n: volume
            for n, other in neighbors.items()
            if (volume := shape.intersect(other).Volume()) > 1e-5
        }

    for x in (-44, -8):
        entry = casing.B((2, 134.5, 2), (x + 0.6, 12.75, 74.5))
        initial = hits(entry, dict(fixed, **{"neutral audio key": key}))
        record(f"audio rear tool complete entry {x}", not initial, initial)
        contact = key.intersect(casing.B((0.8, 2.4, 2), (x - 0.8, -54.5, 74.5)))
        press = casing.B((2.5, 134.5, 2), (x + 0.35, 12.75, 74.5))
        forbidden = hits(press, dict(fixed, **{"key outside named beam contact": key.cut(contact)}))
        record(f"audio tool press forbidden clearance {x}", not forbidden, forbidden)
        volume = press.intersect(contact).Volume()
        record(
            f"audio tool contacts flexible beam {x}",
            volume > 1e-5,
            dict(volume_mm3=volume, contact="0.8 mm flex beam at Z73.5..75.5; pressure toward -X"),
        )
        held = entry.translate((-0.5, 0, 0))
        volume = held.intersect(released).Volume()
        record(f"audio tool / deflected key {x}", volume < 1e-5, volume)
        # Conservative rectangular union of tools during lift and the first 5.5 mm slide.
        hold_sweep = casing.B((2, 140, 2.5), (x + 0.1, 15.5, 74.75))
        remaining = {n: v for n, v in fixed.items() if n not in {"audio-cradle", "USB audio case"}}
        blocked = hits(hold_sweep, remaining)
        record(f"audio tool held until dock disengages {x}", not blocked, blocked)
    # Once rearward 5.5 mm, both hooks are beyond the receiver rear face.
    service = {n: v for n, v in fixed.items() if n not in {"audio-cradle", "USB audio case"}}
    collisions = []
    for y in np.linspace(5.5, 200, 390):
        moved = key.translate((0, float(y), 0.5))
        box = moved.BoundingBox()
        for n, other in service.items():
            ob = other.BoundingBox()
            if (
                box.xmax < ob.xmin
                or box.xmin > ob.xmax
                or box.ymax < ob.ymin
                or box.ymin > ob.ymax
                or box.zmax < ob.zmin
                or box.zmin > ob.zmax
            ):
                continue
            volume = moved.intersect(other).Volume()
            if volume > 1e-5:
                collisions.append(dict(rear_mm=float(y), neighbor=n, volume_mm3=volume))
    record(
        "audio neutral key route after tool withdrawal",
        not collisions,
        dict(collisions=collisions, limitation="0.5 mm samples; physical release force U"),
    )
    return rows


def audio_module_capture_checks(parts):
    """Positive docking capture of the assembled housing, tray, and key."""
    housing = next(h["shape"] for h in layout.hardware() if h["name"] == "USB audio case")
    moving = housing.fuse(parts["audio-cradle"], parts["audio-retaining-key"])
    fixed = parts["body-front"]
    rows = []
    for axis in range(3):
        for sign in (-1, 1):
            overlaps = []
            for distance in (0.2, 0.5, 1, 2, 5, 10):
                delta = [0, 0, 0]
                delta[axis] = sign * distance
                overlaps.append(moving.translate(tuple(delta)).intersect(fixed).Volume())
            rows.append(
                dict(
                    name=f"audio module finite escape {'XYZ'[axis]} {sign}",
                    passed=max(overlaps) > 1e-5,
                    detail=overlaps,
                )
            )
    for axis in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
        for sign in (-1, 1):
            overlaps = []
            for amount in np.linspace(0, 1, 11)[1:]:
                moved = moving.rotate(
                    (-27, -40, 88),
                    tuple(np.array((-27, -40, 88)) + np.array(axis)),
                    sign * 10 * amount,
                ).translate((0, 0, 5 * amount))
                overlaps.append(moved.intersect(fixed).Volume())
            rows.append(
                dict(
                    name=f"audio module lift/tilt {axis} {sign}",
                    passed=max(overlaps) > 1e-5,
                    detail=overlaps,
                )
            )
    return rows


def export_speaker_coupons(parts):
    """Crop the actual right receiver and release foot; vary only slot clearance."""
    receiver = parts["body-front"].intersect(casing.B((7.6, 12, 21.4), (54.6, -45.2, 13.9)))
    key = parts["speaker-retaining-key"].intersect(casing.B((2.4, 19.2, 8), (54.6, -46.2, 22)))
    coupons = {"speaker-release-foot": key}
    for gap in (0.1, 0.2, 0.3, 0.4):
        # Fill the original slot and release trench, then cut the chosen test clearance.
        solid = receiver.fuse(casing.B((2.8, 12, 4.4), (54.6, -45.2, 20)))
        solid = solid.cut(casing.B((2.4 + gap, 14, 2.4 + gap), (54.6, -45.2, 20.8)))
        solid = solid.cut(casing.B((2.4 + gap, 14, 1.6), (54.6, -45.2, 18.6))).clean()
        coupons[f"speaker-receiver-clearance-{gap:.1f}"] = solid
    manifest = []
    for name, shape in coupons.items():
        assert shape.isValid() and len(shape.Solids()) == 1, name
        printable = casing.print_transform("speaker-retaining-key", shape)
        layout.export_3mf(printable, OUT / (name + ".3mf"))
        cq.exporters.export(shape, str(OUT / (name + ".step")))
        manifest.append(
            dict(
                name=name,
                volume_mm3=shape.Volume(),
                orientation="Rear face down; local support under projecting release foot as needed",
                status="Unprinted tolerance coupon; release force and holding strength unverified",
            )
        )
    (OUT / "coupon-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def export_audio_coupons(parts):
    """Exact module docking pocket and flex foot, separate from real electronics."""
    coupons = {
        "audio-dock-receiver": parts["body-front"].intersect(
            casing.B((11.4, 7.6, 8.8), (-44, -54.5, 75.9))
        ),
        "audio-dock-release-foot": parts["audio-retaining-key"].intersect(
            casing.B((8, 4, 9.1), (-44, -55, 75.85))
        ),
    }
    manifest = json.loads((OUT / "coupon-manifest.json").read_text())
    for name, shape in coupons.items():
        assert shape.isValid() and len(shape.Solids()) == 1, name
        printable = casing.print_transform("audio-retaining-key", shape)
        layout.export_3mf(printable, OUT / (name + ".3mf"))
        cq.exporters.export(shape, str(OUT / (name + ".step")))
        manifest.append(
            dict(
                name=name,
                volume_mm3=shape.Volume(),
                orientation=(
                    "Rear face down; support receiver pocket ceilings and projecting pads locally"
                ),
                status="Exact nominal docking coupon; release force and 20 cycles unverified",
            )
        )
    (OUT / "coupon-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def export_jetson_edge_coupon():
    """Standalone thickness/depth gauge; no installed Jetson location is assumed."""
    coupon = casing.B((10, 76, 8), (-5, 30, 4))
    for index, gap in enumerate((0.1, 0.2, 0.3, 0.4)):
        center = index * 20
        for sign in (-1, 1):
            y = center + sign * ((11 + gap) / 2 + 1.2)
            coupon = coupon.fuse(casing.B((10.2, 2.4, 8), (5.1, y, 4)))
            coupon = coupon.fuse(
                casing.B((1, 0.5, 8), (9.7, center + sign * ((11 + gap) / 2 - 0.25), 4))
            )
        label = cq.Workplane("XY").text(f"{gap:.1f}", 3, 0.4).val().translate((-5, center, 8))
        coupon = coupon.fuse(label)
    block = casing.B((10, 11, 8), (5, 0, 4))
    block = block.fuse(cq.Workplane("XY").text("11", 3, 0.4).val().translate((5, 0, 8)))
    manifest = []
    for name, shape in (
        ("jetson-edge-clearance-coupon", coupon.clean()),
        ("jetson-11mm-dummy", block.clean()),
    ):
        assert shape.isValid() and len(shape.Solids()) == 1, name
        layout.export_3mf(shape, OUT / (name + ".3mf"))
        cq.exporters.export(shape, str(OUT / (name + ".step")))
        manifest.append(
            dict(
                name=name,
                orientation="Flat base down",
                status=(
                    "User-measured 11 mm thickness / 10 mm depth only; arbitrary 8 mm test length"
                ),
                limitation=(
                    "No installed location or real Jetson retention claim; "
                    "force and flex unverified"
                ),
            )
        )
    (OUT / "jetson-coupon-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    parts = casing.build_parts()
    speaker = speaker_checks(parts)
    audio = audio_checks(parts) + audio_module_capture_checks(parts)
    (OUT / "speaker-checks.json").write_text(json.dumps(speaker, indent=2) + "\n")
    (OUT / "audio-checks.json").write_text(json.dumps(audio, indent=2) + "\n")
    rows = speaker + audio
    report = dict(status="Targeted retention CAD prototype; physical forces U", checks=rows)
    (OUT / "checks.json").write_text(json.dumps(report, indent=2) + "\n")
    failures = [row for row in rows if not row["passed"]]
    print(json.dumps(dict(checks=len(rows), failures=failures), indent=2), flush=True)
    if failures:
        raise SystemExit(1)
    export_speaker_coupons(parts)
    export_audio_coupons(parts)
    export_jetson_edge_coupon()
    import trimesh

    meshes = []
    for manifest in ("coupon-manifest.json", "jetson-coupon-manifest.json"):
        for row in json.loads((OUT / manifest).read_text()):
            file = OUT / (row["name"] + ".3mf")
            mesh = trimesh.load(file, force="mesh")
            passed = (
                mesh.is_watertight
                and mesh.is_volume
                and abs(mesh.bounds[0, 2]) < 1e-5
                and max(mesh.extents[:2]) < 238
                and mesh.extents[2] < 256
            )
            meshes.append(
                dict(
                    file=file.name,
                    closed=bool(mesh.is_watertight),
                    positive_volume=bool(mesh.is_volume),
                    size_mm=mesh.extents.tolist(),
                    bed_z=float(mesh.bounds[0, 2]),
                    printable_dimensions=bool(passed),
                )
            )
    (OUT / "coupon-mesh-checks.json").write_text(json.dumps(meshes, indent=2) + "\n")
    assert all(row["printable_dimensions"] for row in meshes), meshes


if __name__ == "__main__":
    main()
