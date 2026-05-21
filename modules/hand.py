import maya.cmds as cmds
from core.base_builder import BaseBuilder
from core import rig_utils as utils
import re

class HandBuilder(BaseBuilder):

    def __init__(self, side="L"):
        super().__init__(prefix="hand", side=side)

    def _create_fk_ctrl(self, jnt, radius=5.0, color=None, thickness=1.0, normal=(1, 0, 0)):
        orig_parent = cmds.listRelatives(jnt, parent=True)
        ctrl_name = jnt.replace('_bnd_jnt', '').replace('_jnt', '') + '_ctrl'
        
        offs_grp, ctrl = utils.create_ctrl(ctrl_name, radius=radius, target=jnt, offs_grp=True, color=color, thickness=thickness, normal = normal)
        
        if orig_parent:
            cmds.parent(offs_grp, orig_parent[0])
            
        cmds.parent(jnt, ctrl)
        utils.set_joint_drawstyle_none(jnt) 
        
        return offs_grp, ctrl

    def _create_cup_ctrl(self, meta_grps, hand_ctrl):
        con_grp = []
        for g in meta_grps:
            grp = utils.create_offset_grp(g, '_cup_con')
            con_grp.append(grp)
        
        index_fin, middle_fin, ring_fin, pinky_fin = '', '', '', ''
        for m in con_grp:
            if 'index' in m: index_fin = m
            elif 'middle' in m: middle_fin = m
            elif 'ring' in m: ring_fin = m
            elif 'pinky' in m: pinky_fin = m
        
        inner_offs, inner_ctrl = utils.create_ctrl(self.get_name('inner_cup_ctrl'), 7, target=hand_ctrl, offs_grp=True, color=self.sc_color, normal=(1, 0, 0))
        outer_offs, outer_ctrl = utils.create_ctrl(self.get_name('outer_cup_ctrl'), 7, target=hand_ctrl, offs_grp=True, color=self.sc_color, normal=(1, 0, 0))
        
        cmds.setAttr(f'{outer_offs}.scaleZ', -1)
        
        if index_fin: index_const = cmds.parentConstraint(inner_ctrl, index_fin, mo=True)[0]
        if pinky_fin: pinky_const = cmds.parentConstraint(outer_ctrl, pinky_fin, mo=True)[0]
        
        if middle_fin:
            mid_const = cmds.parentConstraint(inner_ctrl, outer_ctrl, middle_fin, mo=True, w=0.5)[0]
            cmds.parentConstraint(inner_ctrl, middle_fin, e=True, w=0.666)
            cmds.parentConstraint(outer_ctrl, middle_fin, e=True, w=0.333)
            cmds.setAttr(f'{mid_const}.interpType', 2)

        if ring_fin:
            ring_const = cmds.parentConstraint(inner_ctrl, outer_ctrl, ring_fin, mo=True, w=0.5)[0]
            cmds.parentConstraint(inner_ctrl, ring_fin, e=True, w=0.333)
            cmds.parentConstraint(outer_ctrl, ring_fin, e=True, w=0.666)
            cmds.setAttr(f'{ring_const}.interpType', 2)
        
        if index_fin: cmds.setAttr(f'{index_const}.interpType', 2)
        if pinky_fin: cmds.setAttr(f'{pinky_const}.interpType', 2)
        
        cmds.parent(inner_offs, hand_ctrl)
        cmds.parent(outer_offs, hand_ctrl)
        
        utils.lock_and_hide(inner_ctrl, attrs=['sx', 'sy', 'sz', 'v'])
        utils.lock_and_hide(outer_ctrl, attrs=['sx', 'sy', 'sz', 'v'])


    def _spread_ctrl(self, first_ctrls, hand_ctrl, spread_axis='Y'):
        spread_axis = spread_axis.upper()
        offs_grp, spread_ctrl = utils.create_ctrl(self.get_name('spread_ctrl'), 10, target=hand_ctrl, offs_grp=True, color=self.sc_color, normal=(1, 0, 0))
        
        index_con, mid_con, ring_con, pink_con = '', '', '', ''
        for c in first_ctrls:
            con_grp = utils.create_offset_grp(c, '_spread')
            if 'index' in c: index_con = con_grp
            elif 'middle' in c: mid_con = con_grp
            elif 'ring' in c: ring_con = con_grp
            elif 'pinky' in c: pink_con = con_grp
            
        rot_attr = f'rotate{spread_axis}'
            
        if index_con: cmds.connectAttr(f'{spread_ctrl}.{rot_attr}', f'{index_con}.{rot_attr}')
        
        if mid_con:
            mid_mult = cmds.createNode('multiplyDivide', name=self.get_name('mid_spread_mult'))
            cmds.setAttr(f'{mid_mult}.input2X', 0.5)
            cmds.connectAttr(f'{spread_ctrl}.{rot_attr}', f'{mid_mult}.input1X')
            cmds.connectAttr(f'{mid_mult}.outputX', f'{mid_con}.{rot_attr}')
        
        if ring_con:
            ring_mult = cmds.createNode('multiplyDivide', name=self.get_name('ring_spread_mult'))
            cmds.setAttr(f'{ring_mult}.input2X', -0.5)
            cmds.connectAttr(f'{spread_ctrl}.{rot_attr}', f'{ring_mult}.input1X')
            cmds.connectAttr(f'{ring_mult}.outputX', f'{ring_con}.{rot_attr}')

        if pink_con:
            pink_mult = cmds.createNode('multiplyDivide', name=self.get_name('pinky_spread_mult'))
            cmds.setAttr(f'{pink_mult}.input2X', -1)
            cmds.connectAttr(f'{spread_ctrl}.{rot_attr}', f'{pink_mult}.input1X')
            cmds.connectAttr(f'{pink_mult}.outputX', f'{pink_con}.{rot_attr}')
        
        cmds.parent(offs_grp, hand_ctrl)
        
        # Smart Lock: lock all except the user-specified spread_axis
        attrs_to_lock = ['tx', 'ty', 'tz', 'sx', 'sy', 'sz', 'v']
        for ax in ['X', 'Y', 'Z']:
            if ax != spread_axis:
                attrs_to_lock.append(f'r{ax.lower()}') # 예: spread_axis가 Y면, rx와 rz가 잠김
                
        utils.lock_and_hide(spread_ctrl, attrs=attrs_to_lock)


    def build(self, hand_jnts, curl_axis='Z', spread_axis='Y', connect_to_wrist=True):
        if not hand_jnts:
            cmds.warning("Please select hand/finger joints.")
            return

        print(f"\n--- [{self.part_name}] Build started ---")

        global_ctrl = self.get_dependency("global_C", "global_ctrl")
        ctrl_grp = self.get_dependency("global_C", "ctrl_grp")
        
        # [Create and organize Hand Group]
        hand_grp = cmds.group(empty=True, name=self.get_name("grp"))
        if ctrl_grp and cmds.objExists(ctrl_grp):
            cmds.parent(hand_grp, global_ctrl)

        curl_finger, first_grps, first_ctrls, ctrls, meta = [], [], [], [], []
        hand_ctrl, hand_ctrl_offs = '', ''
        
        for jnt in hand_jnts:
            if '_04_' in jnt: 
                continue
                
            offs_grp, ctrl = self._create_fk_ctrl(jnt, radius=1.5 if not 'hand' in jnt else 6, color=self.color, thickness=1.5)
            ctrls.append(ctrl)
            
            if 'hand' in jnt:
                hand_ctrl = ctrl
                hand_ctrl_offs = offs_grp
                cmds.parent(hand_ctrl_offs, hand_grp)
            elif '_00_' in jnt:
                meta.append(ctrl)
            else:
                curl_finger.append(ctrl)
                
            if '_01_' in jnt:
                first_grps.append(offs_grp)
                first_ctrls.append(ctrl)
                    
        filtered_curl_fin = [item for item in curl_finger if '_01_' not in item] 
        
        sdk_grps = []
        for finger in filtered_curl_fin:
            offs_grp = utils.create_offset_grp(finger, '_curl_sdk')
            sdk_grps.append(offs_grp)

        for fg in first_grps:
            curl_ctrl_name = fg.replace('_ctrl_offs', '_curl_ctrl')
            curl_ctrl_offs, curl_ctrl = utils.create_ctrl(curl_ctrl_name, radius=2.5, target=fg, offs_grp=True, color=self.sc_color, thickness=1.0, normal=(0, 0, 1))
            
            orig_parent = cmds.listRelatives(fg, parent=True)
            if orig_parent: cmds.parent(curl_ctrl_offs, orig_parent[0])
            cmds.parent(fg, curl_ctrl)
            
            suffix = fg.split('_')[2]
            for sdk in sdk_grps:
                if suffix in sdk:
                    cmds.connectAttr(f"{curl_ctrl}.rotate{curl_axis.upper()}", f"{sdk}.rotate{curl_axis.upper()}", force=True)

        if meta and hand_ctrl:
            self._create_cup_ctrl(meta, hand_ctrl)
        
        # Pass the spread_axis parameter
        if first_ctrls and hand_ctrl:
            self._spread_ctrl(first_ctrls, hand_ctrl, spread_axis=spread_axis)

        if connect_to_wrist and hand_ctrl_offs:
            # Remove '_meta' and use only the pure part name.
            arm_part = f"arm_{self.side}"
            
            ik_wrist_ctrl = self.get_dependency(arm_part, "ik_ctrl")
            fk_wrist_ctrl = self.get_dependency(arm_part, "fk_wrist_ctrl")
            setting_ctrl = self.get_dependency(arm_part, "setting_ctrl")
            wrist_drv = self.get_dependency(arm_part, "drv_wrist")

            if all([ik_wrist_ctrl, fk_wrist_ctrl, setting_ctrl, wrist_drv]):
                # 1. 위치/회전은 메인 그룹(hand_grp)이 손목을 따라가게 제약
                cmds.parentConstraint(wrist_drv, hand_grp, mo=True)
                
                # 2. Scale Blending 노드 생성 및 연결
                blend_node = cmds.createNode("blendColors", name=self.get_name("scale_blend"))
                
                cmds.connectAttr(f"{ik_wrist_ctrl}.scale", f"{blend_node}.color1")
                cmds.connectAttr(f"{fk_wrist_ctrl}.scale", f"{blend_node}.color2")
                cmds.connectAttr(f"{setting_ctrl}.Ik_Fk_Switch", f"{blend_node}.blender")
                
                # 3. 블렌드 결과를 손목 오프셋 그룹의 스케일에 직접 연결
                cmds.connectAttr(f"{blend_node}.output", f"{hand_ctrl_offs}.scale")
                
                print(f"-> [{self.part_name}] Scale blending system and wrist connection complete.")
            else:
                cmds.warning("Required controllers for Arm module not found. Skipping connection.")

        output_map = {}
        if hand_ctrl:
            output_map["hand_ctrl"] = hand_ctrl
            
        # Iterate all finger controllers and assign clean keys.
        for ctrl in ctrls:
            # Example: 'finger_l_index_01_ctrl' -> 'index_01_ctrl' parsing
            clean_key = re.sub(r'^(finger|hand)_[lLrRcC]_', '', ctrl)
            output_map[clean_key] = ctrl
            
        # Now dozens of controllers are robustly connected to the meta node!
        self.register_outputs(output_map)

        self.save_settings({
            "hand_jnts": hand_jnts
        })

        print(f"[{self.part_name}] Build complete!\n")