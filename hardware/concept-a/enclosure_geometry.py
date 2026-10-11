"""Shared tapered exterior and independently verified inset cavity, in millimeters."""

from functools import lru_cache
from math import sqrt
import cadquery as cq

BODY_SECTIONS = ((0, 152, 130, 22), (160, 128, 110, 20))
WALL = 3.2


def wire(w, d, r, z):
    return (
        cq.Workplane("XY")
        .box(w, d, 1)
        .edges("|Z")
        .fillet(r)
        .faces(">Z")
        .wires()
        .val()
        .translate((0, 0, z - 0.5))
    )


@lru_cache(maxsize=4)
def body_envelopes(sections=BODY_SECTIONS, wall=WALL):
    low, high = sections[0], sections[-1]
    raw = cq.Solid.makeLoft([wire(w, d, r, z) for z, w, d, r in (low, high)], True)
    outer = (
        cq.Workplane(obj=raw).faces(">Z").edges().fillet(20).faces("<Z").edges().fillet(22).val()
    )
    height = high[0] - low[0]
    sx = (high[1] - low[1]) / (2 * height)
    sy = (high[2] - low[2]) / (2 * height)
    inset = []
    for z in (low[0] + wall, high[0] - wall):
        fraction = (z - low[0]) / height
        w, d, r = [low[k] + fraction * (high[k] - low[k]) for k in (1, 2, 3)]
        inset.append(
            wire(w - 2 * wall * sqrt(1 + sx * sx), d - 2 * wall * sqrt(1 + sy * sy), r - wall, z)
        )
    cavity = cq.Solid.makeLoft(inset, True)
    inner = (
        cq.Workplane(obj=cavity)
        .faces(">Z")
        .edges()
        .fillet(20 - wall)
        .faces("<Z")
        .edges()
        .fillet(22 - wall)
        .val()
    )
    assert outer.isValid() and inner.isValid()
    return outer, inner


@lru_cache(maxsize=1)
def head_envelopes():
    raw = (
        cq.Workplane("XZ")
        .rect(116, 56)
        .extrude(80)
        .edges("|Y")
        .fillet(22)
        .translate((0, 40, 208))
        .val()
    )
    inner = raw.cut(cq.Workplane(obj=raw).shell(-3).val())
    outer = cq.Workplane(obj=raw).edges("not |Y").fillet(5).val()
    inner = cq.Workplane(obj=inner).edges("not |Y").fillet(2).val()
    return outer, inner
