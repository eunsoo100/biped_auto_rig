import maya.cmds as cmds
from core.spline_builder import SplineBaseBuilder # BaseBuilder 대신 SplineBaseBuilder를 가져옵니다!
from core import rig_utils as utils

class SpineBuilder(SplineBaseBuilder):
    """
    Spine rigging module
    Inherits from SplineBaseBuilder to automatically use advanced spline features.
    """
    def __init__(self):
        super().__init__(prefix="spine", side="C")
        self.fk_ctrl_01_jnt_index = 2
        self.fk_ctrl_02_jnt_index = 5

    def build(self, spine_jnts):
        if not spine_jnts or len(spine_jnts) < 3:
            cmds.warning("At least 3 joints are required for spine rigging.")
            return

        print(f"\n--- [{self.part_name}] Build started ---")
        spine_jnt_start = spine_jnts[0]
        spine_jnt_end = spine_jnts[-1]
        cmds.select(clear=True)

        # 1. Fetch dependencies
        global_ctrl = self.get_dependency("global_C", "global_ctrl")
        global_gimbal = self.get_dependency("global_C", "global_gimbal_ctrl")
        jnt_grp = self.get_dependency("global_C", "jnt_grp")
        dnt_grp = self.get_dependency("global_C", "dnt_grp")

        if not all([global_ctrl, global_gimbal, jnt_grp, dnt_grp]):
            cmds.warning("Cannot find Global part information.")
            return

        # 2. Base joints (COG, Hip)
        cog_jnt = cmds.joint(name=self.get_name('cog_bnd_jnt'))
        cmds.matchTransform(cog_jnt, spine_jnt_start, pos=True)
        cmds.select(clear=True)
        hip_jnt = cmds.joint(name=self.get_name('hip_bnd_jnt'))
        cmds.matchTransform(hip_jnt, spine_jnt_start, pos=True)

        # 3. Create controllers
        cog_ctrl_offs, cog_ctrl = utils.create_ctrl(self.get_name('cog_ctrl'), 28, target=cog_jnt, offs_grp=True, color=17, thickness=2, normal=(0, 1, 0))
        cog_gim_ctrl_offs, cog_gim_ctrl = utils.create_ctrl(self.get_name('cog_gimbal_ctrl'), 24, target=cog_jnt, offs_grp=True, color=25, thickness=1.5, normal=(0, 1, 0))
        cmds.parentConstraint(cog_ctrl, cog_jnt, mo=True)
        cmds.parent(cog_gim_ctrl_offs, cog_ctrl)

        spine_01_fk_jnt = spine_jnts[self.fk_ctrl_01_jnt_index]
        spine_02_fk_jnt = spine_jnts[self.fk_ctrl_02_jnt_index]
        fk_01_offs, fk_01_ctrl = utils.create_ctrl(self.get_name('fk_01_ctrl'), 20, target=spine_01_fk_jnt, offs_grp=True, color=17, thickness=2, normal=(0, 1, 0))
        fk_02_offs, fk_02_ctrl = utils.create_ctrl(self.get_name('fk_02_ctrl'), 20, target=spine_02_fk_jnt, offs_grp=True, color=17, thickness=2, normal=(0, 1, 0))
        cmds.parent(fk_02_offs, fk_01_ctrl)
        cmds.parent(fk_01_offs, cog_gim_ctrl)

        up_ik_offs, up_ik_ctrl = utils.create_ctrl(self.get_name('up_ik_ctrl'), 25, offs_grp=True, color=19, thickness=1.5, normal=(0, 1, 0))
        lo_ik_offs, lo_ik_ctrl = utils.create_ctrl(self.get_name('lo_ik_ctrl'), 18, offs_grp=True, color=19, thickness=1.5, normal=(0, 1, 0))
        cmds.matchTransform(up_ik_offs, spine_jnt_end, pos=True, rot=False)
        cmds.matchTransform(lo_ik_offs, spine_jnt_start, pos=True, rot=False)
        cmds.parent(lo_ik_offs, cog_gim_ctrl)
        cmds.parent(up_ik_offs, fk_02_ctrl)

        hip_offs, hip_ctrl = utils.create_ctrl(self.get_name('hip_ctrl'), 15, target=cog_ctrl, offs_grp=True, color=17, thickness=1.5, normal=(0, 1, 0))
        cmds.parent(hip_offs, lo_ik_ctrl)
        cmds.parentConstraint(hip_ctrl, hip_jnt, mo=True)

        # 4. Create IK Spline
        cmds.select(clear=True)
        spine_ik_hdl = cmds.ikHandle(name=self.get_name('ikHandle'), solver='ikSplineSolver', numSpans=1, sj=spine_jnt_start, ee=spine_jnt_end)[0]
        
        spine_effector = cmds.ikHandle(spine_ik_hdl, query=True, ee=True)
        cmds.rename(spine_effector, self.get_name('ikEffector'))

        ik_spine_crv = cmds.ikHandle(spine_ik_hdl, query=True, curve=True)
        
        shape = cmds.listRelatives(ik_spine_crv, parent=True)[0]
        cmds.rename(shape, self.get_name('ik_crv'))
        spine_ik_crv = self.get_name('ik_crv')
        new_shape = cmds.listRelatives(spine_ik_crv, children=True)[0]

        # Directly call parent class method!
        name_list = ['lo_jnt', 'mid_lo_jnt', 'mid_up_jnt', 'up_jnt']
        spine_ik_crv_jnt = self.create_jnt_on_crv_point(new_shape, name_list, spine_ik_crv)

        spine_mid_lo_ik_ctrl, spine_mid_up_ik_ctrl = None, None
        spine_mid_lo_ik_ctrl_offs, spine_mid_up_ik_ctrl_offs = None, None

        for jnt in spine_ik_crv_jnt:
            crv_ctrl_name = jnt.replace('jnt', 'ctrl')
            if jnt == spine_ik_crv_jnt[0]: cmds.parent(jnt, lo_ik_ctrl)
            elif jnt == spine_ik_crv_jnt[-1]: cmds.parent(jnt, up_ik_ctrl)
            else:
                offset_grp, ctrl = utils.create_ctrl(crv_ctrl_name, 18, target=jnt, offs_grp=True, color=19, thickness=1.5, normal=(0, 1, 0))
                if 'lo' in jnt:
                    spine_mid_lo_ik_ctrl = ctrl
                    spine_mid_lo_ik_ctrl_offs = offset_grp
                elif 'up' in jnt:
                    spine_mid_up_ik_ctrl = ctrl
                    spine_mid_up_ik_ctrl_offs = offset_grp
                cmds.parent(jnt, ctrl)
        
        cmds.skinCluster(spine_ik_crv_jnt, spine_ik_crv, maximumInfluences=1)

        # 5. [Call advanced systems] - all handled by parent (SplineBaseBuilder)!
        self.stretch_and_squash(up_ik_ctrl, spine_jnts, spine_ik_crv, self.get_name('spine_sys'), global_ctrl, stretch_axis='Y', ctrl_pos=[up_ik_ctrl, lo_ik_ctrl])
        
        up_sdk_grp = utils.create_offset_grp(up_ik_ctrl, '_sdk')
        lo_sdk_grp = utils.create_offset_grp(lo_ik_ctrl, '_sdk')
        up_neg_grp = utils.create_offset_grp(spine_ik_crv_jnt[-1], '_neg_grp')
        up_neg_grp = cmds.rename(up_neg_grp, up_neg_grp.replace('jnt', 'ctrl'))
        lo_neg_grp = utils.create_offset_grp(spine_ik_crv_jnt[0], '_neg_grp')
        lo_neg_grp = cmds.rename(lo_neg_grp, lo_neg_grp.replace('jnt', 'ctrl'))
        
        dis_calc = cmds.group(name='dis_cal_grp', parent=lo_ik_ctrl, empty=True)
        cmds.matchTransform(dis_calc, up_ik_ctrl, pos=True)
        distance = cmds.getAttr(f'{dis_calc}.translateY')
        cmds.delete(dis_calc)
        
        self.dynamic_ctrl_pos(up_sdk_grp, up_ik_ctrl, up_neg_grp, value=-distance)
        self.dynamic_ctrl_pos(lo_sdk_grp, lo_ik_ctrl, lo_neg_grp, value=distance)
        
        self.ik_spline_adv_twist(spine_ik_hdl, lo_ik_ctrl, up_ik_ctrl)
        self.pos_ori_follow(spine_mid_lo_ik_ctrl, up_neg_grp, lo_neg_grp)
        self.pos_ori_follow(spine_mid_up_ik_ctrl, up_neg_grp, lo_neg_grp)

        cmds.matchTransform(fk_01_ctrl, spine_mid_lo_ik_ctrl, pos=False, rot=False, piv=True)
        cmds.matchTransform(fk_02_ctrl, spine_mid_up_ik_ctrl, pos=False, rot=False, piv=True)
        cmds.matchTransform(spine_mid_lo_ik_ctrl_offs, fk_01_ctrl, pos=False, rot=True)
        cmds.matchTransform(spine_mid_up_ik_ctrl_offs, fk_02_ctrl, pos=False, rot=True)

        # 6. Organize hierarchy
        cmds.parent(hip_offs, lo_neg_grp)
        cmds.parent(spine_jnt_start, cog_jnt)
        cmds.parent(hip_jnt, cog_jnt)
        cmds.parent(spine_mid_lo_ik_ctrl_offs, fk_01_ctrl)
        cmds.parent(spine_mid_up_ik_ctrl_offs, fk_02_ctrl)
        cmds.parent(cog_ctrl_offs, global_gimbal)

        spine_dnt = cmds.group(spine_ik_hdl, spine_ik_crv, w=True, name=self.get_name('DO_NOT_TOUCH'))
        cmds.parent(cog_jnt, jnt_grp)
        cmds.parent(spine_dnt, dnt_grp)
        cmds.setAttr(f"{spine_dnt}.visibility", 0)

        all_spine_ctrls = [cog_ctrl, cog_gim_ctrl, fk_01_ctrl, fk_02_ctrl, up_ik_ctrl, lo_ik_ctrl, hip_ctrl, spine_mid_lo_ik_ctrl, spine_mid_up_ik_ctrl]
        for ctrl in all_spine_ctrls:
            utils.lock_and_hide(ctrl, attrs=['v'])
            
        # Middle IK controllers: Lock rotation and scale
        mid_ik_ctrls = [spine_mid_lo_ik_ctrl, spine_mid_up_ik_ctrl]
        for ctrl in mid_ik_ctrls:
            utils.lock_and_hide(ctrl, attrs=['rx', 'ry', 'rz', 'sx', 'sy', 'sz'])
            
        # Lock scale for all FK controllers (including cog, hip) and up_ik_ctrl
        scale_lock_ctrls = [cog_ctrl, cog_gim_ctrl, fk_01_ctrl, fk_02_ctrl, hip_ctrl, up_ik_ctrl]
        for ctrl in scale_lock_ctrls:
            utils.lock_and_hide(ctrl, attrs=['sx', 'sy', 'sz'])

        # 7. Register data
        self.register_outputs({
            "cog_ctrl": cog_ctrl,
            "fk_01_ctrl": fk_01_ctrl,
            "fk_02_ctrl": fk_02_ctrl,
            "up_ik_ctrl": up_ik_ctrl,
            "lo_ik_ctrl": lo_ik_ctrl,
            "hip_ctrl": hip_ctrl,
            "spine_end_jnt": spine_jnt_end,
            "spine_ik_hdl": spine_ik_hdl
        })
        self.save_settings({"spine_joints": spine_jnts})

        print(f"[{self.part_name}] Advanced spline system build complete!\n")