import maya.cmds as cmds

# Load core system
from core.base_builder import BaseBuilder
from core import rig_utils as utils

class GlobalBuilder(BaseBuilder):
    """
    This module creates the top-level master group and global controller for the entire rigging system.
    It sets up a clear folder (group) structure for animators, riggers, and modelers to work comfortably.
    """
    def __init__(self):
        # Global control has no direction, so use Center "C"
        super().__init__(prefix="global", side="C")

    def build(self):
        print(f"\n--- [{self.part_name}] Master structure and global control build started ---")

        # =========================================================
        # 1. Master outliner hierarchy setup
        # =========================================================
        rig_grp = cmds.group(empty=True, w=True, name='RIG')
        
        # Sub-master folders for each role
        geo_grp = cmds.group(empty=True, p=rig_grp, name='Geo')               # For modeling meshes
        ctrl_grp = cmds.group(empty=True, p=rig_grp, name='CTRL')             # For controllers
        jnt_grp = cmds.group(empty=True, p=rig_grp, name='JOINT')             # For skeleton/bind joints
        dnt_grp = cmds.group(empty=True, p=rig_grp, name='DO_NOT_TOUCH')      # For rigging system (IK handles, curves, etc)

        # =========================================================
        # 2. Create global controller
        # =========================================================
        # Main global: radius 50, yellow (17), thickness 2
        global_ctrl_offs, global_ctrl = utils.create_ctrl(
            name="global_ctrl", radius=50, offs_grp=True, color=17, thickness=2.0, normal=(0, 1, 0)
        )
        
        # Gimbal global: radius 40, light yellow (25), thickness 1.5
        gimbal_ctrl_offs, gimbal_ctrl = utils.create_ctrl(
            name="global_gimbal_ctrl", radius=40, offs_grp=True, color=25, thickness=1.5, normal=(0, 1, 0)
        )

        # 3. Organize hierarchy
        cmds.parent(gimbal_ctrl_offs, global_ctrl)
        # Place the global controller set into the control master group (CTRL).
        cmds.parent(global_ctrl_offs, ctrl_grp)


        ctrls_to_hide = [gimbal_ctrl, global_ctrl]
        for ctrl in ctrls_to_hide:
            utils.lock_and_hide(ctrl, attrs=['v'])
        utils.lock_and_hide(gimbal_ctrl, attrs=['sx','sy','sz'])

        # =========================================================
        # 4. Register data (connect to meta node)
        # =========================================================
        # Register all so other parts (Spine, Arm, etc.) can easily find and use these groups.
        self.register_outputs({
            "global_ctrl": global_ctrl,
            "global_gimbal_ctrl": gimbal_ctrl,
            "rig_grp": rig_grp,
            "geo_grp": geo_grp,
            "ctrl_grp": ctrl_grp,
            "jnt_grp": jnt_grp,
            "dnt_grp": dnt_grp
        })

        print(f"[{self.part_name}] Build complete! Outliner structure has been set up cleanly.\n")