"""M1126 Stryker M-SHORAD from "Stryker" by gogiart (CC-BY-4.0, sketchfab.com/3d-models/stryker-acf116a1a4904b9e867a578b632aacef).
Real length 6.95 m. The source is a Stryker ICV with a remote weapon station: the station is cut away and the
M-SHORAD's RIwP turret (XM914 30 mm cannon, coaxial M240, 4-round Stinger pod on the left, two Hellfires on
the right) is modelled here by hand as the turret node, the 30 mm as its barrel node. The source wheels
(113k triangles) are replaced by hand-built ones at the same stations."""

import convert
import _usveh
from lib import box, cyl, mat, prism

SOURCE = "stryker.glb"
LENGTH = 6.95
WHEELS = {"Object_32", "Object_33", "Object_34", "Object_35"}
# Headlight and front-light parts: 400k triangles in a few square centimetres, dropped.
LIGHTS = {"Object_5", "Object_6", "Object_7", "Object_8", "Object_9", "Object_10", "Object_11", "Object_14",
          "Object_25", "Object_30", "Object_58", "Object_59", "Object_62", "Object_63", "Object_64"}
SLAT = {"Object_55", "Object_56"}   # the perforated side stowage boxes, decimated on their own
WHEEL_Y = (-2.07, -0.97, 0.33, 1.47)
WHEEL_X, WHEEL_R, WHEEL_W = 1.03, 0.5, 0.42
WHEELS = _usveh.wheel_names(8)
ROOF = 2.07
RING = (0.0, -1.3, ROOF)
GUN = (0.0, 0.55, 0.36)           # 30 mm trunnion, turret-local


def _source_part(n, lo, hi):
    return n not in WHEELS and n not in LIGHTS


def _rws(c):
    """The source's remote weapon station and its pedestal."""
    return c.z > ROOF + 0.1 and -2.65 < c.y < -0.85 and -1.0 < c.x < 0.6


def _wheels(hull, wreck):
    """Eight road wheels, front to back, left then right: nodes wheel_<n> with the origin on the hub."""
    rubber = mat("rubber", (0.07, 0.07, 0.065))
    green = mat("stryker_green", (0.3, 0.33, 0.24))
    wheels = []
    for y in sorted(WHEEL_Y, reverse=True):
        for s in (-1, 1):
            name = f"{'tyre' if wreck else 'wheel'}_{len(wheels) + 1}"
            w = cyl(name, WHEEL_R, WHEEL_W, (s * WHEEL_X + 0.03, y, WHEEL_R), rubber, axis="X", segments=20,
                    parent=hull, bevel=0.06)
            cyl("rim", 0.3, WHEEL_W + 0.02, (0, 0, 0), green, axis="X", segments=10, parent=w)
            cyl("hub", 0.12, WHEEL_W + 0.08, (0, 0, 0), green, axis="X", segments=8, parent=w)
            # Five spoke bolts on the outer face: the turning reads on screen.
            for k in range(5):
                import math
                a = k * 2 * math.pi / 5
                cyl("bolt", 0.035, 0.04, (s * (WHEEL_W / 2 + 0.03), 0.2 * math.cos(a), 0.2 * math.sin(a)), green,
                    axis="X", segments=6, parent=w)
            wheels.append(w)
    if not wreck:
        _usveh.spin_wheels(wheels)


def _riwp(hull, wreck):
    green = mat("stryker_green", (0.3, 0.33, 0.24))
    dark = mat("dark_metal", (0.1, 0.1, 0.09))
    glass = mat("glass", (0.05, 0.07, 0.08))
    olive = mat("missile_olive", (0.24, 0.27, 0.18))
    turret = cyl("turret", 0.58, 0.1, RING, dark, segments=24, parent=hull)
    # Faceted turret body, seen from the side: low nose, flat roof, sloped rear.
    prism("body", [(-0.62, 0.08), (0.42, 0.08), (0.62, 0.28), (0.5, 0.56), (-0.52, 0.6), (-0.68, 0.36)],
          0.98, (0, 0, 0), green, parent=turret, bevel=0.02)
    # EO/IR sight head on the roof, right of the gun.
    box("sight", (0.34, 0.32, 0.26), (0.24, 0.12, 0.72), green, parent=turret, bevel=0.02)
    box("sight_glass", (0.24, 0.02, 0.16), (0.24, 0.29, 0.72), glass, parent=turret)
    box("hatch", (0.36, 0.36, 0.04), (-0.22, -0.3, 0.62), green, parent=turret)
    # XM914 30 mm: mantlet on the turret, the gun is the barrel node.
    box("mantlet", (0.3, 0.26, 0.28), (0.0, 0.6, 0.36), green, parent=turret, bevel=0.02)
    barrel = box("barrel", (0.14, 0.5, 0.16), (GUN[0], GUN[1] + 0.25, GUN[2]), dark, parent=turret)
    cyl("tube_30", 0.04, 1.35, (0, 1.12, 0), dark, axis="Y", segments=10, parent=barrel)
    cyl("muzzle_30", 0.06, 0.16, (0, 1.8, 0), dark, axis="Y", segments=10, parent=barrel)
    barrel.location = (0, 0, 0)
    barrel.data.transform(convert.Matrix.Translation((0, 0.25, 0)))
    barrel.location = GUN
    # Coaxial M240, right of the cannon.
    box("m240", (0.07, 0.36, 0.09), (0.2, 0.62, 0.26), dark, parent=turret)
    cyl("m240_tube", 0.015, 0.5, (0.2, 1.04, 0.27), dark, axis="Y", segments=6, parent=turret)
    # Stinger pod (4 rounds, 2 x 2) on an arm on the left side.
    box("stinger_arm", (0.26, 0.2, 0.12), (-0.58, 0.05, 0.36), dark, parent=turret)
    box("stinger_pod", (0.34, 1.0, 0.4), (-0.84, 0.1, 0.42), green, parent=turret, bevel=0.02)
    for dx in (-0.08, 0.08):
        for dz in (-0.09, 0.09):
            cyl("stinger_cap", 0.065, 0.03, (-0.84 + dx, 0.61, 0.42 + dz), dark, axis="Y", segments=10,
                parent=turret)
    # Two Hellfires on a launcher rail on the right side.
    box("hellfire_arm", (0.26, 0.2, 0.12), (0.58, 0.05, 0.4), dark, parent=turret)
    box("hellfire_rail", (0.1, 1.1, 0.42), (0.76, 0.05, 0.42), green, parent=turret)
    for dz in (0.27, 0.57):
        cyl("hellfire", 0.09, 1.5, (0.9, 0.12, dz), olive, axis="Y", segments=12, parent=turret)
        cyl("hellfire_nose", 0.09, 0.14, (0.9, 0.94, dz), olive, axis="Y", segments=12, parent=turret,
            radius2=0.03)
    if wreck:
        turret.location.z += 0.12
        turret.rotation_euler = (0.1, 0.22, -0.9)
        barrel.rotation_euler = (-0.3, 0, 0)
    return turret


def build(wreck=False):
    o = _usveh.load(SOURCE, keep=_source_part, group=lambda n, lo, hi: "slat" if n in SLAT else "body")
    convert.raw_colours(o)
    # The source's paint is a blue-teal; the game's Stryker is US Army CARC green.
    _usveh.paint(o, _usveh.GREEN, amount=0.9, flatten=0.3)
    convert.normalize(o, front="+Y", length=LENGTH)
    parts = _usveh.split(o, {"rws": lambda c, g: g == "body" and _rws(c), "slat": lambda c, g: g == "slat"},
                         rest="hull")
    hull, slat = parts["hull"], parts["slat"]
    convert.bpy.data.objects.remove(parts["rws"], do_unlink=True)
    for part, budget in ((hull, 14000), (slat, 2500)):
        convert.weld(part)
        _usveh.drop_specks(part, 0.12)   # the rivets: they bake to black dots
        convert.decimate(part, budget)
    convert.parent(slat, hull)
    _wheels(hull, wreck)
    _riwp(hull, wreck)

    return _usveh.done(hull)


FINISH = {"flat": False, "keep": ("hull", "turret", "barrel") + WHEELS, "export_options": _usveh.NLA}
