"""Test pieces for the first print. fit-test-plate.stl has a hub-style and a corner-style M3 nut
channel and the four M2 camera posts at 32.3 mm on a 40 x 40 frame. slot-test-piece.stl is 15 mm
of the Jetson slot: slide it onto the plastic strip of the real Jetson. Run with
build/hardware-layout/venv/bin/python; it writes both STLs to output/print/Test pieces/ and
asserts the printcheck numbers.
"""

import sys
from pathlib import Path

HARDWARE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HARDWARE)]
import printcheck  # noqa: E402
from body import (  # noqa: E402
    M3_CLEAR, NUT_AF, NUT_FLOOR, NUT_T, SLOT_GRIP, box, cyl, detent_ridges, hex_pocket, probe,
    to_print_mesh,
)  # fmt: skip
from geometry import JETSON_STRIP_T, SLOT_GAP, SLOT_WALL  # noqa: E402

OUT = Path(__file__).resolve().parent / "output" / "print" / "Test pieces"
PLATE_T, EDGE_Y = 3.2, 32.0  # plate thickness (the roof thickness); channel mouths sit at EDGE_Y
SEAT, CHANNEL_H = 3.8, NUT_T + 0.4  # mouth to nut centre (hub and corner); channel height
LENGTH = SEAT + 3.29 + 2.7  # block length: behind the pocket stays 2.7 mm thick
PITCH, POST_D, POST_H, PILOT_D = 32.3, 7.0, 7.0, 1.7  # camera posts as in head.py
SLOT_COUPON_H = 15.0  # height of the slot coupon
# name: (block width, solid below the channel, blind hole depth above the nut); channel and
# floor heights land on 0.2 mm layer boundaries
BLOCKS = {"hub": (12.0, PLATE_T, 0.0), "corner": (10.6, PLATE_T + 3.2, 2.1)}


def nut_block(width, below, blind):
    "Block with a nut channel open at u = 0, a hex pocket, and a screw hole, in channel frame."
    top = below + CHANNEL_H + NUT_FLOOR
    block = box(0, LENGTH, -width / 2, width / 2, 0, top)
    channel = box(-1, SEAT, -NUT_AF / 2, NUT_AF / 2, below, below + CHANNEL_H)
    channel = channel.cut(*detent_ridges(SEAT, below, below + CHANNEL_H))
    pocket = hex_pocket(SEAT, 0, below, below + CHANNEL_H)
    hole = cyl(SEAT, 0, M3_CLEAR / 2, below - blind if blind else -1, top + 1)
    return block, [channel, pocket, hole]


def build():
    plate = box(-20, 20, -20, EDGE_Y, 0, PLATE_T)
    cuts = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            xy = (sx * PITCH / 2, sy * PITCH / 2)
            plate = plate.fuse(cyl(*xy, POST_D / 2, 0, PLATE_T + POST_H))
            cuts.append(cyl(*xy, PILOT_D / 2, PLATE_T, PLATE_T + POST_H + 1))
    for x, (width, below, blind) in zip((10.0, -10.0), BLOCKS.values(), strict=True):
        block, block_cuts = nut_block(width, below, blind)
        move = lambda s, x=x: s.rotate((0, 0, 0), (0, 0, 1), -90).translate((x, EDGE_Y, 0))  # noqa: E731
        plate = plate.fuse(move(block))
        cuts += [move(c) for c in block_cuts]
    plate = plate.cut(*cuts).clean()
    assert plate.isValid() and len(plate.Solids()) == 1
    return plate


def check(plate):
    "Pockets, holes and ridges exist where the nuts and screws need them."
    for x, (_, below, blind) in zip((10.0, -10.0), BLOCKS.values(), strict=True):
        zm = below + CHANNEL_H / 2
        assert not probe(plate, x, EDGE_Y - SEAT, zm)  # pocket
        assert probe(plate, x, EDGE_Y - SEAT, 0.5) == (blind > 0)  # hub through, corner blind
        assert not probe(plate, x, EDGE_Y - SEAT, below + CHANNEL_H + 1.0)  # hole in the floor
        assert probe(plate, x + NUT_AF / 2 - 0.15, EDGE_Y - SEAT + 2.2, zm)  # ridge on a wall
    for sx in (-1, 1):
        for sy in (-1, 1):
            assert not probe(plate, sx * PITCH / 2, sy * PITCH / 2, PLATE_T + 3.0)  # camera pilot


def build_slot():
    "The slot's U (back wall and two side walls, open at +X and top), 15 mm tall, on the bed."
    width = JETSON_STRIP_T + 2 * SLOT_GAP
    y = width / 2 + SLOT_WALL
    blank = box(0, SLOT_WALL + SLOT_GAP + SLOT_GRIP, -y, y, 0, SLOT_COUPON_H)
    open_end = blank.BoundingBox().xmax + 1
    slot = box(SLOT_WALL, open_end, -width / 2, width / 2, -1, SLOT_COUPON_H + 1)
    return blank.cut(slot)


def check_slot(coupon):
    "The slot is the strip's width plus 0.5 mm a side, with 3 mm walls all round."
    mid = SLOT_WALL + SLOT_GAP + SLOT_GRIP / 2
    half = JETSON_STRIP_T / 2 + SLOT_GAP
    assert not probe(coupon, mid, half - 0.05, 7.0) and probe(coupon, mid, half + 0.05, 7.0)
    assert probe(coupon, mid, half + SLOT_WALL - 0.05, 7.0)
    assert not probe(coupon, mid, half + SLOT_WALL + 0.05, 7.0)
    assert probe(coupon, SLOT_WALL - 0.05, 0, 7.0) and not probe(coupon, SLOT_WALL + 0.05, 0, 7.0)


def export(solid, name):
    mesh = to_print_mesh(solid)
    row = printcheck.analyze(mesh)
    assert row["floating_islands"] == 0 and row["thin_mm2"] == 0, row
    OUT.mkdir(parents=True, exist_ok=True)
    mesh.export(OUT / name)
    print(name, "ok", [round(float(v), 1) for v in mesh.extents], row)


def main():
    plate = build()
    check(plate)
    export(plate, "fit-test-plate.stl")
    slot = build_slot()
    check_slot(slot)
    export(slot, "slot-test-piece.stl")


if __name__ == "__main__":
    main()
