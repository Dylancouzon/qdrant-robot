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
# Sizes come from NVIDIA's kit drawing (O), estimates (E), and Dylan's measurements (2026-10-13).
JETSON_STRIP_T, JETSON_STRIP_D = 6.0, 8.0  # strip thickness and depth; the strip is the tray's
JETSON_SLAB_T = 11.0  # outer face. The flat board with its tray is 11 mm thick, beyond the strip
# Slot gap per side of the strip: 0.5 mm held the Jetson loosely on the test piece, and Dylan asked
# for about 1 mm tighter (2026-10-15). 0.1 mm leaves room for print shrink over the 38 mm slide; the
# full-height slot test piece confirms it. The back wall keeps 0.5 mm from the strip's edge.
SLOT_GAP, SLOT_BACK_GAP, SLOT_WALL = 0.1, 0.5, 3.4  # walls grow so the outer faces stay in place
X0, Y0, Z0 = -52.75, -7.5, 10.0  # lowest corner of the 90.5 x 35 x 103 envelope
X1, Y1, Z1 = X0 + 90.5, Y0 + 35.0, Z0 + 103.0
SLAB_Y = Y0 + JETSON_SLAB_T  # top face of the flat tray and board
PORT_TOP_Y = Y0 + 7.6 + 1.57 + 16.7  # tray and feet (E), carrier board (O), USB and RJ45 stack (O)
PORT_X0 = X1 - 20.0  # the I/O band is about 20 mm deep (E)
HEAT_X = ((X0 + JETSON_STRIP_D) + PORT_X0) / 2  # between the board's far edge and the I/O band
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
    "Jetson tray strip": placed((X0, X0 + JETSON_STRIP_D), (Y0, Y0 + JETSON_STRIP_T), (Z0, Z1)),
    "Jetson tray and board": placed((X0 + JETSON_STRIP_D, X1), (Y0, SLAB_Y), (Z0, Z1)),
    "Jetson ports": placed((PORT_X0, X1), (SLAB_Y, PORT_TOP_Y), (MID_Z - 50, MID_Z + 50)),
    "Jetson heatsink": placed(HEAT_RANGE[0], (SLAB_Y, Y1), HEAT_RANGE[1]),
}

# USB sound card on the plate. Its USB-A plug is on one short end and the speaker connector and
# audio jack on the other (U, which end is unknown), so both end walls have a notch and both ends
# keep plug room up to the speaker's underside (Z 25) for an angled USB-A extension (U).
POCKET_GAP, POCKET_WALL = 1.0, 2.4  # loose pockets: clearance each side, and wall thickness
AUDIO_X, AUDIO_Y, AUDIO_Z = (-26.5, 26.5), (-54.9, -31.4), (7.6, 22.2)
AUDIO_NOTCH, AUDIO_PLUG = 16.0, 16.0  # notch width in each end wall (U); plug room past the wall
AUDIO_MID_Y = sum(AUDIO_Y) / 2
AUDIO_END = AUDIO_X[1] + POCKET_GAP + POCKET_WALL + AUDIO_PLUG  # plug room reaches this |X|

# Servo adapter board (Dylan: 42 x 32 x 13 mm; sold as 42 x 33). It stands on a short edge in the
# band between the audio case and the Jetson, its long edges facing -X and +X. The servo plug
# enters one long edge and the barrel plug the other (U, both near the same short end, so turn the
# board to put that end up or down as the USB port needs). The USB data port is on an unknown short
# end (U); the end that points up has plug room, and the board turns end for end if it is the other.
BUS_L, BUS_W, BUS_T = 42.0, 32.0, 13.0
BUS_CX = -12.0  # board center X: 12 mm for plug rooms beyond the barrel side's 40 mm
BAND_Y = (-28.0, -11.0)  # pocket interior between the audio wall and the Jetson wall
BUS_Y = sum(BAND_Y) / 2
BUS_Z = (7.6, 7.6 + BUS_L)
BUS_RIB_TOP_Z = BUS_Z[0] + 2.4  # end stop ribs; plug rooms start above them
PLUG_BARREL, PLUG_SERVO, PLUG_USB = 40.0, 25.0, 20.0  # room: 10 x 40 plug; 8 x 6 x 15 plus a bend

_bx0, _bx1 = BUS_CX - BUS_W / 2, BUS_CX + BUS_W / 2

# name: (size X, Y, Z, center X, Y, Z). Boxes are external envelopes, reservations included.
# Speaker: Waveshare 8 ohm 5 W. The rest are unmeasured (U).
BOXES = JETSON_PARTS | {
    "One speaker": ((100, 21, 45), (0, -45.5, 47.5)),
    "USB audio case": placed(AUDIO_X, AUDIO_Y, AUDIO_Z),
    "Audio plug space -": placed(
        (-AUDIO_END, AUDIO_X[0]),
        (AUDIO_MID_Y - AUDIO_NOTCH / 2, AUDIO_MID_Y + AUDIO_NOTCH / 2),
        (AUDIO_Z[0], 25.0),
    ),
    "Audio plug space +": placed(
        (AUDIO_X[1], AUDIO_END),
        (AUDIO_MID_Y - AUDIO_NOTCH / 2, AUDIO_MID_Y + AUDIO_NOTCH / 2),
        (AUDIO_Z[0], 25.0),
    ),
    "Bus interface": placed((_bx0, _bx1), (BUS_Y - BUS_T / 2, BUS_Y + BUS_T / 2), BUS_Z),
    "Bus barrel plug space": placed((_bx1, _bx1 + PLUG_BARREL), BAND_Y, (BUS_RIB_TOP_Z, BUS_Z[1])),
    "Bus servo plug space": placed((_bx0 - PLUG_SERVO, _bx0), BAND_Y, (BUS_RIB_TOP_Z, BUS_Z[1])),
    "Bus USB plug space": placed((_bx0, _bx1), BAND_Y, (BUS_Z[1], BUS_Z[1] + PLUG_USB)),
    "Jetson USB/power plugs": ((24, 34, 108), (49.75, 10, 62)),
    # 30 x 30 x 30 mm of slack for the camera cable, under the roof hole and on top of the plug
    # space above, which is the way down to a Jetson USB port.
    "Camera cable slack loop": placed((17, 47), (8, 38), (116, 146)),
    "Fan intake space": placed(HEAT_RANGE[0], (Y1, Y1 + 22), HEAT_RANGE[1]),
    "Outlet space": placed((-63, -55), (Y0 + JETSON_STRIP_T + SLOT_GAP + SLOT_WALL, Y1), (Z0, Z1)),
    "Camera rear cable space": ((43, 18, 43), (-24, 23, 208)),
}


def hardware():
    return [
        dict(name=name, shape=cq.Workplane("XY").box(*size).translate(center).val())
        for name, (size, center) in BOXES.items()
    ]
