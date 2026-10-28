"""9K720 Iskander-M launcher (9P78-1 on the MZKT-7930) from "ISKANDER" by dofash_76 (CC-BY-4.0,
sketchfab.com/3d-models/iskander-244b511ee2ca4f3794d118b872ee229c).
Real length 13.07 m, height 3.3 m. The actor has no turret.

The source is a simple model posed mid-launch: one missile half-raised, the roof doors folded out. Here it is
in its march configuration: the body above the wheels brought down to the real 3.3 m (the source stands
4.1 m tall), the folded-out roof doors pulled in flush with the sides, and the missile laid down in its
cradle, nose forward, with its twin beside it (the 9P78-1 carries two)."""

import math
import convert
import _ruv

SOURCE = "iskander.glb"
LENGTH = 13.07
WHEEL_TOP = 1.4       # metres; above this the body is squashed
SQUASH = 0.73         # 4.1 m -> 3.3 m
HALF_WIDTH = 1.55     # real 3.07 m wide
# The missile axis in the normalized (unsquashed) source: base at the erector hinge, tip in the air.
BASE = (0.58, -5.14, 2.21)
TIP = (0.58, -1.67, 7.52)
RADIUS = 0.5
AXLES = (3.71, 1.21, -2.54, -5.00)   # wheel hubs along y; hub height 0.695, radius 0.69


def _on_missile(c):
    ax = [TIP[i] - BASE[i] for i in range(3)]
    n2 = sum(a * a for a in ax)
    t = sum((c[i] - BASE[i]) * ax[i] for i in range(3)) / n2
    d2 = sum((c[i] - BASE[i] - t * ax[i]) ** 2 for i in range(3))
    return -0.05 < t < 1.02 and d2 < RADIUS ** 2


def _squash(o):
    for v in o.data.vertices:
        if v.co.z > WHEEL_TOP:
            v.co.z = WHEEL_TOP + (v.co.z - WHEEL_TOP) * SQUASH
        if v.co.z > 2.9 and abs(v.co.x) > HALF_WIDTH:
            v.co.x = math.copysign(HALF_WIDTH, v.co.x)


def build(wreck=False):
    o = _ruv.load(SOURCE, "-X", LENGTH)
    parts = _ruv.split(o, {"missile": lambda c, m: _on_missile(c)})
    hull, missile = parts["hull"], parts["missile"]
    _squash(hull)
    if not wreck:
        _ruv.wheels(hull, AXLES, 0.695, 0.7, 0.9, "Mat.5", hub_x=1.27)
    rim = _ruv.top(hull, 1.45, -2.0)    # top of the missile bay's side walls

    # Lay the missile down: pivot on its base, swing the nose forward and down to level (the hull sits at
    # the origin unrotated, so its local space is world space).
    convert.pivot(missile, BASE)
    convert.parent(missile, hull)
    rise = math.atan2(TIP[2] - BASE[2], TIP[1] - BASE[1])
    missile.rotation_euler = (-rise, 0, 0)
    missile.location = (0.5, -5.6, rim - 0.45)
    twin = missile.copy()
    twin.data = missile.data.copy()
    hull.users_collection[0].objects.link(twin)
    twin.location.x = -0.5


    if wreck:
        bpy_remove(twin)
        missile.rotation_euler = (-0.25, 0.3, 0.12)
        missile.location = (0.3, -5.6, rim - 0.75)
        _ruv.tilt(hull, roll=-0.04, pitch=0.01, sink=0.1)
    return _ruv.done(hull)


def bpy_remove(o):
    import bpy
    bpy.data.objects.remove(o, do_unlink=True)


FINISH = {"flat": False, "keep": _ruv.keep_with_wheels(len(AXLES)), "export_options": _ruv.WHEEL_EXPORT}
PREVIEW = {"distance": 20}
