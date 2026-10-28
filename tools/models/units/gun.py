"""GUN: gun turret - a T-90A turret with its 125 mm 2A46 on a cast concrete emplacement, the way surplus tank
turrets are set into fixed defences. The turret is cut from "T90" by Karnage (CC-BY-4.0,
sketchfab.com/3d-models/t90-8f577602505248f79e2b8a95f24b33fb) exactly as units/t90.py cuts it (same
measurements, same split); the tank hull is dropped. The emplacement is hand-built: an octagonal block 5.4 m
across and 1.3 m tall with a chamfered crown, a steel turret collar, a rear access door and vents."""

import math
import bpy
import convert
import t90
import _defences as D
from lib import box, cyl, extrude, mat

TOP = 1.3   # emplacement crown height; the turret ring sits on it


def build(wreck=False):
    o = convert.load(t90.SOURCE)
    convert.normalize(o, front="-Y", length=t90.LENGTH)
    r2 = (1.25 * t90.K) ** 2
    ring, gun = t90.RING, t90.GUN
    parts = convert.split(o, {
        "barrel": lambda c: abs(c.x - t90.GUN_X) < 0.2 and abs(c.z - t90.GUN_Z) < 0.2 and c.y > gun[1] - 0.15,
        "turret": lambda c: c.z > ring[2] + 0.02 and (c.x - ring[0]) ** 2 + (c.y - ring[1]) ** 2 < r2,
    }, rest="tank_hull")
    bpy.data.objects.remove(parts["tank_hull"], do_unlink=True)
    turret, barrel = parts["turret"], parts["barrel"]
    convert.pivot(turret, ring)
    convert.pivot(barrel, gun)
    convert.parent(barrel, turret)

    concrete = mat("concrete", D.CONCRETE)
    dark = mat("concrete_dark", D.CONCRETE_DARK)
    steel = mat("steel", D.STEEL)
    octagon = [(2.7 * math.cos(math.radians(22.5 + 45 * i)), 2.7 * math.sin(math.radians(22.5 + 45 * i))) for i in range(8)]
    hull = extrude("hull", octagon, TOP - 0.25, material=concrete, top_scale=0.96, bevel=0.04)
    crown = extrude("crown", [(x * 0.96, y * 0.96) for x, y in octagon], 0.25, (0, 0, TOP - 0.25), concrete,
                    top_scale=0.86, parent=hull)
    extrude("footing", [(x * 1.08, y * 1.08) for x, y in octagon], 0.18, material=dark, top_scale=0.97, parent=hull)
    cyl("collar", 1.7, 0.16, (0, 0, TOP + 0.02), steel, segments=24, parent=hull)
    box("door", (1.0, 0.08, 0.95), (0, -2.46, 0.62), steel, parent=hull, rot=(0, 0, 0))
    box("door_frame", (1.25, 0.12, 1.15), (0, -2.42, 0.62), dark, parent=hull)
    for x in (-1.6, 1.6):
        cyl("vent", 0.12, 0.5, (x, -1.3, TOP + 0.15), steel, segments=8, parent=hull)
        cyl("vent_cap", 0.2, 0.06, (x, -1.3, TOP + 0.42), steel, segments=8, parent=hull)
    # The turret stands on the collar, centred (parented first: its world matrix is still the source's).
    convert.parent(turret, hull)
    turret.location = (0.0, 0.0, TOP + 0.1)
    if wreck:
        turret.location.z += 0.2
        turret.location.x += 0.4
        turret.rotation_euler = (0.1, -0.16, 0.5)
        barrel.rotation_euler = (-0.22, 0, 0)
        D.shard_scatter(10, (-3.4, -3.4, 3.4, 3.4), parent=hull)
    return D.done(hull)


FINISH = {"flat": False}
PREVIEW = {"distance": 15, "target_z": 1.3}
