"""Fixed exterior and hardware boxes shared by body.py, head.py and study.py, in millimeters.
The tapered body and head envelopes carry the approved outline. hardware() lists reserved spaces.
"""

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


# Jetson standing on edge: 90.5 along X, 35 along Y, 103 along Z. Its I/O edge faces +X (the port
# panel), the flat black tray faces -Y, and the heatsink faces +Y. The tray overhangs the carrier
# board on the edge opposite the I/O only, so a plastic strip along -X is what the body holds.
# Sizes come from NVIDIA's kit drawing (O) and estimates (E); the strip thickness is Dylan's (U).
JETSON_STRIP_T = 11.0  # U: thickness of the flat tray and board; Dylan is measuring it
SLOT_GAP, SLOT_WALL = 0.5, 3.0  # slot clearance per side of the strip (U) and slot wall thickness
X0, Y0, Z0 = -52.75, -7.5, 10.0  # lowest corner of the 90.5 x 35 x 103 envelope
X1, Y1, Z1 = X0 + 90.5, Y0 + 35.0, Z0 + 103.0
SLAB_Y = Y0 + JETSON_STRIP_T  # top face of the flat tray and board
PORT_TOP_Y = Y0 + 7.6 + 1.57 + 16.7  # tray and feet (E), carrier board (O), USB and RJ45 stack (O)
PORT_X0 = X1 - 20.0  # the I/O band is about 20 mm deep (E)
HEAT_X = ((X0 + 11.5) + PORT_X0) / 2  # between the board's far edge (90.5 - 79) and the I/O band
HEAT_XZ = (47.0, 66.0)  # 39 x 58 mm footprint (E) plus 4 mm each way for the position error
MID_Z = (Z0 + Z1) / 2


def placed(x, y, z):
    "(size, center) of a box from three (low, high) ranges."
    return tuple(hi - lo for lo, hi in (x, y, z)), tuple((hi + lo) / 2 for lo, hi in (x, y, z))


HEAT_RANGE = (  # X and Z ranges of the heatsink block
    (HEAT_X - HEAT_XZ[0] / 2, HEAT_X + HEAT_XZ[0] / 2),
    (MID_Z - HEAT_XZ[1] / 2, MID_Z + HEAT_XZ[1] / 2),
)
JETSON_PARTS = {
    "Jetson tray and board": placed((X0, X1), (Y0, SLAB_Y), (Z0, Z1)),
    "Jetson ports": placed((PORT_X0, X1), (SLAB_Y, PORT_TOP_Y), (MID_Z - 50, MID_Z + 50)),
    "Jetson heatsink": placed(HEAT_RANGE[0], (SLAB_Y, Y1), HEAT_RANGE[1]),
}

# Servo adapter board (Dylan): 42 x 32 x 13 mm, standing on a long edge in the band between the
# audio case and the Jetson. Its barrel jack takes a plug straight up from the top edge, near the
# -X end (U). Its USB data port is on an unknown end, so both short ends keep plug room (U).
BUS_X, BUS_T, BUS_Z = 42.0, 13.0, (7.6, 39.6)
BAND_Y = (-28.0, -11.0)  # pocket interior between the audio wall and the Jetson wall
BUS_FACE_GAP = 2.0  # U: room before the servo connector face (-Y); 3.0 mm is the most here
BUS_Y = BAND_Y[0] + BUS_FACE_GAP + BUS_T / 2
PLUG_USB_X, PLUG_POWER = 20.0, (14.0, 40.0)  # USB plug room per end; barrel plug zone width, length
PLUG_FLOOR_Z = BUS_Z[0] + 3.2  # the end stop ribs are 3.2 mm tall

# name: (size X, Y, Z, center X, Y, Z). Boxes are external envelopes, reservations included.
# Speaker: Waveshare 8 ohm 5 W. The rest are unmeasured (U).
BOXES = JETSON_PARTS | {
    "One speaker": ((100, 21, 45), (0, -45.5, 47.5)),
    "USB audio case": ((53, 23.5, 14.6), (-27, -40, 88)),
    "Bus interface": placed((-BUS_X / 2, BUS_X / 2), (BUS_Y - BUS_T / 2, BUS_Y + BUS_T / 2), BUS_Z),
    "Bus power plug space": placed(
        (-BUS_X / 2, -BUS_X / 2 + PLUG_POWER[0]), BAND_Y, (BUS_Z[1], BUS_Z[1] + PLUG_POWER[1])
    ),
    "Bus USB plug space -": placed(
        (-BUS_X / 2 - PLUG_USB_X, -BUS_X / 2), BAND_Y, (PLUG_FLOOR_Z, BUS_Z[1])
    ),
    "Bus USB plug space +": placed(
        (BUS_X / 2, BUS_X / 2 + PLUG_USB_X), BAND_Y, (PLUG_FLOOR_Z, BUS_Z[1])
    ),
    "Jetson USB/power plugs": ((24, 34, 108), (49.75, 10, 62)),
    # 30 x 30 x 30 mm of slack for the camera cable, under the roof hole and on top of the plug
    # space above, which is the way down to a Jetson USB port.
    "Camera cable slack loop": placed((17, 47), (8, 38), (116, 146)),
    "Fan intake space": placed(HEAT_RANGE[0], (Y1, Y1 + 22), HEAT_RANGE[1]),
    "Outlet space": placed((-63, -55), (SLAB_Y + SLOT_GAP + SLOT_WALL, Y1), (Z0, Z1)),
    "Camera rear cable space": ((43, 18, 43), (-24, 23, 208)),
}


def hardware():
    return [
        dict(name=name, shape=cq.Workplane("XY").box(*size).translate(center).val())
        for name, (size, center) in BOXES.items()
    ]
