"""Define the source hardware envelopes, shared mesh exporter, and fit coupons.
Run with the pinned CadQuery environment to regenerate the two coupons.
"""

from __future__ import annotations
import json
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree
import cadquery as cq
import trimesh

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
HEAD_Z = 208
CAMERA_X = -24
CAMERA_Z = HEAD_Z
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
            (0, -45.5, 47.5),
            "#555960",
            "hardware",
            "E: larger manufacturer envelope; actual speaker size is U.",
            "https://www.waveshare.com/8ohm-5w-speaker.htm",
        ),
        item(
            "USB audio case",
            (53, 23.5, 14.6),
            (-27, -40, 88),
            "#767a84",
            "hardware",
            (
                "E: case only, without USB plug. Flatter reference orientation; "
                "actual microphone and USB direction remain U."
            ),
            "https://www.waveshare.com/usb-to-audio.htm",
        ),
        item(
            "Audio USB extension",
            (20, 20, 22),
            (10, -40, 88),
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


def speaker_contact_regions():
    """Provisional rigid housing contact windows; verify the owned speaker frame first."""
    return [
        item(
            "Speaker upper rear housing corner " + str(x),
            (6, 4, 1),
            (x, -37, 69.5),
            "#ad76bc",
            "contact region",
            (
                "User describes a rectangular housing. Frame/terminal contact is physical U; "
                "use a dummy."
            ),
        )
        for x in (-47, 47)
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


def main():
    OUT.mkdir(exist_ok=True)
    report = coupons()
    (OUT / "coupon-checks.json").write_text(json.dumps(report, indent=2) + "\n")
    print("Two closed millimeter fit coupons exported.")


if __name__ == "__main__":
    main()
