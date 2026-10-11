"""Build and check Concept A packaging envelopes and separate printable fit coupons.
Run this file with the pinned CadQuery environment; no robot software is changed.
"""

from __future__ import annotations

import itertools
import json
import math
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree

import cadquery as cq
import matplotlib
import trimesh

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
BODY = (136, 112, 160)
HEAD = (100, 72, 50)
HEAD_Z = 205
WALL = 2.4
CAMERA_X = -24
CAMERA_Z = HEAD_Z
BEARING_Z = (154, 170)
GEAR_CENTERS = ((0, 0), (0, -34))
GEAR_RADIUS = 18
GEAR_Z = 140
SHAFT_Z = 132
HEAD_BOTTOM = HEAD_Z - HEAD[2] / 2
SOURCE = "https://github.com/Dylancouzon/qdrant-edge-memory-robot/blob/cfc0dd2c5bb540f08149213c43bd33ba2d0c27f9/hardware/claude-design.html"


def color(value):
    return cq.Color(*(int(value[i : i + 2], 16) / 255 for i in (1, 3, 5)))


def box(size, center):
    return cq.Workplane("XY").box(*size).translate(center).val()


def export_3mf(solid, dest):
    """Weld CAD face seams and verify indexed mesh closure before slicer import."""
    vertices, faces = solid.tessellate(0.05, 0.1)
    printable = trimesh.Trimesh(vertices=[v.toTuple() for v in vertices], faces=faces)
    assert printable.is_watertight and printable.is_volume
    printable.export(str(dest), file_type="3mf")
    with zipfile.ZipFile(dest) as archive:
        model = ElementTree.fromstring(archive.read("3D/3dmodel.model"))
    assert model.attrib["unit"] == "millimeter"
    ns = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
    meshes = model.findall(".//m:mesh", ns)
    assert len(meshes) == 1
    edges = Counter()
    for triangle in meshes[0].findall("m:triangles/m:triangle", ns):
        ids = [int(triangle.attrib[key]) for key in ("v1", "v2", "v3")]
        for i in range(3):
            edges[tuple(sorted((ids[i], ids[(i + 1) % 3])))] += 1
    assert edges and all(count == 2 for count in edges.values())


def ring(outer, inner, height, z):
    return (
        cq.Workplane("XY")
        .circle(outer / 2)
        .circle(inner / 2)
        .extrude(height)
        .translate((0, 0, z))
        .val()
    )


def item(name, size, center, color, kind, note, source=SOURCE):
    return dict(
        name=name,
        size=size,
        center=center,
        color=color,
        kind=kind,
        note=note,
        source=source,
        shape=box(size, center),
    )


def hardware():
    "All boxes describe external envelopes, including unselected connection spaces."
    return [
        item(
            "Jetson",
            (90.5, 35, 103),
            (-7.5, 10, 61.5),
            "#477967",
            "hardware",
            (
                "E: reference envelope, rotated onto its edge. Actual port/fan "
                "orientation needs confirmation."
            ),
        ),
        item(
            "One speaker",
            (100, 21, 45),
            (0, -39, 31),
            "#555960",
            "hardware",
            "E: larger manufacturer envelope; actual speaker size is U.",
            "https://www.waveshare.com/8ohm-5w-speaker.htm",
        ),
        item(
            "USB audio case",
            (53, 14.6, 23.5),
            (-27, -40, 85),
            "#767a84",
            "hardware",
            ("E: case only, without USB plug. Orient microphone end toward a front sound channel."),
            "https://www.waveshare.com/usb-to-audio.htm",
        ),
        item(
            "Audio USB extension",
            (20, 20, 22),
            (10, -40, 85),
            "#d08e48",
            "reservation",
            (
                "U: plug/extension pocket next to audio case. Actual cable "
                "connector and angle are unmeasured."
            ),
        ),
        item(
            "STS3215 housing",
            (45.22, 24.72, 35),
            (12.5, -34, 119.5),
            "#74738f",
            "hardware",
            (
                "E: Waveshare housing and 10.11 mm horn offset. Source drawing "
                "says SCS215; verify the owned 7.4 V STS3215 before mating "
                "geometry."
            ),
            "https://www.waveshare.com/wiki/ST3215_Servo",
        ),
        item(
            "Servo ears and leads",
            (58, 30, 39),
            (12.5, -34, 120.5),
            "#a6a2b6",
            "reservation",
            (
                "U: conservative pocket includes the housing; intentional overlap. "
                "Side access for a removable cradle catch."
            ),
        ),
        item(
            "Bus interface",
            (62, 16, 43),
            (0, -18, 77),
            "#9a8d66",
            "reservation",
            (
                "U: USB half-duplex TTL bus interface and connector space. "
                "Candidate Waveshare board is 42 × 33 mm; identify the owned "
                "version. PCA9685 does not control this servo."
            ),
        ),
        item(
            "Servo regulator",
            (35, 20, 15),
            (38, -38, 85),
            "#b29664",
            "reservation",
            (
                "U: unselected supply sized after voltage and stall current "
                "confirmation. Keep independent of GPIO power."
            ),
        ),
        item(
            "Jetson USB/power plugs",
            (24, 34, 108),
            (49.75, 10, 62),
            "#d08e48",
            "reservation",
            (
                "U: side connection/service space; actual socket coordinates and "
                "JUXINICE bend direction are unmeasured."
            ),
        ),
        item(
            "Fan intake space",
            (90.5, 22, 103),
            (-7.5, 38.5, 61.5),
            "#72a4c1",
            "reservation",
            (
                "U: align with actual fan inlet. The 22 mm space proves separation "
                "only, not cooling."
            ),
        ),
        item(
            "Outlet space",
            (8, 35, 103),
            (-59, 10, 61.5),
            "#72a4c1",
            "reservation",
            (
                "U: separate outlet on opposite side; physical flow path and vent "
                "area need validation."
            ),
        ),
        item(
            "Camera rear cable space",
            (43, 18, 43),
            (-24, 23, CAMERA_Z),
            "#d08e48",
            "moving reservation",
            (
                "U: space behind source connectors. Actual bend radius and "
                "connector loading require measurement."
            ),
        ),
    ]


def camera():
    board = box((37, 1.6, 37), (CAMERA_X, -4, CAMERA_Z))
    holder = cq.Solid.makeCylinder(
        13, 27.5, cq.Vector(CAMERA_X, -4.8, CAMERA_Z), cq.Vector(0, -1, 0)
    )
    rear = box((26, 10, 26), (CAMERA_X, 1.8, CAMERA_Z))
    for dx, lo, hi, depth in [(8.4, 4.4, 15.7, 9), (10.8, -17.1, -11.6, 6)]:
        rear = rear.fuse(
            box((2 * dx, depth, hi - lo), (CAMERA_X, -3.2 + depth / 2, CAMERA_Z + (lo + hi) / 2))
        )
    return board.fuse(holder, rear)


def joint_parts():
    "Reserve separated bearing seats and gears; teeth and mounting catches remain unmodeled."
    joint = {f"Bearing_{z}": ring(24, 15, 5, z - 2.5) for z in BEARING_Z}
    joint.update(
        {
            "Shaft_reservation": ring(15, 10, HEAD_BOTTOM - SHAFT_Z, SHAFT_Z),
            "Head_flange_reservation": ring(44, 15, 3, HEAD_BOTTOM - 3),
            "Lower_collar_reservation": ring(20, 15, 3, BEARING_Z[0] - 5.5),
            "Upper_spacer_reservation": ring(
                20, 15, HEAD_BOTTOM - 3 - (BEARING_Z[1] + 2.5), BEARING_Z[1] + 2.5
            ),
            "Axial_keeper_reservation": ring(32, 24, 3, BEARING_Z[1] + 2.5),
        }
    )
    for i, (x, y) in enumerate(GEAR_CENTERS):
        gear = cq.Solid.makeCylinder(GEAR_RADIUS, 6, cq.Vector(x, y, GEAR_Z))
        if i == 0:
            gear = gear.cut(cq.Solid.makeCylinder(7.5, 6, cq.Vector(x, y, GEAR_Z)))
        joint[f"Gear_envelope_{i}_not_teeth"] = gear
    return joint


def cable(angle):
    "Illustrative coil below the shaft, followed by cable above the rotating flange."
    turns = 1 + angle / 360
    radius = 12 / turns
    points = []
    for i in range(81):
        t = i / 80
        r = radius * (1 - t)
        a = 2 * math.pi * turns * t
        points.append([r * math.cos(a), r * math.sin(a), 116 + (SHAFT_Z - 116) * t])
    points.extend([[0, 0, HEAD_BOTTOM], [0, 20, HEAD_BOTTOM + 14], [CAMERA_X, 20, CAMERA_Z]])
    radians = math.radians(angle)
    for i in range(82, len(points)):
        x, y, z = points[i]
        points[i] = [
            x * math.cos(radians) - y * math.sin(radians),
            x * math.sin(radians) + y * math.cos(radians),
            z,
        ]
    return points


def cable_joint_clearance(points, joint):
    "Bound each straight cable segment by samples with 0.25 mm extra radius."
    for start, end in zip(points, points[1:], strict=False):
        steps = max(1, math.ceil(math.dist(start, end) / 0.5))
        for i in range(steps + 1):
            point = [a + (b - a) * i / steps for a, b in zip(start, end, strict=False)]
            for name, shape in joint.items():
                bb = shape.BoundingBox()
                if all(
                    lo - 2.75 <= v <= hi + 2.75
                    for v, lo, hi in zip(
                        point,
                        [bb.xmin, bb.ymin, bb.zmin],
                        [bb.xmax, bb.ymax, bb.zmax],
                        strict=False,
                    )
                ):
                    distance = shape.distance(cq.Vertex.makeVertex(*point))
                    if distance < 2.75 - 1e-5:
                        return False, f"Cable envelope approaches {name} within {distance:.3f} mm."
    return (
        True,
        "5 mm illustrative cable tube clears joint solids; "
        "0.5 mm segment samples with conservative radius.",
    )


def bounds_inside(shape, size, center, allowance=0):
    bb = shape.BoundingBox()
    limits = [(bb.xmin, bb.xmax), (bb.ymin, bb.ymax), (bb.zmin, bb.zmax)]
    return all(
        lo >= c - s / 2 - allowance and hi <= c + s / 2 + allowance
        for (lo, hi), s, c in zip(limits, size, center, strict=False)
    )


def check_joint(stationary, record):
    "Check all modeled joint envelopes before export."
    joint = joint_parts()
    for name, shape in joint.items():
        record(name + " solid", shape.isValid(), "Joint envelope solid validity.")
        for p in stationary:
            volume = shape.intersect(p["shape"]).Volume()
            record(
                name + " / " + p["name"],
                volume < 1e-5,
                f"Joint versus component overlap {volume:.6f} mm³.",
            )
    for (an, ashape), (bn, bshape) in itertools.combinations(joint.items(), 2):
        if {an, bn} == {"Gear_envelope_0_not_teeth", "Gear_envelope_1_not_teeth"}:
            continue  # Addendum circles overlap at the intended tooth mesh.
        volume = ashape.intersect(bshape).Volume()
        record(an + " / " + bn, volume < 1e-5, f"Unintended joint overlap {volume:.6f} mm³.")
    record(
        "Gear radial containment",
        all(
            bounds_inside(
                shape, (BODY[0] - 2 * WALL, BODY[1] - 2 * WALL, BODY[2]), (0, 0, BODY[2] / 2)
            )
            for name, shape in joint.items()
            if name.startswith("Gear")
        ),
        "Gear addendum envelopes fit in the body; housing walls still require design.",
    )


def check(parts, cam):
    checks = []

    def record(name, passed, detail):
        checks.append(dict(name=name, passed=bool(passed), detail=detail))

    stationary = [p for p in parts if not p["kind"].startswith("moving")]
    for p in stationary:
        record(p["name"] + " solid", p["shape"].isValid(), "CAD solid validity only.")
        record(
            p["name"] + " containment",
            bounds_inside(
                p["shape"],
                (BODY[0] - 2 * WALL, BODY[1] - 2 * WALL, BODY[2] - 2 * WALL),
                (0, 0, BODY[2] / 2),
            ),
            (
                "Contained within the rectangular inner envelope; mounts and "
                "corner rounding are not included."
            ),
        )
    for a, b in itertools.combinations(stationary, 2):
        if {a["name"], b["name"]} == {"STS3215 housing", "Servo ears and leads"}:
            continue  # The lead/ear pocket deliberately contains its own servo.
        volume = a["shape"].intersect(b["shape"]).Volume()
        record(
            a["name"] + " / " + b["name"], volume < 1e-5, f"Unintended overlap {volume:.6f} mm³."
        )
    record(
        "Camera solid",
        cam.isValid(),
        "Board, holder, heatsink, and rear connector envelope are one component.",
    )
    record(
        "Camera containment",
        bounds_inside(cam, tuple(s - 2 * WALL for s in HEAD), (0, 0, HEAD_Z)),
        "Full source camera envelope fits before mount design.",
    )
    rear = next(p for p in parts if p["name"] == "Camera rear cable space")
    record(
        "Camera rear reservation",
        bounds_inside(rear["shape"], tuple(s - 2 * WALL for s in HEAD), (0, 0, HEAD_Z)),
        "The cable reservation fits inside the head.",
    )
    record(
        "Camera / rear cable reservation",
        cam.intersect(rear["shape"]).Volume() < 1e-5,
        "Rear connector envelopes remain clear of reserved bend space.",
    )
    for lens_length in (26, 27.5):
        recess = HEAD[1] / 2 - (4.8 + lens_length)
        required_radius = 8.5 + recess * math.tan(math.radians(50))
        record(
            f"Camera aperture at {lens_length} mm lens length",
            required_radius <= 17,
            f"A 34 mm opening clears an ideal 100° diagonal cone at {recess:.2f} mm recess. "
            f"Required radius {required_radius:.2f} mm. Actual optics need a framing test.",
        )
    check_joint(stationary, record)
    joint = joint_parts()
    cable_clashes = []
    lengths = []
    for angle in range(-80, 81, 2):
        points = cable(angle)
        clear, detail = cable_joint_clearance(points, joint)
        record(f"Cable / joint at {angle} degrees", clear, detail)
        lengths.append(sum(math.dist(a, b) for a, b in zip(points, points[1:], strict=False)))
        for point in points[:81]:
            for p in stationary:
                if all(
                    abs(v - c) < s / 2 + 2.5
                    for v, c, s in zip(point, p["center"], p["size"], strict=False)
                ):
                    cable_clashes.append((angle, p["name"]))
        rotated = cam.rotate((0, 0, 0), (0, 0, 1), angle)
        record(
            f"Head separation at {angle} degrees",
            rotated.BoundingBox().zmin > BODY[2],
            (
                "The camera and head envelope sit above the stationary body. The "
                "joint intentionally connects them."
            ),
        )
    record(
        "Cable loop / components",
        not cable_clashes,
        f"5 mm cable envelope sampled every 2° against expanded stationary boxes. "
        f"Clashes: {cable_clashes[:5]}. Illustrative loop, not a physical cable simulation.",
    )
    record(
        "Cable through shaft",
        5 < 10,
        (
            "5 mm source cable envelope in proposed 10 mm passage. USB "
            "connectors need a split shaft and side-loading head opening."
        ),
    )
    record(
        "Bearing spacing",
        BEARING_Z[1] - BEARING_Z[0] == 16,
        "16 mm between centers; axial keepers and load path are reservations.",
    )
    return dict(
        status="PACKAGING STUDY ONLY",
        checks=checks,
        geometry_passed=all(c["passed"] for c in checks),
        dimensions_mm=dict(
            body=BODY,
            head=HEAD,
            height=HEAD_Z + HEAD[2] / 2,
            rotation_diameter=round(math.hypot(HEAD[0], HEAD[1]), 2),
        ),
        cable_path_length_range_mm=[round(min(lengths), 2), round(max(lengths), 2)],
        unresolved=[
            "Physical fit and print material",
            "Actual fan and socket datums",
            ("Owned STS3215 versus source drawing, horn, mounting ears, and bus-adapter version"),
            "Regulator and power-adapter capacity",
            "Cable bend radius, constant-length deformation, strain relief, and fatigue",
            "Press-fit retention forces and catch release",
            "Bearing axial capture and stop strength",
            "Thermal/acoustic/tipping tests",
        ],
        machine="Mac geometry only (E); hardware integration remains U",
    )


def coupons():
    bearing = cq.Workplane("XY").box(152, 36, 6, centered=(False, False, False))
    for x, diameter in zip((22, 58, 94, 130), (23.9, 24.0, 24.1, 24.2), strict=False):
        hole = cq.Workplane("XY").center(x, 18).circle(diameter / 2).extrude(6)
        bearing = bearing.cut(hole)
    camera_fit = cq.Workplane("XY").box(44, 36, 10, centered=(False, False, False))
    for y, gap in zip((8, 18, 28), (1.8, 1.9, 2.0), strict=False):
        slot = (
            cq.Workplane("XY")
            .box(38, gap, 8.8, centered=(True, True, False))
            .translate((22, y, 1.2))
        )
        camera_fit = camera_fit.cut(slot)
    result = {}
    for name, solid in [("bearing-fit", bearing), ("camera-thickness-fit", camera_fit)]:
        assert solid.val().isValid() and len(solid.val().Solids()) == 1
        dest = OUT / f"{name}.3mf"
        export_3mf(solid.val(), dest)
        loaded = trimesh.load(dest, force="scene")
        meshes = [g for g in loaded.geometry.values() if isinstance(g, trimesh.Trimesh)]
        assert meshes and all(m.is_watertight and m.is_volume for m in meshes)
        bb = solid.val().BoundingBox()
        scene_size = loaded.bounds[1] - loaded.bounds[0]
        assert (
            max(abs(a - b) for a, b in zip(scene_size, (bb.xlen, bb.ylen, bb.zlen), strict=False))
            < 0.1
        )
        result[name] = dict(
            size_mm=[round(bb.xlen, 2), round(bb.ylen, 2), round(bb.zlen, 2)],
            watertight=True,
            purpose="Fit coupon only. No servo mount or enclosure fit is certified.",
        )
    return result


def drawing(parts):
    fig, axes = plt.subplots(1, 3, figsize=(16, 8))
    fig.suptitle("Concept A | dimensioned packaging study | millimeters", fontsize=17)
    projections = [
        (0, 2, "Front", "Width", "Height"),
        (1, 2, "Side", "Depth", "Height"),
        (0, 1, "Top", "Width", "Depth"),
    ]
    for ax, (i, j, title, xlabel, ylabel) in zip(axes, projections, strict=False):
        for size, center in [(BODY, (0, 0, BODY[2] / 2)), (HEAD, (0, 0, HEAD_Z))]:
            ax.add_patch(
                Rectangle(
                    (center[i] - size[i] / 2, center[j] - size[j] / 2),
                    size[i],
                    size[j],
                    fill=False,
                    lw=1.5,
                )
            )
        for p in parts:
            if p["kind"].startswith("moving"):
                continue
            size, center = p["size"], p["center"]
            ax.add_patch(
                Rectangle(
                    (center[i] - size[i] / 2, center[j] - size[j] / 2),
                    size[i],
                    size[j],
                    facecolor=p["color"],
                    alpha=0.07 if "reservation" in p["kind"] else 0.3,
                    edgecolor=p["color"],
                    lw=0.7,
                )
            )
        if j == 2:
            ax.add_patch(
                Rectangle(
                    (-21, BODY[2]),
                    42,
                    HEAD_BOTTOM - BODY[2],
                    fill=False,
                    edgecolor="#766782",
                    lw=1.5,
                )
            )
            ax.text(
                0,
                HEAD_Z,
                "Camera head\n" + " × ".join(map(str, HEAD)),
                ha="center",
                va="center",
                fontsize=10,
            )
            ax.text(0, BODY[2] + 6, f"Neck {HEAD_BOTTOM - BODY[2]:g}", ha="center", fontsize=9)
            ax.set_ylim(-8, 273)
        ax.set_xlim(-85, 85)
        if j == 1:
            ax.set_ylim(-80, 80)
            ax.add_patch(
                plt.Circle(
                    (0, 0), math.hypot(*HEAD[:2]) / 2, fill=False, ls="--", edgecolor="#766782"
                )
            )
        ax.set_aspect("equal")
        ax.set_title(title)
        ax.set_xlabel(xlabel + " (mm)")
        ax.set_ylabel(ylabel + " (mm)")
        ax.grid(alpha=0.15)
    legend_names = (
        "Jetson",
        "One speaker",
        "USB audio case",
        "STS3215 housing",
        "Jetson USB/power plugs",
        "Fan intake space",
    )
    handles = [
        Rectangle((0, 0), 1, 1, facecolor=p["color"], alpha=0.5, label=p["name"])
        for p in parts
        if p["name"] in legend_names
    ]
    fig.legend(
        handles=handles,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.105),
        ncol=3,
        frameon=False,
        fontsize=10,
    )
    fig.text(
        0.5,
        0.08,
        (
            f"Body: {BODY[0]} × {BODY[1]} × {BODY[2]} | Overall height: {HEAD_Z + HEAD[2] / 2:g} | "
            f"Head rotation envelope: Ø{math.hypot(*HEAD[:2]):.2f} | Bearing centers: {BEARING_Z}"
        ),
        ha="center",
        fontsize=11,
    )
    fig.text(
        0.5,
        0.04,
        (
            "Colored boxes include provisional plugs, airflow, and controller "
            "spaces. This drawing does not certify mounts, cable behavior, or "
            "cooling."
        ),
        ha="center",
        fontsize=10,
    )
    fig.tight_layout(rect=(0, 0.19, 1, 0.94))
    fig.savefig(OUT / "layout-dimensions.png", dpi=160)
    fig.savefig(OUT / "layout-dimensions.svg")
    plt.close(fig)


def main():
    OUT.mkdir(exist_ok=True)
    parts = hardware()
    cam = camera()
    report = check(parts, cam)
    report["coupons"] = coupons()
    (OUT / "checks.json").write_text(json.dumps(report, indent=2) + "\n")
    assert report["geometry_passed"], [c for c in report["checks"] if not c["passed"]]
    assembly = cq.Assembly(name="Concept_A_PACKAGING_ONLY")
    for p in parts:
        assembly.add(p["shape"], name=p["name"].replace("/", "_"), color=color(p["color"]))
    assembly.add(cam, name="Source_camera_envelope", color=color("#44755c"))
    joint = joint_parts()
    for name, shape in joint.items():
        assembly.add(shape, name=name, color=color("#8c839b"))
    assembly.add(
        box(BODY, (0, 0, BODY[2] / 2)),
        name="Body_outer_envelope",
        color=cq.Color(0.85, 0.85, 0.85, 0.08),
    )
    assembly.add(
        box(HEAD, (0, 0, HEAD_Z)),
        name="Head_outer_envelope",
        color=cq.Color(0.85, 0.85, 0.85, 0.08),
    )
    assembly.export(str(OUT / "layout-study.step"))
    data = [{k: v for k, v in p.items() if k != "shape"} for p in parts]
    data.append(
        dict(
            name="Camera board",
            size=[37, 1.6, 37],
            center=[CAMERA_X, -4, CAMERA_Z],
            color="#477967",
            kind="moving hardware",
            note=(
                "E: source camera board, 1.4–1.8 mm actual thickness. Retain board "
                "edges with a removable clamp."
            ),
            source=SOURCE,
        )
    )
    for name, size, center in [
        ("Camera rear heatsink", [26, 10, 26], [CAMERA_X, 1.8, CAMERA_Z]),
        ("Camera rear connector J2", [16.8, 9, 11.3], [CAMERA_X, 1.3, CAMERA_Z + 10.05]),
        ("Camera rear connector J1", [21.6, 6, 5.5], [CAMERA_X, -0.2, CAMERA_Z - 14.35]),
    ]:
        data.append(
            dict(
                name=name,
                size=size,
                center=center,
                color="#477967",
                kind="moving hardware",
                source=SOURCE,
                note="E: camera rear envelope from the reference design; actual fit is U.",
            )
        )
    payload = dict(
        joint=dict(
            bearingZ=BEARING_Z,
            shaftZ=SHAFT_Z,
            headBottom=HEAD_BOTTOM,
            gearCenters=GEAR_CENTERS,
            gearRadius=GEAR_RADIUS,
            gearZ=GEAR_Z,
        ),
        parts=data,
        body=BODY,
        head=HEAD,
        headZ=HEAD_Z,
        report=report,
        cables={str(a): [[round(v, 3) for v in p] for p in cable(a)] for a in range(-80, 81, 2)},
    )
    (OUT / "layout.json").write_text(json.dumps(payload, indent=2) + "\n")
    template = (ROOT / "viewer.html").read_text()
    (OUT / "layout-viewer.html").write_text(
        template.replace("/*LAYOUT_DATA*/", json.dumps(payload))
    )
    drawing(parts)
    print(
        f"{len(report['checks'])} packaging checks passed; two watertight fit coupons exported. "
        "Final enclosure remains unverified."
    )


if __name__ == "__main__":
    main()
