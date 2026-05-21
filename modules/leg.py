import maya.cmds as cmds
from core.limb_builder import LimbBaseBuilder
from core import rig_utils as utils

class LegBuilder(LimbBaseBuilder):
    def __init__(self, side="L"):
        super().__init__(prefix="leg", side=side)

    def build(self, leg_jnts, pv_multiplier=0.5, number_of_fol=12, stretch_axis='Y', ctrl_rot_offset=(0, 0, 0), pv_rot_offset=(0, 0, 0), ankle_rot_offset=(0, 0, 0), connect_to_hip=True):
        if len(leg_jnts) < 4:
            cmds.warning("Please select pelvis, thigh, knee, and ankle joints.")
            return

        print(f"\n--- [{self.part_name}] Build started (Ankle world smart snap enabled!) ---")

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

        spine_hip_ctrl = None
        if connect_to_hip:
            if standalone:
                cmds.warning("Cannot connect to Hip without Global/Spine part. Skipping connection.")
                connect_to_hip = False
            else:
                spine_hip_ctrl = self.get_dependency("spine_C", "hip_ctrl")
                if not spine_hip_ctrl:
                    cmds.warning("Cannot find Hip controller of Spine. Skipping connection.")
                    connect_to_hip = False

        pelvis_jnt = cmds.rename(leg_jnts[0], self.get_name('pelvis_bnd_jnt'))
        sys_jnts = leg_jnts[1:4] 
        part_keywords = ['thigh', 'knee', 'ankle']
        drv_jnts = []
        
        for i, jnt in enumerate(sys_jnts):
            new_name = self.get_name(f'{part_keywords[i]}_drv_jnt')
            drv_jnts.append(cmds.rename(jnt, new_name))
            
        ik_jnts = self._duplicate_chain(drv_jnts, 'drv', 'ik')
        fk_jnts = self._duplicate_chain(drv_jnts, 'drv', 'fk')

        leg_jnt_grp = cmds.group(empty=True, name=self.get_name('jnt_grp'))
        cmds.matchTransform(leg_jnt_grp, pelvis_jnt)
        cmds.parent(pelvis_jnt, leg_jnt_grp)
        cmds.parent(ik_jnts[0], pelvis_jnt)
        cmds.parent(fk_jnts[0], pelvis_jnt)
        cmds.parent(leg_jnt_grp, jnt_grp) 

        # =========================================================
        # 1. IK setup & Ankle smart snap
        # =========================================================
        leg_ik_hdl = cmds.ikHandle(name=self.get_name('ikHandle'), solver='ikRPsolver', sj=ik_jnts[0], ee=ik_jnts[2])[0]
        
        leg_effector = cmds.ikHandle(leg_ik_hdl, query=True, ee=True)
        cmds.rename(leg_effector, self.get_name('ikEffector'))
        
        pv_pos = utils.calculate_pole_vector_pos(ik_jnts[0], ik_jnts[1], ik_jnts[2], multiplier=pv_multiplier)
        ik_pv_offs, ik_pv_ctrl = self.create_poleVector_ctrl(pv_pos, ik_jnts[1], self.get_name('knee'), radius=3, rot_offset=pv_rot_offset)
        cmds.poleVectorConstraint(ik_pv_ctrl, leg_ik_hdl)
        
        # 1. Joint matching and apply ankle_rot_offset
        ik_leg_offs, ik_leg_ctrl = utils.create_ctrl(self.get_name('ik_ctrl'), 10, target=ik_jnts[2], offs_grp=True, color=self.color, thickness=2, normal=(0, 1, 0), rot_offset=ankle_rot_offset)
        
        # 2. Snap to closest world axis based on current orientation
        utils.snap_to_closest_world_axis(ik_leg_offs)
        
        ik_thi_offs, ik_thi_ctrl = utils.create_ctrl(self.get_name('thigh_ik_ctrl'), 15, target=ik_jnts[0], offs_grp=True, color=self.color, thickness=1.5, rot_offset=ctrl_rot_offset, normal=(0, 1, 0))
        
        cmds.parent(leg_ik_hdl, ik_leg_ctrl)
        cmds.orientConstraint(ik_leg_ctrl, ik_jnts[2], mo=True)
        cmds.pointConstraint(ik_thi_ctrl, ik_jnts[0], mo=True)
        ik_ctrl_grp = cmds.group(ik_leg_offs, ik_thi_offs, ik_pv_offs, name=self.get_name('ik_ctrl_grp'), w=True)

        # =========================================================
        # 2. FK setup & Ankle smart snap
        # =========================================================
        thi_fk_offs, thi_fk_ctrl = utils.create_ctrl(self.get_name('thigh_fk_ctrl'), 12, target=fk_jnts[0], offs_grp=True, color=self.color, thickness=2, rot_offset=ctrl_rot_offset, normal=(0, 1, 0))
        kn_fk_offs, kn_fk_ctrl = utils.create_ctrl(self.get_name('knee_fk_ctrl'), 12, target=fk_jnts[1], offs_grp=True, color=self.color, thickness=2, rot_offset=ctrl_rot_offset, normal=(0, 1, 0))
        
        # 1. Joint matching and apply ankle_rot_offset
        ak_fk_offs, ak_fk_ctrl = utils.create_ctrl(self.get_name('ankle_fk_ctrl'), 12, target=fk_jnts[2], offs_grp=True, color=self.color, thickness=2, normal=(0, 1, 0), rot_offset=ankle_rot_offset)
        
        # 2. Snap to closest world axis as above
        utils.snap_to_closest_world_axis(ak_fk_offs)
        
        cmds.parentConstraint(thi_fk_ctrl, fk_jnts[0], mo=True)
        cmds.parentConstraint(kn_fk_ctrl, fk_jnts[1], mo=True)
        cmds.parentConstraint(ak_fk_ctrl, fk_jnts[2], mo=True)
        
        cmds.parent(ak_fk_offs, kn_fk_ctrl)
        cmds.parent(kn_fk_offs, thi_fk_ctrl)
        fk_ctrl_grp = cmds.group(thi_fk_offs, name=self.get_name('fk_ctrl_grp'), w=True)

        # [IK/FK Switch]
        setting_offs, setting_ctrl = utils.create_ctrl(self.get_name('setting_ctrl'), 15, target=drv_jnts[-1], offs_grp=True, color=22, thickness=1.5)
        cmds.parentConstraint(drv_jnts[-1], setting_offs, mo=True)
        self.setup_ikfk_switch(ik_jnts, fk_jnts, drv_jnts, setting_ctrl)
        self.setup_ikfk_visibility([ik_ctrl_grp, ik_thi_offs], [fk_ctrl_grp], setting_ctrl)

        # [Squash & Stretch]
        distance_node = utils.create_distance_measurement(ik_thi_ctrl, ik_leg_ctrl, self.get_name('ik_dist'))
        dist_grps = self.stretch_and_squash([ik_thi_ctrl, ik_leg_ctrl], ik_jnts[0:2], distance_node, self.part_name, stretch_axis, ik_pv_ctrl, global_ctrl, connect_to_hip)

        # [Advanced Ribbon setup]
        ribbon_surf, ribbon_bnd_jnts, ribbon_twk_offs, fol_sys_grp, follicles = self.create_ribbon(drv_jnts, self.part_name, number_of_fol)
        twist_jnt = self.create_twist_jnt(drv_jnts)
        fol_ctrl_grps, up_low_twk_jnts, mid_twk_jnts, twk_ctrls, fol_ctrl_grp = self.create_follicle_ctrl([thi_fk_ctrl, kn_fk_ctrl, ak_fk_ctrl], drv_jnts=drv_jnts)
        
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

        if connect_to_hip:
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

        # [Organize hierarchy and apply options]
        pelvis_offs, pelvis_ctrl = utils.create_ctrl(self.get_name('pelvis_ctrl'), 12, target=pelvis_jnt, offs_grp=True, color=self.color, thickness=2, rot_offset=ctrl_rot_offset, normal=(0, 1, 0))
        cmds.setAttr(f"{pelvis_offs}.rotate",  0, 0, 0, type="double3")
        cmds.parentConstraint(pelvis_ctrl, pelvis_jnt, mo=True)
        
        mirror_scale_targets = [ik_leg_offs, ik_thi_offs, ik_pv_offs, pelvis_offs]
        for offs in mirror_scale_targets:
            cmds.setAttr(f"{offs}.scaleX", self.mirror_val)

        if connect_to_hip:
            cmds.parent(pelvis_offs, spine_hip_ctrl)
            print("-> Successfully connected to Spine part (Hip).")
        else:
            cmds.parent(pelvis_offs, ctrl_grp)
            print("-> Built independently, ignoring Spine.")

        leg_ctrl_grp = cmds.group(ik_ctrl_grp, fol_ctrl_grp, setting_offs, name=self.get_name('ctrl_grp'), w=True)
        cmds.parent(leg_ctrl_grp, global_ctrl)
        
        cmds.parent(fk_ctrl_grp, pelvis_ctrl)
        cmds.parent(ik_thi_offs, pelvis_ctrl)

        leg_dnt = cmds.group(ribbon_surf, fol_sys_grp, distance_node, *dist_grps, w=True, name=self.get_name('DO_NOT_TOUCH'))
        cmds.parent(leg_dnt, dnt_grp)
        cmds.setAttr(f"{leg_dnt}.visibility", 0)

        ctrls_to_lock = [pelvis_ctrl, ik_thi_ctrl, ik_pv_ctrl, thi_fk_ctrl, kn_fk_ctrl, setting_ctrl, ik_leg_ctrl, ak_fk_ctrl]
        for ctrl in ctrls_to_lock:
            utils.lock_and_hide(ctrl, attrs=['v', 'sx', 'sy', 'sz'])
        tw_ctrls_to_lock = [twk_ctrls[0], twk_ctrls[1], twk_ctrls[2]]
        for ctrl in tw_ctrls_to_lock:
            utils.lock_and_hide(ctrl, attrs=['v'])
        utils.lock_and_hide([ik_pv_ctrl,ik_thi_ctrl], attrs=['rx', 'ry', 'rz'])
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
            "pelvis_ctrl": pelvis_ctrl,
            "ik_ctrl": ik_leg_ctrl,
            "ik_thi_ctrl": ik_thi_ctrl,
            "ik_pv_ctrl": ik_pv_ctrl,
            "fk_thigh_ctrl": thi_fk_ctrl,
            "fk_knee_ctrl": kn_fk_ctrl,
            "fk_ankle_ctrl": ak_fk_ctrl,
            "setting_ctrl": setting_ctrl,
            "tweak_up_ctrl": twk_ctrls[0],
            "tweak_mid_ctrl": twk_ctrls[1],
            "tweak_lo_ctrl": twk_ctrls[2],
            "pelvis_bnd_jnt": pelvis_jnt,
            "drv_ankle": drv_jnts[-1],
            "leg_ik_hdl": leg_ik_hdl,
            "ribbon_surf": ribbon_surf
        })

        updated_leg_jnts = [pelvis_jnt] + drv_jnts
        self.save_settings({
            "leg_jnts": updated_leg_jnts,
            "drv_jnts": drv_jnts,
            "ik_jnts": ik_jnts,
            "fk_jnts": fk_jnts,
            "ribbon_bnd_jnts": ribbon_bnd_jnts,
            "pv_multiplier": pv_multiplier,
            "number_of_fol": number_of_fol,
            "stretch_axis": stretch_axis,
            "ctrl_rot_offset": ctrl_rot_offset,
            "pv_rot_offset": pv_rot_offset,
            "ankle_rot_offset": ankle_rot_offset,
            "connect_to_hip": connect_to_hip
        })

        print(f"✅ [{self.part_name}] Build complete!\n")