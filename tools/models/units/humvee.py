"""M1025 HMMWV from "Humvee Transport" by karmy2k (CC-BY-4.0,
sketchfab.com/3d-models/humvee-transport-48336bc41caf4fa1bdf147823a774111). Real length 4.57 m.
The source is an unarmed hardtop; the roof ring mount with gunner shield and M240B (the game unit fires
a 7.62 mm MG) is modelled here by hand and is the turret node."""

import convert
import _usveh
from lib import box, cyl, mat

SOURCE = "humvee_transport.glb"
LENGTH = 4.57
ROOF = 1.78
RING = (0.0, -0.35, ROOF)       # roof ring centre, behind the front seats
HUB_Y, HUB_Z, HUB_X = (1.665, -1.535), 0.445, 0.9   # wheel hubs (front, rear), measured on the source
TYRE_R = 0.46
WHEELS = _usveh.wheel_names(4)


def _ring_mount(hull, wreck):
    tan = mat("hmv_tan", (0.46, 0.41, 0.31))
    dark = mat("hmv_dark", (0.12, 0.12, 0.1))
    gun = mat("gunmetal", (0.1, 0.1, 0.09))
    turret = cyl("turret", 0.52, 0.08, RING, dark, segments=24, bevel=0.015, parent=hull)
    cyl("ring_hatch", 0.47, 0.03, (0, 0, 0.09), tan, segments=24, parent=turret)
    # Gunner protection kit: front shield in three angled panels with a slot for the gun, side plates.
    box("shield_l", (0.42, 0.04, 0.56), (-0.27, 0.46, 0.38), tan, parent=turret, bevel=0.01)
    box("shield_r", (0.42, 0.04, 0.56), (0.27, 0.46, 0.38), tan, parent=turret, bevel=0.01)
    box("shield_low", (0.14, 0.04, 0.24), (0, 0.46, 0.22), tan, parent=turret)
    box("shield_top", (0.14, 0.04, 0.12), (0, 0.46, 0.6), tan, parent=turret)
    for s in (-1, 1):
        box("wing", (0.36, 0.04, 0.56), (s * 0.62, 0.33, 0.38), tan, parent=turret, rot=(0, 0, -s * 40), bevel=0.01)
        box("side_plate", (0.04, 0.55, 0.42), (s * 0.55, -0.12, 0.31), tan, parent=turret, bevel=0.01)
        box("glass", (0.3, 0.03, 0.14), (s * 0.27, 0.48, 0.52), mat("glass", (0.08, 0.1, 0.1)), parent=turret)
    # M240B on a pintle.
    cyl("pintle", 0.03, 0.42, (0, 0.22, 0.21), dark, segments=8, parent=turret)
    box("cradle", (0.1, 0.16, 0.06), (0, 0.24, 0.44), dark, parent=turret)
    box("receiver", (0.08, 0.42, 0.12), (0, 0.26, 0.52), gun, parent=turret, bevel=0.01)
    box("feed_cover", (0.09, 0.16, 0.03), (0, 0.32, 0.6), gun, parent=turret)
    box("stock", (0.05, 0.26, 0.09), (0, -0.07, 0.5), gun, parent=turret)
    box("grip", (0.03, 0.04, 0.1), (0, 0.06, 0.43), gun, parent=turret)
    cyl("barrel_m240", 0.018, 0.62, (0, 0.78, 0.53), gun, axis="Y", segments=8, parent=turret)
    cyl("gas_tube", 0.012, 0.4, (0, 0.66, 0.5), gun, axis="Y", segments=6, parent=turret)
    cyl("flash_hider", 0.026, 0.09, (0, 1.12, 0.53), gun, axis="Y", segments=8, parent=turret)
    box("carry_handle", (0.02, 0.14, 0.05), (0.06, 0.62, 0.58), gun, parent=turret)
    box("ammo_can", (0.1, 0.27, 0.17), (-0.13, 0.28, 0.44), mat("olive", (0.25, 0.27, 0.16)), parent=turret)
    if wreck:
        turret.location.z += 0.06
        turret.rotation_euler = (0.2, -0.28, 1.1)
    return turret


def build(wreck=False):
    o = convert.load(SOURCE)
    convert.raw_colours(o)
    convert.normalize(o, front="-Y", length=LENGTH)
    hubs = [(sx * HUB_X, y, HUB_Z) for y in HUB_Y for sx in (-1, 1)]

    def on_wheel(h):
        return lambda c: c.x * h[0] > 0.7 * HUB_X and (c.y - h[1]) ** 2 + (c.z - h[2]) ** 2 < TYRE_R ** 2

    # Wreck: the wheels stay part of the hull (no wheel nodes, nothing turns).
    names = WHEELS if not wreck else tuple(f"tyre_{i}" for i in range(1, 5))
    parts = convert.split(o, {n: on_wheel(h) for n, h in zip(names, hubs)}, rest="hull")
    hull = parts["hull"]
    convert.decimate(hull, 16000)
    wheels = []
    for n, h in zip(names, hubs):
        w = parts[n]
        convert.decimate(w, 1600)
        convert.pivot(w, h)
        convert.parent(w, hull)
        wheels.append(w)
    if not wreck:
        _usveh.spin_wheels(wheels)
    _ring_mount(hull, wreck)

    return _usveh.done(hull)


FINISH = {"flat": False, "keep": ("hull", "turret", "barrel") + WHEELS, "export_options": _usveh.NLA}
PREVIEW = {"distance": 8}
