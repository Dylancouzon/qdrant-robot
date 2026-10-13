"""Offline robot viewer and assembly guide. STEPS below is the single list of assembly steps. This
script writes the parts and steps into ASSEMBLY.md and builds output/robot-viewer.html, which shows
each step as a 3D picture next to its text. Run bambu.py first (it supplies times and grams), then
run this with build/hardware-layout/venv/bin/python. Check the page with check-viewer.cjs.
"""

import base64
import json
import re
import sys
from dataclasses import dataclass
from html import escape
from math import atan2, copysign, degrees, hypot
from pathlib import Path

import cadquery as cq
import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent)]
import body  # noqa: E402
import head  # noqa: E402
import neck  # noqa: E402
from interface import HUB_SCREWS_XY, ROOF_BOTTOM_Z  # noqa: E402

OUT = HERE / "output" / "robot-viewer.html"
GUIDE = HERE / "ASSEMBLY.md"
WHITE, BLACK, STEEL, STEEL_DARK = "#e8e6df", "#2b2b2e", "#9aa0a8", "#7a7f87"
# stem: (color, print orientation, plain name, what it is); print order is the table order
PARTS = {
    "body-shell": ("White", "Upside down, roof on the bed", "Body shell",
                   "The white tapered shell. It holds the servo under its roof and carries the "
                   "neck hub."),
    "base-plate": ("White", "Flat, underside on the bed", "Base plate",
                   "The white floor. Its pockets hold the Jetson, the USB sound card, the speaker,"
                   " and the servo adapter board."),
    "port-panel": ("White", "Outside face on the bed", "Port panel",
                   "The white cover for the port window on the port side."),
    "head-shell": ("White", "Rear face on the bed", "Head shell",
                   "The white box that forms the head. It screws to the head shaft."),
    "visor": ("Black", "Front face on the bed", "Visor",
              "The black front plate of the head. It holds the camera on four posts."),
    "speaker-grille": ("Black", "Inside face on the bed", "Speaker grille",
                       "The black plate with holes in the front window. Sound passes through its "
                       "holes."),
    "neck-hub": ("Black", "Lower face on the bed", "Neck hub",
                 "The black ring on the roof that holds the two bearings."),
    "head-shaft": ("Black", "Flange on the bed", "Head shaft",
                   "The black post that turns in the bearings. The head screws to its wide top, "
                   "the flange."),
    "horn-disc": ("Black", "Flat on the bed", "Horn disc",
                  "The black disc between the servo horn and the head shaft."),
}  # fmt: skip
# Hardware you supply: (name, what it is and does, what it connects to)
HARDWARE = (
    ("Jetson (Jetson Orin Nano Super developer kit)", "The computer. It runs the robot.",
     "Its four USB ports take the camera, the USB sound card, and the servo adapter board (data "
     "and power). Its own power cable leaves through the port window."),
    ("Jetson power supply (comes with the Jetson kit)",
     "Powers the Jetson from the wall.",
     "Its cable plugs into the Jetson power jack and leaves through the port window."),
    ("USB sound card (Waveshare USB to Audio)",
     "The small box that the speaker plugs into. It holds the microphone.",
     "Plugs into a Jetson USB port with an angled USB cable. The speaker lead plugs into it."),
    ("Speaker (Waveshare 8 Ω 5 W)", "Plays the robot's voice.",
     "Its lead plugs into the USB sound card."),
    ("Servo (Feetech STS3215, 7.4 V)",
     "Turns the head. The servo kit includes the horn, the arm on its output shaft, and the horn "
     "screw.",
     "Its lead plugs into the servo adapter board. The horn screws to the horn disc."),
    ("Servo adapter board (bus servo adapter from the SO-ARM100 kit, 42 × 32 × 13 mm)",
     "Lets the Jetson drive the servo.",
     "A USB data cable goes to a Jetson USB port. A USB-A to 5.5 × 2.1 mm barrel cable from a "
     "second Jetson USB port gives it 5 V, which also powers the servo. The build has no servo "
     "regulator. The servo lead plugs into it."),
    ("Camera (Arducam IMX291 USB board)", "The robot's eye.",
     "Screws to the four visor posts. Its USB cable leaves the head through a hole in the rear of "
     "the head floor, crosses the neck gap, and enters the body through a hole in the roof. It "
     "plugs into a Jetson USB port."),
    ("Bearings (two, 15 × 24 × 5 mm)", "Let the head shaft turn.",
     "Press into the neck hub, one on each side."),
    ("Servo adapter board USB data cable",
     "A USB cable that carries data between the servo adapter board and the Jetson.",
     "Joins the data port of the servo adapter board to a Jetson USB port."),
    ("USB-A to 5.5 × 2.1 mm barrel cable",
     "A cable that carries 5 V power to the servo adapter board.",
     "The barrel plug goes into the servo adapter board. The USB-A end goes into a second "
     "Jetson USB port."),
    ("Angled USB cables (three)",
     "USB cables with a right-angle plug. They fit the tight gaps inside the body.",
     "One joins the USB sound card to the Jetson, one joins the servo adapter board data port, "
     "and the camera cable ends in the third."),
)  # fmt: skip
# Hardware boxes from body.components() and head.ghost_solids(): name prefix, label, color. The
# first prefix that matches names the box, so a prefix covers every box that starts with it.
GHOSTS = (
    ("Jetson", "Jetson", "#477967"),
    ("Speaker", "Speaker", "#555960"),
    ("USB audio case", "USB sound card", "#767a84"),
    ("Bus board", "Servo adapter board", "#9a8d66"),
    ("servo case", "Servo", "#74738f"),
    ("servo horn", "Servo horn", "#a6a2b6"),
    ("bearing lower", "Bearing", "#8fa3b8"),
    ("bearing upper", "Bearing", "#8fa3b8"),
    ("camera connector", "Camera", "#3d6a9e"),
    ("camera", "Camera", "#3d6a9e"),
)
# screw group: (what it holds, nut, tool); counts and lengths come from the CAD constants
SCREWS = {
    "hub": ("Hub to the roof", True, "2.5 mm hex key from above"),
    "center": ("Shaft to the horn disc", True, "2.5 mm hex key from above"),
    "horn": ("Horn disc to the servo horn", False, "2.5 mm hex key through the disc"),
    "head": ("Head to the shaft flange", True, "2.5 mm ball-end key through the front, about 25°"),
    "visor": ("Visor to the head", True, "2.5 mm short-arm L-key from below"),
    "plate": ("Base plate to the shell", True, "2.5 mm hex key from the plate side"),
    "panel": ("Port panel to the plate ear", True, "2.5 mm hex key from outside"),
}
SHELLS = {"body-shell", "port-panel", "head-shell", "visor"}  # hidden by the cutaway control
MOVING = {  # keys that turn with the head
    "head-shell", "visor", "head-shaft", "horn-disc", "servo horn", "camera", "camera connector",
    "center screw", "disc nut", "horn screw", "flange nut", "head screw", "tab nut",
    "visor screw", "camera screw",
}  # fmt: skip
STEMS = {  # head.build() names to part names
    "head shell": "head-shell",
    "visor": "visor",
    "hub": "neck-hub",
    "head shaft": "head-shaft",
    "horn disc": "horn-disc",
}


def mesh_of(solid):
    vertices, faces = solid.tessellate(0.1, 0.3)
    mesh = trimesh.Trimesh([v.toTuple() for v in vertices], faces)
    mesh.merge_vertices()
    return mesh


def encode(array):
    return base64.b64encode(np.ascontiguousarray(array).tobytes()).decode()


def entry(name, key, label, color, kind, solid):
    "One mesh. `key` is what steps call it: several meshes (three hub nuts) share one key."
    mesh = mesh_of(solid)
    return dict(
        name=name,
        key=key,
        label=label,
        color=color,
        kind=kind,
        shell=name in SHELLS,
        moving=key in MOVING,
        center=[round(v, 1) for v in mesh.bounds.mean(axis=0)],
        vertices=encode(mesh.vertices.astype(np.float32)),
        indices=encode(mesh.faces.astype(np.uint32)),
    )


def fastener_solids():
    "Every screw and nut that the steps show, from the CAD positions."
    plate = ("plate", body.plate_screws(), body.CB_DEPTH, body.PLATE_SCREW_LEN, None, True)
    out = neck.screw_ghosts([*head.SCREWS, plate]) | head.nut_ghosts()
    for i, (x, y) in enumerate(HUB_SCREWS_XY):
        out[f"hub nut {i}"] = neck.nut_ghost((x, y), ROOF_BOTTOM_Z - 2.4, degrees(atan2(y, x)))
    for i, xy in enumerate(body.plate_screws()):
        out[f"corner nut {i}"] = neck.nut_ghost(xy, body.CORNER_NUT_Z[1] - 2.4, 0)
    back = head.BOARD_FRONT_Y + head.BOARD_T  # M2 heads sit behind the camera board
    for i, (x, z) in enumerate(head.standoff_xz()):
        shank = cq.Solid.makeCylinder(
            1.0, head.M2_LENGTH, cq.Vector(x, back - head.M2_LENGTH, z), cq.Vector(0, 1, 0)
        )
        cap = cq.Solid.makeCylinder(2.0, 1.6, cq.Vector(x, back, z), cq.Vector(0, 1, 0))
        out[f"camera screw {i}"] = shank.fuse(cap)
    y, z = body.PANEL_SCREW  # in the side wall frame: head in the counterbore, shank inward
    depth = body.PANEL_CB_DEPTH
    shank = cq.Solid.makeCylinder(
        1.5, body.PANEL_SCREW_LEN, cq.Vector(-depth, y, z), cq.Vector(-1, 0, 0)
    )
    cap = cq.Solid.makeCylinder(2.75, depth, cq.Vector(-depth, y, z), cq.Vector(1, 0, 0))
    out["panel screw"] = body.side_to_world(shank.fuse(cap))
    return out


def scene():
    "Every drawn mesh as JSON: base64 float32 vertices and uint32 triangle indices."
    solids = body.build_all()["assembly"] | {STEMS[k]: v for k, v in head.build()[0].items()}
    ghosts = {k: body.box(*b) for k, b in body.components().items()} | head.ghost_solids()
    out = []
    for name, solid in solids.items():
        color, _, label, _ = PARTS[name]
        out.append(entry(name, name, label, WHITE if color == "White" else BLACK, "printed", solid))
    for name, solid in ghosts.items():
        style = next((g for g in GHOSTS if name.startswith(g[0])), None)
        assert style, f"no GHOSTS prefix for hardware box {name!r}"
        out.append(entry(name, style[0], style[1], style[2], "ghost", solid))
    for name, solid in fastener_solids().items():
        key = re.sub(r" \d+$", "", name)
        color = STEEL_DARK if key.endswith("nut") else STEEL
        out.append(entry(name, key, key.capitalize(), color, "fastener", solid))
    return out


def fastener_rows():
    "(screw, length, count, nut, holds, tool) per group, from the CAD constants."
    counts = {name: (len(xys), length) for name, xys, _, length, _, _ in head.SCREWS}
    counts["plate"] = (len(body.plate_screws()), body.PLATE_SCREW_LEN)
    counts["panel"] = (1, body.PANEL_SCREW_LEN)
    rows = []
    for name, (holds, nut, tool) in SCREWS.items():
        count, length = counts[name]
        rows.append(("M3", int(length), count, nut, holds, tool))
    return rows + [("M2", head.M2_LENGTH, 4, False, "Camera to the visor posts", "M2 driver")]


def fastener_text():
    "Step wording per group: {hub} is '3 × M3 × 16 screw' and {hub_nut} is '3 × M3 nut'."
    out = {}
    for name, (size, length, count, nut, *_) in zip(
        [*SCREWS, "camera"], fastener_rows(), strict=True
    ):
        out[name] = f"{count} × {size} × {length} screw"
        if nut:
            out[f"{name}_nut"] = f"{count} × M3 nut"
    return out


# Steps -------------------------------------------------------------------------------------------
# Keys name meshes: a printed part stem, a GHOSTS prefix, or a fastener group such as "hub screw".
# Frame: X toward the Jetson ports, Y rearward (the front faces -Y), Z up.


@dataclass(frozen=True)
class Step:
    group: str
    title: str
    text: str  # at most three short sentences; {hub}, {hub_nut} and so on name the fasteners
    new: tuple  # keys drawn in orange: parts this step adds or works on
    view: tuple  # azimuth (0 is the front, 90 the port side), elevation, distance, target
    details: str = ""  # tolerances, tool angles, and other notes that a builder can skip
    moves: tuple = ()  # ((keys, offset), ...): offset is a vector, or a function of the part center
    reset: tuple | None = None  # keys shown instead of everything fitted so far; None keeps it
    cut: bool = False  # hide the shells so the inside shows
    tilt: float = 0.0  # degrees about X, turning the whole model before the view (see LYING)


def radial(d, corner=False):
    "Offset of d mm away from the yaw axis, or from the nearest plan corner center, in plan."

    def move(c):
        x0, y0 = (
            (copysign(body.CORNER[0], c[0]), copysign(body.CORNER[1], c[1])) if corner else (0, 0)
        )
        dx, dy = c[0] - x0, c[1] - y0
        return (d * dx / hypot(dx, dy), d * dy / hypot(dx, dy), 0)

    return move


UP, DOWN, REAR, FRONT, OUT_X = (0, 0, 1), (0, 0, -1), (0, 1, 0), (0, -1, 0), (1, 0, 0)


def away(direction, mm):
    return tuple(mm * v for v in direction)


NECK = ("body-shell", "neck-hub", "bearing lower", "bearing upper", "hub nut", "hub screw")
SERVO = ("servo case", "servo horn", "horn-disc", "disc nut", "horn screw")
SHAFT = ("center screw", "head-shaft", "flange nut", "head-shell", "head screw")
VISOR = ("visor", "tab nut", "camera", "camera connector", "camera screw")
UPPER = NECK + SERVO + SHAFT + VISOR + ("visor screw", "corner nut", "speaker-grille")
ON_PLATE = ("base-plate", "Jetson", "USB audio case", "Speaker", "Bus board")
LIFT = ((UPPER, away(UP, 60)),)  # the shell held 60 mm above the base plate
LYING = -(90 + body.LEAN_FRONT)  # tilt that lays the shell on its flat rear face

STEPS = (
    Step("Neck", "Press the two bearings into the neck hub.",
         "Press one bearing into each side of the hub, by its outer ring. Each bearing stops on "
         "the center shoulder.",
         ("bearing lower", "bearing upper"), (30, 10, 260, (0, 0, 167)),
         moves=((("bearing lower",), away(DOWN, 28)), (("bearing upper",), away(UP, 28))),
         reset=("neck-hub",)),
    Step("Neck", "Fit three nuts into the roof.",
         "Stand the body shell roof up on four 60 mm blocks. Take {hub_nut}. Hold each nut in "
         "tweezers, lower it through the roof hole to just under the roof, and push it outward "
         "into its channel until it clicks.",
         ("hub nut",), (0, -80, 260, (0, 0, 140)),
         "Each channel has a 0.3 mm ridge. The nut must click past it and stay. A nut that is "
         "let go falls through the hole. The blocks leave room to reach under the roof.",
         ((("hub nut",), radial(-10)),), reset=("body-shell",)),
    Step("Neck", "Screw the neck hub to the roof.",
         "Set the hub, with its bearings, over the roof hole, so its three screw holes sit over "
         "the nuts. The holes lie at the port side, the rear, and the front, and the stop post "
         "stands between the rear hole and the side with no hole. Drive {hub} down through the "
         "hub into the roof nuts.",
         ("neck-hub", "bearing lower", "bearing upper", "hub screw"), (0, 50, 300, (0, 0, 168)),
         "The hub fits one way only. The side with no hole faces away from the port side. Use the "
         "2.5 mm hex key from above.",
         moves=((("neck-hub", "bearing lower", "bearing upper"), away(UP, 30)),
                (("hub screw",), away(UP, 55)))),
    Step("Neck", "Fit the servo horn.",
         "Set the servo horn on the servo output shaft so the head will point forward. Fix it with "
         "the screw from the servo kit. Calibration at first power-on sets the exact middle.",
         ("servo case", "servo horn"), (30, 20, 200, (-10, 0, 140)),
         "The servo horn has 14.4° spline steps, so the head can sit up to 7.2° off forward until "
         "calibration.",
         ((("servo horn",), away(UP, 20)),), reset=()),
    Step("Neck", "Set the horn disc on the servo horn.",
         "Press {center_nut} into the pocket on the underside of the horn disc. Set the horn disc "
         "on the servo horn with the nut pocket down. Turn it until its four holes line up with "
         "the holes in the servo horn.",
         ("horn-disc", "disc nut"), (30, 20, 200, (0, 0, 150)),
         "Press the nut in until it snaps past the two lips. It must stay when you turn the horn "
         "disc over.",
         ((("horn-disc", "disc nut"), away(UP, 30)),), reset=("servo case", "servo horn")),
    Step("Neck", "Screw the horn disc to the servo horn.",
         "Drive {horn} through the horn disc into the servo horn. Use the 2.5 mm hex key.",
         ("horn screw",), (30, 20, 200, (0, 0, 150)),
         moves=((("horn screw",), away(UP, 22)),)),
    Step("Neck", "Slide the servo into the shell.",
         "Lay the shell on its rear face on the cloth. Slide the servo into its pocket through the "
         "open bottom, with the horn disc entering the roof hole. The servo rests on the long "
         "pocket wall under it.",
         SERVO, (-25, 25, 460, (0, 60, -5)),
         "The two long pocket walls stop the servo from turning. The rear face of the shell is "
         "flat, so the shell lies steady.",
         ((SERVO, away(DOWN, 45)),), reset=NECK, tilt=LYING),
    Step("Neck", "Insert the head shaft and drive the center screw.",
         "Turn the shaft until the two nut channels in its flange face the front. Push the shaft "
         "in through both bearings, so the hub post enters the arc slot under the flange. Drive "
         "{center} down the shaft bore into the nut in the horn disc.",
         ("head-shaft", "center screw"), (140, 25, 480, (0, 150, -5)),
         "Use the 2.5 mm hex key. The shaft clears the hub post only within about 60° of the "
         "front. A square boss on the horn disc fits the socket in the shaft. Do not overtighten: "
         "the shaft keeps 0.5 mm of axial play.",
         ((("head-shaft",), away(UP, 45)), (("center screw",), away(UP, 80))), tilt=LYING),
    Step("Head", "Slide two nuts into the shaft flange.",
         "Stand the shell upright on the four blocks, and take {head_nut}. Slide each nut to the "
         "end of its channel in the flange rim, until it clicks past the ridge.",
         ("flange nut",), (0, 25, 260, (0, 0, 178)),
         "",
         ((("flange nut",), radial(12)),)),
    Step("Head", "Screw the head shell to the flange.",
         "Set the head shell on the flange, with the front opening toward you and the visor off. "
         "Drive {head} down through the head floor into the nuts. Use the 2.5 mm ball-end key "
         "through the front opening.",
         ("head-shell", "head screw"), (0, 40, 430, (0, -10, 195)),
         "Tilt the key about 25° so it clears the top rim of the front opening and reaches the "
         "screws.",
         ((("head-shell",), away(UP, 40)), (("head screw",), away(UP, 65)))),
    Step("Head", "Slide two nuts into the visor tabs.",
         "Take {visor_nut}. Slide one nut into each tab slot from the rear of the visor, until it "
         "clicks past the ridge.",
         ("tab nut",), (160, 25, 260, (0, -25, 208)),
         "",
         ((("tab nut",), away(REAR, 15)),), reset=("visor",)),
    Step("Head", "Screw the camera to the visor posts.",
         "Set the camera board on the four posts, with the lens in the round hole. Drive {camera} "
         "through the board into the posts. Use a driver that fits the M2 head.",
         ("camera", "camera connector", "camera screw"), (160, 20, 300, (-10, -25, 208)),
         "The screws cut their own thread in the 1.7 mm pilot holes.",
         ((("camera", "camera connector"), away(REAR, 25)), (("camera screw",), away(REAR, 50)))),
    Step("Head", "Plug the USB cable into the camera.",
         "Plug the camera USB cable into the connector on the back of the camera board. The free "
         "end carries an angled USB-A plug. Leave the free end loose.",
         ("camera connector",), (160, 20, 300, (-10, -25, 208)),
         "An angled plug fits the gaps inside the body."),
    Step("Head", "Thread the camera cable into the body.",
         "Pass the free end down through the hole in the rear of the head floor. Lead it across "
         "the neck gap behind the hub, and down through the roof hole into the body. Leave a slack"
         " loop inside the body.",
         ("camera connector",), (150, 20, 360, (0, 10, 190)),
         "Both holes pass a USB-A plug, and they line up when the head faces forward. The slack "
         "loop absorbs the ±80° head turn.",
         ((VISOR, away(FRONT, 45)),), reset=NECK + SERVO + SHAFT + VISOR, cut=True),
    Step("Head", "Fit the visor to the head.",
         "Press the visor into the front opening of the head. Keep the cable slack and out of the "
         "pinch points. Drive {visor} up through the head floor lip into the tab nuts.",
         ("visor", "visor screw"), (20, -35, 330, (0, -20, 195)),
         "The ring on the visor locates it in the head opening. Use the 2.5 mm short-arm L-key "
         "from below.",
         ((VISOR, away(FRONT, 45)), (("visor screw",), away(DOWN, 25)))),
    Step("Body", "Fit the corner nuts.",
         "Take {plate_nut}. Reach up into the shell opening, and slide one nut into each corner "
         "channel until it clicks.",
         ("corner nut",), (0, -75, 430, (0, 0, 60)),
         "Each nut rests on a 2 mm floor and clicks past its ridge. Keep the nut flats along the "
         "channel walls.",
         ((("corner nut",), radial(-7, corner=True)),)),
    Step("Body", "Fit the speaker grille.",
         "Reach into the shell from below. Press the grille into the front window from the inside "
         "until it snaps.",
         ("speaker-grille",), (20, -35, 380, (0, -45, 50)),
         "The flange of the grille covers the window edge from behind.",
         ((("speaker-grille",), away(REAR, 25)),)),
    Step("Body", "Set the Jetson and the servo adapter board in the base plate.",
         "Take the base plate. Slide the plastic strip of the Jetson down into the slot, with the "
         "fan facing the rear vents and the ports toward the port side. Set the servo adapter "
         "board on its long edge in the pocket between the Jetson and the front pockets.",
         ("Jetson", "Bus board"), (40, 30, 650, (0, 0, 80)),
         "Each pocket leaves about 1 mm of clearance on each side. Nothing presses in.",
         ((("Jetson",), away(UP, 45)), (("Bus board",), away(UP, 40))), reset=("base-plate",)),
    Step("Body", "Set the USB sound card in its pocket and plug it in.",
         "Set the USB sound card in the front pocket. Plug an angled USB cable and the speaker "
         "lead into the card. Lead the USB cable up over the pocket walls and along the open band "
         "to a Jetson USB port on the port side.",
         ("USB audio case",), (40, 35, 480, (0, -30, 40)),
         "Do this before the speaker goes in, because the gap above the card is only 2.8 mm. Plug "
         "the Jetson end of the cable too, while the base plate is open.",
         ((("USB audio case",), away(UP, 40)),)),
    Step("Body", "Set the speaker on its rails.",
         "Lower the speaker onto the two rails above the card, and face it toward the front. Keep "
         "the speaker lead and the USB cable clear of the rails.",
         ("Speaker",), (40, 35, 480, (0, -30, 40)),
         moves=((("Speaker",), away(UP, 55)),)),
    Step("Body", "Connect the servo adapter board.",
         "Plug the board's USB data cable into a Jetson USB port. Plug the USB-A to 5.5 × 2.1 mm "
         "barrel cable into the board, and its USB-A end into a second Jetson USB port. Lead both "
         "cables up over the pocket walls and along the open band to the port side.",
         ("Bus board",), (40, 35, 480, (0, -30, 40)),
         "The barrel cable gives the servo 5 V."),
    Step("Body", "Plug in the servo lead and the camera cable.",
         "Lay the shell on its rear face on the cloth next to the base plate, with its open "
         "bottom toward the base plate. Plug the servo lead into the servo adapter board. Plug "
         "the camera USB cable into the last Jetson USB port.",
         ("servo case", "Bus board", "Jetson"), (60, 25, 900, (0, -80, 90)),
         "Both cables come out of the open bottom. The camera cable drops straight down from the "
         "roof hole on the port side to the last free Jetson USB port. Keep it clear of the other "
         "cables. The picture shows the shell "
         "upright and moved aside. Leave enough slack to lift the shell over the base plate.",
         moves=((UPPER, away(FRONT, 170)),), reset=ON_PLATE + UPPER, cut=True),
    Step("Body", "Lower the shell onto the base plate.",
         "Lift the shell over the base plate, and lower it straight down. Keep the servo lead and "
         "the camera cable clear of the base plate edge and the pockets.",
         ("body-shell",), (35, 15, 700, (0, 0, 110)), moves=LIFT),
    Step("Body", "Screw the shell to the base plate.",
         "Tip the robot onto its back on the cloth. Drive {plate} up through the base plate into "
         "the corner nuts. Use the 2.5 mm hex key from the plate side.",
         ("plate screw",), (0, -60, 430, (0, 0, 40)),
         "The heads sit in counterbores, so none stands below the base plate.",
         ((("plate screw",), away(DOWN, 25)),)),
    Step("Body", "Connect the Jetson power cable.",
         "Plug the cable of the Jetson power supply into the Jetson through the open port "
         "window. Route it out through the notch in the bottom edge of the window.",
         ("Jetson",), (90, 15, 480, (45, 10, 70)), cut=True),
    Step("Body", "Fit the port panel.",
         "Drop {panel_nut} into the slot in the base plate ear. Set the port panel in the port "
         "window. Drive {panel} through the panel into the nut.",
         ("port-panel", "panel screw"), (90, 10, 420, (60, 0, 70)),
         "Use the 2.5 mm hex key from outside.",
         ((("port-panel",), away(OUT_X, 30)), (("panel screw",), away(OUT_X, 55)))),
    Step("Body", "Check the head turn by hand.",
         "Keep the power off. Turn the head slowly from one stop to the other. The camera cable "
         "must slide freely through both holes, and nothing may rub.",
         ("head-shell", "visor"), (0, 10, 520, (0, 0, 150)),
         "The unpowered servo resists a little, so turn the head gently. The stops are at ±80°."),
)  # fmt: skip


def step_data(meshes):
    "STEPS as JSON rows: mesh indices to show, to color orange, and each moved mesh's offset."
    index = {}
    for i, m in enumerate(meshes):
        index.setdefault(m["key"], []).append(i)
    fasteners = fastener_text()
    fitted, rows = set(), []
    for n, s in enumerate(STEPS, 1):
        fitted = set(s.reset) if s.reset is not None else fitted
        fitted |= set(s.new)
        moved = {k for keys, _ in s.moves for k in keys}
        missing = (fitted | moved | set(s.new)) - set(index)
        assert not missing, f"step {n} names unknown keys {missing}"
        assert moved <= fitted, f"step {n} moves parts that are not fitted: {moved - fitted}"
        assert not s.cut or not any(meshes[i]["shell"] for k in s.new for i in index[k]), n
        assert len(re.findall(r"[.!?](?:\s|$)", s.text)) <= 3, f"step {n} has over three sentences"
        offsets = {}
        for keys, move in s.moves:
            for i in (i for k in keys for i in index[k]):
                vector = move(meshes[i]["center"]) if callable(move) else move
                offsets[i] = [round(v, 1) for v in vector]
        rows.append(dict(
            group=s.group, title=s.title, text=s.text.format(**fasteners), details=s.details,
            show=sorted(i for k in fitted for i in index[k]),
            new=sorted(i for k in s.new for i in index[k]),
            offsets=offsets, view=list(s.view[:3]), target=list(s.view[3]), cut=s.cut,
            tilt=round(s.tilt, 2),
        ))  # fmt: skip
    assert fitted == set(index), f"no step fits {set(index) - fitted}"
    return rows


# Page and guide text ----------------------------------------------------------------------------


def parts_table():
    slices = {
        Path(r["part"]).name: r
        for r in json.loads((HERE / "output" / "bambu" / "slice-checks.json").read_text())["parts"]
        if r["part"].startswith("Required")
    }
    assert set(slices) == set(PARTS), set(slices) ^ set(PARTS)
    rows = ""
    for stem, (color, orientation, name, what) in PARTS.items():
        s = slices[stem]
        size = " × ".join(f"{v:g}" for v in s["size_mm"])
        button = f'<button type="button" data-part="{stem}">{name}</button>'
        rows += (
            f"<tr><td>{button}</td><td>{color}</td><td>{what}</td><td>{orientation}</td><td>{size}</td>"
            f"<td>{s['seconds'] / 3600:.1f} h</td><td>{s['grams']:.0f} g</td></tr>"
        )
    hours = sum(s["seconds"] for s in slices.values()) / 3600
    grams = sum(round(s["grams"]) for s in slices.values())  # the sum of the rows shown
    return rows, f"{hours:.1f} h and {grams} g of PLA in total"


def hardware_html():
    return "".join(
        f"<tr><th scope='row'>{escape(n)}</th><td>{escape(what)}</td><td>{escape(link)}</td></tr>"
        for n, what, link in HARDWARE
    )


def fastener_table():
    rows = fastener_rows()
    html = "".join(
        f"<tr><td>{s} × {n}</td><td>{length} mm</td><td>{'yes' if nut else 'no'}</td>"
        f"<td>{holds}</td><td>{tool}</td></tr>"
        for s, length, n, nut, holds, tool in rows
    )
    m3 = sum(n for s, _, n, _, _, _ in rows if s == "M3")
    nuts = sum(n for _, _, n, nut, _, _ in rows if nut)
    return html, f"{m3} M3 screws, 4 M2 screws, and {nuts} M3 nuts"


def steps_html(rows):
    "One <ol> per group; each item carries a button that opens its step in the 3D view."
    out, group = "", None
    for n, s in enumerate(rows):
        if s["group"] != group:
            group = s["group"]
            out += ("</ol>" if n else "") + f"<h3>{group}</h3><ol start='{n + 1}'>"
        details = (
            f' <span class="note">Details: {escape(s["details"])}</span>' if s["details"] else ""
        )
        out += (
            f"<li><strong>{escape(s['title'])}</strong> {escape(s['text'])}{details} "
            f'<button type="button" data-step="{n}">Show step</button></li>'
        )
    return out + "</ol>"


def steps_markdown(rows):
    out, group = [], None
    for n, s in enumerate(rows, 1):
        if s["group"] != group:
            group = s["group"]
            out += ["", f"### {group}", ""]
        details = f" Details: {s['details']}" if s["details"] else ""
        out.append(f"{n}. **{s['title']}** {s['text']}{details}")
    return "\n".join(out).strip()


def parts_markdown():
    hardware = ["| Part | What it is | What it connects to |", "| --- | --- | --- |"]
    hardware += [f"| {n} | {what} | {link} |" for n, what, link in HARDWARE]
    printed = ["| Part | Color | What it is |", "| --- | --- | --- |"]
    printed += [
        f"| {name} (`{stem}`) | {c} | {what} |" for stem, (c, _, name, what) in PARTS.items()
    ]
    return (
        "### Parts you supply\n\n"
        + "\n".join(hardware)
        + "\n\n### Printed parts\n\n"
        + "\n".join(printed)
    )


def write_guide(rows):
    "Replace the generated blocks of ASSEMBLY.md between its <!-- name:start --> markers."
    text = GUIDE.read_text()
    for name, block in (("parts", parts_markdown()), ("steps", steps_markdown(rows))):
        pattern = rf"(<!-- {name}:start -->\n).*?(<!-- {name}:end -->)"
        text, found = re.subn(pattern, lambda m, b=block: m[1] + b + "\n" + m[2], text, flags=re.S)
        assert found == 1, (
            f"ASSEMBLY.md needs one <!-- {name}:start --> and <!-- {name}:end --> pair"
        )
    GUIDE.write_text(text)


def write_readme_total(total):
    "Keep the print total in README.md equal to the sum of the table rows."
    pattern = r"The nine parts take [\d.]+ h and \d+ g of PLA"
    text, found = re.subn(pattern, f"The nine parts take {total}", (HERE / "README.md").read_text())
    assert found == 1, "README.md needs the sentence 'The nine parts take ... of PLA'"
    (HERE / "README.md").write_text(text)


def main():
    data = scene()
    rows = step_data(data)
    write_guide(rows)
    part_rows, print_total = parts_table()
    write_readme_total(print_total.removesuffix(" in total"))
    fastener_rows_html, fastener_total = fastener_table()
    html = (
        TEMPLATE.replace("__DATA__", json.dumps(data, separators=(",", ":")))
        .replace("__STEPS__", json.dumps(rows, separators=(",", ":")))
        .replace("__STEP_COUNT__", str(len(rows)))
        .replace("__HARDWARE_ROWS__", hardware_html())
        .replace("__PART_ROWS__", part_rows)
        .replace("__PRINT_TOTAL__", print_total)
        .replace("__FASTENER_ROWS__", fastener_rows_html)
        .replace("__FASTENER_TOTAL__", fastener_total)
        .replace("__STEP_LIST__", steps_html(rows))
    )
    OUT.write_text(html)
    print(f"{OUT.name}: {len(html) / 1e6:.2f} MB, {len(data)} meshes, {len(rows)} steps")
    print(fastener_total)


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Robot assembly guide</title>
<style>
:root{--bg:#f4f2ec;--fg:#282b30;--card:#fffdf7;--line:#d6d2c8;--accent:#275c71;--muted:#5d6168;--new:#c25a0e}
@media(prefers-color-scheme:dark){:root{--bg:#1b1d21;--fg:#e6e4de;--card:#25282d;--line:#3a3e45;--accent:#8fc3d8;--muted:#a3a7ae;--new:#ff9a52}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif}
main{max-width:1100px;margin:auto;padding:24px 16px}
h1{font-size:26px;margin:0 0 8px}h2{margin-top:32px}h3{margin:24px 0 0}
a{color:var(--accent)}
canvas{width:100%;height:600px;display:block;border-radius:16px;background:#dfe3e8;touch-action:none}
.controls{display:flex;flex-wrap:wrap;gap:12px 24px;align-items:center;margin:12px 0}
.controls label{display:flex;gap:8px;align-items:center}
button{border:1px solid var(--line);background:var(--card);color:inherit;border-radius:8px;padding:8px 12px;cursor:pointer;font:inherit}
button[aria-pressed=true]{background:var(--fg);color:var(--bg)}
button:disabled{opacity:.45;cursor:default}
canvas:focus-visible,button:focus-visible,input:focus-visible{outline:3px solid var(--accent);outline-offset:3px}
.wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:14px}
th,td{text-align:left;vertical-align:top;padding:8px 12px;border-bottom:1px solid var(--line)}
li{margin:10px 0}.note{font-size:14px;color:var(--muted)}#error{color:#b03030}
#guide{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 16px;margin:12px 0}
#guide h2{margin:4px 0}#step-count{margin:0;color:var(--new);font-weight:600}
@media(max-width:720px){canvas{height:420px}}
</style></head><body><main>
<h1>Robot assembly guide</h1>
<p>Read <a href="#hardware">Parts you supply</a> and <a href="#printed-parts">Printed parts</a> first. Then press Next to follow __STEP_COUNT__ steps. Orange parts are the ones you work on in the current step. Each step shows the parts that are already fitted.</p>
<nav class="controls" aria-label="Page sections"><a href="#hardware">Parts you supply</a><a href="#printed-parts">Printed parts</a><a href="#fasteners">Fasteners</a><a href="#assembly">All steps</a></nav>
<section id="guide" aria-live="polite">
<p id="step-count"></p><h2 id="step-title"></h2><p id="step-text"></p><p id="step-details" class="note"></p>
<div class="controls"><button id="prev" type="button">Previous</button><button id="next" type="button">Next</button><button id="free" type="button">Free view</button></div>
</section>
<canvas id="scene" tabindex="0" aria-label="Interactive 3D view of the current assembly step"></canvas>
<p id="error" role="alert"></p>
<div class="controls">
<span role="group" aria-label="View"><button data-view="three" aria-pressed="true">3D</button> <button data-view="front" aria-pressed="false">Front</button> <button data-view="rear" aria-pressed="false">Rear</button> <button data-view="side" aria-pressed="false">Port side</button></span>
<label for="yaw">Head turn <input id="yaw" type="range" min="-80" max="80" value="0" step="1"> <output id="yaw-value">0°</output></label>
<label><input id="shells" type="checkbox" checked> Show shells</label>
<label><input id="ghosts" type="checkbox" checked> Show hardware and fasteners</label>
<span id="count" class="note"></span>
</div>
<p class="note">Drag to turn the view, scroll to zoom, and use the arrow keys when the view has focus. Translucent parts are hardware you supply.</p>
<section id="hardware"><h2>Parts you supply</h2>
<div class="wrap"><table><caption class="note">Everything the robot needs that is not printed</caption><thead><tr><th scope="col">Part</th><th scope="col">What it is</th><th scope="col">What it connects to</th></tr></thead><tbody>__HARDWARE_ROWS__</tbody></table></div></section>
<section id="printed-parts"><h2>Printed parts</h2>
<p>Select a part name to see it in orange. All parts print in PLA with a 0.4 mm nozzle, 0.2 mm layers, and no supports.</p>
<div class="wrap"><table><caption class="note">What each part is, its print orientation, size, and the Bambu Studio estimate for the P1S</caption><thead><tr><th scope="col">Part</th><th scope="col">Color</th><th scope="col">What it is</th><th scope="col">Orientation</th><th scope="col">Size (mm)</th><th scope="col">Time</th><th scope="col">PLA</th></tr></thead><tbody>__PART_ROWS__</tbody></table></div>
<p class="note">Estimate: __PRINT_TOTAL__. Print the coupon plate first.</p></section>
<section id="fasteners"><h2>Fasteners</h2>
<div class="wrap"><table><caption class="note">__FASTENER_TOTAL__</caption><thead><tr><th scope="col">Screw</th><th scope="col">Length</th><th scope="col">M3 nut</th><th scope="col">Holds</th><th scope="col">Tool</th></tr></thead><tbody>__FASTENER_ROWS__</tbody></table></div></section>
<section id="assembly"><h2>All steps</h2>
__STEP_LIST__
<p>Service is the same steps in reverse. The full guide is in ASSEMBLY.md.</p></section>
</main><script>
'use strict';
const parts = __DATA__;
const steps = __STEPS__;
const $ = id => document.getElementById(id);
const canvas = $('scene');
const gl = canvas.getContext('webgl', {antialias: true});
const VIEWS = {three: [35, 18], front: [0, 0], rear: [180, 0], side: [90, 0]};
const HOME = {az: 35, el: 18, dist: 640, target: [0, 0, 118]};
const ORANGE = [1, 0.48, 0.14];
const state = {...HOME, yaw: 0, shells: true, ghosts: true, selected: '', step: -1};
const rad = deg => deg * Math.PI / 180;
if (!gl) {
  $('error').textContent = 'This browser cannot display WebGL. The lists below still work.';
} else {
  start();
}

function decode(text, Type) {
  const bin = atob(text), bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Type(bytes.buffer);
}

// Flat shading: expand the indexed mesh so every triangle carries its own normal.
function expand(part) {
  const v = decode(part.vertices, Float32Array), idx = decode(part.indices, Uint32Array);
  const pos = new Float32Array(idx.length * 3), nor = new Float32Array(idx.length * 3);
  for (let t = 0; t < idx.length; t += 3) {
    const a = [0, 1, 2].map(k => idx[t + k] * 3);
    const u = [0, 1, 2].map(i => v[a[1] + i] - v[a[0] + i]);
    const w = [0, 1, 2].map(i => v[a[2] + i] - v[a[0] + i]);
    const n = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]];
    const len = Math.hypot(...n) || 1;
    for (let k = 0; k < 3; k++) for (let i = 0; i < 3; i++) {
      pos[(t + k) * 3 + i] = v[a[k] + i];
      nor[(t + k) * 3 + i] = n[i] / len;
    }
  }
  return {pos, nor, count: idx.length};
}

function perspective(fovy, aspect, near, far) {
  const f = 1 / Math.tan(fovy / 2), nf = 1 / (near - far);
  return [f / aspect, 0, 0, 0, 0, f, 0, 0, 0, 0, (far + near) * nf, -1, 0, 0, 2 * far * near * nf, 0];
}

function lookAt(eye, target) {
  const sub = (a, b) => a.map((x, i) => x - b[i]);
  const norm = a => a.map(x => x / Math.hypot(...a));
  const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const z = norm(sub(eye, target)), x = norm(cross([0, 0, 1], z)), y = cross(z, x);
  return [x[0], y[0], z[0], 0, x[1], y[1], z[1], 0, x[2], y[2], z[2], 0, -dot(x, eye), -dot(y, eye), -dot(z, eye), 1];
}

function multiply(a, b) {
  const out = new Array(16).fill(0);
  for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++) for (let k = 0; k < 4; k++) out[c * 4 + r] += a[k * 4 + r] * b[c * 4 + k];
  return out;
}

function start() {
  const vs = `attribute vec3 position;attribute vec3 normal;uniform mat4 viewProj;uniform float yaw;uniform float tilt;uniform vec3 offset;uniform vec3 light;varying float shade;
void main(){float c=cos(yaw),s=sin(yaw),ct=cos(tilt),st=sin(tilt);mat3 r=mat3(c,s,0.,-s,c,0.,0.,0.,1.);
mat3 t=mat3(1.,0.,0.,0.,ct,st,0.,-st,ct);
gl_Position=viewProj*vec4(t*(r*(position+offset)),1.);shade=0.4+0.6*abs(dot(t*(r*normal),light));}`;
  const fs = `precision mediump float;uniform vec4 color;varying float shade;void main(){gl_FragColor=vec4(color.rgb*shade,color.a);}`;
  const compile = (type, source) => {
    const s = gl.createShader(type);
    gl.shaderSource(s, source);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw Error(gl.getShaderInfoLog(s));
    return s;
  };
  const program = gl.createProgram();
  gl.attachShader(program, compile(gl.VERTEX_SHADER, vs));
  gl.attachShader(program, compile(gl.FRAGMENT_SHADER, fs));
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw Error(gl.getProgramInfoLog(program));
  gl.useProgram(program);
  const attribute = name => gl.getAttribLocation(program, name);
  const uniform = Object.fromEntries(['viewProj', 'yaw', 'tilt', 'offset', 'light', 'color'].map(k => [k, gl.getUniformLocation(program, k)]));
  for (const part of parts) {
    const mesh = expand(part);
    part.count = mesh.count;
    part.rgb = [1, 3, 5].map(i => parseInt(part.color.slice(i, i + 2), 16) / 255);
    for (const [key, data] of [['posBuffer', mesh.pos], ['norBuffer', mesh.nor]]) {
      part[key] = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, part[key]);
      gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
    }
    delete part.vertices;
    delete part.indices;
  }

  function draw() {
    const box = canvas.getBoundingClientRect(), ratio = Math.min(devicePixelRatio || 1, 2);
    canvas.width = Math.round(box.width * ratio);
    canvas.height = Math.round(box.height * ratio);
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.clearColor(0.875, 0.89, 0.91, 1);
    gl.enable(gl.DEPTH_TEST);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    gl.depthMask(true);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    const az = rad(state.az), el = rad(state.el), d = state.dist, target = state.target;
    const eye = [target[0] + d * Math.sin(az) * Math.cos(el), target[1] - d * Math.cos(az) * Math.cos(el), target[2] + d * Math.sin(el)];
    const matrix = multiply(perspective(rad(30), canvas.width / canvas.height, 50, 2000), lookAt(eye, target));
    const light = [eye[0] - target[0], eye[1] - target[1], eye[2] - target[2] + 0.4 * d].map((x, _, a) => x / Math.hypot(...a));
    gl.uniformMatrix4fv(uniform.viewProj, false, new Float32Array(matrix));
    gl.uniform3fv(uniform.light, light);
    const step = steps[state.step];
    const fitted = step && new Set(step.show), fresh = step && new Set(step.new);
    gl.uniform1f(uniform.tilt, rad(step?.tilt ?? 0));
    let shown = 0;
    for (const ghostPass of [false, true]) {
      gl.depthMask(!ghostPass);
      parts.forEach((part, i) => {
        if ((part.kind === 'ghost') !== ghostPass || (step && !fitted.has(i))) return;
        if (part.kind === 'printed' ? part.shell && !state.shells : !state.ghosts) return;
        const alpha = part.kind === 'ghost' ? 0.4 : 1;
        const orange = fresh ? fresh.has(i) : part.name === state.selected;
        gl.uniform1f(uniform.yaw, part.moving ? rad(state.yaw) : 0);
        gl.uniform3f(uniform.offset, ...(step?.offsets[i] ?? [0, 0, 0]));
        gl.uniform4fv(uniform.color, orange ? [...ORANGE, Math.max(alpha, 0.85)] : [...part.rgb, alpha]);
        for (const [name, key] of [['position', 'posBuffer'], ['normal', 'norBuffer']]) {
          gl.bindBuffer(gl.ARRAY_BUFFER, part[key]);
          gl.vertexAttribPointer(attribute(name), 3, gl.FLOAT, false, 0, 0);
          gl.enableVertexAttribArray(attribute(name));
        }
        gl.drawArrays(gl.TRIANGLES, 0, part.count);
        shown++;
      });
    }
    $('count').textContent = shown + ' parts shown';
  }

  const views = document.querySelectorAll('[data-view]');
  const press = name => { for (const b of views) b.setAttribute('aria-pressed', String(b.dataset.view === name)); };
  // Step n shows its own view and cutaway; step -1 is the free view of the whole robot.
  function goTo(n) {
    state.step = n;
    const s = steps[n];
    Object.assign(state, s ? {az: s.view[0], el: s.view[1], dist: s.view[2], target: s.target, shells: !s.cut} : {...HOME, shells: true});
    $('shells').checked = state.shells;
    press(s ? '' : 'three');
    $('step-count').textContent = s ? `${s.group}, step ${n + 1} of ${steps.length}` : 'Free view';
    $('step-title').textContent = s ? s.title : 'Look around, then press Next to start';
    $('step-text').textContent = s ? s.text : 'This is the finished robot. Each step shows the parts that are already fitted and draws the new parts in orange.';
    $('step-details').textContent = s ? s.details : '';
    $('prev').disabled = n < 1;
    $('next').disabled = n === steps.length - 1;
    $('free').disabled = n < 0;
    draw();
  }
  $('prev').onclick = () => goTo(state.step - 1);
  $('next').onclick = () => goTo(state.step + 1);
  $('free').onclick = () => goTo(-1);
  for (const button of document.querySelectorAll('[data-step]')) {
    button.onclick = () => {
      goTo(Number(button.dataset.step));
      canvas.scrollIntoView?.({block: 'center'});
    };
  }
  for (const button of views) {
    button.onclick = () => {
      [state.az, state.el] = VIEWS[button.dataset.view];
      press(button.dataset.view);
      draw();
    };
  }
  for (const button of document.querySelectorAll('[data-part]')) {
    button.onclick = () => {
      const name = state.selected === button.dataset.part ? '' : button.dataset.part;
      goTo(-1);
      state.selected = name;
      draw();
      canvas.scrollIntoView?.({block: 'center'});
    };
  }
  $('yaw').oninput = e => {
    state.yaw = Number(e.target.value);
    $('yaw-value').textContent = state.yaw + '°';
    draw();
  };
  for (const id of ['shells', 'ghosts']) {
    $(id).onchange = e => {
      state[id] = e.target.checked;
      draw();
    };
  }
  let drag = null;
  canvas.onpointerdown = e => { drag = [e.clientX, e.clientY]; };
  canvas.onpointerup = canvas.onpointercancel = () => { drag = null; };
  canvas.onpointermove = e => {
    if (!drag) return;
    state.az -= (e.clientX - drag[0]) * 0.5;
    state.el = Math.max(-80, Math.min(80, state.el + (e.clientY - drag[1]) * 0.5));
    drag = [e.clientX, e.clientY];
    draw();
  };
  canvas.onwheel = e => {
    e.preventDefault();
    state.dist = Math.max(120, Math.min(1000, state.dist * (e.deltaY > 0 ? 1.1 : 0.9)));
    draw();
  };
  canvas.onkeydown = e => {
    const turn = {ArrowLeft: [-10, 0], ArrowRight: [10, 0], ArrowUp: [0, 10], ArrowDown: [0, -10]}[e.key];
    if (!turn) return;
    e.preventDefault();
    state.az += turn[0];
    state.el = Math.max(-80, Math.min(80, state.el + turn[1]));
    draw();
  };
  new ResizeObserver(draw).observe(canvas);
  goTo(-1);
}
</script></body></html>
"""  # noqa: E501

if __name__ == "__main__":
    main()
