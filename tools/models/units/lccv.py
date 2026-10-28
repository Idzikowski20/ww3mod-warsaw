"""Logistics Centre MCV (LCCV, and the MCV husks): a KamAZ 6x6 with a command / logistics shelter (KUNG).

Chassis: "Kamaz 5330" by Brout (CC-BY-4.0, sketchfab.com/3d-models/kamaz-5330-e86a62f4b8c84e03b2c6e32c51474bc7).
Its cargo bed and tarpaulin are cut away; the shelter and its fittings are built here: a 5 m insulated box body
on a subframe with panel seams, side and rear doors with folding steps and ladders, windows, a roof air
conditioner, two whip antennas and a telescopic mast stowed along the roof, a rolled camouflage net, roof
rails, a diesel generator set and toolboxes on the frame, cable reels and jerrycans at the back.
Real length 7.6 m, height 3.8 m."""

import math

import _ruv
from lib import box, cyl, mat, prism

SOURCE = "kamaz_5330.glb"
LENGTH = 7.6
AXLES = (2.29, -1.26, -2.73)   # wheel hubs along y; hub height 0.575, radius 0.575

# The shelter, in the hull's space (metres; front +Y): over the bed the source carried.
Y0, Y1 = -3.72, 1.22          # rear and front faces
W = 2.5                       # width
Z0, Z1 = 1.42, 3.78           # floor and roof
YC = (Y0 + Y1) / 2
L = Y1 - Y0
H = Z1 - Z0


def _mats():
    return dict(olive=mat("kung_olive", (0.34, 0.37, 0.26)), dark=mat("kung_dark", (0.09, 0.09, 0.08)),
                steel=mat("kung_steel", (0.27, 0.27, 0.25)), glass=mat("kung_glass", (0.1, 0.13, 0.14)),
                rubber=mat("kung_rubber", (0.05, 0.05, 0.05)), net=mat("kung_net", (0.3, 0.3, 0.2)),
                can=mat("kung_can", (0.25, 0.3, 0.18)), red=mat("kung_lamp", (0.45, 0.06, 0.04)))


def _shelter(hull, m):
    """The box body and everything on it; returns the body (its parts are its children)."""
    o = m["olive"]
    # Subframe: two longitudinal beams and cross members carrying the body on the chassis frame.
    for x in (-0.45, 0.45):
        box("subframe", (0.16, L - 0.1, 0.16), (x, YC, Z0 - 0.1), m["dark"], parent=hull)
    body = box("body", (W, L, H), (0, YC, Z0 + H / 2), o, bevel=0.035, parent=hull)
    for i in range(6):
        box("cross", (W - 0.1, 0.12, 0.1), (0, Y0 + 0.4 + i * (L - 0.8) / 5, -H / 2 - 0.05), m["dark"],
            parent=body)
    # Panel seams (aluminium extrusions) on both sides and the roof edge trim.
    for i in range(1, 7):
        y = -L / 2 + i * L / 7
        for s in (-1, 1):
            box("seam", (0.03, 0.05, H - 0.06), (s * (W / 2 + 0.012), y, 0), o, parent=body)
    for s in (-1, 1):
        box("trim", (0.05, L + 0.02, 0.06), (s * (W / 2 + 0.01), 0, H / 2 - 0.03), m["steel"], parent=body)
        box("trim", (0.05, L + 0.02, 0.06), (s * (W / 2 + 0.01), 0, -H / 2 + 0.03), m["steel"], parent=body)

    # Side doors (left and right, near the front of the body) with a folding step under each.
    for s in (-1, 1):
        y = L / 2 - 1.05
        box("door", (0.04, 0.85, 1.85), (s * (W / 2 + 0.02), y, -0.12), o, bevel=0.01, parent=body)
        box("door_win", (0.02, 0.4, 0.3), (s * (W / 2 + 0.045), y, 0.38), m["glass"], parent=body)
        box("handle", (0.04, 0.12, 0.03), (s * (W / 2 + 0.06), y - 0.3, -0.1), m["steel"], parent=body)
        for k in range(3):
            box("hinge", (0.04, 0.05, 0.1), (s * (W / 2 + 0.05), y + 0.43, -0.85 + k * 0.7), m["steel"],
                parent=body)
        # Folding step ladder hanging below the door.
        for k in range(3):
            box("step", (0.3, 0.75, 0.04), (s * (W / 2 + 0.17), y, -H / 2 - 0.2 - k * 0.32), m["steel"],
                parent=body)
        for dy in (-0.37, 0.37):
            box("step_rail", (0.04, 0.04, 0.95), (s * (W / 2 + 0.17), y + dy, -H / 2 - 0.5), m["steel"],
                parent=body)
        # Windows along the side, with armoured shutters folded up above them.
        for y in (-1.6, -0.2):
            box("window", (0.02, 0.7, 0.45), (s * (W / 2 + 0.015), y, 0.35), m["glass"], parent=body)
            box("shutter", (0.05, 0.76, 0.06), (s * (W / 2 + 0.035), y, 0.64), m["steel"], parent=body)
        # Ventilation grilles low on the side.
        box("vent", (0.02, 0.5, 0.25), (s * (W / 2 + 0.015), -L / 2 + 0.6, -0.75), m["dark"], parent=body)

    # Rear: double door, ladder to the roof, cable reels and jerrycans, lamps.
    box("rear_door", (1.5, 0.04, 1.9), (0, -L / 2 - 0.02, -0.1), o, bevel=0.01, parent=body)
    box("rear_split", (0.02, 0.05, 1.85), (0, -L / 2 - 0.045, -0.1), m["dark"], parent=body)
    for x in (-0.35, 0.35):
        box("rear_handle", (0.03, 0.04, 0.25), (x * 0.3, -L / 2 - 0.06, -0.15), m["steel"], parent=body)
    for x in (-0.95, -1.15):
        box("ladder_rail", (0.04, 0.04, H + 0.4), (x, -L / 2 - 0.12, -0.15), m["steel"], parent=body)
    for k in range(8):
        box("rung", (0.24, 0.03, 0.03), (-1.05, -L / 2 - 0.12, -H / 2 - 0.2 + k * 0.33), m["steel"], parent=body)
    for x in (0.95, 0.95):
        cyl("reel", 0.28, 0.22, (x, -L / 2 - 0.16, -H / 2 + 0.45), m["dark"], axis="Y", segments=14, parent=body)
        cyl("reel_hub", 0.1, 0.26, (x, -L / 2 - 0.16, -H / 2 + 0.45), m["steel"], axis="Y", parent=body)
    for x in (0.75, 1.05):
        box("jerrycan", (0.17, 0.36, 0.48), (x, -L / 2 - 0.22, H / 2 - 0.85), m["can"], bevel=0.02, parent=body)
    box("can_rack", (0.6, 0.06, 0.06), (0.9, -L / 2 - 0.2, H / 2 - 0.58), m["steel"], parent=body)
    for x in (-1.1, 1.1):
        box("tail_lamp", (0.18, 0.04, 0.08), (x, -L / 2 - 0.03, -H / 2 + 0.12), m["red"], parent=body)

    # Roof: rails, air conditioner, mast stowed along the roof, whips, camouflage net, satcom terminal.
    r = H / 2
    for s in (-1, 1):
        box("rail", (0.04, L - 0.3, 0.04), (s * (W / 2 - 0.08), 0, r + 0.22), m["steel"], parent=body)
        for k in range(6):
            box("post", (0.04, 0.04, 0.22), (s * (W / 2 - 0.08), -L / 2 + 0.3 + k * (L - 0.6) / 5, r + 0.11),
                m["steel"], parent=body)
    box("aircon", (1.2, 0.8, 0.42), (0, L / 2 - 0.6, r + 0.21), o, bevel=0.03, parent=body)
    box("aircon_grille", (1.0, 0.02, 0.3), (0, L / 2 - 0.21, r + 0.22), m["dark"], parent=body)
    cyl("aircon_fan", 0.25, 0.03, (0, L / 2 - 0.6, r + 0.43), m["dark"], segments=16, parent=body)
    # Telescopic antenna mast lying in its cradles along the roof, head toward the rear.
    cyl("mast", 0.11, 3.6, (0.55, -0.35, r + 0.2), m["steel"], axis="Y", segments=10, parent=body)
    cyl("mast_sec", 0.075, 0.9, (0.55, -2.55, r + 0.2), m["steel"], axis="Y", segments=10, parent=body)
    box("mast_head", (0.5, 0.25, 0.12), (0.55, -2.25, r + 0.2), m["dark"], parent=body)
    for y in (0.9, -0.5, -1.8):
        box("cradle", (0.3, 0.08, 0.14), (0.55, y, r + 0.07), m["dark"], parent=body)
    cyl("mast_base", 0.2, 0.35, (0.55, 1.45, r + 0.17), m["dark"], segments=12, parent=body)
    # Rolled camouflage net on the left of the roof.
    cyl("net", 0.22, L - 1.4, (-0.75, -0.5, r + 0.22), m["net"], axis="Y", segments=12, parent=body)
    for y in (-2.2, -0.5, 1.1):
        box("strap", (0.47, 0.05, 0.46), (-0.75, y, r + 0.22), m["dark"], parent=body)
    # Satcom terminal (stowed) and two whip antennas on insulated bases at the front corners.
    cyl("satcom", 0.42, 0.12, (-0.55, 1.1, r + 0.25), m["olive"], segments=20, parent=body)
    cyl("satcom_base", 0.12, 0.2, (-0.55, 1.1, r + 0.1), m["dark"], parent=body)
    for s in (-1, 1):
        cyl("whip_base", 0.07, 0.18, (s * (W / 2 - 0.2), L / 2 - 0.15, r + 0.09), m["dark"], parent=body)
        cyl("whip", 0.015, 2.6, (s * (W / 2 - 0.2), L / 2 - 0.15, r + 1.4), m["dark"], segments=6, parent=body)
    return body


def _frame_kit(hull, m):
    """Under the body on the chassis frame: generator set, toolboxes, spare wheel."""
    # Diesel generator set (right side, between the front and middle axles).
    gx = 0.95
    box("genset", (0.6, 1.3, 0.75), (gx, 0.55, 0.95), m["olive"], bevel=0.03, parent=hull)
    for k in range(7):
        box("gen_louvre", (0.02, 0.9, 0.035), (gx + 0.31, 0.55, 0.72 + k * 0.07), m["dark"], parent=hull)
    cyl("gen_exhaust", 0.045, 0.6, (gx + 0.2, 0.0, 1.45), m["dark"], parent=hull)
    box("gen_panel", (0.02, 0.3, 0.25), (gx + 0.31, 1.0, 1.1), m["steel"], parent=hull)
    # Toolboxes (left side, behind the fuel tank) and a spare wheel hung under the rear of the frame.
    box("toolbox", (0.45, 0.8, 0.45), (-1.0, -0.35, 0.95), m["olive"], bevel=0.02, parent=hull)
    box("toolbox_lid", (0.47, 0.82, 0.04), (-1.0, -0.35, 1.19), m["steel"], parent=hull)
    cyl("spare", 0.52, 0.32, (0, -3.35, 0.8), m["rubber"], axis="Z", segments=18, parent=hull)
    # Power cable from the generator to the body's socket.
    cyl("cable", 0.03, 0.9, (gx - 0.2, 0.55, 1.35), m["dark"], axis="Y", parent=hull)


def build(wreck=False):
    hull = _ruv.load(SOURCE, "-Y", LENGTH)
    # The cargo bed (sides) and its tarpaulin are their own materials: cut both.
    parts = _ruv.split(hull, {"bed": lambda c, mname: mname in ("Bed_Top", "material")})
    import bpy
    bpy.data.objects.remove(parts["bed"], do_unlink=True)
    if not wreck:
        _ruv.wheels(hull, AXLES, 0.575, 0.6, 0.4, "Wheels", hub_x=1.05)
    m = _mats()
    body = _shelter(hull, m)
    _frame_kit(hull, m)


    if wreck:
        # Burnt out: the shelter sagging off its subframe and twisted, antennas gone.
        import bpy as _b
        for o in list(_b.data.objects):
            if o.name.startswith(("whip", "satcom", "aircon_fan")):
                _b.data.objects.remove(o, do_unlink=True)
        body.rotation_euler = (math.radians(-2.5), math.radians(4), math.radians(1.5))
        body.location.z -= 0.12
        _ruv.tilt(hull, roll=0.05, pitch=-0.02, sink=0.12)
    return _ruv.done(hull)


FINISH = {"flat": False, "keep": _ruv.keep_with_wheels(len(AXLES)), "export_options": _ruv.WHEEL_EXPORT}
PREVIEW = {"distance": 15}
