"""Ranging system (MSAR), from "Renault TRM Radar Truck" by Muhamad Mirza Arrafi (CC-BY-4.0,
sketchfab.com/3d-models/renault-trm-radar-truck-1ad95e5724624a3bba7d36a686817efc): a 6x6 Renault TRM 10000
carrying a mast-mounted surveillance radar. Real length 9.0 m.

On the march the antenna stands still, squared fore-and-aft; msar_deployed.py turns it (idle clip). It cannot
fold flat: the dish hangs 2.6 m off the mast axis, so any fold puts it far outside the truck."""

import math
from mathutils import Matrix

import convert
import _ruv

SOURCE = "renault_trm_radar_truck.glb"
LENGTH = 9.0
SHIFT_X = -0.575            # the antenna overhangs one side: centre the truck, not its bounding box
AXLES = (2.87, -1.32, -2.51)   # wheel hubs along y; hub height 0.655, radius 0.64
MAST = (0.0, -1.3, 4.45)    # top of the mast housing on the mast axis (measured on the normalized model)


def truck():
    """The normalized source split into hull and antenna (a node turning about the mast axis)."""
    o = _ruv.load(SOURCE, "-Y", LENGTH, shift_x=SHIFT_X)
    parts = _ruv.split(o, {"antenna": lambda c, m: c.z > MAST[2]})
    hull, antenna = parts["hull"], parts["antenna"]
    antenna["node"] = True          # lib.finish keeps it as its own glTF node
    convert.pivot(antenna, MAST)
    convert.parent(antenna, hull)
    return hull, antenna


def wreck_pose(hull, antenna):
    antenna.location.z -= 0.3
    antenna.rotation_euler = (0.25, -0.15, 0.4)
    _ruv.tilt(hull, roll=-0.05, pitch=0.02, sink=0.1)


def build(wreck=False):
    hull, antenna = truck()
    # March: the dish squared to the truck's axis (the source has it turned 20 degrees), facing aft.
    antenna.rotation_euler.z = math.radians(-20)
    if not wreck:
        _ruv.wheels(hull, AXLES, 0.655, 0.66, 0.75, hub_x=1.07)
    else:
        wreck_pose(hull, antenna)
    return _ruv.done(hull)


FINISH = {"flat": False, "keep": _ruv.keep_with_wheels(len(AXLES), "antenna"),
          "export_options": _ruv.WHEEL_EXPORT}
PREVIEW = {"distance": 17, "target_z": 2.0}
