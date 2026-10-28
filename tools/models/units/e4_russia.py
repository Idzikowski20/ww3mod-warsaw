"""Russian Flame trooper (E4.russia): tank pack, wand.
Rigid-part soldier built by _infantry.soldier(). Sources:
- Figure: "FSB Operator" by Mateusz Woliński (CC-BY-4.0, sketchfab.com/3d-models/fsb-operator-43a561e941704eefb1ab0614be4f0049), its own rifle removed.
- Tank pack and wand: built by hand (the flamethrower.glb source could not be reduced).
- Motion: "Human Soldier Animations 2.0 FREE" by Kevin Iglesias (Unity Asset Store EULA).
"""

import _infantry as inf


def kit(fig):
    inf.carry(fig, inf.load_kit("tanks", "tanks"), height=0.18)


def build(wreck=False):
    return inf.soldier("russia", "flamer", kit=kit)


FINISH = inf.FINISH
WRECK = False
PREVIEW = inf.PREVIEW
