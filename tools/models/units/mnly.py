"""Minelayer (MNLY): a GMZ-3 tracked minelayer.

No model of it exists, so it is built on the GM-family chassis it shares with the 2S5: the hull and running
gear of "2S5 Giatsint-S (WARNO)" by KojfDiscord (CC-BY-4.0,
sketchfab.com/3d-models/2s5-giatsint-s-warno-80c611c463d84aa2b48b770e3add5ddd), with the gun, its cradle and the
recoil spade cut away. Built here: the armoured crew cab at the front (sloped glacis, vision blocks, hatches,
commander's cupola with a PKT), the raised mine-storage compartment behind it with its loading hatches, and at
the rear the mine chute and the furrow plough folded up on its arms for the march.
Real length 9.3 m with the plough, width 3.25 m, height 2.7 m. No turret."""

import math
import bpy

import _ruv
from lib import box, cyl, mat, prism

SOURCE = "2s5_giatsint-s_warno.glb"
LENGTH = 8.95          # the 2S5's own length: keeps the chassis at its real size
ROOF = 1.77            # hull roof height on the 2S5 chassis
REAR = -3.02           # rear hull plate
FRONT = 3.55


def _mats():
    return dict(olive=mat("gmz_olive", (0.36, 0.38, 0.27)), dark=mat("gmz_dark", (0.08, 0.08, 0.07)),
                steel=mat("gmz_steel", (0.26, 0.26, 0.24)), glass=mat("gmz_glass", (0.12, 0.15, 0.16)),
                rubber=mat("gmz_rubber", (0.06, 0.06, 0.05)), wood=mat("gmz_log", (0.3, 0.22, 0.13)),
                flag=mat("gmz_flag", (0.55, 0.5, 0.2)))


def _chassis():
    hull = _ruv.load(SOURCE, "-Y", LENGTH, tris=17000)
    # The gun, cradle, equilibrators and the rear recoil spade.
    _ruv.drop(hull, lambda c: c.z > ROOF + 0.08 or (c.y < REAR + 0.1 and 0.15 < c.z < 1.15))
    return hull


def _cab(hull, m):
    o = m["olive"]
    # Armoured cab over the front third: sloped glacis plate, flat roof.
    prism("cab", [(1.15, ROOF - 0.02), (FRONT - 0.45, ROOF - 0.02), (FRONT - 0.95, ROOF + 0.72),
                  (1.15, ROOF + 0.78)], 2.9, (0, 0, 0), o, parent=hull, bevel=0.03)
    # Vision blocks across the glacis and on the cab sides.
    for x in (-1.0, -0.55, 0.55, 1.0):
        box("vision", (0.26, 0.05, 0.12), (x, FRONT - 0.73, ROOF + 0.5), m["glass"], rot=(-55, 0, 0), parent=hull)
        box("vision_hood", (0.32, 0.12, 0.04), (x, FRONT - 0.8, ROOF + 0.6), o, rot=(-55, 0, 0), parent=hull)
    for s in (-1, 1):
        box("side_vision", (0.04, 0.24, 0.12), (s * 1.46, 2.2, ROOF + 0.48), m["glass"], parent=hull)
        box("headlamp", (0.2, 0.08, 0.14), (s * 1.15, FRONT - 0.42, ROOF + 0.08), m["glass"], parent=hull)
        box("lamp_guard", (0.26, 0.06, 0.2), (s * 1.15, FRONT - 0.36, ROOF + 0.09), m["steel"], parent=hull)
    # Driver's hatch (left) and commander's cupola with a PKT (right).
    cyl("hatch", 0.33, 0.07, (-0.75, 2.05, ROOF + 0.81), o, segments=16, parent=hull)
    box("hatch_hinge", (0.4, 0.08, 0.06), (-0.75, 1.72, ROOF + 0.82), m["steel"], parent=hull)
    cyl("cupola", 0.42, 0.22, (0.7, 1.75, ROOF + 0.88), o, segments=18, parent=hull, bevel=0.02)
    cyl("cupola_hatch", 0.3, 0.06, (0.7, 1.7, ROOF + 1.02), o, segments=16, parent=hull)
    for k in range(4):
        a = math.radians(-60 + k * 40)
        box("periscope", (0.12, 0.06, 0.1), (0.7 + 0.4 * math.sin(a), 1.75 + 0.4 * math.cos(a), ROOF + 0.9),
            m["glass"], parent=hull)
    box("pkt", (0.12, 0.75, 0.12), (0.92, 2.3, ROOF + 1.05), m["dark"], parent=hull)
    cyl("pkt_barrel", 0.025, 0.55, (0.92, 2.9, ROOF + 1.06), m["dark"], axis="Y", parent=hull)
    box("pkt_ammo", (0.18, 0.22, 0.16), (0.78, 2.2, ROOF + 1.0), m["olive"], parent=hull)
    # Antenna and a smoke grenade bank on the cab's rear corners.
    cyl("antenna_base", 0.06, 0.16, (-1.25, 1.3, ROOF + 0.86), m["dark"], parent=hull)
    cyl("antenna", 0.012, 2.2, (-1.25, 1.3, ROOF + 1.95), m["dark"], segments=6, parent=hull)
    for k in range(3):
        cyl("smoke", 0.05, 0.25, (1.3 - k * 0.12, 1.25, ROOF + 0.88), m["dark"], axis="Y", segments=8,
            parent=hull)


def _storage(hull, m):
    o = m["olive"]
    # Mine-storage compartment: a raised box from the cab back to the rear plate.
    y0, y1 = REAR + 0.05, 1.18
    prism("store", [(y0, ROOF - 0.02), (y1, ROOF - 0.02), (y1, ROOF + 0.55), (y0 + 0.25, ROOF + 0.55),
                    (y0, ROOF + 0.3)], 2.7, (0, 0, 0), o, parent=hull, bevel=0.025)
    # Two big loading hatches with hinges and grab handles.
    for k, y in enumerate((-0.15, -1.55)):
        box("load_hatch", (1.9, 1.15, 0.05), (0, y, ROOF + 0.58), o, bevel=0.01, parent=hull)
        for x in (-0.6, 0.6):
            box("hinge", (0.22, 0.08, 0.06), (x, y + 0.6, ROOF + 0.6), m["steel"], parent=hull)
        box("handle", (0.3, 0.04, 0.05), (0, y - 0.5, ROOF + 0.63), m["steel"], parent=hull)
    # Stowage boxes and an unditching log on the fenders, tow cables on the flanks.
    for s in (-1, 1):
        for y in (-2.2, -0.9, 0.4):
            box("fender_box", (0.3, 1.0, 0.36), (s * 1.42, y, ROOF + 0.02), o, bevel=0.02, parent=hull)
            box("box_latch", (0.04, 0.08, 0.1), (s * 1.58, y, ROOF + 0.05), m["steel"], parent=hull)
        cyl("tow_cable", 0.035, 4.2, (s * 1.36, -0.9, ROOF + 0.3), m["steel"], axis="Y", segments=6, parent=hull)
    cyl("log", 0.13, 2.6, (0, REAR + 0.15, ROOF + 0.7), m["wood"], axis="X", segments=10, parent=hull)
    for x in (-0.9, 0.9):
        box("log_strap", (0.05, 0.3, 0.3), (x, REAR + 0.15, ROOF + 0.7), m["dark"], parent=hull)
    # Marker-pole rack: pennant poles stowed upright at the rear corners, used to mark the minefield.
    for s in (-1, 1):
        box("pole_rack", (0.3, 0.3, 0.5), (s * 1.15, REAR + 0.45, ROOF + 0.8), m["steel"], parent=hull)
        for k in range(4):
            x = s * 1.15 + (k % 2 - 0.5) * 0.14
            y = REAR + 0.45 + (k // 2 - 0.5) * 0.14
            cyl("pole", 0.015, 1.3, (x, y, ROOF + 1.2), m["dark"], segments=5, parent=hull)
            box("pennant", (0.01, 0.2, 0.12), (x, y - 0.1, ROOF + 1.78), m["flag"], parent=hull)


def _plough(hull, m, wreck):
    """Mine chute down the rear and the furrow plough folded up behind it; returns the plough frame."""
    st, o = m["steel"], m["olive"]
    # Chute: an inclined trough from the storage roof down to just above the ground behind the hull.
    top, bottom = (REAR + 0.1, ROOF + 0.45), (REAR - 0.7, 1.25)
    length = math.dist(top, bottom)
    angle = math.degrees(math.atan2(top[1] - bottom[1], top[0] - bottom[0]))
    mid = ((top[0] + bottom[0]) / 2, (top[1] + bottom[1]) / 2)
    box("chute", (0.6, length, 0.06), (0, mid[0], mid[1]), st, rot=(angle, 0, 0), parent=hull)
    for s in (-1, 1):
        box("chute_wall", (0.05, length, 0.25), (s * 0.3, mid[0], mid[1] + 0.1), st, rot=(angle, 0, 0),
            parent=hull)
    box("chute_drive", (0.8, 0.35, 0.45), (0, REAR - 0.05, ROOF + 0.25), o, bevel=0.02, parent=hull)
    cyl("chute_roller", 0.1, 0.7, (0, bottom[0] + 0.05, bottom[1] + 0.05), m["dark"], axis="X", parent=hull)

    # Plough: two arms pivoting on the rear hull, a cross beam, the share and two cutting discs.
    pivot_y, pivot_z = REAR - 0.05, 1.3
    lift = 0 if wreck else -10      # degrees the plough is lifted off the ground for the march (arms aft, -y)
    frame = box("plough", (2.3, 0.18, 0.18), (0, pivot_y - 1.5, pivot_z), st, parent=hull)
    for s in (-1, 1):
        box("arm", (0.14, 1.55, 0.18), (s * 1.0, 0.78, 0), st, parent=frame)
        cyl("arm_pin", 0.11, 0.24, (s * 1.0, 1.5, 0), m["dark"], axis="X", parent=frame)
        cyl("disc", 0.33, 0.06, (s * 0.65, -0.1, -0.32), m["dark"], axis="X", segments=16, parent=frame)
        cyl("disc_hub", 0.08, 0.14, (s * 0.65, -0.1, -0.32), st, axis="X", parent=frame)
    prism("share", [(-0.4, -0.55), (0.25, -0.55), (0.2, 0.0), (-0.15, 0.0)], 0.7, (0, 0, 0), o, parent=frame)
    box("coulter", (0.05, 0.35, 0.55), (0, 0.15, -0.4), st, parent=frame)
    for s in (-1, 1):
        box("brace", (0.06, 0.06, 0.6), (s * 0.4, -0.05, -0.25), st, rot=(20, 0, 0), parent=frame)
        cyl("ram", 0.06, 1.2, (s * 0.7, 0.95, 0.4), st, axis="Y", parent=frame)
    # Fold about the arm pivots (on the hull): rotate the frame's placement about that axis.
    a = math.radians(lift)
    dy, dz = frame.location.y - pivot_y, frame.location.z - pivot_z
    frame.location.y = pivot_y + dy * math.cos(a) - dz * math.sin(a)
    frame.location.z = pivot_z + dy * math.sin(a) + dz * math.cos(a)
    frame.rotation_euler.x = a
    return frame


def build(wreck=False):
    hull = _chassis()
    m = _mats()
    _cab(hull, m)
    _storage(hull, m)
    plough = _plough(hull, m, wreck)


    if wreck:
        for o in list(bpy.data.objects):
            if o.name.startswith(("pole", "pennant", "antenna")):
                bpy.data.objects.remove(o, do_unlink=True)
        plough.location.z -= 0.25
        plough.rotation_euler = (0.15, 0.1, 0.12)
        _ruv.tilt(hull, roll=0.04, pitch=0.02, sink=0.06)
    return _ruv.done(hull)


FINISH = {"flat": False}
PREVIEW = {"distance": 14}
