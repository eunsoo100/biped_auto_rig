import maya.cmds as cmds
import maya.mel as mel
from .base_builder import BaseBuilder
from . import rig_utils as utils

class LimbBaseBuilder(BaseBuilder):
    """
    팔(Arm)과 다리(Leg) 리깅 시스템의 공통 로직을 담은 부모 클래스입니다.
    """
    def __init__(self, prefix, side):
        super().__init__(prefix=prefix, side=side)

    def _duplicate_chain(self, jnt_list, replace_str, new_str):
        chain = []
        for i, jnt in enumerate(jnt_list):
            new_name = jnt.replace(replace_str, new_str)
            dup = cmds.duplicate(jnt, parentOnly=True, name=new_name)[0]
            if cmds.listRelatives(dup, parent=True):
                dup = cmds.parent(dup, world=True)[0]
            if i > 0:
                cmds.parent(dup, chain[i-1])
            chain.append(dup)
        return chain

    def create_poleVector_ctrl(self, pos, mid_jnt, name, radius=5, rot_offset=(0,0,0)):
        offs_grp_name = self.get_name(f'{name}_pv_ctrl_offs')
        pv_ctrl_name = self.get_name(f'{name}_pv_ctrl')
        
        offs_grp = cmds.group(empty=True, name=offs_grp_name)
        cmds.xform(offs_grp, translation=pos, worldSpace=True)
        
        # Joint Base 회전 매칭
        cmds.matchTransform(offs_grp, mid_jnt, pos=False, rot=True)
        
        if rot_offset != (0, 0, 0):
            cmds.rotate(rot_offset[0], rot_offset[1], rot_offset[2], offs_grp, relative=True, objectSpace=True)

        utils.create_ctrl(pv_ctrl_name, radius=radius, color=self.color, thickness=2)
        cmds.parent(pv_ctrl_name, offs_grp)
        utils.clean_transformation(pv_ctrl_name)
        
        return offs_grp_name, pv_ctrl_name

    def setup_ikfk_switch(self, ik_jnts, fk_jnts, drv_jnts, setting_ctrl):
        if not cmds.attributeQuery('Ik_Fk_Switch', node=setting_ctrl, exists=True):
            cmds.addAttr(setting_ctrl, longName='Ik_Fk_Switch', attributeType='float', defaultValue=0, minValue=0, maxValue=1, keyable=True)
        ik_fk_swt = f'{setting_ctrl}.Ik_Fk_Switch'

        for i in range(len(drv_jnts)):
            ik_jnt, fk_jnt, drv_jnt = ik_jnts[i], fk_jnts[i], drv_jnts[i]
            part_name = drv_jnt.split('_')[-3] 

            bc_trans = cmds.createNode('blendColors', name=self.get_name(f'{part_name}_ikfk_trans_bc'))
            bc_rot = cmds.createNode('blendColors', name=self.get_name(f'{part_name}_ikfk_rot_bc'))
            bc_scale = cmds.createNode('blendColors', name=self.get_name(f'{part_name}_ikfk_scale_bc'))

            cmds.connectAttr(ik_fk_swt, f'{bc_trans}.blender', force=True)
            cmds.connectAttr(ik_fk_swt, f'{bc_rot}.blender', force=True)
            cmds.connectAttr(ik_fk_swt, f'{bc_scale}.blender', force=True)

            for ax, col in zip(['X','Y','Z'], ['R','G','B']):
                cmds.connectAttr(f'{fk_jnt}.translate{ax}', f'{bc_trans}.color1{col}', force=True)
                cmds.connectAttr(f'{ik_jnt}.translate{ax}', f'{bc_trans}.color2{col}', force=True)
                cmds.connectAttr(f'{bc_trans}.output{col}', f'{drv_jnt}.translate{ax}', force=True)
                cmds.connectAttr(f'{fk_jnt}.rotate{ax}', f'{bc_rot}.color1{col}', force=True)
                cmds.connectAttr(f'{ik_jnt}.rotate{ax}', f'{bc_rot}.color2{col}', force=True)
                cmds.connectAttr(f'{bc_rot}.output{col}', f'{drv_jnt}.rotate{ax}', force=True)
                cmds.connectAttr(f'{fk_jnt}.scale{ax}', f'{bc_scale}.color1{col}', force=True)
                cmds.connectAttr(f'{ik_jnt}.scale{ax}', f'{bc_scale}.color2{col}', force=True)
                cmds.connectAttr(f'{bc_scale}.output{col}', f'{drv_jnt}.scale{ax}', force=True)

    def setup_ikfk_visibility(self, ik_grps, fk_grps, setting_ctrl):
        driver = f"{setting_ctrl}.Ik_Fk_Switch"
        if not isinstance(ik_grps, list): ik_grps = [ik_grps]
        if not isinstance(fk_grps, list): fk_grps = [fk_grps]
        for ik_grp in ik_grps:
            cmds.setDrivenKeyframe(ik_grp, at='visibility', v=1, cd=driver, dv=0)
            cmds.setDrivenKeyframe(ik_grp, at='visibility', v=0, cd=driver, dv=1)
        for fk_grp in fk_grps:
            cmds.setDrivenKeyframe(fk_grp, at='visibility', v=0, cd=driver, dv=0)
            cmds.setDrivenKeyframe(fk_grp, at='visibility', v=1, cd=driver, dv=1)

    def create_sqush_nodes(self, name):
        power = cmds.createNode('multiplyDivide', name=f'{name}_pow')
        cmds.setAttr(f'{power}.operation', 3)
        cmds.setAttr(f'{power}.input2X', 0.5)
        div = cmds.createNode('multiplyDivide', name=f'{name}_div')
        cmds.setAttr(f'{div}.operation', 2)
        cmds.setAttr(f'{div}.input1X', 1)
        cmds.connectAttr(f'{power}.outputX', f'{div}.input2X')
        vol_bc = cmds.createNode('blendColors', name=f'{name}_volume_bc')
        cmds.setAttr(f'{vol_bc}.color2R', 1)
        cmds.connectAttr(f'{div}.outputX', f'{vol_bc}.color1R')
        return power, vol_bc

    def create_volume_presv(self, distance_node, name):
        distance_shape = cmds.listRelatives(distance_node, shapes=True)[0]
        distance_value = cmds.getAttr(f'{distance_shape}.distance')
        global_sc = cmds.createNode('multiplyDivide', name=f"{name}_global_sc")
        cmds.setAttr(f'{global_sc}.operation', 2)
        cmds.setAttr(f'{global_sc}.input2X', 1)
        cmds.connectAttr(f'{distance_shape}.distance', f'{global_sc}.input1X')
        dist_perc = cmds.createNode('multiplyDivide', name=f'{name}_dist_percentage')
        cmds.setAttr(f'{dist_perc}.operation', 2)
        cmds.setAttr(f'{dist_perc}.input2X', distance_value)
        cmds.connectAttr(f'{global_sc}.outputX', f'{dist_perc}.input1X')
        manual_mult = cmds.createNode('multDoubleLinear', name=f'{name}_manual_mult')
        cmds.connectAttr(f'{dist_perc}.outputX', f'{manual_mult}.input1')
        strch_bc = cmds.createNode('blendColors', name=f'{name}_strch_bc')
        cmds.setAttr(f'{strch_bc}.color2R', 1)
        cmds.connectAttr(f'{manual_mult}.output', f'{strch_bc}.color1R')
        cond = cmds.createNode('condition', name=f'{name}_condition')
        cmds.setAttr(f'{cond}.operation', 2)
        cmds.setAttr(f'{cond}.secondTerm', distance_value)
        cmds.connectAttr(f'{global_sc}.outputX', f'{cond}.firstTerm')
        cmds.connectAttr(f'{strch_bc}.outputR', f'{cond}.colorIfTrueR')
        return manual_mult, strch_bc, cond, global_sc

    def create_mid_lock(self, pv_ctrl, ctrls, mid_jnt, name):
        cmds.addAttr(pv_ctrl, longName='Lock', keyable=True, min=0, max=1)
        upper_dist = utils.create_distance_measurement(ctrls[0], pv_ctrl, f'{name}_lock_up')
        lower_dist = utils.create_distance_measurement(ctrls[1], pv_ctrl, f'{name}_lock_lo')
        cmds.matchTransform(pv_ctrl, mid_jnt)
        
        up_dist_shape = cmds.listRelatives(upper_dist, shapes=True)[0]
        lo_dist_shape = cmds.listRelatives(lower_dist, shapes=True)[0]
        
        up_dist_val = cmds.getAttr(f'{up_dist_shape}.distance')
        lo_dist_val = cmds.getAttr(f'{lo_dist_shape}.distance')
        utils.clean_transformation(pv_ctrl)
        
        lock_global_sc = cmds.createNode('multiplyDivide', name=f'{name}_lock_global_sc')
        cmds.setAttr(f'{lock_global_sc}.operation', 2) # Divide
        cmds.setAttr(f'{lock_global_sc}.input2X', 1)
        cmds.setAttr(f'{lock_global_sc}.input2Y', 1)
        
        cmds.connectAttr(f'{up_dist_shape}.distance', f'{lock_global_sc}.input1X')
        cmds.connectAttr(f'{lo_dist_shape}.distance', f'{lock_global_sc}.input1Y')
        
        dist_perc = cmds.createNode('multiplyDivide', name=f'{name}_lock_dist_perc')
        cmds.setAttr(f'{dist_perc}.operation', 2)
        cmds.setAttr(f'{dist_perc}.input2X', up_dist_val)
        cmds.setAttr(f'{dist_perc}.input2Y', lo_dist_val)
        
        cmds.connectAttr(f'{lock_global_sc}.outputX', f'{dist_perc}.input1X')
        cmds.connectAttr(f'{lock_global_sc}.outputY', f'{dist_perc}.input1Y')
        
        bc = cmds.createNode('blendColors', name=f'{name}_lock_bc')
        cmds.connectAttr(f'{dist_perc}.outputX', f'{bc}.color1R')
        cmds.connectAttr(f'{dist_perc}.outputY', f'{bc}.color1G')
        
        up_power, up_bc_node = self.create_sqush_nodes(f'{name}_up')
        lo_power, lo_bc_node = self.create_sqush_nodes(f'{name}_lo')
        
        cmds.connectAttr(f'{bc}.outputR', f'{up_power}.input1X')
        cmds.connectAttr(f'{bc}.outputG', f'{lo_power}.input1X')
        cmds.connectAttr(f'{pv_ctrl}.Lock', f'{bc}.blender')
        
        return bc, up_bc_node, lo_bc_node, [upper_dist, lower_dist], lock_global_sc

    def stretch_and_squash(self, ctrls, joints, distance_node, name, stretch_axis, pv_ctrl, global_ctrl, is_connect):
        stretch_axis = stretch_axis.upper()
        all_axes = ['X', 'Y', 'Z']
        if stretch_axis not in all_axes: stretch_axis = 'Y'
        volume_axes = [ax for ax in all_axes if ax != stretch_axis]
        
        lock_bc, lock_up_vol_bc, lock_lo_vol_bc, dist_grps, lock_global_sc = self.create_mid_lock(pv_ctrl, ctrls, joints[1], name)
        manual_mult_node, stretch_bc_node, condition_node, global_sc = self.create_volume_presv(distance_node, name)
        
        attr_ctrl = ctrls[-1]
        if is_connect:
            cmds.connectAttr(f'{global_ctrl}.scale{stretch_axis}', f'{global_sc}.input2X', force=True)
            cmds.connectAttr(f'{global_ctrl}.scale{stretch_axis}', f'{global_sc}.input2X', force=True)
            cmds.connectAttr(f'{global_ctrl}.scale{stretch_axis}', f'{lock_global_sc}.input2X', force=True)

        cmds.connectAttr(f'{condition_node}.outColorR', f'{lock_bc}.color2R', force=True)
        cmds.connectAttr(f'{condition_node}.outColorR', f'{lock_bc}.color2G', force=True)
        
        for attr in ['auto_stretch', 'auto_volume']:
            if cmds.attributeQuery(attr, node=attr_ctrl, exists=True): cmds.deleteAttr(f"{attr_ctrl}.{attr}")
            cmds.addAttr(attr_ctrl, longName=attr, attributeType='float', keyable=True, min=0, max=1)
            
        if cmds.attributeQuery('manual_stretch', node=attr_ctrl, exists=True): cmds.deleteAttr(f"{attr_ctrl}.manual_stretch")
        cmds.addAttr(attr_ctrl, longName='manual_stretch', attributeType='float', keyable=True, min=1, max=10)
            
        for joint in joints:
            if joint == joints[0]:
                cmds.connectAttr(f'{lock_bc}.outputR', f'{joint}.scale{stretch_axis}', force=True)
                cmds.connectAttr(f'{lock_up_vol_bc}.outputR', f'{joint}.scale{volume_axes[0]}', force=True)
                cmds.connectAttr(f'{lock_up_vol_bc}.outputR', f'{joint}.scale{volume_axes[1]}', force=True)
            else:
                cmds.connectAttr(f'{lock_bc}.outputG', f'{joint}.scale{stretch_axis}', force=True)
                cmds.connectAttr(f'{lock_lo_vol_bc}.outputR', f'{joint}.scale{volume_axes[0]}', force=True)
                cmds.connectAttr(f'{lock_lo_vol_bc}.outputR', f'{joint}.scale{volume_axes[1]}', force=True)
                
        cmds.connectAttr(f'{attr_ctrl}.auto_stretch', f'{stretch_bc_node}.blender', force=True)
        cmds.connectAttr(f'{attr_ctrl}.manual_stretch', f'{manual_mult_node}.input2', force=True)
        cmds.connectAttr(f'{attr_ctrl}.manual_stretch', f'{condition_node}.colorIfFalseR', force=True)
        cmds.connectAttr(f'{attr_ctrl}.auto_volume', f'{lock_up_vol_bc}.blender', force=True)
        cmds.connectAttr(f'{attr_ctrl}.auto_volume', f'{lock_lo_vol_bc}.blender', force=True)
        
        return dist_grps

    def parent_jnts(self, follicles_list, name):
        joints = []
        twk_offs_list = []
        
        for i, fol in enumerate(follicles_list):
            twk_offs = self.get_name(f'ribbon_{i + 1:02d}_twk_offs')
            cmds.group(empty=True, name=twk_offs)
            cmds.matchTransform(twk_offs, fol)
            cmds.parent(twk_offs, fol)

            jnt_name = self.get_name(f'ribbon_{i + 1:02d}_bnd_jnt')
            cmds.joint(n=jnt_name)
            cmds.matchTransform(jnt_name, twk_offs)
            cmds.FreezeTransformations(jnt_name)
            
            joints.append(jnt_name)
            twk_offs_list.append(twk_offs)
            cmds.select(clear=True)
            
        return joints, twk_offs_list

    def create_ribbon(self, joints, name, u_span):
        positions = [cmds.xform(jnt, query=True, worldSpace=True, translation=True) for jnt in joints]
        first_crv = cmds.curve(p=positions, degree=1, name=self.get_name('ribbon_crv_1'))
        second_crv = cmds.duplicate(first_crv, name=self.get_name('ribbon_crv_2'))[0]

        cmds.setAttr(f'{first_crv}.translateZ', 2)
        cmds.setAttr(f'{second_crv}.translateZ', -2)
        
        ribbon_surf = cmds.loft(first_crv, second_crv, constructionHistory=False, name=self.get_name('ribbon_surf'),
                                uniform=True, close=False, ar=True, d=3, ss=0, rn=False, po=0, rsn=True)[0]
        cmds.rebuildSurface(ribbon_surf, ch=1, rpo=1, rt=0, end=1, kr=0, kcp=0, kc=0, su=u_span, du=3, sv=1, dv=3, tol=0.01, fr=0, dir=2)
        cmds.delete([first_crv, second_crv])
        
        cmds.select(ribbon_surf, replace=True)
        mel.eval(f"createHair {u_span} 1 10 0 0 0 0 5 0 1 1 1;")
        hair = cmds.ls(sl=True)
        hair_p = cmds.listRelatives(hair, p=True)
        hairSystem = cmds.listConnections(hair) or []

        for sys in set(hairSystem):
            if 'nucleus' in sys or 'pfxHair' in sys: cmds.delete(sys)

        loft_shpe_node = cmds.listRelatives(ribbon_surf)[0]
        loftSystem = cmds.listConnections(loft_shpe_node)
        cmds.delete(hair_p)
        
        follicle_list_inOrder = sorted(list(set(loftSystem)), key=utils.get_number)
        if 'initialShadingGroup' in follicle_list_inOrder:
            follicle_list_inOrder.remove('initialShadingGroup')
            
        follicle_list_renamed = []
        for i, fol in enumerate(follicle_list_inOrder):
            follicle_name = self.get_name(f'follicle_{i + 1:02d}')
            cmds.rename(fol, follicle_name)
            cmds.delete(cmds.listRelatives(follicle_name)[1])
            follicle_list_renamed.append(follicle_name)

        follicle_grp_name = self.get_name('follicle_grp')
        cmds.rename(cmds.listRelatives(follicle_list_renamed[0], ap=True)[0], follicle_grp_name)
        
        bnd_jnts, twk_offs_list = self.parent_jnts(follicle_list_renamed, name)
        return ribbon_surf, bnd_jnts, twk_offs_list, follicle_grp_name, follicle_list_renamed

    def scale_connect_attr(self, drv_axis, drn_axis, driver, driven):
        for obj in driven:
            for d_ax, drn_ax in zip(drv_axis, drn_axis):
                cmds.connectAttr(f'{driver}.scale{d_ax}', f'{obj}.scale{drn_ax}', force=True)

    def create_twist_jnt(self, drv_jnt):
        upper_jnt, mid_jnt, lower_jnt = drv_jnt[0], drv_jnt[1], drv_jnt[2]
        
        up_aim, up_up = utils.get_aim_and_up_vectors(upper_jnt, mid_jnt)
        
        up_twist = cmds.duplicate(upper_jnt, po=True, name=self.get_name('up_twist_jnt'))[0]
        cmds.pointConstraint(upper_jnt, up_twist, mo=True)

        # Use "objectrotation" with the upper joint as worldUpObject
        # to properly sync roll rotation and prevent flipping on mirrored side.
        cmds.aimConstraint(mid_jnt, up_twist, mo=True, weight=1, aimVector=up_aim, upVector=up_up, 
                           worldUpType="objectrotation", worldUpVector=up_up, worldUpObject=upper_jnt)
        
        # ---------------------------------------------------------------------
        
        lo_aim, lo_up = utils.get_aim_and_up_vectors(mid_jnt, lower_jnt)
        
        # Invert aim vector so the lower twist joint looks back up toward the mid joint.
        inv_lo_aim = [-v for v in lo_aim]
        
        low_twist = cmds.duplicate(mid_jnt, po=True, name=self.get_name('lo_twist_jnt'))[0]
        cmds.matchTransform(low_twist, lower_jnt, pos=True, rot=False)
        cmds.parent(low_twist, lower_jnt)

        # Use "object" with the lower joint as worldUpObject
        # to prevent rotation flipping on the mirrored side.
        cmds.aimConstraint(mid_jnt, low_twist, mo=True, weight=1, aimVector=inv_lo_aim, upVector=lo_up, 
                           worldUpType="object", worldUpVector=lo_up, worldUpObject=lower_jnt)
        
        return [up_twist, low_twist]

    def create_follicle_ctrl(self, fk_ctrls, drv_jnts=None):
        fol_ctrl_grp = cmds.group(empty=True, world=True, name=self.get_name('fol_ctrl_grp'))
        
        up_twk_offs = cmds.group(empty=True, name=self.get_name('up_tweak_ctrl_offs'))
        mid_twk_offs = cmds.group(empty=True, name=self.get_name('mid_tweak_ctrl_offs'))
        lo_twk_offs = cmds.group(empty=True, name=self.get_name('lo_tweak_ctrl_offs'))

        cmds.delete(cmds.pointConstraint(fk_ctrls[0], fk_ctrls[1], up_twk_offs, mo=False))
        cmds.delete(cmds.parentConstraint(fk_ctrls[1], mid_twk_offs, mo=False))
        cmds.delete(cmds.pointConstraint(fk_ctrls[1], fk_ctrls[2], lo_twk_offs, mo=False))

        # Match rotation from FK controls so tweak ctrls align visually with the rest.
        # The constraint group (up_cons/lo_cons) absorbs the orient blend separately.
        cmds.delete(cmds.orientConstraint(fk_ctrls[0], up_twk_offs, mo=False))
        cmds.delete(cmds.orientConstraint(fk_ctrls[1], lo_twk_offs, mo=False))

        up_twk_ctrl = utils.create_ctrl(self.get_name('up_tweak_ctrl'), radius=6, color=self.sc_color, normal=(1, 0, 0))
        cmds.parent(up_twk_ctrl, up_twk_offs)
        utils.clean_transformation(up_twk_ctrl)

        mid_twk_ctrl = utils.create_ctrl(self.get_name('mid_tweak_ctrl'), radius=6, color=self.sc_color, normal=(1, 0, 0))
        cmds.parent(mid_twk_ctrl, mid_twk_offs)
        utils.clean_transformation(mid_twk_ctrl)

        lo_twk_ctrl = utils.create_ctrl(self.get_name('lo_tweak_ctrl'), radius=6, color=self.sc_color, normal=(1, 0, 0))
        cmds.parent(lo_twk_ctrl, lo_twk_offs)
        utils.clean_transformation(lo_twk_ctrl)
        # =========================================================================

        cmds.matchTransform(up_twk_offs, fk_ctrls[0], piv=True, pos=False, rot=False)
        cmds.matchTransform(lo_twk_offs, fk_ctrls[1], piv=True, pos=False, rot=False)

        cmds.select(clear=True)
        up_twk_jnt = cmds.joint(n=self.get_name('up_drv_jnt'))
        cmds.parent(up_twk_jnt, up_twk_ctrl)
        utils.clean_transformation(up_twk_jnt, is_joint=True)

        cmds.select(clear=True)
        mid_up_twk_jnt = cmds.joint(n=self.get_name('mid_up_drv_jnt'))
        mid_lo_twk_jnt = cmds.joint(n=self.get_name('mid_lo_drv_jnt'))
        cmds.parent(mid_up_twk_jnt, mid_lo_twk_jnt, mid_twk_ctrl)
        utils.clean_transformation(mid_up_twk_jnt, is_joint=True)
        utils.clean_transformation(mid_lo_twk_jnt, is_joint=True)

        cmds.select(clear=True)
        lo_twk_jnt = cmds.joint(n=self.get_name('lo_drv_jnt'))
        cmds.parent(lo_twk_jnt, lo_twk_ctrl)
        utils.clean_transformation(lo_twk_jnt, is_joint=True)
        
        cmds.parent(up_twk_offs, mid_twk_offs, lo_twk_offs, fol_ctrl_grp)

        return [up_twk_offs, mid_twk_offs, lo_twk_offs], [up_twk_jnt, lo_twk_jnt], [mid_up_twk_jnt, mid_lo_twk_jnt], [up_twk_ctrl, mid_twk_ctrl, lo_twk_ctrl], fol_ctrl_grp

    def surf_transfer_weight(self, source, target, surface, skin_cluster):
        num_u = cmds.getAttr(f'{surface}.spansU') + cmds.getAttr(f'{surface}.degreeU')
        num_v = cmds.getAttr(f'{surface}.spansV') + cmds.getAttr(f'{surface}.degreeV')
        for u in range(num_u):
            for v in range(num_v):
                cv = f'{surface}.cv[{u}][{v}]'
                weight = cmds.skinPercent(skin_cluster, cv, transform=source, query=True)
                if weight > 0:
                    cmds.skinPercent(skin_cluster, cv, transformValue=[(target, weight)])
                    cmds.skinPercent(skin_cluster, cv, transformValue=[(source, 0)])