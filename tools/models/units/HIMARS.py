"""M142 HIMARS from "Ukrainian M142 HIMARS" by 42manako (CC-BY-4.0,
sketchfab.com/3d-models/ukrainian-m142-himars-95d255cd685e4cc5afc35ba5f58679d4). Real length 7.0 m.
The damaged-panel variants in the source are dropped; the launcher pod is cut out by position."""

import convert
import _usveh

SOURCE = "m142_himars.glb"
LENGTH = 7.0
PIVOT = (0.0, -1.5, 1.15)     # launcher turntable centre on the rear deck
WHEELS = _usveh.wheel_names(6)


def build(wreck=False):
    o = _usveh.load(SOURCE, keep=lambda n, lo, hi: "_dam" not in n,
                    group=lambda n, lo, hi: "wheel" if n.startswith("wheels_") else "body")
    convert.raw_colours(o)
    # The source wears Ukrainian camouflage with white crosses: paint them out, then repaint it the plain
    # CARC green of a US Army HIMARS.
    _usveh.erase_white(o, {"Image_0", "Image_2", "Image_3"}, threshold=0.28)
    _usveh.paint(o, _usveh.GREEN, gain=9.0, amount=1.0, only={"Image_0", "Image_2"}, flatten=0.8)
    convert.normalize(o, front="+Y", length=LENGTH)
    convert.weld(o)               # after normalize: the source is in millimetre-sized units
    parts = _usveh.split(o, {
        "wheel_l": lambda c, g: g == "wheel" and c.x < 0,
        "wheel_r": lambda c, g: g == "wheel",
        "turret": lambda c, g: (c.y < 0.15 and c.z > 1.18) or (c.z > 2.45 and c.y < 1.0),
    }, rest="hull")
    hull, turret = parts["hull"], parts["turret"]
    convert.pivot(turret, PIVOT)
    convert.parent(turret, hull)
    # The three axles' wheels, one node per wheel (front to back, left then right), pivot on the hub.
    wheels = []
    for side in ("wheel_l", "wheel_r"):
        for w in _usveh.split_axles(parts[side], 3):
            wheels.append(w)
    wheels.sort(key=lambda w: (-w.matrix_world.translation.y, w.matrix_world.translation.x))
    for i, w in enumerate(wheels, 1):
        w.name = f"wheel_{i}" if not wreck else f"tyre_{i}"
        convert.parent(w, hull)
    if not wreck:
        _usveh.spin_wheels(wheels)

    if wreck:
        turret.location.z -= 0.08
        turret.rotation_euler = (-0.12, 0.2, 0.55)
    return _usveh.done(hull)


FINISH = {"flat": False, "keep": ("hull", "turret", "barrel") + WHEELS, "export_options": _usveh.NLA}
