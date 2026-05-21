import maya.cmds as cmds
from core.limb_builder import LimbBaseBuilder
from core import rig_utils as utils

class ArmBuilder(LimbBaseBuilder):
    def __init__(self, side="L"):
        super().__init__(prefix="arm", side=side)

    # Added pv_rot_offset and wrist_rot_offset parameters for perfect symmetry with leg!
    def build(self, arm_jnts, pv_multiplier=0.5, number_of_fol=12, stretch_axis='Y', ctrl_rot_offset=(0, 0, 0), pv_rot_offset=(0, 0, 0), wrist_rot_offset=(0, 0, 0), connect_to_spine=True):
        if len(arm_jnts) < 4:
            cmds.warning("Please select clavicle, shoulder, elbow, and wrist joints.")
            return

        print(f"\n--- [{self.part_name}] Build started (Joint Base preserved + wrist Offset applied!) ---")

        global_ctrl = self.get_dependency("global_C", "global_ctrl")
        jnt_grp = self.get_dependency("global_C", "jnt_grp")
        ctrl_grp = self.get_dependency("global_C", "ctrl_grp")
        dnt_grp = self.get_dependency("global_C", "dnt_grp")
        
        standalone = not all([global_ctrl, jnt_grp, ctrl_grp, dnt_grp])
        if standalone:
            print("-> Building in standalone mode (no global part found).")
            if not jnt_grp:
                jnt_grp = cmds.group(empty=True, name=self.get_name('JOINT'))
            if not ctrl_grp:
                ctrl_grp = cmds.group(empty=True, name=self.get_name('CTRL'))
            if not dnt_grp:
                dnt_grp = cmds.group(empty=True, name=self.get_name('DO_NOT_TOUCH_GRP'))
            if not global_ctrl:
                global_ctrl = ctrl_grp

        spine_up_ik_ctrl = None
        if connect_to_spine:
            if standalone:
                cmds.warning("Cannot connect to Spine without Global/Spine part. Skipping connection.")
                connect_to_spine = False
            else:
                spine_up_ik_ctrl = self.get_dependency("spine_C", "up_ik_ctrl")
                if not spine_up_ik_ctrl:
                    cmds.warning("Cannot find Spine part. Skipping connection.")
                    connect_to_spine = False

        clavicle_jnt = cmds.rename(arm_jnts[0], self.get_name('clavicle_bnd_jnt'))
        sys_jnts = arm_jnts[1:4] 
        part_keywords = ['shoulder', 'elbow', 'wrist']
        drv_jnts = []
        
        for i, jnt in enumerate(sys_jnts):
            new_name = self.get_name(f'{part_keywords[i]}_drv_jnt')
            drv_jnts.append(cmds.rename(jnt, new_name))
            
        ik_jnts = self._duplicate_chain(drv_jnts, 'drv', 'ik')
        fk_jnts = self._duplicate_chain(drv_jnts, 'drv', 'fk')

        arm_jnt_grp = cmds.group(empty=True, name=self.get_name('jnt_grp'))
        cmds.matchTransform(arm_jnt_grp, clavicle_jnt)
        cmds.parent(clavicle_jnt, arm_jnt_grp)
        cmds.parent(ik_jnts[0], clavicle_jnt)
        cmds.parent(fk_jnts[0], clavicle_jnt)
        cmds.parent(arm_jnt_grp, jnt_grp) 

        # =========================================================
        # 1. IK setup (bug fix + wrist Joint Base preserved)
        # =========================================================
        arm_ik_hdl = cmds.ikHandle(name=self.get_name('ikHandle'), solver='ikRPsolver', sj=ik_jnts[0], ee=ik_jnts[2])[0]
        arm_effector = cmds.ikHandle(arm_ik_hdl, query=True, ee=True)
        cmds.rename(arm_effector, self.get_name('ikEffector'))
        
        pv_pos = utils.calculate_pole_vector_pos(ik_jnts[0], ik_jnts[1], ik_jnts[2], multiplier=pv_multiplier)
        ik_pv_offs, ik_pv_ctrl = self.create_poleVector_ctrl(pv_pos, ik_jnts[1], self.get_name('elbow'), radius=3, rot_offset=pv_rot_offset)
        
        # Mirror pole vector offset group for symmetry
        cmds.setAttr(f"{ik_pv_offs}.scaleX", self.mirror_val)
        
        cmds.poleVectorConstraint(ik_pv_ctrl, arm_ik_hdl)
        
        ik_arm_offs, ik_arm_ctrl = utils.create_ctrl(self.get_name('ik_ctrl'), 10, target=ik_jnts[2], offs_grp=True, color=self.color, thickness=2, normal=(1, 0, 0), rot_offset=wrist_rot_offset)
        
        # Mirror IK wrist controller offset group for symmetry
        cmds.setAttr(f"{ik_arm_offs}.scaleX", self.mirror_val)
        
        ik_sh_offs, ik_sh_ctrl = utils.create_ctrl(self.get_name('shoulder_ik_ctrl'), 15, target=ik_jnts[0], offs_grp=True, color=self.color, thickness=1.5, rot_offset=ctrl_rot_offset, normal=(1, 0, 0))
        
        # Mirror IK shoulder pin controller offset group for symmetry
        cmds.setAttr(f"{ik_sh_offs}.scaleX", self.mirror_val)
        
        cmds.parent(arm_ik_hdl, ik_arm_ctrl)
        cmds.orientConstraint(ik_arm_ctrl, ik_jnts[2], mo=True)
        cmds.pointConstraint(ik_sh_ctrl, ik_jnts[0], mo=True)
        ik_ctrl_grp = cmds.group(ik_arm_offs, ik_pv_offs, name=self.get_name('ik_ctrl_grp'), w=True)

        # =========================================================
        # 2. FK setup (wrist Joint Base preserved)
        # =========================================================
        sh_fk_offs, sh_fk_ctrl = utils.create_ctrl(self.get_name('shoulder_fk_ctrl'), 12, target=fk_jnts[0], offs_grp=True, color=self.color, thickness=2, rot_offset=ctrl_rot_offset, normal=(1, 0, 0))
        el_fk_offs, el_fk_ctrl = utils.create_ctrl(self.get_name('elbow_fk_ctrl'), 12, target=fk_jnts[1], offs_grp=True, color=self.color, thickness=2, rot_offset=ctrl_rot_offset, normal=(1, 0, 0))
        
        # FK wrist controller: apply normal=(1,0,0) and rotate only axis with wrist_rot_offset!
        wr_fk_offs, wr_fk_ctrl = utils.create_ctrl(self.get_name('wrist_fk_ctrl'), 12, target=fk_jnts[2], offs_grp=True, color=self.color, thickness=2, normal=(1, 0, 0), rot_offset=wrist_rot_offset)
        
        cmds.parentConstraint(sh_fk_ctrl, fk_jnts[0], mo=True)
        cmds.parentConstraint(el_fk_ctrl, fk_jnts[1], mo=True)
        cmds.parentConstraint(wr_fk_ctrl, fk_jnts[2], mo=True)
        
        cmds.parent(wr_fk_offs, el_fk_ctrl)
        cmds.parent(el_fk_offs, sh_fk_ctrl)
        fk_ctrl_grp = cmds.group(sh_fk_offs, name=self.get_name('fk_ctrl_grp'), w=True)

        # [IK/FK Switch]
        setting_offs, setting_ctrl = utils.create_ctrl(self.get_name('setting_ctrl'), 15, target=drv_jnts[-1], offs_grp=True, color=22, thickness=1.5)
        cmds.parentConstraint(drv_jnts[-1], setting_offs, mo=True)
        self.setup_ikfk_switch(ik_jnts, fk_jnts, drv_jnts, setting_ctrl)
        self.setup_ikfk_visibility([ik_ctrl_grp, ik_sh_offs], [fk_ctrl_grp], setting_ctrl)

        # [Squash & Stretch]
        distance_node = utils.create_distance_measurement(ik_sh_ctrl, ik_arm_ctrl, self.get_name('ik_dist'))
        dist_grps = self.stretch_and_squash([ik_sh_ctrl, ik_arm_ctrl], ik_jnts[0:2], distance_node, self.part_name, stretch_axis, ik_pv_ctrl, global_ctrl, connect_to_spine)

        # [Advanced Ribbon setup]
        ribbon_surf, ribbon_bnd_jnts, ribbon_twk_offs, fol_sys_grp, follicles = self.create_ribbon(drv_jnts, self.part_name, number_of_fol)
        twist_jnt = self.create_twist_jnt(drv_jnts)
        fol_ctrl_grps, up_low_twk_jnts, mid_twk_jnts, twk_ctrls, fol_ctrl_grp = self.create_follicle_ctrl([sh_fk_ctrl, el_fk_ctrl, wr_fk_ctrl], drv_jnts=drv_jnts)
        
        for i in range(2): 
            parent_const = cmds.parentConstraint(drv_jnts[i], mid_twk_jnts[i], mo=True)[0]
            cmds.connectAttr(f'{twk_ctrls[1]}.parentInverseMatrix[0]', f'{parent_const}.constraintParentInverseMatrix', force=True)
        
        # Set up constraint groups BEFORE skinning so the bind pose captures final positions.
        # Upper Tweak: create dedicated constraint group
        up_cons = cmds.group(empty=True, name=self.get_name('up_twk_cons'))
        cmds.parent(up_cons, fol_ctrl_grp)
        cmds.matchTransform(up_cons, fol_ctrl_grps[0])
        
        cmds.pointConstraint(drv_jnts[0], up_cons, mo=True)
        cmds.setAttr(f"{cmds.orientConstraint(drv_jnts[0], twist_jnt[0], up_cons, mo=False)[0]}.interpType", 2)
        
        cmds.parent(fol_ctrl_grps[0], up_cons)

        # Middle Tweak
        cmds.setAttr(f"{cmds.parentConstraint(drv_jnts[0], drv_jnts[1], fol_ctrl_grps[1], mo=True)[0]}.interpType", 2)
        
        # Lower Tweak: create dedicated constraint group
        lo_cons = cmds.group(empty=True, name=self.get_name('lo_twk_cons'))
        cmds.parent(lo_cons, fol_ctrl_grp)
        cmds.matchTransform(lo_cons, fol_ctrl_grps[2])
        
        cmds.pointConstraint(drv_jnts[1], lo_cons, mo=True)
        cmds.setAttr(f"{cmds.orientConstraint(drv_jnts[1], twist_jnt[1], lo_cons, mo=False)[0]}.interpType", 2)
        
        cmds.parent(fol_ctrl_grps[2], lo_cons)

        # [Dynamic Scale mapping]
        stretch_axis = stretch_axis.upper()
        volume_axes = [ax for ax in ['X', 'Y', 'Z'] if ax != stretch_axis]
        
        map_0 = utils.get_dynamic_scale_mapping(drv_jnts[0], fol_ctrl_grps[0])
        map_1 = utils.get_dynamic_scale_mapping(drv_jnts[1], fol_ctrl_grps[2])
        
        tweak_stretch_0 = [t_ax for t_ax, s_ax in map_0.items() if s_ax == stretch_axis][0]
        tweak_stretch_1 = [t_ax for t_ax, s_ax in map_1.items() if s_ax == stretch_axis][0]
        
        cmds.connectAttr(f'{drv_jnts[0]}.scale{stretch_axis}', f'{fol_ctrl_grps[0]}.scale{tweak_stretch_0}', force=True)
        cmds.connectAttr(f'{drv_jnts[1]}.scale{stretch_axis}', f'{fol_ctrl_grps[2]}.scale{tweak_stretch_1}', force=True)
        
        half_point = int(number_of_fol / 2)
        self.scale_connect_attr(volume_axes, volume_axes, drv_jnts[0], ribbon_bnd_jnts[:half_point])
        self.scale_connect_attr(volume_axes, volume_axes, drv_jnts[1], ribbon_bnd_jnts[half_point:])

        if connect_to_spine:
            for fol in follicles:
                for ax in ['X', 'Y', 'Z']:
                    cmds.connectAttr(f'{global_ctrl}.scale{ax}', f'{fol}.scale{ax}', force=True)

        total_fols = len(ribbon_twk_offs)
        if total_fols >= 3:
            mid_fols = ribbon_twk_offs[1:-1]
            m_count = len(mid_fols)
            part = m_count // 5
            up_c = part * 2
            lo_c = part * 2
            mid_c = m_count - up_c - lo_c
            
            up_twk_targets = mid_fols[:up_c]
            mid_twk_targets = mid_fols[up_c : up_c + mid_c]
            lo_twk_targets = mid_fols[up_c + mid_c :]
            
            for target in up_twk_targets:
                mapping = utils.get_dynamic_scale_mapping(twk_ctrls[0], target)
                for tgt_ax, src_ax in mapping.items():
                    cmds.connectAttr(f"{twk_ctrls[0]}.scale{src_ax}", f"{target}.scale{tgt_ax}", force=True)
            for target in mid_twk_targets:
                mapping = utils.get_dynamic_scale_mapping(twk_ctrls[1], target)
                for tgt_ax, src_ax in mapping.items():
                    cmds.connectAttr(f"{twk_ctrls[1]}.scale{src_ax}", f"{target}.scale{tgt_ax}", force=True)
            for target in lo_twk_targets:
                mapping = utils.get_dynamic_scale_mapping(twk_ctrls[2], target)
                for tgt_ax, src_ax in mapping.items():
                    cmds.connectAttr(f"{twk_ctrls[2]}.scale{src_ax}", f"{target}.scale{tgt_ax}", force=True)

        clavicle_offs, clavicle_ctrl = utils.create_ctrl(self.get_name('clavicle_ctrl'), 12, target=clavicle_jnt, offs_grp=True, color=self.color, thickness=2, rot_offset=ctrl_rot_offset, normal=(1, 0, 0))
        cmds.setAttr(f"{clavicle_offs}.rotate",  0, 0, 0, type="double3")
        cmds.parentConstraint(clavicle_ctrl, clavicle_jnt, mo=True)
        

        mirror_scale_targets = [ik_arm_offs, ik_sh_offs, ik_pv_offs, clavicle_offs]
        for offs in mirror_scale_targets:
            cmds.setAttr(f"{offs}.scaleX", self.mirror_val)
            
        if connect_to_spine:
            cmds.parent(clavicle_offs, spine_up_ik_ctrl)
        else:
            cmds.parent(clavicle_offs, ctrl_grp)
            print("-> Built independently, ignoring Spine.")

        arm_ctrl_grp = cmds.group(ik_ctrl_grp, fol_ctrl_grp, setting_offs, name=self.get_name('ctrl_grp'), w=True)
        cmds.parent(arm_ctrl_grp, global_ctrl)
        cmds.parent(fk_ctrl_grp, clavicle_ctrl)
        cmds.parent(ik_sh_offs, clavicle_ctrl)

        arm_dnt = cmds.group(ribbon_surf, fol_sys_grp, distance_node, *dist_grps, w=True, name=self.get_name('DO_NOT_TOUCH'))
        cmds.parent(arm_dnt, dnt_grp)
        cmds.setAttr(f"{arm_dnt}.visibility", 0)

        ctrls_to_lock = [clavicle_ctrl, ik_sh_ctrl, ik_pv_ctrl, sh_fk_ctrl, el_fk_ctrl, setting_ctrl]
        for ctrl in ctrls_to_lock:
            utils.lock_and_hide(ctrl, attrs=['v', 'sx', 'sy', 'sz'])
        tw_ctrls_to_lock = [twk_ctrls[0], twk_ctrls[1], twk_ctrls[2], wr_fk_ctrl, ik_arm_ctrl]
        for ctrl in tw_ctrls_to_lock:
            utils.lock_and_hide(ctrl, attrs=['v'])
        utils.lock_and_hide([ik_pv_ctrl, ik_sh_ctrl], attrs=['rx', 'ry', 'rz'])
        utils.lock_and_hide(setting_ctrl, attrs=['tx', 'ty', 'tz', 'rx', 'ry', 'rz'])

        # [Skin bind ribbon] — done last so bind pose captures the fully settled hierarchy
        cmds.refresh(force=True)
        skin_cluster = cmds.skinCluster(drv_jnts + up_low_twk_jnts, ribbon_surf, toSelectedBones=True, bindMethod=0, skinMethod=0, maximumInfluences=5)[0]
        cmds.skinCluster(skin_cluster, e=True, dr=4, ug=True, ps=0, ns=10, lw=True, wt=0, ai=twist_jnt)
        cmds.setAttr(f'{twist_jnt[0]}.liw', 0)
        cmds.setAttr(f'{twist_jnt[1]}.liw', 0)
        self.surf_transfer_weight(drv_jnts[0], twist_jnt[0], ribbon_surf, skin_cluster)
        self.surf_transfer_weight(drv_jnts[2], twist_jnt[1], ribbon_surf, skin_cluster)
        cmds.skinCluster(skin_cluster, e=True, dr=4, ug=True, ps=0, ns=10, lw=True, wt=0, ai=mid_twk_jnts)

        # [Register metadata]
        self.register_outputs({
            "clavicle_ctrl": clavicle_ctrl,
            "ik_ctrl": ik_arm_ctrl,
            "ik_sh_ctrl": ik_sh_ctrl,
            "ik_pv_ctrl": ik_pv_ctrl,
            "fk_shoulder_ctrl": sh_fk_ctrl,
            "fk_elbow_ctrl": el_fk_ctrl,
            "fk_wrist_ctrl": wr_fk_ctrl,
            "setting_ctrl": setting_ctrl,
            "tweak_up_ctrl": twk_ctrls[0],
            "tweak_mid_ctrl": twk_ctrls[1],
            "tweak_lo_ctrl": twk_ctrls[2],
            "clavicle_bnd_jnt": clavicle_jnt,
            "drv_wrist": drv_jnts[-1],
            "arm_ik_hdl": arm_ik_hdl,
            "ribbon_surf": ribbon_surf
        })

        updated_arm_jnts = [clavicle_jnt] + drv_jnts

        self.save_settings({
            "arm_jnts": updated_arm_jnts, 
            "drv_jnts": drv_jnts,
            "ik_jnts": ik_jnts,
            "fk_jnts": fk_jnts,
            "ribbon_bnd_jnts": ribbon_bnd_jnts,
            "pv_multiplier": pv_multiplier,
            "number_of_fol": number_of_fol,
            "stretch_axis": stretch_axis,
            "ctrl_rot_offset": ctrl_rot_offset,
            "pv_rot_offset": pv_rot_offset,
            "wrist_rot_offset": wrist_rot_offset,
            "connect_to_spine": connect_to_spine
        })
        print(f"✅ [{self.part_name}] Build complete!\n")

