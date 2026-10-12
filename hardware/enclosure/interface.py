"""Shared positions between the body (body.py) and the neck and head (neck.py, head.py), in mm.
Assembly frame: X toward the Jetson ports, Y rearward, Z up, head yaw axis at X 0, Y 0.
"""

# Roof: part of the body shell. The neck enters through its center opening.
ROOF_TOP_Z = 160.0
ROOF_BOTTOM_Z = 156.8
ROOF_HOLE_D = 32.4

# Hub: sits on the roof top. M3 screws go down through it into nut pockets under the roof.
HUB_OD = 50.0
HUB_TOP_Z = 172.4  # bearings stack from the roof top; the shaft flange sits above
HUB_SCREWS_XY = ((20.0, 0.0), (0.0, 20.0), (0.0, -20.0))  # clear of the servo pocket walls

# Servo: STS3215 hangs from the horn disc, turned so its body runs toward -X (study rot 180).
# Case size and horn height come from a CAD model (U until checked on the owned servo).
SERVO_CASE = (45.4, 24.8, 28.8)
SERVO_CASE_CENTER_XY = (-10.11, 0.0)  # output shaft on the yaw axis
SERVO_CASE_TOP_Z = 148.0
SERVO_HORN_TOP_Z = 154.0
POCKET_CLEARANCE = 1.0  # each side and vertically; the pocket stops rotation only

# Head: its floor screws to the shaft flange with two M3 screws.
HEAD_FLOOR_Z = 180.0
# Front side, so a ball-end key reaches them through the front opening at about 20 degrees of tilt.
HEAD_SCREWS_XY = ((8.0, -20.0), (-8.0, -20.0))
