"""Render the selected tapered CAD silhouette with current component reservations."""

import json
import itertools
from pathlib import Path
import cadquery as cq
import numpy as np
import matplotlib.pyplot as plt
import assembly
import layout
from screen_layouts import envelopes
from enclosure_geometry import body_envelopes, head_envelopes

OUT = Path(__file__).parent / "output" / "silhouettes"
WHITE = "#f5f5f5"
BLACK = "#17191c"


def loft(sections, inner=False):
    return body_envelopes(tuple(tuple(row) for row in sections))[int(inner)]


def candidate(name, sections):  # noqa: C901 - ordered candidate geometry and preview
    top = sections[-1][0]
    outer, inner = loft(sections), loft(sections, True)
    hardware = envelopes()
    speaker_z = 48  # Grille center; physical speaker position comes from layout.hardware.
    # Keep hardware positions from executable packing; the new taper is screened here.
    checks = [dict(name=p["name"], outside_mm3=p["shape"].cut(inner).Volume()) for p in hardware]
    camera_shift = top + 48 - layout.CAMERA_Z
    camera = layout.camera().translate((0, 0, camera_shift))
    cable = next(p["shape"] for p in layout.hardware() if p["kind"].startswith("moving")).translate(
        (0, 0, camera_shift)
    )
    head_center = top + 48
    head_outer, head_inner = head_envelopes()
    head_outer = head_outer.translate((0, 0, head_center - 208))
    head_inner = head_inner.translate((0, 0, head_center - 208))
    head_y = 0
    head_outer = head_outer.translate((0, head_y, 0))
    head_inner = head_inner.translate((0, head_y, 0))
    checks += [
        dict(name="complete camera", outside_mm3=camera.cut(head_inner).Volume()),
        dict(name="camera rear cable reservation", outside_mm3=cable.cut(head_inner).Volume()),
    ]
    visor = (
        cq.Workplane("XZ")
        .rect(98, 46)
        .extrude(2)
        .edges("|Y")
        .fillet(18)
        .translate((0, head_y - 38.1, head_center))
        .val()
    )
    visor = visor.cut(
        cq.Solid.makeCylinder(
            20.2, 10, cq.Vector(-24, head_y - 45, head_center), cq.Vector(0, 1, 0)
        )
    )
    visor = visor.cut(
        cq.Solid.makeCylinder(
            11, 0.3, cq.Vector(22, head_y - 40.11, head_center), cq.Vector(0, 1, 0)
        )
    )
    visor = visor.fuse(
        cq.Solid.makeCylinder(
            11.4, 2, cq.Vector(22, head_y - 39.5, head_center), cq.Vector(0, 1, 0)
        )
    )
    # Integral light baffle: same removable visor, no additional printed part.
    axis = cq.Vector(0, 1, 0)
    origin = cq.Vector(-24, head_y - 40.1, head_center)
    baffle = cq.Solid.makeCone(22, 15, 8.2, origin, axis).cut(
        cq.Solid.makeCone(20.2, 13.2, 8.2, origin, axis)
    )
    visor = visor.fuse(baffle).clean()
    grille_mask = (
        cq.Workplane("XZ")
        .rect(108, 42)
        .extrude(50)
        .edges("|Y")
        .fillet(16)
        .translate((0, -40, speaker_z))
        .val()
    )
    grille = outer.cut(inner).intersect(grille_mask)
    holes = [
        cq.Solid.makeCylinder(1.4, 60, cq.Vector(x, -90, z), axis)
        for x in range(-45, 46, 5)
        for z in range(speaker_z - 15, speaker_z + 16, 5)
    ]
    grille = grille.cut(cq.Compound.makeCompound(holes)).clean()
    assert grille.isValid() and len(grille.Solids()) == 1
    assert not grille.isInside(cq.Vector(0, -75, speaker_z))
    body_visible = outer.cut(grille_mask)
    neck = layout.ring(54, 32.4, 20, top).translate((0, head_y, 0))
    head_shell = head_outer.cut(head_inner).cut(
        cq.Solid.makeCylinder(
            22.2, 17, cq.Vector(-24, head_y - 45, head_center), cq.Vector(0, 1, 0)
        )
    )
    head_shell = head_shell.cut(
        cq.Workplane("XZ")
        .rect(98.4, 46.4)
        .extrude(15)
        .edges("|Y")
        .fillet(18.2)
        .translate((0, head_y - 30, head_center))
        .val()
    )
    display = dict(
        body=body_visible, head=head_shell, visor=visor, grille=grille, neck=neck, camera=camera
    )
    colors = {n: dict(color=WHITE if n in ("body", "head") else BLACK) for n in display}
    cutaway = dict(
        body=outer.cut(inner).cut(layout.box((220, 150, 240), (0, -75, top / 2))),
        head=head_outer.cut(head_inner).cut(
            layout.box((140, 100, 70), (0, head_y - 50, head_center))
        ),
        neck=neck,
        camera=camera,
    )
    cut_colors = {n: dict(color=WHITE if n in ("body", "head") else BLACK) for n in cutaway}
    for p in hardware:
        cutaway[p["name"]] = p["shape"]
        cut_colors[p["name"]] = dict(color=p["color"])
    cutaway["camera cable pocket"] = cable
    cut_colors["camera cable pocket"] = dict(color="#d08e48")
    fig, axes = plt.subplots(1, 3, figsize=(12, 7), facecolor="#e4e8ed")
    for ax, shapes, meta, angle, title in [
        (axes[0], display, colors, 0, "Front"),
        (axes[1], display, colors, -25, "Three-quarter"),
        (axes[2], cutaway, cut_colors, -15, "Complete reference envelopes"),
    ]:
        pixels = assembly.raster(shapes, meta, angle, width=600, height=900)
        bg = np.all(np.isclose(pixels, [0.957, 0.949, 0.925]), axis=2)
        pixels[bg] = [0.894, 0.91, 0.929]
        ax.imshow(pixels)
        ax.axis("off")
        ax.set_title(title)
    max_w, max_d = max(r[1] for r in sections), max(r[2] for r in sections)
    fig.suptitle(
        f"{name} | body {max_w} × {max_d} × {top} mm | overall {top + 76} mm | neutral white",
        fontsize=14,
    )
    failures = [r for r in checks if r["outside_mm3"] > 1e-5]
    collisions = []
    for a, b in itertools.combinations(hardware, 2):
        if {a["name"], b["name"]} == {"STS3215 housing", "Servo ears and leads"}:
            continue
        volume = a["shape"].intersect(b["shape"]).Volume()
        if volume > 1e-5:
            collisions.append(dict(a=a["name"], b=b["name"], volume_mm3=volume))
    fig.text(
        0.5,
        0.02,
        (
            f"Actual CAD surfaces. Preliminary packing only: {len(failures)} containment "
            f"conflicts. Mounts, cable motion, cooling, and physical fit remain U."
        ),
        ha="center",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    fig.savefig(OUT / (name.lower().replace(" ", "-") + ".png"), dpi=150)
    plt.close(fig)
    cq.exporters.export(
        cq.Compound.makeCompound([outer, head_outer]),
        str(OUT / (name.lower().replace(" ", "-") + ".step")),
    )
    viewer_shapes = {
        "body-front": display["body"],
        "head-front": display["head"],
        "head-visor": display["visor"],
        "speaker-grille": display["grille"],
        "neck-cover": display["neck"],
    }
    viewer_meta = {
        part: dict(
            kind="casing",
            color=WHITE if part in ("body-front", "head-front") else BLACK,
            moving=part.startswith("head-"),
            removable=False,
        )
        for part in viewer_shapes
    }
    viewer_hardware = hardware + [
        dict(
            name="Complete camera",
            shape=camera,
            kind="moving hardware",
            color=BLACK,
            note=(
                "E: source camera envelope. Physical support, focus clearance, and cable "
                "motion remain U."
            ),
        ),
        dict(
            name="Camera rear cable reservation",
            shape=cable,
            kind="moving reservation",
            color="#d08e48",
            note=(
                "U: reference connector and cable space. Practical bend radius remains unmeasured."
            ),
        ),
    ]
    assembly.viewer(
        viewer_shapes,
        viewer_meta,
        hardware_entries=viewer_hardware,
        destination=OUT / (name.lower().replace(" ", "-") + ".html"),
        study_name=name,
    )
    return dict(
        name=name,
        body_mm=[max_w, max_d, top],
        overall_height_mm=top + 76,
        sections=sections,
        head_mm=[116, 80, 56],
        speaker_center_z_mm=speaker_z,
        footprint_increase_percent=(max_w * max_d / (136 * 112) - 1) * 100,
        containment=checks,
        collisions=collisions,
        passed=not failures and not collisions,
        limits=(
            "Preliminary cavity only; no validated mounts, seams, wall thickness, "
            "admission, joint relocation, physical fit, or thermal claim."
        ),
    )


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    results = [
        candidate("A upright taper", [(0, 152, 130, 22), (160, 128, 110, 20)]),
    ]
    (OUT / "containment.json").write_text(json.dumps(results, indent=2) + "\n")
    for r in results:
        print(
            r["name"],
            r["body_mm"],
            [
                (c["name"], round(c["outside_mm3"], 2))
                for c in r["containment"]
                if c["outside_mm3"] > 1e-5
            ],
            flush=True,
        )


if __name__ == "__main__":
    main()
