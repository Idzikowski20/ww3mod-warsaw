"""2S5 Giatsint-S 152 mm self-propelled gun from "2S5 Giatsint-S (WARNO)" by KojfDiscord (CC-BY-4.0,
sketchfab.com/3d-models/2s5-giatsint-s-warno-80c611c463d84aa2b48b770e3add5ddd).
Real length 8.95 m with the gun. The actor has no turret: the open-mounted gun stays part of the hull; the
wreck drops the barrel off its cradle."""

import convert
import _ruv

SOURCE = "2s5_giatsint-s_warno.glb"
LENGTH = 8.95
BREECH = (0.0, -1.05, 2.29)   # where the barrel leaves the cradle (measured on the normalized model)


def build(wreck=False):
    o = _ruv.load(SOURCE, "-Y", LENGTH, tris=24000)
    hull = o

    if wreck:
        # Barrel knocked off the cradle and slumped onto the deck; it is merged back into the hull.
        gun = _ruv.split(hull, {
            "gun": lambda c, m: abs(c.x) < 0.3 and c.z > 2.1 and c.y > BREECH[1],
        })["gun"]
        convert.pivot(gun, BREECH)
        convert.parent(gun, hull)
        gun.rotation_euler = (-0.07, 0, 0.06)
        _ruv.tilt(hull, roll=-0.035, pitch=0.02, sink=0.05)
    return _ruv.done(hull)


FINISH = {"flat": False}
PREVIEW = {"distance": 14}
