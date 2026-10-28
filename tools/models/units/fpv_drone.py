"""FPV drone (the drone operator's quadcopter): "FPV-dron_NonStop" by Viktor_ (CC-BY-4.0,
sketchfab.com/3d-models/fpv-dron-nonstop-c75dea6e3ae441ac87f292efb17f5bae). About 0.3 m across the props.
The four propellers are cut out as nodes (prop_fl/fr/rl/rr) and spin in the idle and move clips."""

import math

import bpy
from mathutils import Quaternion

import _infantry as inf
import convert

WIDTH = 0.30
# Propeller hubs (x, y) and the height of the propeller disc, measured in the normalized model.
PROPS = {"prop_fl": (-0.092, 0.093), "prop_fr": (0.092, 0.093), "prop_rl": (-0.092, -0.093), "prop_rr": (0.092, -0.093)}
PROP_Z = 0.068
PROP_R = 0.08


def build(wreck=False):
    o = inf.load_prop("fpv-dron_nonstop.glb", WIDTH, "+Y", tris=1800, name="body", axis="width", specks=0.004)
    parts = convert.split(o, {n: (lambda c, x=x, y=y: (c.x - x) ** 2 + (c.y - y) ** 2 < PROP_R ** 2
                                  and c.z > PROP_Z - 0.006) for n, (x, y) in PROPS.items()}, rest="body")
    for n, (x, y) in PROPS.items():
        p = parts.get(n)
        if p is None:
            continue
        convert.pivot(p, (x, y, PROP_Z))
        convert.parent(p, parts["body"])
        p.rotation_mode = "QUATERNION"
        spin = 1 if n in ("prop_fl", "prop_rr") else -1     # opposite pairs turn the other way
        for clip, steps in (("idle", 4), ("move", 3)):   # one turn in that many frames, a key per frame
            for i in range(steps + 1):
                p.rotation_quaternion = Quaternion((0, 0, 1), spin * i * 2 * math.pi / steps)
                p.keyframe_insert("rotation_quaternion", frame=i)
            ad = p.animation_data
            act = ad.action
            act.name = f"{clip}_{n}"
            for fc in inf._fcurves(act):
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
            track = ad.nla_tracks.new()
            track.name = clip
            strip = track.strips.new(clip, 0, act)
            if getattr(act, "slots", None) and hasattr(strip, "action_slot") and strip.action_slot is None:
                strip.action_slot = act.slots[0]
            ad.action = None
        p.rotation_quaternion = Quaternion()
    return parts["body"]


FINISH = {"flat": False, "keep": ("body", *PROPS), "texture_size": 512,
          "export_options": {"export_animation_mode": "NLA_TRACKS",
                             "export_optimize_animation_keep_anim_object": True}}
WRECK = False
PREVIEW = {"distance": 1.2, "target_z": 0.05}
