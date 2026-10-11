"""Shared actual geometry validators and complete reservation metadata."""

import cadquery as cq
from OCP.BRepAdaptor import BRepAdaptor_Surface

import layout


def rounded_wall_thickness(outer, inner):  # noqa: C901 - dispatch actual surface families
    """Match the actual planar, cylindrical, and spherical offset surfaces.

    OCC's shell distance fails for some concentric spheres. Analytic matching
    verifies each actual surface instead of accepting failed distance queries.
    """
    if any(f.geomType() not in ("PLANE", "CYLINDER", "SPHERE") for f in outer.Faces()):
        # Actual trimmed offset and rolled surfaces, including taper splines/torus.
        gap = outer.Shells()[0].distance(inner.Shells()[0])
        assert gap > 0, "Failed actual wall distance"
        return gap
    descriptors = []
    for solid in (outer, inner):
        faces = []
        for face in solid.Faces():
            surface = BRepAdaptor_Surface(face.wrapped)
            kind = face.geomType()
            if kind == "PLANE":
                geometry = surface.Plane()
                axis = geometry.Axis().Direction()
                n = cq.Vector(axis.X(), axis.Y(), axis.Z())
                loc = geometry.Location()
                p = cq.Vector(loc.X(), loc.Y(), loc.Z())
                faces.append((kind, n, p.dot(n), None))
            elif kind == "CYLINDER":
                geometry = surface.Cylinder()
                axis = geometry.Axis().Direction()
                n = cq.Vector(axis.X(), axis.Y(), axis.Z())
                loc = geometry.Location()
                p = cq.Vector(loc.X(), loc.Y(), loc.Z())
                faces.append((kind, n, p - n * p.dot(n), geometry.Radius()))
            elif kind == "SPHERE":
                geometry = surface.Sphere()
                loc = geometry.Location()
                faces.append((kind, None, cq.Vector(loc.X(), loc.Y(), loc.Z()), geometry.Radius()))
            else:
                raise AssertionError("Unsupported wall surface " + kind)
        descriptors.append(faces)
    gaps = []
    for kind, n, position, radius in descriptors[0]:
        candidates = []
        for ikind, inn, iposition, iradius in descriptors[1]:
            if kind != ikind:
                continue
            if kind == "PLANE" and abs(n.dot(inn)) > 1 - 1e-6:
                candidates.append(abs(position - iposition * n.dot(inn)))
            elif (
                (
                    kind == "CYLINDER"
                    and abs(n.dot(inn)) > 1 - 1e-6
                    and (position - iposition).Length < 1e-5
                )
                or kind == "SPHERE"
                and (position - iposition).Length < 1e-5
            ):
                candidates.append(abs(radius - iradius))
        assert candidates, kind
        gaps.append(min(candidates))
    return min(gaps)


def validate_final_geometry(cavities, reservations, parts, walls, supports):
    """Check final cavities, wall sections, and declared continuous support cores.

    Call after constructing final casing parts. Wall entries contain unperforated
    outer/inner solids plus explicit section slabs. Support entries contain a
    2.4 × 6 mm minimum core, its support solid, and its attached shell.
    """
    checks = []

    def record(name, passed, measured):
        checks.append(dict(name=name, passed=bool(passed), measured=measured))

    for name, shape, cavity_name in reservations:
        outside = shape.cut(cavities[cavity_name]).Volume()
        record(name + " final cavity containment", outside < 1e-5, outside)
        for part_name, (part, scope) in parts.items():
            if scope == cavity_name:
                overlap = shape.intersect(part).Volume()
                record(name + " / " + part_name, overlap < 1e-5, overlap)
    for name, outer, inner, sections in walls:
        gap = rounded_wall_thickness(outer, inner)
        record(name + " minimum wall", gap >= 2.4 - 1e-5, gap)
        for index, slab in enumerate(sections):
            outer_section, inner_section = outer.intersect(slab), inner.intersect(slab)
            # Section solids share slab caps. Measure their side faces only.
            normal = slab.BoundingBox()
            axis = min(("x", "y", "z"), key=lambda a: getattr(normal, a + "len"))
            outer_faces = [
                f for f in outer_section.Faces() if abs(getattr(f.normalAt(), axis)) < 0.99
            ]
            inner_faces = [
                f for f in inner_section.Faces() if abs(getattr(f.normalAt(), axis)) < 0.99
            ]
            gap = min(a.distance(b) for a in outer_faces for b in inner_faces)
            record(name + f" section {index} wall", gap >= 2.4 - 1e-5, gap)
    for entry in supports:
        name, support, core, attached_shell = entry[:4]
        load_axis = entry[4] if len(entry) > 4 else "z"
        bb = core.BoundingBox()
        rectangular = abs(core.Volume() - bb.xlen * bb.ylen * bb.zlen) < 1e-5
        section = sorted(getattr(bb, axis + "len") for axis in "xyz" if axis != load_axis)
        record(
            name + " support section",
            rectangular and section[0] >= 2.4 - 1e-5 and section[1] >= 6 - 1e-5,
            dict(load_axis=load_axis, section_mm=section),
        )
        missing = core.cut(support).Volume()
        record(
            name + " continuous core",
            missing < 1e-5,
            dict(core_mm3=core.Volume(), missing_mm3=missing),
        )
        joined = support.fuse(attached_shell).clean()
        record(name + " shell load path", len(joined.Solids()) == 1, len(joined.Solids()))
    assert checks, "No geometry checks were executed"
    return checks


def envelopes():
    """Complete current stationary hardware and airflow/connector reservations."""
    return [dict(p) for p in layout.hardware() if not p["kind"].startswith("moving")]
