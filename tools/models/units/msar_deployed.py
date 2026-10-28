"""Ranging system (MSAR) deployed: msar.py's Renault TRM radar truck (same source and credit) with its
antenna turning, one revolution every 6 s (idle clip)."""

import math
import bpy

import msar
import _ruv

PERIOD = 6.0     # seconds per revolution


def _spin(antenna):
    fps = bpy.context.scene.render.fps
    start = antenna.rotation_euler.z
    for i in range(9):      # eighth turns, so no sampled step is ambiguous
        antenna.rotation_euler.z = start + i * math.pi / 4
        antenna.keyframe_insert("rotation_euler", index=2, frame=i * PERIOD * fps / 8)
    _ruv.push(antenna, "idle")
    antenna.rotation_euler.z = start


def build(wreck=False):
    hull, antenna = msar.truck()
    if wreck:
        msar.wreck_pose(hull, antenna)
    else:
        _spin(antenna)
    return _ruv.done(hull)


FINISH = {"flat": False, "export_options": {"export_animation_mode": "NLA_TRACKS"}}
PREVIEW = msar.PREVIEW
