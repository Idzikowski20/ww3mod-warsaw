"""US Mortarman (MT.america): rifle, mortar on the back.
Rigid-part soldier built by _infantry.soldier(). Sources:
- Figure: "Soldier Full Tactical Gear" by DanlyVostok (CC-BY-4.0, sketchfab.com/3d-models/soldier-full-tactical-gear-850593a8c7114c188395ba1849a66eb9).
- "M4 Carbine" by SINNIK (CC-BY-4.0, sketchfab.com/3d-models/m4-carbine-b516a8416b1044a7839b4a89dc24ca38).
- "Mortar - M224" by jcherry3d (CC-BY-4.0, sketchfab.com/3d-models/mortar-m224-c86a73e40d994431bcdb57dc741cf8be), voxel-rebuilt.
- Motion: "Human Soldier Animations 2.0 FREE" by Kevin Iglesias (Unity Asset Store EULA).
"""

import _infantry as inf


def kit(fig):
    inf.carry(fig, inf.load_kit("mortar", "mortar"), rot=(0, 10, 0), height=0.12)


def build(wreck=False):
    return inf.soldier("america", "m4", kit=kit)


FINISH = inf.FINISH
WRECK = False
PREVIEW = inf.PREVIEW
