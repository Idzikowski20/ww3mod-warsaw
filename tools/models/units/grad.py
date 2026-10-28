"""BM-21 Grad on the Ural-375D from "БМ-21 Град (BM-21 Grad)" by Basic Hsu (CC-BY-4.0,
sketchfab.com/3d-models/21-bm-21-grad-c90559a30e6a414d993a0d3bdf6c5ff8).
Real length 7.35 m. The 40-tube launcher and its traversing base turn as the turret."""

import convert
import _ruv

SOURCE = "-21___bm-21_grad.glb"
LENGTH = 7.35
AXLES = (2.41, -1.05, -2.43)   # wheel hubs along y; hub height 0.60, radius 0.60
RING = (0.0, -2.33, 1.62)   # launcher turntable centre on the rear bed (measured on the normalized model)


def build(wreck=False):
    o = _ruv.load(SOURCE, "-Y", LENGTH, shift_x=-0.15)
    for m in o.data.materials:      # the source's paint is a saturated toy green: Soviet olive drab instead
        if m and m.name in ("Body_blinn3", "Bump_blinn12"):
            next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"].default_value =                 (0.29, 0.31, 0.2, 1)
    parts = _ruv.split(o, {
        "turret": lambda c, m: abs(c.x) < 1.2 and ((c.z > RING[2] and -3.35 < c.y < -1.2) or (c.z > 2.2 and -3.35 < c.y < -0.3)),
    })
    hull, turret = parts["hull"], parts["turret"]
    if not wreck:   # cut before decimating: the source's tyres are clean separate shells
        _ruv.wheels(hull, AXLES, 0.60, 0.61, 0.7, hub_x=1.0, tris=500)
    convert.decimate(hull, 12000 if not wreck else 15000)
    convert.decimate(turret, 9000)
    convert.pivot(turret, RING)
    convert.parent(turret, hull)


    if wreck:
        _ruv.turret_off(turret, lift=0.06, rot=(-0.12, 0.1, 0.45))
        _ruv.tilt(hull, roll=0.05, pitch=0.015, sink=0.08)
    return _ruv.done(hull)


FINISH = {"flat": False, "keep": _ruv.keep_with_wheels(len(AXLES), "turret"),
          "export_options": _ruv.WHEEL_EXPORT}
PREVIEW = {"distance": 13}
