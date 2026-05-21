import maya.cmds as cmds
from .base_builder import BaseBuilder
from . import rig_utils as utils

class SplineBaseBuilder(BaseBuilder):
    """
    Intermediate parent class for modules (Spine, Neck, Tail, etc.) that use the spline IK system.
    Provides advanced spline-related logic in addition to BaseBuilder's basic functionality.
    """
    def __init__(self, prefix, side):
        super().__init__(prefix=prefix, side=side)

    def create_jnt_on_crv_point(self, cv_shape, name_list, curve):
        curve_jnts = []
        cvs = cmds.ls(cv_shape + '.cv[*]', fl=True)
        
        if len(cvs) == len(name_list):
            for i, comp in enumerate(cvs):
                p = cmds.pointPosition(comp, w=True)
                cmds.select(clear=True)
                crv_jnt = cmds.joint(p=p, n=self.get_name(f'crv_{name_list[i]}'))
                curve_jnts.append(crv_jnt)
        else:
            for i, name in enumerate(name_list):
                if name != name_list[0] and name != name_list[-1]:
                    pos_dummy = cmds.group(empty=True, w=True, name='pos_dummy')
                    pos_dummy_loc = []
                    for f in cvs[1:-1]:
                        point_pos = cmds.pointPosition(f, w=True)
                        space_loc = cmds.spaceLocator(n=f'pos_dummy_loc_{f}')[0]
                        cmds.setAttr(f'{space_loc}.translate', *point_pos, type='double3')
                        pos_dummy_loc.append(space_loc)
                        cmds.pointConstraint(space_loc, pos_dummy, mo=False)
                        
                    p = cmds.xform(pos_dummy, q=True, ws=True, t=True)
                    cmds.delete(pos_dummy)
                    cmds.delete(pos_dummy_loc)
                    cmds.select(clear=True)
                    crv_jnt = cmds.joint(p=p, n=self.get_name(f'crv_{name}'))
                    curve_jnts.append(crv_jnt)
                else:
                    p = cmds.pointPosition(cvs[0] if i == 0 else cvs[-1], w=True)
                    cmds.select(clear=True)
                    crv_jnt = cmds.joint(p=p, n=self.get_name(f'crv_{name}'))
                    curve_jnts.append(crv_jnt)
        return curve_jnts

    def create_volume_presv(self, curve, name):
            crvInfo_node = cmds.createNode('curveInfo', name=f'{name}_curveInfo')
            print('in create_volume_presv, curve:', curve)
            # (Modified) Deleted the meaningless utils.connect_transform_attrs line and left only the basic connection.
            cmds.connectAttr(f'{curve}.worldSpace[0]', f'{crvInfo_node}.inputCurve', force=True)
            
            archLength = cmds.getAttr(f'{crvInfo_node}.arcLength')
            glb_sc_node = cmds.createNode('multiplyDivide', name=f'{name}_glb_scale')
            cmds.setAttr(f'{glb_sc_node}.input2X', 1)
            cmds.setAttr(f'{glb_sc_node}.operation', 2)
            cmds.connectAttr(f'{crvInfo_node}.arcLength', f'{glb_sc_node}.input1X', force=True)
            
            dist_percentage_node = cmds.createNode('multiplyDivide', name=f'{name}_dist_percentage')
            cmds.setAttr(f'{dist_percentage_node}.operation', 2)
            cmds.setAttr(f'{dist_percentage_node}.input2X', archLength)
            cmds.connectAttr(f'{glb_sc_node}.outputX', f'{dist_percentage_node}.input1X', force=True)
            
            stretch_bc_node = cmds.createNode('blendColors', name=f'{name}_strch_bc')
            cmds.setAttr(f'{stretch_bc_node}.color2R', 1)
            cmds.connectAttr(f'{dist_percentage_node}.outputX', f'{stretch_bc_node}.color1R', force=True)
            
            power = cmds.createNode('multiplyDivide', name=f'{name}_pow')
            cmds.setAttr(f'{power}.operation', 3)
            cmds.setAttr(f'{power}.input2X', 0.5)
            cmds.connectAttr(f'{stretch_bc_node}.outputR', f'{power}.input1X', force=True)
            
            div = cmds.createNode('multiplyDivide', name=f'{name}_div')
            cmds.setAttr(f'{div}.operation', 2)
            cmds.setAttr(f'{div}.input1X', 1)
            cmds.connectAttr(f'{power}.outputX', f'{div}.input2X', force=True)
            
            volume_bc_node = cmds.createNode('blendColors', name=f'{name}_volume_bc')
            cmds.setAttr(f'{volume_bc_node}.color2R', 1)
            cmds.connectAttr(f'{div}.outputX', f'{volume_bc_node}.color1R', force=True)
            
            return stretch_bc_node, volume_bc_node, glb_sc_node

    def stretch_and_squash(self, ctrl, joints, ik_curve, name, global_scale, stretch_axis='Y', ctrl_pos=None):

        stretch_axis = stretch_axis.upper() # Convert to uppercase even if entered in lowercase (safety measure)
        all_axes = ['X', 'Y', 'Z']

        if stretch_axis not in all_axes:
            cmds.warning(f"Invalid axis entered: {stretch_axis}. Using default 'Y'.")
            stretch_axis = 'Y'
        volume_axes = [ax for ax in all_axes if ax != stretch_axis]

        attributes = ['auto_stretch', 'auto_volume']

        if ctrl_pos:
            attributes.append('ctrl_position')

        stretch_bc_node, volume_bc_node, global_scale_node = self.create_volume_presv(ik_curve, name)

        for attr in attributes:
            if cmds.attributeQuery(attr, node=ctrl, exists=True):
                cmds.deleteAttr(f"{ctrl}.{attr}")
            
            if attr == 'ctrl_position':
                for ik_ctrl in ctrl_pos:
                    cmds.addAttr(ik_ctrl, longName=attr, attributeType='float', keyable=True, min=0, max=1)
            else:         
                cmds.addAttr(ctrl, longName=attr, attributeType='float', keyable=True, min=0, max=1)
            
        for joint in joints:
            # (Modified) Use variables instead of hardcoded X, Y, Z.
            cmds.connectAttr(f'{stretch_bc_node}.outputR', f'{joint}.scale{stretch_axis}', force=True)
            cmds.connectAttr(f'{volume_bc_node}.outputR', f'{joint}.scale{volume_axes[0]}', force=True)
            cmds.connectAttr(f'{volume_bc_node}.outputR', f'{joint}.scale{volume_axes[1]}', force=True)
            
        cmds.connectAttr(f'{ctrl}.auto_stretch', f'{stretch_bc_node}.blender', force=True)
        cmds.connectAttr(f'{ctrl}.auto_volume', f'{volume_bc_node}.blender', force=True)
        
        # (Modified) Also calculate global scale according to the stretching axis (stretch_axis).
        cmds.connectAttr(f'{global_scale}.scale{stretch_axis}', f'{global_scale_node}.input2X', force=True)

    def dynamic_ctrl_pos(self, sdk, source, neg_grp, value):
        cmds.setDrivenKeyframe(sdk, at='translateY', v=0, cd=f'{source}.ctrl_position', dv=0)
        cmds.setDrivenKeyframe(sdk, at='translateY', v=value, cd=f'{source}.ctrl_position', dv=1)
        
        mult_node = cmds.createNode('multiplyDivide', name=f'{source}_mult')
        cmds.setAttr(f'{mult_node}.input2X', -1)
        cmds.setAttr(f'{mult_node}.input2Y', -1)
        cmds.setAttr(f'{mult_node}.input2Z', -1)
        
        # (Modified) Since multiplyDivide node does not have translate attribute, connect input1 and output directly.
        cmds.connectAttr(f'{sdk}.translateX', f'{mult_node}.input1X', force=True)
        cmds.connectAttr(f'{sdk}.translateY', f'{mult_node}.input1Y', force=True)
        cmds.connectAttr(f'{sdk}.translateZ', f'{mult_node}.input1Z', force=True)
        
        cmds.connectAttr(f'{mult_node}.outputX', f'{neg_grp}.translateX', force=True)
        cmds.connectAttr(f'{mult_node}.outputY', f'{neg_grp}.translateY', force=True)
        cmds.connectAttr(f'{mult_node}.outputZ', f'{neg_grp}.translateZ', force=True)

    def ik_spline_adv_twist(self, ikHandle, world_up1, world_up2):
        cmds.setAttr(f"{ikHandle}.dTwistControlEnable", 1)
        cmds.setAttr(f"{ikHandle}.dWorldUpType", 4)
        cmds.setAttr(f"{ikHandle}.dForwardAxis", 2)
        cmds.setAttr(f"{ikHandle}.dWorldUpAxis", 4)
        cmds.setAttr(f"{ikHandle}.dWorldUpVectorZ", -1)
        cmds.setAttr(f"{ikHandle}.dWorldUpVectorEndZ", -1)

        cmds.connectAttr(f"{world_up1}.worldMatrix[0]", f"{ikHandle}.dWorldUpMatrix", force=True)
        cmds.connectAttr(f"{world_up2}.worldMatrix[0]", f"{ikHandle}.dWorldUpMatrixEnd", force=True)

    def pos_ori_follow(self, ctrl, up_parent, bot_parent):
        for attr in ['pos_follow', 'orient_follow']:
            if cmds.attributeQuery(attr, node=ctrl, exists=True):
                cmds.deleteAttr(f"{ctrl}.{attr}")
            cmds.addAttr(ctrl, longName=attr, attributeType='float', keyable=True, min=0, max=1)
                
        up_pos = cmds.group(empty=True, name=f'{ctrl}_upPos')
        bot_pos = cmds.group(empty=True, name=f'{ctrl}_botPos')
        
        cmds.matchTransform(up_pos, ctrl)
        cmds.parent(up_pos, up_parent)
        cmds.matchTransform(bot_pos, ctrl)
        cmds.parent(bot_pos, bot_parent)
        
        offset_grp = cmds.listRelatives(ctrl, parent=True)[0]
        point_constrain = cmds.pointConstraint(up_pos, bot_pos, offset_grp, mo=True)[0]
        orient_constrain = cmds.orientConstraint(up_pos, bot_pos, offset_grp, mo=True)[0]
        
        cmds.setDrivenKeyframe(point_constrain, at=f'{up_pos}W0', v=1, cd=f'{ctrl}.pos_follow', dv=1)
        cmds.setDrivenKeyframe(point_constrain, at=f'{up_pos}W0', v=0, cd=f'{ctrl}.pos_follow', dv=0)
        cmds.setDrivenKeyframe(point_constrain, at=f'{bot_pos}W1', v=0, cd=f'{ctrl}.pos_follow', dv=1)
        cmds.setDrivenKeyframe(point_constrain, at=f'{bot_pos}W1', v=1, cd=f'{ctrl}.pos_follow', dv=0)
        
        cmds.setDrivenKeyframe(orient_constrain, at=f'{up_pos}W0', v=1, cd=f'{ctrl}.orient_follow', dv=1)
        cmds.setDrivenKeyframe(orient_constrain, at=f'{up_pos}W0', v=0, cd=f'{ctrl}.orient_follow', dv=0)
        cmds.setDrivenKeyframe(orient_constrain, at=f'{bot_pos}W1', v=0, cd=f'{ctrl}.orient_follow', dv=1)
        cmds.setDrivenKeyframe(orient_constrain, at=f'{bot_pos}W1', v=1, cd=f'{ctrl}.orient_follow', dv=0)
        
        if 'lo' in ctrl:
            cmds.setAttr(f'{ctrl}.pos_follow', 0.333)
            cmds.setAttr(f'{ctrl}.orient_follow', 0.5)
        elif 'up' in ctrl:
            cmds.setAttr(f'{ctrl}.pos_follow', 0.666)
            cmds.setAttr(f'{ctrl}.orient_follow', 0.666)
        else:
            cmds.setAttr(f'{ctrl}.pos_follow', 0.5)
            cmds.setAttr(f'{ctrl}.orient_follow', 0.5)