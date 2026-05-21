import maya.cmds as cmds
from core.base_builder import BaseBuilder
from core import rig_utils as utils

class FootBuilder(BaseBuilder):

    def __init__(self, side="L"):
        super().__init__(prefix="foot", side=side)


    def _duplicate_and_rename(self, base_jnt, target_str, suffix_str):
        new_chain = cmds.duplicate(base_jnt, name=base_jnt.replace(target_str, suffix_str))
        children = cmds.listRelatives(new_chain[0], ad=True, type='joint', fullPath=True)
        if children:
            children.sort(key=lambda x: len(x.split('|')), reverse=True)
            for child in children:
                short_name = child.split('|')[-1]
                cmds.rename(child, short_name.replace(target_str, suffix_str).replace('1', ''))
        return new_chain[0]

    def setup_ikfk_blend(self, ik_jnts, fk_jnts, drv_jnts, setting_ctrl):
        ik_fk_swt = f'{setting_ctrl}.Ik_Fk_Switch'

        for i in range(len(drv_jnts)):
            ik_jnt, fk_jnt, drv_jnt = ik_jnts[i], fk_jnts[i], drv_jnts[i]
            part_name = drv_jnt.split('_')[-3] # extract 'ball' or 'toe'
            
            bc_trans = cmds.createNode('blendColors', name=self.get_name(f'{part_name}_ikfk_trans_bc'))
            bc_rot = cmds.createNode('blendColors', name=self.get_name(f'{part_name}_ikfk_rot_bc'))
            bc_scale = cmds.createNode('blendColors', name=self.get_name(f'{part_name}_ikfk_scale_bc'))

            cmds.connectAttr(ik_fk_swt, f'{bc_trans}.blender', force=True)
            cmds.connectAttr(ik_fk_swt, f'{bc_rot}.blender', force=True)
            cmds.connectAttr(ik_fk_swt, f'{bc_scale}.blender', force=True)

            for ax, col in zip(['X','Y','Z'], ['R','G','B']):
                cmds.connectAttr(f'{ik_jnt}.translate{ax}', f'{bc_trans}.color1{col}', force=True)
                cmds.connectAttr(f'{fk_jnt}.translate{ax}', f'{bc_trans}.color2{col}', force=True)
                cmds.connectAttr(f'{bc_trans}.output{col}', f'{drv_jnt}.translate{ax}', force=True)
                
                cmds.connectAttr(f'{ik_jnt}.rotate{ax}', f'{bc_rot}.color1{col}', force=True)
                cmds.connectAttr(f'{fk_jnt}.rotate{ax}', f'{bc_rot}.color2{col}', force=True)
                cmds.connectAttr(f'{bc_rot}.output{col}', f'{drv_jnt}.rotate{ax}', force=True)
                
                cmds.connectAttr(f'{ik_jnt}.scale{ax}', f'{bc_scale}.color1{col}', force=True)
                cmds.connectAttr(f'{fk_jnt}.scale{ax}', f'{bc_scale}.color2{col}', force=True)
                cmds.connectAttr(f'{bc_scale}.output{col}', f'{drv_jnt}.scale{ax}', force=True)

    def setup_ikfk_visibility(self, ik_grps, fk_grps, setting_ctrl):
        """Controls visibility of Foot controllers based on Leg switch."""
        driver = f"{setting_ctrl}.Ik_Fk_Switch"
        for ik_grp in ik_grps:
            cmds.setDrivenKeyframe(ik_grp, at='visibility', v=0, cd=driver, dv=0)
            cmds.setDrivenKeyframe(ik_grp, at='visibility', v=1, cd=driver, dv=1)
        for fk_grp in fk_grps:
            cmds.setDrivenKeyframe(fk_grp, at='visibility', v=1, cd=driver, dv=0)
            cmds.setDrivenKeyframe(fk_grp, at='visibility', v=0, cd=driver, dv=1)

    def foot_sdk_setup(self, attr_ctrl, ball_ctrl, heel_ctrl, tip_ctrl):
        attributes = {
            'foot_roll': None,
            'roll': (-180, 180),
            'roll_lift': (0, 180), 
            'roll_straight': (0, 180),
            'lean': (-180, 180), 
            'tilt': (-180, 180),
            'heel_spin': (-180, 180),
            'toe_spin': (-180, 180)
        }
        
        for attr, range_val in attributes.items():
            if not cmds.attributeQuery(attr, node=attr_ctrl, exists=True):
                if range_val is None:
                    cmds.addAttr(attr_ctrl, longName=attr, attributeType='enum', en='-', keyable=True)
                    cmds.setAttr(f'{attr_ctrl}.{attr}', lock=True)
                else:
                    min_val, max_val = range_val
                    cmds.addAttr(attr_ctrl, longName=attr, attributeType='float', keyable=True, min=min_val, max=max_val)
        
        utils.simple_connect(attr_ctrl, 'lean', ball_ctrl, 'rotateY')
        utils.simple_connect(attr_ctrl, 'heel_spin', heel_ctrl, 'rotateY')
        utils.simple_connect(attr_ctrl, 'toe_spin', tip_ctrl, 'rotateY')

    def foot_roll(self, driver, driven, prefix, attr='_roll'):
        drv_value = (-90, 0, 45, 90)
        drn_value = [(0, 0 , 1, 0), (0, 0, 0, 1), (-90, 0, 0, 0)]
        driver_attr = f"{driver}.roll"
        adjustable_attr = ['roll_lift', 'roll_straight']
        transform, axis = ['rotate', 'rotate', 'rotate'], ['X', 'X', 'X']
        
        drn_ofs_grp = []
        for drn in driven:
            ofs_grp = utils.create_offset_grp(drn, attr)
            drn_ofs_grp.append(ofs_grp)
            
        for i, drn_node in enumerate(drn_ofs_grp):
            attr_name = f"{transform[i]}{axis[i]}"
            for j, drv_val in enumerate(drv_value):
                drn_val = drn_value[i][j]
                utils.set_driven_key(drn_node, attr_name, drn_val, driver_attr, drv_val)
            
            connections = cmds.listConnections(f"{drn_node}.{attr_name}", type='animCurve')
            if not connections: continue
            sdk_node = connections[0]
            
            if driven[0] in drn_node: # Ball
                lin_mult = cmds.createNode('multDoubleLinear', n=prefix + adjustable_attr[0] + '_mult')
                source_attr = f'{driver}.{adjustable_attr[0]}'
                cmds.connectAttr(f'{sdk_node}.output', f'{lin_mult}.input1', force=True)
                cmds.connectAttr(source_attr, f'{lin_mult}.input2', force=True)
                cmds.connectAttr(f'{lin_mult}.output', f"{drn_node}.{attr_name}", force=True)
                cmds.setAttr(source_attr, 60)
                
            elif driven[1] in drn_node: # Tip
                utils.set_driven_key(drn_node, attr_name, 2, driver_attr, 180)
                lin_mult = cmds.createNode('multDoubleLinear', n=prefix + adjustable_attr[1] + '_mult')
                source_attr = f'{driver}.{adjustable_attr[1]}'
                cmds.connectAttr(f'{sdk_node}.output', f'{lin_mult}.input1', force=True)
                cmds.connectAttr(source_attr, f'{lin_mult}.input2', force=True)
                cmds.connectAttr(f'{lin_mult}.output', f"{drn_node}.{attr_name}", force=True)
                cmds.setAttr(source_attr, 80)
                
        cmds.setAttr(driver_attr, 0)

    # =====================================================================
    # Main build function
    # =====================================================================
    def build(self, ankle_drv_jnt, ankle_fk_jnt, ankle_ik_jnt, loc_heel, loc_toetip, loc_outer, loc_inner):
        print(f"\n--- [{self.part_name}] Foot rig setup started ---")

        # Auto-fetch dependencies (controllers) from Leg module!
        leg_setting_ctrl = self.get_dependency(f"leg_{self.side}", "setting_ctrl")
        ankle_ik_ctrl = self.get_dependency(f"leg_{self.side}", "ik_ctrl")
        ankle_fk_ctrl = self.get_dependency(f"leg_{self.side}", "fk_ankle_ctrl")
        ctrl_grp = self.get_dependency("global_C", "ctrl_grp")

        ball_drv = cmds.listRelatives(ankle_drv_jnt, children=True, type='joint')[0]
        toe_drv = cmds.listRelatives(ball_drv, children=True, type='joint')[0]
        
        ball_drv = cmds.rename(ball_drv, self.get_name("ball_drv_jnt"))
        toe_drv = cmds.rename(toe_drv, self.get_name("toe_drv_jnt"))
        
        # 1. Create IK Chain
        ik_chain_top = self._duplicate_and_rename(ball_drv, 'drv', 'ik')
        ball_ik = ik_chain_top
        toe_ik = cmds.listRelatives(ball_ik, children=True, type='joint')[0]
        cmds.parent(ball_ik, ankle_ik_jnt)
        
        # 2. IK Handles
        ball_ikHandle = cmds.ikHandle(sj=ankle_ik_jnt, ee=ball_ik, sol="ikSCsolver", name=self.get_name("ball_ikHandle"))[0]
        ball_effector = cmds.listConnections(f"{ball_ikHandle}.endEffector", type="ikEffector")[0]
        cmds.rename(ball_effector, ball_ikHandle.replace('ikHandle', 'effector'))
        
        toe_ikHandle = cmds.ikHandle(sj=ball_ik, ee=toe_ik, sol="ikSCsolver", name=self.get_name("toe_ikHandle"))[0]
        toe_effector = cmds.listConnections(f"{toe_ikHandle}.endEffector", type="ikEffector")[0]
        cmds.rename(toe_effector, toe_ikHandle.replace('ikHandle', 'effector'))
        
        # 3. Ball & Toe Controllers (using utils)
        ik_ball_ctrl_offs, ik_ball_ctrl = utils.create_ctrl(self.get_name('ball_ik_ctrl'), target=ball_ik, offs_grp=True, normal=(0, 1, 0), radius=5, color=18)
        ik_toe_ctrl_offs, ik_toe_ctrl = utils.create_ctrl(self.get_name('toe_ik_ctrl'), target=toe_ik, offs_grp=True, normal=(0, 1, 0), radius=6, color=18)
        cmds.matchTransform(ik_toe_ctrl_offs, ik_ball_ctrl_offs)
        
        cmds.parent(ball_ikHandle, ik_ball_ctrl)
        
        if ankle_ik_ctrl:
            ik_leg_children = cmds.listRelatives(ankle_ik_ctrl, children=True, type='transform')
            if ik_leg_children:
                cmds.parent(ik_leg_children, ik_ball_ctrl)
        cmds.parent(toe_ikHandle, ik_toe_ctrl)

        # 4. Foot Roll Locators Controllers
        heel_ctrl_offs, heel_ctrl = utils.create_ctrl(self.get_name('heel_ctrl'), target=loc_heel, offs_grp=True, normal=(0, 1, 1), radius=1.5, color=29)
        toetip_ctrl_offs, toetip_ctrl = utils.create_ctrl(self.get_name('toetip_ctrl'), target=loc_toetip, offs_grp=True, normal=(0, 1, 0), radius=1.5, color=29)
        outer_ctrl_offs, outer_ctrl = utils.create_ctrl(self.get_name('outer_ctrl'), target=loc_outer, offs_grp=True, normal=(0, 1, 0), radius=1.5, color=29)
        inner_ctrl_offs, inner_ctrl = utils.create_ctrl(self.get_name('inner_ctrl'), target=loc_inner, offs_grp=True, normal=(0, 1, 0), radius=1.5, color=29)
        
        if ankle_ik_ctrl:
            cmds.parent(heel_ctrl_offs, ankle_ik_ctrl)
            
        cmds.parent(toetip_ctrl_offs, heel_ctrl)
        cmds.parent(outer_ctrl_offs, toetip_ctrl)
        cmds.parent(inner_ctrl_offs, outer_ctrl)
        cmds.parent([ik_ball_ctrl_offs, ik_toe_ctrl_offs], inner_ctrl)

        # 5. FK Chain Setup
        cmds.matchTransform(ball_drv, ball_ik)
        cmds.matchTransform(toe_drv, toe_ik)
        
        fk_chain_top = self._duplicate_and_rename(ball_drv, 'drv', 'fk')
        ball_fk = fk_chain_top
        toe_fk = cmds.listRelatives(ball_fk, children=True, type='joint')[0]
        cmds.parent(ball_fk, ankle_fk_jnt)
        
        fk_ball_ctrl_offs, fk_ball_ctrl = utils.create_ctrl(self.get_name('ball_fk_ctrl'), target=ball_fk, offs_grp=True, normal=(0, 1, 0), radius=6, color=self.color)
        cmds.parentConstraint(fk_ball_ctrl, ball_fk)
        
        if ankle_fk_ctrl:
            cmds.parent(fk_ball_ctrl_offs, ankle_fk_ctrl)
        
        # 6. [Core] Full integration with Leg switch system and IK/FK
        if leg_setting_ctrl:
            ik_jnts = [ball_ik, toe_ik]
            fk_jnts = [ball_fk, toe_fk]
            drv_jnts = [ball_drv, toe_drv]
            
            # Bind foot joints to Leg's Ik_Fk_Switch.
            self.setup_ikfk_blend(ik_jnts, fk_jnts, drv_jnts, leg_setting_ctrl)
            # Bind Foot Roll group (IK) and FK group visibility to Leg switch!
            self.setup_ikfk_visibility([heel_ctrl_offs], [fk_ball_ctrl_offs], leg_setting_ctrl)

        # 7. Set Driven Keys & Foot Roll Integration
        if ankle_ik_ctrl:
            self.foot_sdk_setup(ankle_ik_ctrl, ik_ball_ctrl, heel_ctrl, toetip_ctrl)
            
            driven_ctrls = [ik_ball_ctrl, toetip_ctrl, heel_ctrl]
            self.foot_roll(driver=ankle_ik_ctrl, driven=driven_ctrls, prefix=f"{self.part_name}_")

            drv_value = (0, 180, -180)
        
            if self.side == "R":
                drn_value = [(0, 180, 0), (0, 0, -180)]
            else:
                drn_value = [(0, -180, 0), (0, 0, 180)]
                
            attr = 'tilt'
            driven = [outer_ctrl, inner_ctrl]
            transform = ['rotate', 'rotate']
            axis = ['Z', 'Z']
            utils.simple_sdk(ankle_ik_ctrl, attr, driven, axis, transform, drv_value, drn_value)
        
        
        # 8-1. Hide visibility ('v') of all controllers created by this script
        all_foot_ctrls = [ik_ball_ctrl, ik_toe_ctrl, fk_ball_ctrl, heel_ctrl, toetip_ctrl, outer_ctrl, inner_ctrl]
        for ctrl in all_foot_ctrls:
            utils.lock_and_hide(ctrl, attrs=['v'])

        # 8-2. Lock and hide Scale ('sx', 'sy', 'sz') of foot roll pivot controllers
        pivot_ctrls = [fk_ball_ctrl, ik_ball_ctrl, ik_toe_ctrl, heel_ctrl, toetip_ctrl, outer_ctrl, inner_ctrl]
        for ctrl in pivot_ctrls:
            utils.lock_and_hide(ctrl, attrs=['v', 'sx', 'sy', 'sz'])

        loc = [loc_heel, loc_toetip, loc_outer, loc_inner]
        cmds.delete(loc)

        # 9. Register metadata
        self.register_outputs({
            "ik_ball_ctrl": ik_ball_ctrl,
            "ik_toe_ctrl": ik_toe_ctrl,
            "fk_ball_ctrl": fk_ball_ctrl,
            "heel_ctrl": heel_ctrl,
            "toetip_ctrl": toetip_ctrl,
            "outer_ctrl": outer_ctrl,
            "inner_ctrl": inner_ctrl,
            "ball_drv_jnt": ball_drv,
            "toe_drv_jnt": toe_drv
        })

        self.save_settings({
            "ankle_drv_jnt": ankle_drv_jnt,
            "ankle_fk_jnt": ankle_fk_jnt,
            "ankle_ik_jnt": ankle_ik_jnt,
            "loc_heel": loc_heel,
            "loc_toetip": loc_toetip,
            "loc_outer": loc_outer,
            "loc_inner": loc_inner
        })

        print(f"[{self.part_name}] Foot rigging and IK/FK system integration complete!\n")