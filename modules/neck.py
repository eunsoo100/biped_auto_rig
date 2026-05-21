import maya.cmds as cmds
from core.spline_builder import SplineBaseBuilder
from core import rig_utils as utils

class NeckBuilder(SplineBaseBuilder):

    def __init__(self):
        super().__init__(prefix="neck", side="C")

    def build(self, neck_jnts, head_jnt, connect_to_spine=True):
        if not neck_jnts or not head_jnt:
            cmds.warning("Neck joint list and Head joint are required.")
            return

        print(f"\n--- [{self.part_name}] Build started ---")
        neck_jnt_start = neck_jnts[0]
        neck_jnt_end = neck_jnts[-1]
        cmds.select(clear=True)

        # 1. Fetch dependencies (Global)
        global_ctrl = self.get_dependency("global_C", "global_ctrl")
        dnt_grp = self.get_dependency("global_C", "dnt_grp")
        ctrl_grp = self.get_dependency("global_C", "ctrl_grp")  # fallback group if connection fails
        jnt_grp = self.get_dependency("global_C", "jnt_grp")

        if not all([global_ctrl, dnt_grp, ctrl_grp, jnt_grp]):
            cmds.warning("Cannot find Global part information.")
            return

        # Optionally fetch Spine dependencies
        spine_up_ik_ctrl, spine_end_jnt = None, None
        if connect_to_spine:
            spine_up_ik_ctrl = self.get_dependency("spine_C", "up_ik_ctrl")
            spine_end_jnt = self.get_dependency("spine_C", "spine_end_jnt")
            
            if not all([spine_up_ik_ctrl, spine_end_jnt]):
                cmds.warning("Cannot find Spine part. Building independently.")
                connect_to_spine = False

        if connect_to_spine and neck_jnt_start == spine_end_jnt:
            cmds.error(f"Selection error: Neck start joint ({neck_jnt_start}) overlaps with Spine end joint!")
            return

        # 2. Create IK Spline
        neck_ik_hdl = cmds.ikHandle(name=self.get_name('ikHandle'), solver='ikSplineSolver', numSpans=1, sj=neck_jnt_start, ee=neck_jnt_end)[0]
        
        neck_effector = cmds.ikHandle(neck_ik_hdl, query=True, ee=True)
        cmds.rename(neck_effector, self.get_name('ikEffector'))

        ik_neck_crv = cmds.ikHandle(neck_ik_hdl, query=True, curve=True)
        
        shape = cmds.listRelatives(ik_neck_crv, parent=True)[0]
        cmds.rename(shape, self.get_name('ik_crv'))
        neck_ik_crv = self.get_name('ik_crv')
        new_shape = cmds.listRelatives(neck_ik_crv, children=True)[0]

        name_list = ['lo_jnt', 'mid_jnt', 'up_jnt']
        neck_ik_crv_jnt = self.create_jnt_on_crv_point(new_shape, name_list, neck_ik_crv)

        # 3. Create Neck & Head controllers
        neck_lo_ctrl_offs, neck_lo_ctrl = utils.create_ctrl(self.get_name('lo_ctrl'), 10, target=neck_ik_crv_jnt[0], offs_grp=True, color=22, thickness=1.5, normal=(0, 1, 0))
        neck_mid_ctrl_offs, neck_mid_ctrl = utils.create_ctrl(self.get_name('mid_ctrl'), 10, target=neck_ik_crv_jnt[1], offs_grp=True, color=22, thickness=1.5, normal=(0, 1, 0))
        neck_up_ctrl_offs, neck_up_ctrl = utils.create_ctrl(self.get_name('up_ctrl'), 10, target=neck_ik_crv_jnt[-1], offs_grp=True, color=22, thickness=1.5, normal=(0, 1, 0))
        head_ctrl_offs, head_ctrl = utils.create_ctrl(self.get_name('head_ctrl'), 15, target=head_jnt, offs_grp=True, color=22, thickness=1.5, normal=(0, 1, 0))
        neck_ik_ctrl_offs, neck_ik_ctrl = utils.create_ctrl(self.get_name('mid_ik_ctrl'), 8, target=neck_mid_ctrl, offs_grp=True, color=19, thickness=1.0, normal=(0, 1, 0))
        cmds.parent(neck_ik_crv_jnt[0], neck_lo_ctrl)
        cmds.parent(neck_ik_crv_jnt[1], neck_ik_ctrl)
        cmds.parent(neck_ik_crv_jnt[-1], neck_up_ctrl)
        cmds.skinCluster(neck_ik_crv_jnt, neck_ik_crv, maximumInfluences=1)

        # 4. Controller hierarchy and option-based Spine connection
        cmds.parentConstraint(head_ctrl, head_jnt, mo=True)
        cmds.orientConstraint(neck_up_ctrl, neck_jnt_end, mo=True)
        
        cmds.parent(head_ctrl_offs, neck_up_ctrl)
        cmds.parent(neck_up_ctrl_offs, neck_mid_ctrl)
        cmds.parent(neck_mid_ctrl_offs, neck_lo_ctrl)
        cmds.parent(neck_ik_ctrl_offs, neck_mid_ctrl)

        # Optionally connect to Spine or Global master
        if connect_to_spine:
            cmds.parent(neck_lo_ctrl_offs, spine_up_ik_ctrl)
            cmds.parent(neck_jnt_start, spine_end_jnt) 
            print("-> Successfully connected to Spine part.")
        else:
            cmds.parent(neck_lo_ctrl_offs, ctrl_grp)
            cmds.parent(neck_jnt_start, jnt_grp)
            print("-> Built independently, ignoring Spine.")

        # 5. [Call advanced systems]
        self.stretch_and_squash(neck_up_ctrl, neck_jnts, new_shape, self.get_name('sys'), global_ctrl, stretch_axis='Y')
        self.ik_spline_adv_twist(neck_ik_hdl, neck_lo_ctrl, neck_up_ctrl)
        self.pos_ori_follow(neck_ik_ctrl, neck_up_ctrl, neck_lo_ctrl)

        # 6. Organize master folders
        neck_dnt = cmds.group(neck_ik_hdl, neck_ik_crv, w=True, name=self.get_name('DO_NOT_TOUCH'))
        cmds.parent(neck_dnt, dnt_grp)
        cmds.setAttr(f"{neck_dnt}.visibility", 0)

        all_neck_ctrls = [neck_lo_ctrl, neck_mid_ctrl, neck_up_ctrl, head_ctrl, neck_ik_ctrl]
        for ctrl in all_neck_ctrls:
            utils.lock_and_hide(ctrl, attrs=['v'])
            
        # mid_ik_ctrl (middle IK controller): Lock rotation and scale
        utils.lock_and_hide(neck_ik_ctrl, attrs=['rx', 'ry', 'rz', 'sx', 'sy', 'sz'])
        
        # Lock scale for all FK (mid_ctrl, lo_ctrl) and up_ctrl
        # (head_ctrl is also treated as FK in the Neck system)
        scale_lock_ctrls = [neck_lo_ctrl, neck_mid_ctrl, neck_up_ctrl, head_ctrl]
        for ctrl in scale_lock_ctrls:
            utils.lock_and_hide(ctrl, attrs=['sx', 'sy', 'sz'])

        # 7. Register data
        self.register_outputs({
            "lo_ctrl": neck_lo_ctrl,
            "mid_ctrl": neck_mid_ctrl,
            "up_ctrl": neck_up_ctrl,
            "mid_ik_ctrl": neck_ik_ctrl,
            "head_ctrl": head_ctrl,
            "neck_ik_hdl": neck_ik_hdl
        })
        self.save_settings({"neck_joints": neck_jnts, "head_joint": head_jnt})

        print(f"[{self.part_name}] Build complete!\n")