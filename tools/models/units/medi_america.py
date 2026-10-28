"""US Medic (MEDI.america): rifle, medical bag.
Rigid-part soldier built by _infantry.soldier(). Sources:
- Figure: "Soldier Full Tactical Gear" by DanlyVostok (CC-BY-4.0, sketchfab.com/3d-models/soldier-full-tactical-gear-850593a8c7114c188395ba1849a66eb9).
- "M4 Carbine" by SINNIK (CC-BY-4.0, sketchfab.com/3d-models/m4-carbine-b516a8416b1044a7839b4a89dc24ca38).
- "Medical Kit Bag" by yronthal (CC-BY-4.0, sketchfab.com/3d-models/medical-kit-bag-abc2f95bce4c4e69bfc0d8742d37e78b).
- Motion: "Human Soldier Animations 2.0 FREE" by Kevin Iglesias (Unity Asset Store EULA).
"""

import _infantry as inf


def kit(fig):
    inf.carry(fig, inf.load_kit("medbag", "medbag"), segment="pelvis", height=0.02)


def build(wreck=False):
    return inf.soldier("america", "m4", kit=kit)


FINISH = inf.FINISH
WRECK = False
PREVIEW = inf.PREVIEW
