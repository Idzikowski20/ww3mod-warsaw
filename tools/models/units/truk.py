"""Supply truck: Ural-4320 6x6 from "Ural 4320" by Brout (CC-BY-4.0,
sketchfab.com/3d-models/ural-4320-f953c51a5dbc4a15949f4dcc0905c4e8). Real length 7.37 m. No turret."""

import _ruv
from lib import box, mat

SOURCE = "ural_4320.glb"
LENGTH = 7.37
AXLES = (2.235, -1.21, -2.565)   # wheel hubs along y; hub height 0.58, radius 0.57


def build(wreck=False):
    hull = _ruv.load(SOURCE, "-Y", LENGTH)
    if not wreck:
        _ruv.wheels(hull, AXLES, 0.58, 0.58, 0.75, hub_x=1.1)
    if wreck:
        # Tarpaulin burnt away down to the bare bows over a burnt-out load.
        _ruv.drop(hull, lambda c: c.z > 2.05 and c.y < 0.6)
        steel = mat("bow", (0.2, 0.19, 0.17))
        for i, y in enumerate((0.3, -0.9, -2.1, -3.3)):
            sag = (0.0, 0.12, -0.05, 0.2)[i]
            box("bow", (2.3, 0.05, 0.05), (0, y, 3.0 - sag), steel, parent=hull)
            for side in (-1, 1):
                box("bow", (0.05, 0.05, 1.0), (side * 1.15, y, 2.5 - sag / 2), steel, parent=hull)
        box("load", (2.0, 3.6, 0.35), (0, -1.5, 1.55), mat("ash", (0.12, 0.11, 0.1)), parent=hull)
        _ruv.tilt(hull, roll=0.06, pitch=-0.02, sink=0.1)
    return _ruv.done(hull)


FINISH = {"flat": False, "keep": _ruv.keep_with_wheels(len(AXLES)), "export_options": _ruv.WHEEL_EXPORT}
PREVIEW = {"distance": 13}
