"""Build the removable Concept A casing and print gauges from the source envelopes.
Run with build/hardware-layout/venv/bin/python hardware/concept-a/casing.py.
"""

from __future__ import annotations
import itertools
import math
from enclosure_geometry import body_envelopes, head_envelopes
import json
from pathlib import Path
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
import cadquery as cq
import numpy as np
import trimesh
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import layout
from screen_layouts import validate_final_geometry

OUT = Path(__file__).resolve().parent / "output" / "casing"
CREAM = "#f5f5f5"
BLACK = "#222326"
B = layout.box


def cylinder(radius, length, center, axis=(0, 0, 1)):
    return cq.Solid.makeCylinder(radius, length, cq.Vector(*center), cq.Vector(*axis))


def rounded(size, center, radius=2):
    """Round only the outside vertical edges; preserve the rectangular interior."""
    return cq.Workplane("XY").box(*size).edges("|Z").fillet(radius).translate(center).val()


def fuse(shapes):
    result = shapes[0]
    for shape in shapes[1:]:
        result = result.fuse(shape)
    return result.clean()


def receiver(center, size, slot_size):
    block = B(size, center)
    slot = B(slot_size, center)
    return block.cut(slot)


def _body_panels():
    outer, inner = body_envelopes()
    shell = outer.cut(inner).intersect(B((160, 140, 140), (0, 0, 70)))
    rear_region = B((180, 100, 134), (0, 70.1, 75))
    rear = shell.intersect(rear_region)
    right = shell.intersect(B((80, 99.8, 134), (83.1, -30.1, 75)))
    front = shell.cut(B((180, 100.2, 134), (0, 70, 75))).cut(B((80.2, 150, 134), (83, -5, 75)))
    missing = shell.cut(front.fuse(rear, right))
    difference = abs(
        front.Volume() + rear.Volume() + right.Volume() + missing.Volume() - shell.Volume()
    )
    preflight = dict(
        shell_mm3=shell.Volume(),
        front_mm3=front.Volume(),
        rear_mm3=rear.Volume(),
        port_mm3=right.Volume(),
        seam_gap_mm3=missing.Volume(),
        conservation_error_mm3=difference,
    )
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "panel-preflight.json").write_text(json.dumps(preflight, indent=2) + "\n")
    assert all(
        shape.isValid() and len(shape.Solids()) == 1 and shape.Volume() > 1000
        for shape in (front, rear, right)
    ), preflight
    assert (
        difference < max(0.05, shell.Volume() * 1e-6) and missing.Volume() < shell.Volume() * 0.02
    ), preflight
    for x in (-46, -8):
        front = front.cut(cylinder(1.7, 16, (x, -65, 85), (0, 1, 0)))
    rear = rear.cut(B((10, 20, 12), (24, 56, 137)))
    port_window = B((50, 48, 124), (65, 6, 58))
    right = right.cut(port_window)
    front = front.cut(port_window)
    return front, rear, right


def _panel_catches(front, rear, right):
    for z in (15, 125):
        rz = 10 if z == 15 else z
        # Rear catches sit beyond the reserved outlet, with3mm side ligaments.
        rear = rear.fuse(
            B((2, 8, 3), (-61.8, 42, rz)),
            B((4, 30, 3), (-61.8, 52, rz)).intersect(body_envelopes()[0]),
        )
        clearance = B((2.2, 8.2, 3.2), (-61.8, 42, rz))
        front = front.cut(clearance)
        socket = receiver((-61.8, 35, rz), (8.2, 10, 8), (2.2, 20, 3.2))
        front = front.fuse(
            socket, B((14, 30, 8), (-70, 23, rz)).cut(clearance).intersect(body_envelopes()[0])
        )
        # Port cover releases laterally; rear cover releases rearward.
        tongue = B((8, 2, 3), (46, -53.4, z))
        right = right.fuse(tongue, B((26, 4, 3), (58, -53.4, z)).intersect(body_envelopes()[0]))
        clearance = B((30, 2.2, 3.2), (46, -53.4, z))
        front = front.cut(clearance)
        socket = receiver((38, -53.4, z), (10, 7, 8), (30, 2.2, 3.2))
        front = front.fuse(socket)
    return front, rear, right


def _roof(front, rear, right):
    outer, inner = body_envelopes()
    roof = outer.cut(inner).intersect(B((160, 140, 20), (0, 0, 150.2)))
    plate = B((136, 112, 3.2), (0, 0, 158.4)).intersect(outer)
    roof = roof.fuse(plate)
    roof = roof.cut(cylinder(16.2, 25, (0, 0, 139)))
    roof = roof.cut(B((10, 18, 25), (24, 56, 151)))
    for x in (-46, 46):
        for y in (-36, 36):
            roof = roof.cut(B((2.2, 3.2, 8), (x, y, 142)))
            post = B((2, 3, 3), (x, y, 141.3))
            support = B((6, 28, 6), (x, y + (-12 if y < 0 else 12), 136.8)).intersect(outer)
            beam = B((6, 12, 6), (x, y, 136.8))
            if y < 0 and x > 43:
                right = right.fuse(post, support, beam)
            elif y < 0:
                front = front.fuse(post, support, beam)
            else:
                rear = rear.fuse(post, support, beam)
    for x in (-21, 21):
        post = B((3, 4, 5), (x, 0, 162.5)).cut(B((1.8, 6, 1.8), (x, 0, 163.4)))
        roof = roof.fuse(post)
    return front, rear, right, roof


def _roof_bridge(roof):
    # A rear edge-open channel admits the joint with its gear below the roof.
    bridge_region = B((32, 60, 25), (0, 30, 151)).fuse(B((37.6, 60, 14), (0, 30, 147)))
    bridge = roof.intersect(bridge_region)
    roof = roof.cut(B((32.4, 62, 25), (0, 31, 151)))
    roof = roof.cut(B((38, 62, 14), (0, 31, 147)))
    bridge_parts = {"roof-bridge": bridge}
    for sign in (-1, 1):
        roof = roof.cut(B((36.4, 2.2, 2.2), (sign * 33.3, 25, 158.4)))
        roof = roof.cut(B((3, 5.2, 5), (sign * 51, 25, 158.4)))
        bridge = bridge.cut(B((4.2, 2.2, 2.2), (sign * 14, 25, 158.4)))
        bridge = bridge.cut(B((1.8, 1, 5), (sign * 13.3, 25, 158.4)))
        pin = B((38.5, 2, 2), (sign * 31.25, 25, 158.4))
        pin = pin.fuse(B((2, 5, 3.2), (sign * 51, 25, 158.4)))
        pin = pin.cut(B((1.8, 1, 5), (sign * 13.3, 25, 158.4)))
        keeper = B((1.5, 0.8, 5.6), (sign * 13.3, 25, 157.6))
        keeper = keeper.fuse(B((2.8, 0.8, 0.8), (sign * 13.3, 25, 160.4)))
        # Two narrow barbs flex through the keeper slit and capture the underside.
        for side in (-1, 1):
            poly = [
                (sign * 13.3 + side * 0.75, 155.8),
                (sign * 13.3 + side * 1.1, 156.3),
                (sign * 13.3 + side * 0.75, 156.6),
            ]
            barb = (
                cq.Workplane("XZ").polyline(poly).close().extrude(0.8).translate((0, 25.4, 0)).val()
            )
            keeper = keeper.fuse(barb)
        bridge_parts[f"roof-bridge-pin-{sign}"] = pin.clean()
        bridge_parts[f"roof-bridge-keeper-{sign}"] = keeper.clean()
    bridge_parts["roof-bridge"] = bridge.clean()
    return roof, bridge_parts


def _head_shells():
    head_outer, head_inner = head_envelopes()
    head = head_outer.cut(head_inner)
    rear_shell = head_outer.cut(head_inner).intersect(B((120, 20, 70), (0, 42.1, 208)))
    head = head.cut(B((120, 20.2, 70), (0, 42, 208)))
    # Visor is inset in the front face rather than increasing the depth envelope.
    head = head.cut(
        cq.Workplane("XZ")
        .rect(98.4, 46.4)
        .extrude(15)
        .edges("|Y")
        .fillet(18.2)
        .translate((0, -30, 208))
        .val()
    )
    head = head.cut(cylinder(7.6, 5, (0, 0, 179)))
    for x in (-18, 18):
        head = head.cut(B((3.4, 4.4, 5), (x, 0, 181.2)))
        head = head.cut(B((2.7, 40, 1.3), (x, 20, 183.8)))
    # External cable entry: rear floor edge remains open when rear cover is removed.
    head = head.cut(B((9, 20, 5), (24, 28, 181.2)))
    visor = (
        cq.Workplane("XZ")
        .rect(98, 46)
        .extrude(2)
        .edges("|Y")
        .fillet(18)
        .translate((0, -38.1, 208))
        .val()
    )
    visor = visor.cut(cylinder(20.2, 8, (-24, -44, 208), (0, 1, 0)))
    # Decorative second eye is a shallow recessed circle in the matte black panel.
    visor = visor.cut(cylinder(11, 0.3, (22, -40.11, 208), (0, 1, 0)))
    visor = visor.fuse(cylinder(11.4, 2, (22, -39.5, 208), (0, 1, 0)))
    axis = cq.Vector(0, 1, 0)
    origin = cq.Vector(-24, -40.1, 208)
    baffle = cq.Solid.makeCone(22, 15, 8.2, origin, axis).cut(
        cq.Solid.makeCone(20.2, 13.2, 8.2, origin, axis)
    )
    visor = visor.fuse(baffle)
    head = head.cut(cylinder(22.2, 17, (-24, -45, 208), (0, 1, 0)))
    for x in (-47, 47):
        for z in (198, 218):
            tongue = B((4, 4, 2), (x - (1 if x > 0 else -1), -37, z))
            visor = visor.fuse(tongue)
            head = head.cut(B((4.2, 4.2, 2.2), (x - (1 if x > 0 else -1), -37, z)))
    head_rear = rear_shell
    for x in (-52, 52):
        for z in (204, 212):
            beam_x = x + (1.5 if x > 0 else -1.5)
            head_rear = head_rear.cut(B((4.2, 8.2, 4.2), (beam_x, 29, z)))
            head_rear = head_rear.fuse(B((1, 8, 2), (x, 35, z)))
            head = head.cut(B((1.2, 8.2, 2.2), (x, 35, z)))
            socket = B((4, 8, 4), (beam_x, 29, z)).cut(B((1.2, 10, 2.2), (x, 33, z)))
            head = head.fuse(
                socket, B((12, 6, 4), (x + (6 if x > 0 else -6), 27, z)).intersect(head_outer)
            )
    # Small rear relief prevents forcing a cable through a closed aperture.
    head_rear = head_rear.cut(B((10, 5, 5), (24, 36, 184.4)))
    return head, head_rear, visor


def _floor_cradles(front):
    mounts = {}
    # Floor trays are captured on removable friction posts. All contact gaps are 0.4 mm.
    for label, sx, sy, cx, cy, bottom in [
        ("speaker-cradle", 100, 21, 0, -45.5, 25),
        ("jetson-cradle", 90.5, 35, -7.5, 10, 10),
    ]:
        top = bottom - 0.4
        tray = B((sx + 1, sy + 1, 2.4), (cx, cy, top - 1.2))
        tray = tray.fuse(B((1.2, sy + 3.2, 5), (cx - sx / 2 - 1, cy, top + 2.5)))
        tray = tray.fuse(B((sx + 3.2, 1.2, 5), (cx, cy - sy / 2 - 1, top + 2.5)))
        if label == "speaker-cradle":
            tray = tray.fuse(B((1.2, sy + 3.2, 5), (cx + sx / 2 + 1, cy, top + 2.5)))
        foot_x = [cx - sx / 2 + 8, cx + sx / 2 - 8]
        foot_y = [cy] if label == "speaker-cradle" else [cy - sy / 2 + 5, cy + sy / 2 - 5]
        for px in foot_x:
            for py in foot_y:
                height = top - 2.4 - 3.2
                foot = B((6, 6, height), (px, py, 3.2 + height / 2))
                tray = tray.cut(B((2.2, 3.2, 2.6), (px, py, top - 1.2)))
                front = front.fuse(foot, B((2, 3, 2.2), (px, py, top - 1.3)))
        if label == "jetson-cradle":
            tray = tray.cut(B((10, 100, 30), (42.35, cy, 10)))
        mounts[label] = tray.clean()
    return front, mounts


def _audio_cradle(front):
    # Forward shelf extension supports audio without consuming the raised speaker.
    audio = B((54.8, 26.2, 2.4), (-27, -43.9, 74.65))
    audio = audio.fuse(B((1.2, 18, 5), (-54.5, -40, 78.35)), B((54.8, 1.2, 5), (-27, -48.3, 78.35)))
    for px in (-44, -8):
        beam = B((6, 12, 6), (px, -60.9, 70.45))
        beam = beam.cut(B((102, 23, 47), (0, -45.5, 47.5)))
        front = front.fuse(beam, B((2, 2, 2), (px, -55.9, 74.45)))
        audio = audio.cut(B((2.2, 2.2, 2.2), (px, -55.9, 74.45)))
    audio = audio.cut(B((4, 30, 10), (1.6, -40, 82)))
    audio = audio.intersect(body_envelopes(wall=3.4)[1])
    return front, audio.clean()


def _camera_cradle(head):
    # Camera edge gauge surrounds the PCB while leaving optics and connectors open.
    frame = B((41.8, 3.2, 41.8), (-24, -4, 208)).cut(B((37.8, 5, 37.8), (-24, -4, 208)))
    for px in (-43.9, -10):
        foot = (
            B((2, 3.2, 1.5), (px, -4, 186.35)) if px < -20 else B((8, 3.2, 1.5), (-7.1, -4, 186.35))
        )
        foot = cq.Workplane(obj=foot).edges("|Y").fillet(0.3).val()
        frame = frame.fuse(foot).cut(B((1, 1.8, 2.4), (px, -4, 186.6)))
        head = head.fuse(B((0.8, 1.6, 4.4), (px, -4, 184.6)))
    frame = frame.cut(B((3, 5, 0.6), (-18, -4, 187.35)))
    return head, frame.clean()


def build_parts():
    """Assembly coordinates match layout.py. Panel fits have 0.1 mm per side."""
    front, rear, right = _body_panels()
    front, rear, right = _panel_catches(front, rear, right)
    front, rear, right, roof = _roof(front, rear, right)
    roof, bridge_parts = _roof_bridge(roof)
    head, head_rear, visor = _head_shells()
    front, mounts = _floor_cradles(front)
    front, mounts["audio-cradle"] = _audio_cradle(front)
    head, mounts["camera-cradle"] = _camera_cradle(head)
    outer, _ = body_envelopes()
    front, rear, right = [p.intersect(outer) for p in (front, rear, right)]
    head_outer, head_inner = head_envelopes()
    head, head_rear = [p.intersect(head_outer) for p in (head, head_rear)]
    # A removable curved acoustic panel replaces the cream slot grille.
    outer, inner = body_envelopes()
    grille_mask = (
        cq.Workplane("XZ")
        .rect(108, 42)
        .extrude(50)
        .edges("|Y")
        .fillet(16)
        .translate((0, -40, 48))
        .val()
    )
    grille = outer.cut(inner).intersect(grille_mask)
    front = front.cut(grille_mask)
    holes = [
        cylinder(1.4, 60, (x, -90, z), (0, 1, 0))
        for x in range(-45, 46, 5)
        for z in range(33, 64, 5)
    ]
    grille = grille.cut(cq.Compound.makeCompound(holes)).clean()
    for x in (-51, 51):
        tongue = B((4, 6.4, 3), (x, -59.5, 48))
        grille = grille.fuse(tongue)
        front = front.cut(B((4.2, 6.6, 3.2), (x, -59.5, 48)))
    rear = rear.cut(grille_mask).cut(front).clean()
    right = right.cut(grille_mask).cut(front).cut(rear).clean()
    vents = [B((28, 3, 6), (-68, y, z)) for y in range(-34, 45, 6) for z in range(21, 108, 10)]
    cuts = cq.Compound.makeCompound(vents)
    front, rear = front.cut(cuts).clean(), rear.cut(cuts).clean()
    intake = cq.Compound.makeCompound(
        [B((3, 50, 6), (x, 55, z)) for x in range(-48, 35, 6) for z in range(21, 108, 10)]
    )
    rear = rear.cut(intake).clean()
    neck = layout.ring(54, 50.8, 17, 160)
    for x in (-26.2, 26.2):
        neck = neck.fuse(B((1.2, 3, 3), (x, 0, 159)))
        roof = roof.cut(B((1.4, 3.2, 3.2), (x, 0, 159)))
    # The neck cover lifts off after removing the head, exposing the joint keys.
    return (
        {
            "body-front": front.clean(),
            "body-rear": rear.clean(),
            "body-right": right.clean(),
            "body-roof": roof.clean(),
            "head-front": head.clean(),
            "head-rear": head_rear.clean(),
            "head-visor": visor.clean(),
            "speaker-grille": grille.clean(),
            "neck-cover": neck.clean(),
        }
        | mounts
        | bridge_parts
    )


def metadata():
    return {
        name: dict(
            kind="casing",
            color=BLACK if name in ("head-visor", "speaker-grille", "neck-cover") else CREAM,
            moving=name.startswith("head-") or name == "camera-cradle",
            removable=name not in ("body-front", "head-front"),
        )
        for name in (
            "body-front",
            "body-rear",
            "body-right",
            "body-roof",
            "head-front",
            "head-rear",
            "head-visor",
            "speaker-grille",
            "neck-cover",
            "speaker-cradle",
            "jetson-cradle",
            "audio-cradle",
            "camera-cradle",
            "roof-bridge",
            "roof-bridge-pin--1",
            "roof-bridge-pin-1",
            "roof-bridge-keeper--1",
            "roof-bridge-keeper-1",
        )
    }


def gauges():
    """Loose envelope trays establish dimensions before selecting component contact lands."""
    result = {}
    for name, sx, sy in [
        ("speaker-gauge", 100, 21),
        ("jetson-gauge", 90.5, 35),
        ("audio-case-gauge", 53, 14.6),
    ]:
        # Open rear side makes extraction possible without levering populated boards.
        outer = B((sx + 5.6, sy + 5.6, 8), (0, 0, 4))
        cavity = B((sx + 0.8, sy + 0.8, 8), (0, 0, 6.4))
        tray = outer.cut(cavity).cut(B((sx + 0.8, 6, 9), (0, sy / 2 + 2, 6.5)))
        result[name] = tray.clean()
    coupon = B((65, 26, 6), (32.5, 13, 3))
    for i, gap in enumerate((0, 0.1, 0.2, 0.3)):
        coupon = coupon.cut(B((2 + gap, 8, 3 + gap), (10 + i * 15, 24, 3.5)))
    result["panel-socket-coupon"] = coupon.clean()
    result["panel-tongue-coupon"] = fuse(
        [B((30, 20, 2), (15, 10, 1)), B((2, 10, 3), (15, 20, 3.5))]
    )
    return result


def print_transform(name, shape):
    """Put the indicated broad flat face on the bed with Zmin exactly zero."""
    if name == "body-front":
        shape = shape.rotate((0, 0, 0), (1, 0, 0), 90 + math.degrees(math.atan(0.0625)))
    elif name in ("head-front", "head-visor", "camera-cradle"):
        shape = shape.rotate((0, 0, 0), (1, 0, 0), 90)
    elif name == "speaker-grille":
        shape = shape.rotate((0, 0, 0), (1, 0, 0), -90)
    elif name == "neck-cover":
        shape = shape.rotate((0, 0, 0), (1, 0, 0), 180)
    elif name == "body-rear":
        shape = shape.rotate((0, 0, 0), (1, 0, 0), -90 - math.degrees(math.atan(0.0625)))
    elif name == "head-rear":
        shape = shape.rotate((0, 0, 0), (1, 0, 0), -90)
    elif name.startswith("roof-bridge-pin-"):
        sign = int(name.rsplit("-", 1)[1]) if "--" not in name else -1
        shape = shape.rotate((0, 0, 0), (0, 1, 0), 90 * sign)
    elif name.startswith("roof-bridge-keeper-"):
        shape = shape.rotate((0, 0, 0), (1, 0, 0), 90)
    elif name == "body-right":
        shape = shape.rotate((0, 0, 0), (0, 1, 0), 90 + math.degrees(math.atan(0.075)))
    vertices, _ = shape.tessellate(0.05, 0.1)
    minima = np.min([v.toTuple() for v in vertices], axis=0)
    return shape.translate(tuple(-minima))


def mesh(shape):
    vertices, faces = shape.tessellate(0.16, 0.25)
    return trimesh.Trimesh(vertices=[v.toTuple() for v in vertices], faces=faces)


def check(parts):  # noqa: C901 - one ordered CAD validation report
    rows = []

    def record(name, passed, detail):
        rows.append(dict(name=name, passed=bool(passed), detail=detail))

    for name, shape in parts.items():
        record(
            name + " solid",
            shape.isValid() and len(shape.Solids()) == 1,
            f"{len(shape.Solids())} connected solids; {shape.Volume():.3f} mm³.",
        )
    for (an, a), (bn, b) in itertools.combinations(parts.items(), 2):
        volume = a.intersect(b).Volume()
        record(
            an + " / " + bn, volume < 1e-5, f"Overlap {volume:.6f} mm³; boundary contact allowed."
        )
    hardware = layout.hardware()
    for name, shape in parts.items():
        for p in hardware:
            if (name.startswith("head-") or name == "camera-cradle") != p["kind"].startswith(
                "moving"
            ):
                continue
            overlap = shape.intersect(p["shape"]).Volume()
            record(
                name + " / " + p["name"],
                overlap < 1e-5,
                f"Hardware/reservation overlap {overlap:.6f} mm³.",
            )
        if name.startswith("head-") or name == "camera-cradle":
            overlap = shape.intersect(layout.camera()).Volume()
            record(name + " / full camera", overlap < 1e-5, f"Overlap {overlap:.6f} mm³.")
    _check_admission(parts, hardware, record)
    for focus in (26, 27.5):
        recess = 40 - (4.8 + focus)
        required = 8.5 + recess * np.tan(np.radians(50))
        record(
            f"Lens opening / focus {focus}",
            required <= 20.2,
            f"Ø40.4 aperture; ideal 100° diagonal cone radius {required:.3f} mm; actual framing U.",
        )
    record(
        "Roof flange footprint",
        abs(parts["body-roof"].intersect(cylinder(25, 5, (0, 0, 160))).Volume() - 94.08) < 1e-5,
        "Only the two specified 3×4×5 mm posts enter the Ø50 flange footprint above Z160.",
    )
    outer, inner = body_envelopes()
    head_outer, head_inner = head_envelopes()

    reservations = [
        (p["name"], p["shape"], "head" if p["kind"].startswith("moving") else "body")
        for p in layout.hardware()
    ]
    reservations.append(("complete camera", layout.camera(), "head"))
    metadata_rows = metadata()
    scopes = {
        name: (shape, "head" if metadata_rows[name]["moving"] else "body")
        for name, shape in parts.items()
    }
    walls = [
        ("body", outer, inner, [B((160, 0.1, 180), (0, y, 80)) for y in (-54, 0, 54)]),
        ("head", head_outer, head_inner, [B((130, 0.1, 70), (0, y, 208)) for y in (-34, 0, 34)]),
    ]
    supports = []
    # Validate continuous rectangular cores within the actual structural shell.
    base_shell = outer.cut(inner).intersect(B((160, 140, 140), (0, 0, 70)))
    for label, sx, sy, cx, cy, bottom in [
        ("speaker", 100, 21, 0, -45.5, 25),
        ("Jetson", 90.5, 35, -7.5, 10, 10),
    ]:
        height = bottom - 0.4 - 5.6
        ys = [cy] if label == "speaker" else [cy - sy / 2 + 5, cy + sy / 2 - 5]
        for x in (cx - sx / 2 + 8, cx + sx / 2 - 8):
            for y in ys:
                core = B((6, 6, height), (x, y, 3.2 + height / 2))
                supports.append(
                    (
                        f"{label} pedestal {x}/{y}",
                        parts["body-front"],
                        core,
                        parts["body-front"].intersect(base_shell),
                        "z",
                    )
                )
    for x in (-44, -8):
        core = B((6, 2.4, 2.4), (x, -56.1, 72.225))
        # The flat central wall keeps this entire specified support core rectangular.
        supports.append(
            (
                f"audio support {x}",
                parts["body-front"],
                core,
                parts["body-front"].intersect(base_shell),
                "y",
            )
        )
    for x in (-46, 46):
        for y in (-36, 36):
            core = B((6, 12, 6), (x, y, 136.8))
            owner = (
                parts["body-right"]
                if y < 0 and x > 43
                else parts["body-front"]
                if y < 0
                else parts["body-rear"]
            )
            supports.append(
                (f"roof support {x}/{y}", owner, core, owner.intersect(base_shell), "y")
            )
    # Actual section areas along declared load beams, not only their bounding boxes.
    for x in (-44, -8):
        areas = [
            parts["body-front"].intersect(B((6, 0.1, 2.4), (x, y, 72.225))).Volume() / 0.1
            for y in np.linspace(-56.1, -57.2, 8)
        ]
        record(
            f"audio beam {x} load sections",
            min(areas) >= 14.4 - 1e-5,
            f"Actual minimum section area {min(areas):.6f} mm² over8 sections; 2.4×6 mm reference.",
        )
    for x in (-46, 46):
        for y in (-36, 36):
            owner = (
                parts["body-right"]
                if y < 0 and x > 43
                else parts["body-front"]
                if y < 0
                else parts["body-rear"]
            )
            areas = [
                owner.intersect(B((6, 0.1, 6), (x, yy, 136.8))).Volume() / 0.1
                for yy in np.linspace(y, 53 if y > 0 else -53, 12)
            ]
            record(
                f"roof beam {x}/{y} load sections",
                min(areas) >= 14.4 - 1e-5,
                (
                    f"Actual minimum section area {min(areas):.6f} mm² over12 sections; 2.4×6 mm "
                    f"reference."
                ),
            )
    # Socket top/bottom lands are real2.4mm solids in the final perforated owner.
    for label, x, y, zs, width, depth in [
        ("rear", -61.8, 35, (10, 125), 8.2, 10),
        ("port", 38, -53.4, (15, 125), 10, 7),
    ]:
        for z in zs:
            for sign in (-1, 1):
                land = B((width, depth, 2.4), (x, y, z + sign * 2.8))
                missing = land.cut(parts["body-front"]).Volume()
                record(
                    f"{label} socket {z} ligament {sign}",
                    missing < 1e-5,
                    f"2.4mm structural land; missing {missing:.6g} mm³ from actual final part.",
                )
    final_checks = validate_final_geometry(
        {"body": inner, "head": head_inner}, reservations, scopes, walls, supports
    )
    for result in final_checks:
        record(result["name"], result["passed"], str(result["measured"]))
    closed_body = cq.Compound.makeCompound(
        [parts[n] for n in ("body-front", "body-rear", "body-right", "body-roof", "roof-bridge")]
    )
    for label, probes in [
        (
            "outlet",
            [B((28, 3, 6), (-68, y, z)) for y in range(-34, 45, 6) for z in range(21, 108, 10)],
        ),
        (
            "intake",
            [B((3, 50, 6), (x, 55, z)) for x in range(-48, 35, 6) for z in range(21, 108, 10)],
        ),
    ]:
        blocked = [probe.intersect(closed_body).Volume() for probe in probes]
        endpoints = []
        for probe in probes:
            c = probe.Center()
            endpoint = (
                B((0.02, 3, 6), (-54, c.y, c.z))
                if label == "outlet"
                else B((3, 0.02, 6), (c.x, 30, c.z))
            )
            exterior = (
                B((0.02, 3, 6), (-82, c.y, c.z))
                if label == "outlet"
                else B((3, 0.02, 6), (c.x, 80, c.z))
            )
            endpoints.append(
                endpoint.cut(inner).Volume() < 1e-5 and exterior.intersect(outer).Volume() < 1e-5
            )
        area = sum(
            18 for value, valid in zip(blocked, endpoints, strict=True) if value < 1e-5 and valid
        )
        record(
            label + " actual cavity endpoints",
            all(endpoints),
            (
                f"{sum(endpoints)}/{len(endpoints)} complete endpoint faces inside cavity "
                f"and outside outer shell."
            ),
        )
        record(
            label + " actual clear projected opening",
            area >= 2268,
            (
                f"{area} mm²; {len(probes)} complete 3×6 mm through-prisms; worst "
                f"obstruction {max(blocked):.6g} mm³."
            ),
        )
    for result in check_cover_service(parts):
        record(result["name"] + " sampled service travel", result["passed"], json.dumps(result))
    return rows


def check_cover_service(parts):
    """Actual-solid sampled service travel; physical release and cable behavior remain U."""
    hardware = [
        p["shape"]
        for p in layout.hardware()
        if p["kind"] == "hardware" or p["name"] == "Jetson USB/power plugs"
    ]
    poses = sorted(set(np.arange(0, 8.01, 0.5).tolist() + np.arange(10, 80.01, 2).tolist()))
    results = []
    for name, direction in (("body-rear", (0, 1, 0)), ("body-right", (1, 0, 0))):
        other = "body-right" if name == "body-rear" else "body-rear"
        fixed = cq.Compound.makeCompound(
            [
                parts[n]
                for n in ("body-front", other, "speaker-cradle", "jetson-cradle", "audio-cradle")
            ]
            + hardware
        )
        overlaps = []
        for travel in poses:
            moved = parts[name].translate(tuple(travel * value for value in direction))
            volume = moved.intersect(fixed).Volume()
            if volume > 1e-5:
                overlaps.append(dict(travel_mm=travel, overlap_mm3=volume))
        results.append(
            dict(
                name=name,
                poses_mm=poses,
                direction=direction,
                passed=not overlaps,
                obstructions=overlaps,
                validation=(
                    "Actual solid poses every0.5mm for initial8mm and every2mm to80mm. Sampled "
                    "validation, not a continuous clearance proof. Head, joint, neck, roof and "
                    "bridge removed; other cover, cradles, fixed hardware and plug reservation "
                    "retained. Physical release and cables remain U."
                ),
            )
        )
    (OUT / "cover-sweeps.json").write_text(json.dumps(results, indent=2) + "\n")
    return results


def _check_admission(parts, hardware, record):
    # Rear insertion sweep through the open casing, with rear/right/roof removed.
    # A continuous swept prism is conservative for straight translation.
    for p in hardware:
        if p["kind"] != "hardware":
            continue
        sx, sy, sz = p["size"]
        x, y, z = p["center"]
        lift = 0  # Rear-open speaker guide permits nominal-height slide below audio beams.
        sweep = B((sx, 200 + sy, sz), (x, y + 100, z + lift))
        settling = B((sx, sy, sz + lift), (x, y, z + lift / 2))
        cradle_name = {
            "One speaker": "speaker-cradle",
            "Jetson": "jetson-cradle",
            "USB audio case": "audio-cradle",
        }.get(p["name"])
        admission = parts["body-front"]
        if cradle_name:
            admission = admission.fuse(parts[cradle_name])
        overlap = sweep.intersect(admission).Volume() + settling.intersect(admission).Volume()
        record(
            p["name"] + " rear insertion",
            overlap < 1e-5,
            (
                f"Continuous 200 mm rear sweep and {lift} mm lowering versus shell "
                f"and matching cradle: {overlap:.6f} mm³. Install speaker/audio "
                f"before Jetson; remove loose cradles first."
            ),
        )
    # Source camera inserts through the open rear head, visor removed.
    # Separate convex hulls of full source parts would fill the lens cone unnecessarily;
    # use the entire camera bounding prism as a deliberately conservative admission test.
    swept = B((37, 131.6, 37), (layout.CAMERA_X, 61, layout.CAMERA_Z)).fuse(
        cylinder(13, 27.5, (layout.CAMERA_X, -32.3, layout.CAMERA_Z), (0, 1, 0))
    )
    volume = swept.intersect(parts["head-front"].fuse(parts["camera-cradle"])).Volume()
    record(
        "Camera rear insertion", volume < 1e-5, f"Continuous bounding-prism sweep {volume:.6f} mm³."
    )
    frame = parts["camera-cradle"]
    fb = frame.BoundingBox()
    frame_sweep = B(
        (fb.xlen, fb.ylen + 120, fb.zlen),
        ((fb.xmin + fb.xmax) / 2, (fb.ymin + fb.ymax) / 2 + 60, (fb.zmin + fb.zmax) / 2 + 1.5),
    )
    frame_overlap = frame_sweep.intersect(parts["head-front"]).Volume()
    lowering_overlap = max(
        frame.translate((0, 0, float(z))).intersect(parts["head-front"]).Volume()
        for z in np.linspace(0, 1.5, 16)
    )
    record(
        "Camera cradle rear admission",
        frame_overlap < 1e-5 and lowering_overlap < 1e-5,
        (
            f"Continuous prism at1.5 mm lift {frame_overlap:.6f} mm³; lowering "
            f"samples every0.1 mm {lowering_overlap:.6f} mm³."
        ),
    )
    # The bridge slides in horizontally at its final height after the joint is seated.
    bridge = parts["roof-bridge"]
    bands = [bridge.intersect(B((80, 100, h), (0, 30, z))) for h, z in ((14, 147), (8, 158))]
    sweeps = []
    for band in bands:
        bb = band.BoundingBox()
        sweeps.append(
            B(
                (bb.xlen, bb.ylen + 120, bb.zlen),
                ((bb.xmin + bb.xmax) / 2, (bb.ymin + bb.ymax) / 2 + 60, (bb.zmin + bb.zmax) / 2),
            )
        )
    bridge_sweep = fuse(sweeps)
    bridge_overlap = bridge_sweep.intersect(parts["body-roof"]).Volume()
    record(
        "Roof bridge horizontal admission",
        bridge_overlap < 1e-5,
        (
            f"Continuous rear admission prism versus roof {bridge_overlap:.6f} "
            f"mm³; keeper and pins removed."
        ),
    )


def check_joint_admission(parts, joint_parts):
    """Check rear sliding at 5.2 mm lift, then lowering onto the two roof posts.
    Pass preassembled joint parts with roof and head closure keys removed.
    """
    roof = parts["body-roof"]
    core = fuse(list(joint_parts.values()))
    slide_peak = max(
        core.translate((0, float(y), 5.2)).intersect(roof).Volume()
        for y in np.linspace(0, 120, 241)
    )
    lowering_peak = max(
        core.translate((0, 0, float(z))).intersect(roof).Volume() for z in np.linspace(0, 5.2, 53)
    )
    bridge = parts["roof-bridge"]
    bridge_peak = max(
        bridge.translate((0, float(y), 0)).intersect(core).Volume()
        for y in np.linspace(0, 120, 241)
    )
    return [
        dict(
            name="Joint rear admission / roof",
            passed=slide_peak < 1e-5,
            detail=f"Peak {slide_peak:.6f} mm³ at0.5 mm rear samples, joint lifted5.2 mm.",
        ),
        dict(
            name="Joint lowering / roof",
            passed=lowering_peak < 1e-5,
            detail=f"Peak {lowering_peak:.6f} mm³ at0.1 mm lowering samples; roof keys removed.",
        ),
        dict(
            name="Roof bridge admission / seated joint",
            passed=bridge_peak < 1e-5,
            detail=f"Peak {bridge_peak:.6f} mm³ at0.5 mm rear samples; bridge pins removed.",
        ),
    ]


def check_neck_admission(parts, joint_parts):
    """Check the complete vertical cover path with the head casing removed."""
    sweep = layout.ring(54, 50.8, 77, 160)
    for x in (-26.2, 26.2):
        sweep = sweep.fuse(B((1.2, 3, 63), (x, 0, 189)))
    fixed = cq.Compound.makeCompound([parts["body-roof"], *joint_parts.values()])
    overlap = sweep.intersect(fixed).Volume()
    return dict(
        name="Neck cover continuous vertical admission",
        passed=overlap < 1e-5,
        detail=(
            f"60 mm complete vertical sweep with head casing removed; obstruction "
            f"{overlap:.6g} mm³."
        ),
    )


def render(parts):
    fig = plt.figure(figsize=(13, 7.5), facecolor="#f4f2ec")
    for pos, azim, title in [(121, -65, "Front / right"), (122, 115, "Rear / left")]:
        ax = fig.add_subplot(pos, projection="3d", facecolor="#f4f2ec")
        all_vertices = []
        all_colors = []
        for name, shape in parts.items():
            m = mesh(shape)
            vertices = m.vertices[m.faces]
            base = np.array(
                matplotlib.colors.to_rgb(
                    BLACK if name in ("head-visor", "speaker-grille", "neck-cover") else CREAM
                )
            )
            light = np.array([0.3, -0.7, 0.8])
            light /= np.linalg.norm(light)
            brightness = 0.55 + 0.45 * np.abs(m.face_normals @ light)
            colors = np.clip(brightness[:, None] * base, 0, 1)
            all_vertices.extend(vertices)
            all_colors.extend(colors)
        ax.add_collection3d(
            Poly3DCollection(
                all_vertices,
                facecolors=all_colors,
                linewidths=0,
                edgecolors="none",
                rasterized=True,
            )
        )
        ax.set_xlim(-85, 85)
        ax.set_ylim(-70, 70)
        ax.set_zlim(0, 240)
        ax.set_box_aspect((170, 140, 240))
        ax.view_init(elev=16, azim=azim)
        ax.set_axis_off()
        ax.set_title(title, fontsize=12)
    fig.suptitle("Concept A | casing geometry | 148.6 × 127.2 × 236 mm", fontsize=16)
    fig.text(
        0.5,
        0.04,
        (
            "White shell, inset black visor, removable panels. Joint exported "
            "separately. Physical fit remains unverified."
        ),
        ha="center",
        fontsize=10,
    )
    fig.subplots_adjust(left=0, right=1, bottom=0.08, top=0.92, wspace=-0.1)
    fig.savefig(OUT / "casing-exterior.png", dpi=180)
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    parts = build_parts()
    coupons = gauges()
    rows = check(parts)
    report = dict(
        status="MECHANICAL PROTOTYPE; physical fit U",
        checks=rows,
        geometry_passed=all(r["passed"] for r in rows),
        contacts=(
            "Only zero-volume printed boundary contacts. No electronics contact is authorized."
        ),
        unknowns=[
            "Part contact lands and retention",
            "Port datums and installed connector shapes",
            "Camera cable movement",
            "Cooling and acoustics",
            "PLA creep",
            "Bambu Studio slicing",
        ],
    )
    (OUT / "checks.json").write_text(json.dumps(report, indent=2) + "\n")
    failures = [r for r in rows if not r["passed"]]
    assert not failures, failures
    export_parts(parts, coupons)


def export_parts(parts, coupons):
    """Export already validated geometry; main performs the full CAD checks first."""
    manifest = []
    support = {
        "speaker-grille": (
            "Rear down on two flat tongue tips. Support the raised curved panel locally; "
            "inspect holes and support removal."
        ),
        "neck-cover": (
            "Complete upper ring face on bed, tabs upward. No major supports; inspect tab roots."
        ),
        "body-front": (
            "Front exterior face down. Support the short raised receiver "
            "blocks and roof catches locally."
        ),
        "body-rear": "Rear exterior face down. Support the raised roof catch beams locally.",
        "body-right": (
            "Right exterior face down. No major supports; inspect small receiver bridges."
        ),
        "body-roof": (
            "Flat underside on bed, posts up. The 1.8 mm post slot roof is a "
            "short bridge; inspect or support locally."
        ),
        "head-front": (
            "Front exterior face down. Support local rear-cover socket "
            "bridges. Print the visor separately."
        ),
        "head-rear": "Rear exterior face down. No major supports; inspect four small tongues.",
        "camera-cradle": "Front frame face down. No major supports.",
        "roof-bridge": "Flat underside on bed. Inspect the short pin-slot bridges.",
        "roof-bridge-pin--1": "Outer head face on bed, pin upright. No major supports.",
        "roof-bridge-pin-1": "Outer head face on bed, pin upright. No major supports.",
        "roof-bridge-keeper--1": (
            "Broad face on bed. Verify the small flex barbs with PLA before use."
        ),
        "roof-bridge-keeper-1": (
            "Broad face on bed. Verify the small flex barbs with PLA before use."
        ),
        "head-visor": (
            "Black exterior face down. Decorative recess needs a local 0.3 mm "
            "support patch or remove it for a plain visor."
        ),
    }
    for name, shape in (parts | coupons).items():
        printable = print_transform(name, shape)
        layout.export_3mf(printable, OUT / (name + ".3mf"))
        loaded = trimesh.load(OUT / (name + ".3mf"), force="scene")
        meshes = list(loaded.geometry.values())
        assert meshes and all(m.is_watertight and m.is_volume for m in meshes)
        # CAD extrema independent of cached triangulation on curved loft surfaces.
        bounds = Bnd_Box()
        BRepBndLib.AddOptimal_s(printable.wrapped, bounds, False, False)
        low_x, low_y, low_z, high_x, high_y, high_z = bounds.Get()
        dims = [high_x - low_x, high_y - low_y, high_z - low_z]
        assert max(dims[:2]) <= 256 and abs(loaded.bounds[0, 2]) < 1e-5, (
            name,
            dims,
            loaded.bounds[0, 2],
        )
        assert np.max(np.abs(loaded.bounds[1] - loaded.bounds[0] - dims)) < 0.1, (
            name,
            dims,
            loaded.extents.tolist(),
        )
        bottom_area = sum(
            float(m.area_faces[np.all(np.abs(m.vertices[m.faces][:, :, 2]) < 1e-5, axis=1)].sum())
            for m in meshes
        )
        assert bottom_area > 10, (name, bottom_area)
        manifest.append(
            dict(
                name=name,
                base_contact_area_mm2=round(bottom_area, 2),
                file=name + ".3mf",
                color=BLACK if name in ("head-visor", "speaker-grille", "neck-cover") else CREAM,
                print_size_mm=[round(v, 3) for v in dims],
                cad_volume_mm3=round(shape.Volume(), 3),
                support=support.get(name, "Flat tray/coupon base down. No major supports."),
                mesh_closed=True,
                raw_index_edges_twice=True,
                bed="P1S 256×256 mm",
                status="Export checked; slice and physical coupon checks pending",
            )
        )
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    assembly = cq.Assembly(name="Concept_A_casing_printed_parts")
    for name, shape in parts.items():
        assembly.add(
            shape,
            name=name,
            color=layout.color(
                BLACK if name in ("head-visor", "speaker-grille", "neck-cover") else CREAM
            ),
        )
    assembly.export(str(OUT / "casing-printed.step"))
    for p in layout.hardware():
        assembly.add(
            p["shape"],
            name=p["name"].replace(" ", "_").replace("/", "_"),
            color=cq.Color(0.3, 0.65, 0.55, 0.25),
        )
    assembly.add(layout.camera(), name="Full_source_camera", color=cq.Color(0.25, 0.6, 0.4, 0.35))
    assembly.export(str(OUT / "casing-hardware-ghost.step"))
    render(parts)
    print((f"{len(manifest)} closed, millimeter 3MF parts exported."))


if __name__ == "__main__":
    main()
