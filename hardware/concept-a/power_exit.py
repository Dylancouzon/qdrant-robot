"""Build and check a removable power-exit trial from Dylan's plug measurements.
Run with the packaging study's pinned CAD environment.
"""

from __future__ import annotations

import json
from pathlib import Path

import cadquery as cq
import matplotlib
import trimesh

from layout import box, color, export_3mf

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

OUT = Path(__file__).resolve().parent / "output"
SOCKET_X = 37.75
SOCKET_Y = 10.5
SOCKET_Z = 18
FACE_X = SOCKET_X + 9
BOTTOM = 8.5
TOP = 42
WALL = 1.6
PLUG_DIAMETER = 11
CHANNEL_WIDTH = 13


def insert():
    """Make an upward-open well with two outer panel wings and a continuous floor."""
    rear_x = FACE_X - WALL
    pieces = [
        box((WALL, 39.2, TOP - BOTTOM), (FACE_X - WALL / 2, SOCKET_Y, (TOP + BOTTOM) / 2)),
        box((68 - rear_x, 60, WALL), ((68 + rear_x) / 2, SOCKET_Y, BOTTOM + WALL / 2)),
    ]
    for sign in (-1, 1):
        pieces.extend(
            [
                box(
                    (68 - rear_x, WALL, TOP - BOTTOM),
                    ((68 + rear_x) / 2, SOCKET_Y + sign * 18.8, (TOP + BOTTOM) / 2),
                ),
                box((2.4, 12, TOP - BOTTOM), (66.8, SOCKET_Y + sign * 24, (TOP + BOTTOM) / 2)),
            ]
        )
    shape = pieces[0]
    for piece in pieces[1:]:
        shape = shape.fuse(piece)
    slot_bottom = SOCKET_Z - CHANNEL_WIDTH / 2
    opening = box(
        (WALL + 2, CHANNEL_WIDTH, TOP - slot_bottom + 2),
        (FACE_X - WALL / 2, SOCKET_Y, (TOP + slot_bottom) / 2 + 1),
    )
    return shape.cut(opening).clean()


def trial_plug():
    """Reserve a round stem and a square elbow, with an extra 5.5 mm at both ends."""
    stem = cq.Solid.makeCylinder(
        PLUG_DIAMETER / 2,
        11,
        cq.Vector(SOCKET_X, SOCKET_Y, SOCKET_Z),
        cq.Vector(1, 0, 0),
    )
    elbow = box((11, 11, 21), (SOCKET_X + 11, SOCKET_Y, SOCKET_Z + 5))
    return stem.fuse(elbow).clean()


def mesh(shape):
    vertices, faces = shape.tessellate(0.05, 0.1)
    return trimesh.Trimesh(vertices=[v.toTuple() for v in vertices], faces=faces)


def overview(well, plug):
    fig = plt.figure(figsize=(11, 7))
    axis = fig.add_subplot(111, projection="3d", proj_type="ortho")
    for shape, tint, alpha in ((well, "#477967", 0.85), (plug, "#de9249", 0.8)):
        triangles = mesh(shape).triangles
        axis.add_collection3d(
            Poly3DCollection(triangles, facecolor=tint, edgecolor="none", alpha=alpha)
        )
    axis.set(
        xlim=(35, 70),
        ylim=(-21, 42),
        zlim=(8, 44),
        xlabel="X (mm)",
        ylabel="Y (mm)",
        zlabel="Z (mm)",
    )
    axis.set_box_aspect((35, 63, 36))
    axis.view_init(elev=48, azim=-8)
    fig.suptitle("Power-exit trial | upward-open removable recess", fontsize=16)
    fig.text(
        0.04,
        0.04,
        "Plug: reported Ø11 mm, 11 mm straight reach, 10 mm elbow. Channel: 13 mm.\n"
        "Exterior face: 9 mm from provisional socket plane. Part: 22.85 × 60 × 33.5 mm.\n"
        "Orange: assumed rigid plug envelope. Test actual fit before casing integration.",
        fontsize=11,
    )
    fig.subplots_adjust(bottom=0.20, top=0.90)
    fig.savefig(OUT / "power-exit-trial.png", dpi=180)
    plt.close(fig)


def main():
    OUT.mkdir(exist_ok=True)
    well = insert()
    plug = trial_plug()
    assert well.isValid() and len(well.Solids()) == 1 and well.Volume() > 0
    assert plug.isValid() and len(plug.Solids()) == 1
    checks = ["One valid connected insert solid", "Valid assumed plug envelope"]
    board = box((90.5, 35, 103), (-7.5, 10, 61.5))
    assert well.distance(board) >= 7.39
    checks.append("Insert clears the reference Jetson envelope by at least 7.39 mm")
    # Translate the well upward from below the connected plug. A downward move removes it.
    # Check every segment conservatively: expand the rigid plug by the full sample distance.
    # This bounds translations between samples as well as at the samples.
    bounds = plug.BoundingBox()
    guarded_plug = box(
        (bounds.xlen, bounds.ylen, bounds.zlen + 0.5),
        ((bounds.xmax + bounds.xmin) / 2, SOCKET_Y, (bounds.zmax + bounds.zmin) / 2),
    )
    for step in range(161):
        position = well.translate((0, 0, -40 + step * 0.25))
        assert position.intersect(guarded_plug).Volume() < 1e-6
    checks.append("161 upward insertion positions clear the plug, with 0.25 mm translation guard")
    assert well.distance(plug) > 0.9
    checks.append("Final trial plug separation exceeds 0.9 mm")
    assert FACE_X < SOCKET_X + 11
    checks.append("Recess face is 2 mm before the reported elbow transition")
    bb = well.BoundingBox()
    printed = well.translate((-bb.xmin, -bb.ymin, -bb.zmin))
    file = OUT / "power-exit-trial.3mf"
    export_3mf(printed, file)
    scene = trimesh.load(file, force="scene")
    assert len(scene.geometry) == 1
    loaded = next(iter(scene.geometry.values()))
    assert loaded.is_watertight and loaded.is_volume
    assert (
        max(abs(a - b) for a, b in zip(scene.extents, (bb.xlen, bb.ylen, bb.zlen), strict=True))
        < 0.1
    )
    assert abs(scene.bounds[0][2]) < 1e-6
    assert max(scene.extents[:2]) < 256
    checks.extend(
        [
            "3MF indexed edges are closed; independent reload has positive volume",
            "Millimeter scale, Z0 base, and P1S bed fit",
        ]
    )
    # The floor is a full rectangle. All vertical walls start on this continuous base.
    floor = printed.intersect(box((bb.xlen, bb.ylen, 0.2), (bb.xlen / 2, bb.ylen / 2, 0.1)))
    assert abs(floor.Volume() - bb.xlen * bb.ylen * 0.2) < 1e-4
    checks.append("Continuous rectangular first layer")
    assembly = cq.Assembly()
    assembly.add(well, name="removable_trial_insert", color=color("#477967"))
    assembly.add(plug, name="assumed_plug_envelope", color=color("#de9249"))
    assembly.export(str(OUT / "power-exit-trial.step"))
    reloaded = cq.importers.importStep(str(OUT / "power-exit-trial.step")).val()
    assert all(s.isValid() for s in reloaded.Solids()) and len(reloaded.Solids()) == 2
    checks.append("STEP reload contains two valid assembly solids")
    overview(well, plug)
    report = dict(
        machine="Mac geometry checks (E); physical fit remains U",
        slicing_evidence="../BAMBU_CHECK.md",
        checks=checks,
        dimensions_mm=dict(
            part=[round(bb.xlen, 2), round(bb.ylen, 2), round(bb.zlen, 2)],
            plug_diameter=PLUG_DIAMETER,
            channel_width=CHANNEL_WIDTH,
            wall_thickness=WALL,
            socket_plane_x=SOCKET_X,
            recess_exterior_x=FACE_X,
            recess_depth=68 - FACE_X,
            final_plug_separation=round(well.distance(plug), 3),
        ),
        assumptions=[
            "Socket coordinates are provisional reference-layout datums.",
            "The elbow is represented by an 11 × 11 × 21 mm block around its centerline.",
            "The trial has no casing attachment. Hold it by hand for the fit check.",
            "Other USB plugs and cable flexibility are outside this isolated trial.",
        ],
        release="Trial geometry only. See BAMBU_CHECK.md for independent slicing evidence.",
    )
    (OUT / "power-exit-checks.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"{len(checks)} checks passed; power-exit trial 3MF and STEP exported.")


if __name__ == "__main__":
    main()
