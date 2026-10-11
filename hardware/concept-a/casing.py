"""Build the removable Concept A casing and print gauges from the source envelopes.
Run with build/hardware-layout/venv/bin/python hardware/concept-a/casing.py.
"""

from __future__ import annotations
import itertools
import json
from pathlib import Path
import cadquery as cq
import numpy as np
import trimesh
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import layout

OUT = Path(__file__).resolve().parent / "output" / "casing"
CREAM = "#e7dfcf"
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
    outer = rounded((136, 112, 156.8), (0, 0, 78.4), 2)
    front = outer.cut(B((133.6, 109.6, 160), (1.2, 1.2, 82.4)))
    # The front shell contains the front, left side, and floor only.
    front = front.cut(B((150, 10, 170), (0, 58.6, 85)))
    front = front.cut(B((10, 120, 170), (70.6, 0, 85)))
    for x in range(-46, 47, 4):
        for z in (18, 26, 34, 42):
            front = front.cut(B((2.2, 5, 5), (x, -54.8, z)))
    for x in (-46, -8):
        front = front.cut(cylinder(1.7, 5, (x, -57, 85), (0, 1, 0)))
    for y in range(-2, 27, 6):
        for z in range(21, 107, 10):
            front = front.cut(B((5, 3, 6), (-66.8, y, z)))
    rear = B((130.8, 2.4, 154), (0, 54.8, 79.6))
    rear = rear.cut(B((10, 5, 12), (24, 54.8, 153.6)))
    for x in range(-48, 35, 6):
        for z in range(21, 108, 10):
            rear = rear.cut(B((3, 5, 6), (x, 54.8, z)))
    right = B((2.4, 106.8, 154), (66.8, 0, 79.6))
    # A large edge-open service exit accepts the separate power-exit trial later.
    right = right.cut(B((6, 24, 116), (66.8, 18, 60.4)))
    return front, rear, right


def _panel_catches(front, rear, right):
    # Rear panel tongues and accessible straight friction sockets.
    for x in (-62.9, 62.9):
        for z in (18, 143):
            tongue = B((2, 5, 3), (x, 51.1, z))
            rear = rear.fuse(tongue)
            socket = receiver((x, 50.9, z), (5.4, 5, 8), (2.2, 6, 3.2))
            if x < 0:
                front = front.fuse(socket)
            else:
                right = right.fuse(socket)
    # Right panel insertion is along X. Remove it before inserting connectors.
    for y in (-45, 45):
        for z in (6.4, 152.8):
            right = right.fuse(B((3.2, 3, 2), (64, y, z)))
            socket = receiver((63.9, y, z), (3.4, 7, 8), (4, 3.2, 2.2))
            if z < 20:
                # Pedestal reaches the floor without entering a hardware envelope.
                socket = socket.fuse(B((3.4, 7, 0.4), (63.9, y, 2.6)))
                front = front.fuse(socket)
            else:
                # This socket is carried by a front/rear wall beam.
                beam_y = -49.3 if y < 0 else 49.3
                beam = B((3.4, 8.6, 8), (63.9, beam_y, z))
                beam = beam.cut(B((4, 3.2, 2.2), (63.9, y, z)))
                if y < 0:
                    front = front.fuse(socket, beam)
                else:
                    rear = rear.fuse(socket, beam)
    return front, rear, right


def _roof(front, rear):
    roof = B((136, 112, 3.2), (0, 0, 158.4))
    roof = roof.cut(cylinder(16.2, 5, (0, 0, 156)))
    roof = roof.cut(B((10, 8, 5), (24, 55, 158.4)))
    # The roof prints flat. Perimeter posts rise from the casing into through-holes.
    for x in (-59, 59):
        for y in (-49.6, 49.6):
            roof = roof.cut(B((2.2, 3.2, 5), (x, y, 158.4)))
            post = B((2, 3, 3), (x, y, 158.3))
            support = B((5, 8, 6), (x, y, 153.8))
            if y < 0:
                front = front.fuse(post, support)
            else:
                rear = rear.fuse(post, support)
    for x in (-21, 21):
        post = B((3, 4, 5), (x, 0, 162.5))
        post = post.cut(B((1.8, 6, 1.8), (x, 0, 163.4)))
        roof = roof.fuse(post)
    return front, rear, roof


def _roof_bridge(roof):
    # A rear edge-open channel admits the joint with its gear below the roof.
    bridge = B((32, 56, 3.2), (0, 28, 158.4)).cut(cylinder(16.2, 5, (0, 0, 156)))
    roof = roof.cut(B((32.4, 58, 5), (0, 29, 158.4)))
    bridge_parts = {"roof-bridge": bridge}
    for sign in (-1, 1):
        roof = roof.cut(B((49.6, 2.2, 2.2), (sign * 40.9, 40, 158.4)))
        roof = roof.cut(B((3, 5.2, 5), (sign * 67, 40, 158.4)))
        bridge = bridge.cut(B((4.2, 2.2, 2.2), (sign * 14, 40, 158.4)))
        bridge = bridge.cut(B((1.8, 1, 5), (sign * 13.3, 40, 158.4)))
        pin = B((53.6, 2, 2), (sign * 38.8, 40, 158.4))
        pin = pin.fuse(B((2, 5, 3.2), (sign * 66.6, 40, 158.4)))
        pin = pin.cut(B((1.8, 1, 5), (sign * 13.3, 40, 158.4)))
        keeper = B((1.5, 0.8, 5.6), (sign * 13.3, 40, 157.6))
        keeper = keeper.fuse(B((2.8, 0.8, 0.8), (sign * 13.3, 40, 160.4)))
        # Two narrow barbs flex through the keeper slit and capture the underside.
        for side in (-1, 1):
            poly = [
                (sign * 13.3 + side * 0.75, 155.8),
                (sign * 13.3 + side * 1.1, 156.3),
                (sign * 13.3 + side * 0.75, 156.6),
            ]
            barb = (
                cq.Workplane("XZ").polyline(poly).close().extrude(0.8).translate((0, 40.4, 0)).val()
            )
            keeper = keeper.fuse(barb)
        bridge_parts[f"roof-bridge-pin-{sign}"] = pin.clean()
        bridge_parts[f"roof-bridge-keeper-{sign}"] = keeper.clean()
    bridge_parts["roof-bridge"] = bridge.clean()
    return roof, bridge_parts


def _head_shells():
    # Head has a full rectangular cavity; small outside radii preserve corner clearance.
    head = rounded((100, 72, 50), (0, 0, 205), 2.8)
    head = head.cut(B((95.2, 69.6, 45.2), (0, 1.2, 205)))
    head = head.cut(B((110, 8, 60), (0, 37.6, 205)))
    # Visor is inset in the front face rather than increasing the depth envelope.
    head = head.cut(B((88.4, 5, 38.4), (0, -35.2, 205)))
    head = head.cut(cylinder(7.6, 5, (0, 0, 179)))
    for x in (-18, 18):
        head = head.cut(B((3.4, 4.4, 5), (x, 0, 181.2)))
    # External cable entry: rear floor edge remains open when rear cover is removed.
    head = head.cut(B((9, 20, 5), (24, 28, 181.2)))
    visor = B((88, 2, 38), (0, -35, 205))
    visor = visor.cut(cylinder(17, 5, (-24, -38, 205), (0, 1, 0)))
    # Decorative second eye is a shallow recessed circle in the matte black panel.
    visor = visor.cut(cylinder(11, 0.6, (22, -36.01, 205), (0, 1, 0)))
    for x in (-45, 45):
        for z in (190, 220):
            tongue = B((4, 4, 2), (x - (1 if x > 0 else -1), -33, z))
            visor = visor.fuse(tongue)
            head = head.cut(B((4.2, 4.2, 2.2), (x - (1 if x > 0 else -1), -33, z)))
    head_rear = B((95.2, 2.4, 45.2), (0, 34.8, 205))
    for x in (-46.7, 46.7):
        for z in (188, 222):
            head_rear = head_rear.fuse(B((1, 4, 2), (x, 31.6, z)))
            socket = receiver((x, 31.6, z), (1.8, 4, 4), (1.2, 5, 2.2))
            head = head.fuse(socket)
    # Small rear relief prevents forcing a cable through a closed aperture.
    head_rear = head_rear.cut(B((10, 5, 5), (24, 34.8, 184.4)))
    return head, head_rear, visor


def _floor_cradles(front):
    mounts = {}
    # Floor trays are captured on removable friction posts. All contact gaps are 0.4 mm.
    for label, sx, sy, cx, cy, bottom in [
        ("speaker-cradle", 100, 21, 0, -39, 8.5),
        ("jetson-cradle", 90.5, 35, -7.5, 10, 10),
    ]:
        top = bottom - 0.4
        tray = B((sx + 1, sy + 1, 2.4), (cx, cy, top - 1.2))
        tray = tray.fuse(B((1.2, sy + 3.2, 5), (cx - sx / 2 - 1, cy, top + 2.5)))
        tray = tray.fuse(B((sx + 3.2, 1.2, 5), (cx, cy - sy / 2 - 1, top + 2.5)))
        if label == "speaker-cradle":
            tray = tray.fuse(B((1.2, sy + 3.2, 5), (cx + sx / 2 + 1, cy, top + 2.5)))
            tray = tray.fuse(B((sx + 3.2, 1.2, 5), (cx, cy + sy / 2 + 1, top + 2.5)))
        foot_x = [cx - sx / 2 + 8, cx + sx / 2 - 8]
        foot_y = [cy] if label == "speaker-cradle" else [cy - sy / 2 + 5, cy + sy / 2 - 5]
        for px in foot_x:
            for py in foot_y:
                height = top - 2.4 - 2.4
                foot = B((6, 6, height), (px, py, 2.4 + height / 2))
                tray = tray.cut(B((2.2, 3.2, 2.6), (px, py, top - 1.2)))
                front = front.fuse(foot, B((2, 3, 2.2), (px, py, top - 1.3)))
        if label == "jetson-cradle":
            tray = tray.cut(B((10, 100, 30), (42.35, cy, 10)))
        mounts[label] = tray.clean()
    return front, mounts


def _audio_cradle(front):
    # Audio housing shelf fits below its case, with two releasable support posts.
    audio = B((54.8, 22.8, 2.4), (-27, -42.2, 71.65))
    audio = audio.fuse(B((1.2, 18, 5), (-54.5, -40, 75.35)), B((54.8, 1.2, 5), (-27, -48.3, 75.35)))
    for px in (-50, -8):
        front = front.fuse(B((6, 3.2, 6), (px, -52, 67.45)), B((2, 2, 2), (px, -52, 71.45)))
        audio = audio.cut(B((2.2, 2.2, 2.2), (px, -52, 71.45)))
    audio = audio.cut(B((4, 30, 10), (1.6, -40, 79)))
    return front, audio.clean()


def _camera_cradle(head):
    # Camera edge gauge surrounds the PCB while leaving optics and connectors open.
    frame = B((41.8, 3.2, 41.8), (-24, -4, 205)).cut(B((37.8, 5, 37.8), (-24, -4, 205)))
    for px in (-43.9, -10):
        foot = (
            B((2, 3.2, 1.7), (px, -4, 183.25)) if px < -20 else B((8, 3.2, 1.7), (-7.1, -4, 183.25))
        )
        frame = frame.fuse(foot).cut(B((1, 1.8, 2.4), (px, -4, 183.6)))
        head = head.fuse(B((0.8, 1.6, 1.4), (px, -4, 183.1)))
    frame = frame.cut(B((3, 5, 0.6), (-18, -4, 184.35)))
    return head, frame.clean()


def build_parts():
    """Assembly coordinates match layout.py. Panel fits have 0.1 mm per side."""
    front, rear, right = _body_panels()
    front, rear, right = _panel_catches(front, rear, right)
    front, rear, roof = _roof(front, rear)
    roof, bridge_parts = _roof_bridge(roof)
    head, head_rear, visor = _head_shells()
    front, mounts = _floor_cradles(front)
    front, mounts["audio-cradle"] = _audio_cradle(front)
    head, mounts["camera-cradle"] = _camera_cradle(head)
    return (
        {
            "body-front": front.clean(),
            "body-rear": rear.clean(),
            "body-right": right.clean(),
            "body-roof": roof.clean(),
            "head-front": head.clean(),
            "head-rear": head_rear.clean(),
            "head-visor": visor.clean(),
        }
        | mounts
        | bridge_parts
    )


def metadata():
    return {
        name: dict(
            kind="casing",
            color=BLACK if name == "head-visor" else CREAM,
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
    if name in ("body-front", "head-front", "head-visor", "camera-cradle"):
        shape = shape.rotate((0, 0, 0), (1, 0, 0), 90)
    elif name in ("body-rear", "head-rear"):
        shape = shape.rotate((0, 0, 0), (1, 0, 0), -90)
    elif name.startswith("roof-bridge-pin-"):
        sign = int(name.rsplit("-", 1)[1]) if "--" not in name else -1
        shape = shape.rotate((0, 0, 0), (0, 1, 0), 90 * sign)
    elif name.startswith("roof-bridge-keeper-"):
        shape = shape.rotate((0, 0, 0), (1, 0, 0), 90)
    elif name == "body-right":
        shape = shape.rotate((0, 0, 0), (0, 1, 0), 90)
    vertices, _ = shape.tessellate(0.05, 0.1)
    minima = np.min([v.toTuple() for v in vertices], axis=0)
    return shape.translate(tuple(-minima))


def mesh(shape):
    vertices, faces = shape.tessellate(0.16, 0.25)
    return trimesh.Trimesh(vertices=[v.toTuple() for v in vertices], faces=faces)


def check(parts):
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
        recess = 36 - (4.8 + focus)
        required = 8.5 + recess * np.tan(np.radians(50))
        record(
            f"Lens opening / focus {focus}",
            required <= 17,
            f"Ø34 aperture; ideal 100° diagonal cone radius {required:.3f} mm; actual framing U.",
        )
    record(
        "Roof flange footprint",
        abs(parts["body-roof"].intersect(cylinder(25, 5, (0, 0, 160))).Volume() - 94.08) < 1e-5,
        "Only the two specified 3×4×5 mm posts enter the Ø50 flange footprint above Z160.",
    )
    return rows


def _check_admission(parts, hardware, record):
    # Rear insertion sweep through the open casing, with rear/right/roof removed.
    # A continuous swept prism is conservative for straight translation.
    for p in hardware:
        if p["kind"] != "hardware":
            continue
        sx, sy, sz = p["size"]
        x, y, z = p["center"]
        lift = 6 if p["name"] == "One speaker" else 0
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
    camera = layout.camera()
    # Separate convex hulls of full source parts would fill the lens cone unnecessarily;
    # use the entire camera bounding prism as a deliberately conservative admission test.
    bb = camera.BoundingBox()
    swept = B(
        (bb.xlen, bb.ylen + 120, bb.zlen),
        ((bb.xmin + bb.xmax) / 2, (bb.ymin + bb.ymax) / 2 + 60, (bb.zmin + bb.zmax) / 2),
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
    bb = bridge.BoundingBox()
    bridge_sweep = B(
        (bb.xlen, bb.ylen + 120, bb.zlen),
        ((bb.xmin + bb.xmax) / 2, (bb.ymin + bb.ymax) / 2 + 60, (bb.zmin + bb.zmax) / 2),
    )
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


def render(parts):
    fig = plt.figure(figsize=(13, 7.5), facecolor="#f4f2ec")
    for pos, azim, title in [(121, -65, "Front / right"), (122, 115, "Rear / left")]:
        ax = fig.add_subplot(pos, projection="3d", facecolor="#f4f2ec")
        all_vertices = []
        all_colors = []
        for name, shape in parts.items():
            m = mesh(shape)
            vertices = m.vertices[m.faces]
            base = np.array(matplotlib.colors.to_rgb(BLACK if name == "head-visor" else CREAM))
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
    fig.suptitle("Concept A | casing geometry | 136 × 112 × 230 mm", fontsize=16)
    fig.text(
        0.5,
        0.04,
        (
            "Cream shell, inset black visor, removable panels. Joint exported "
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
    manifest = []
    support = {
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
            "Black exterior face down. Decorative recess needs a local 0.6 mm "
            "support patch or remove it for a plain visor."
        ),
    }
    for name, shape in (parts | coupons).items():
        printable = print_transform(name, shape)
        layout.export_3mf(printable, OUT / (name + ".3mf"))
        loaded = trimesh.load(OUT / (name + ".3mf"), force="scene")
        meshes = list(loaded.geometry.values())
        assert meshes and all(m.is_watertight and m.is_volume for m in meshes)
        bb = printable.BoundingBox()
        dims = [bb.xlen, bb.ylen, bb.zlen]
        assert max(dims[:2]) <= 256 and abs(loaded.bounds[0, 2]) < 1e-5, (
            name,
            dims,
            loaded.bounds[0, 2],
        )
        assert np.max(np.abs(loaded.bounds[1] - loaded.bounds[0] - dims)) < 0.1
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
                color=BLACK if name == "head-visor" else CREAM,
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
        assembly.add(shape, name=name, color=layout.color(BLACK if name == "head-visor" else CREAM))
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
    print(
        (
            f"{len(rows)} casing geometry checks pass; {len(manifest)} closed, "
            f"millimeter 3MF parts exported."
        )
    )


if __name__ == "__main__":
    main()
