import maya.cmds as cmds
from functools import partial

from .face_rig_base import FaceRigBase


class FaceRig(FaceRigBase):

    PARTS = ['jaw', 'skull', 'lip_lower_C', 'lip_upper_C', 'lip_corner_L', 'lip_lower_L_sec', 'lip_upper_L_sec',]

    def __init__(self, input_joints):
        """input_joints: dict {part_name: joint_name}
        e.g. {'jaw': 'jaw_bnd_jnt', 'lip_corner_L': 'lip_corner_L_drv_jnt', ...}
        """
        super(FaceRig, self).__init__(input_joints, part_name='jaw')

        self.u_span = 11
        self.reg_ctrl_radius = 1
        self.twk_ctrl_radius = 0.4
        self.sec_ctrl_radius = 0.7
        self.normal = (0, 0, 1)

        self.lip_surf = {}
        self.lip_surf_local = {}

    # =============== jaw / lip specific build steps =============== #

    def build_lips(self):
        # jnt offs와 ctrl offs 양쪽에 같은 미러 스케일 → 좌표계가 일치해 회전 방향이 맞음
        cmds.setAttr(f"{self.jnt_offs['lip_lower_C']}.scale", 1, -1, 1, type='double3')
        cmds.setAttr(f"{self.ctrl_offs['lip_lower_C']}.scale", 1, -1, 1, type='double3')
        # cmds.setAttr(f"{self.jnt_offs['lip_lower_L_sec']}.scale", 1, -1, 1, type='double3')
        # cmds.setAttr(f"{self.ctrl_offs['lip_lower_L_sec']}.scale", 1, -1, 1, type='double3')

        r_corner_jnt_offs, r_corner_jnt = self.mirror_obj(self.jnt_offs['lip_corner_L'], (-1, 1, 1), ltor=True)
        self.register('lip_corner_R', jnt=r_corner_jnt, jnt_offs=r_corner_jnt_offs)
        r_corner_ctrl, r_corner_ctrl_offs = self.create_ctrl_and_connect(r_corner_jnt, radius = self.reg_ctrl_radius)   # (ctrl, offs) 순서 주의
        self.register('lip_corner_R', ctrl=r_corner_ctrl, ctrl_offs=r_corner_ctrl_offs)

        r_low_jnt_offs, r_low_jnt = self.mirror_obj(self.jnt_offs['lip_lower_L_sec'], (-1, 1, 1), ltor=True)
        self.register('lip_lower_R_sec', jnt=r_low_jnt, jnt_offs=r_low_jnt_offs)
        r_low_ctrl, r_low_ctrl_offs = self.create_ctrl_and_connect(r_low_jnt, radius = self.reg_ctrl_radius)
        self.register('lip_lower_R_sec', ctrl=r_low_ctrl, ctrl_offs=r_low_ctrl_offs)

        r_up_jnt_offs, r_up_jnt = self.mirror_obj(self.jnt_offs['lip_upper_L_sec'], (-1, 1, 1), ltor=True)
        self.register('lip_upper_R_sec', jnt=r_up_jnt, jnt_offs=r_up_jnt_offs)
        r_up_ctrl, r_up_ctrl_offs = self.create_ctrl_and_connect(r_up_jnt, radius = self.reg_ctrl_radius)
        self.register('lip_upper_R_sec', ctrl=r_up_ctrl, ctrl_offs=r_up_ctrl_offs)

        lip_drv_jnt_grp = cmds.group(empty=True, name = 'lip_drv_jnt_grp')
        lip_ctrl_grp = cmds.group(empty=True, name = 'lip_ctrl_grp')
        lip_aux_ctrl_grp = cmds.group(empty=True, name = 'lip_aux_ctrl_grp')
        lip_rig_grp = cmds.group(empty=True, name = 'lip_rig_setup')

        cmds.parent(self.jnt_offs['lip_lower_C'], self.jnts['jaw'])
        cmds.parent(self.jnt_offs['lip_upper_C'], self.jnts['skull'])
        cmds.parent(self.ctrl_offs['lip_lower_C'], self.ctrls['jaw'])
        cmds.parent(self.ctrl_offs['lip_upper_C'], self.ctrls['skull'])

        cmds.parent(self.ctrl_offs['lip_corner_L'], lip_ctrl_grp)
        cmds.parent(self.ctrl_offs['lip_corner_R'], lip_ctrl_grp)
        cmds.parent(self.ctrl_offs['lip_upper_L_sec'], lip_aux_ctrl_grp)
        cmds.parent(self.ctrl_offs['lip_upper_R_sec'], lip_aux_ctrl_grp)
        cmds.parent(self.ctrl_offs['lip_lower_L_sec'], lip_aux_ctrl_grp)
        cmds.parent(self.ctrl_offs['lip_lower_R_sec'], lip_aux_ctrl_grp)

        cmds.parent(self.jnt_offs['lip_corner_L'], lip_drv_jnt_grp)
        cmds.parent(self.jnt_offs['lip_corner_R'], lip_drv_jnt_grp)
        cmds.parent(self.jnt_offs['lip_upper_L_sec'], lip_drv_jnt_grp)
        cmds.parent(self.jnt_offs['lip_upper_R_sec'], lip_drv_jnt_grp)
        cmds.parent(self.jnt_offs['lip_lower_L_sec'], lip_drv_jnt_grp)
        cmds.parent(self.jnt_offs['lip_lower_R_sec'], lip_drv_jnt_grp)

        for part in ('lip_lower_C', 'lip_upper_C'):
            sec_jnt_offs, sec_jnt = self.duplicate_and_rename(self.jnt_offs[part], 'drv', 'sec_drv')

            sec_ctrl, sec_ctrl_offs = self.create_ctrl_and_connect(sec_jnt, radius=self.sec_ctrl_radius)

            self.register(f'{part}_sec', jnt=sec_jnt, jnt_offs=sec_jnt_offs,
                          ctrl=sec_ctrl, ctrl_offs=sec_ctrl_offs)

            cmds.parent(sec_jnt_offs, lip_drv_jnt_grp)
            cmds.parent(sec_ctrl_offs, lip_aux_ctrl_grp)

        cmds.setAttr(f"{self.jnt_offs['lip_lower_C_sec']}.scale", 1, 1, 1, type='double3')
        cmds.setAttr(f"{self.ctrl_offs['lip_lower_C_sec']}.scale", 1, 1, 1, type='double3')
        cmds.setAttr(f"{self.jnt_offs['lip_lower_C_sec']}.rotate", 0, 0, 0, type='double3')
        cmds.setAttr(f"{self.ctrl_offs['lip_lower_C_sec']}.rotate", 0, 0, 0, type='double3')


        cmds.addAttr(self.ctrls['jaw'], ln='jaw_follow', min=0.0, max=1.0, k=True)

        l_corner_ctrl_const = cmds.parentConstraint(self.ctrls['jaw'],self.ctrls['skull'], self.ctrl_offs['lip_corner_L'], mo=True)[0]
        r_corner_ctrl_const = cmds.parentConstraint(self.ctrls['jaw'],self.ctrls['skull'], self.ctrl_offs['lip_corner_R'], mo=True)[0]

        constraints = [
            cmds.parentConstraint(self.ctrls['lip_lower_C'], self.ctrl_offs['lip_lower_C_sec'], mo=True)[0],
            cmds.parentConstraint(self.ctrls['lip_upper_C'], self.ctrl_offs['lip_upper_C_sec'], mo=True)[0],
            cmds.parentConstraint(self.ctrls['lip_corner_R'], self.ctrls['lip_lower_C'], self.ctrl_offs['lip_lower_R_sec'], mo=True)[0],
            cmds.parentConstraint(self.ctrls['lip_corner_R'], self.ctrls['lip_upper_C'], self.ctrl_offs['lip_upper_R_sec'], mo=True)[0],
            cmds.parentConstraint(self.ctrls['lip_corner_L'], self.ctrls['lip_lower_C'], self.ctrl_offs['lip_lower_L_sec'], mo=True)[0],
            cmds.parentConstraint(self.ctrls['lip_corner_L'], self.ctrls['lip_upper_C'], self.ctrl_offs['lip_upper_L_sec'], mo=True)[0],
        ]

        for const in constraints:
            cmds.setAttr(f'{const}.interpType', 2)

        def _setup_follow_sdk(constraint):
            driver = f"{self.ctrls['jaw']}.jaw_follow"
            w_jaw, w_skull = cmds.parentConstraint(constraint, q=True, weightAliasList=True)

            # jaw_follow = 1 → jaw 웨이트 1, skull 웨이트 0
            cmds.setDrivenKeyframe(constraint, at=w_jaw,   cd=driver, dv=1, v=1)
            cmds.setDrivenKeyframe(constraint, at=w_skull, cd=driver, dv=1, v=0)

            # jaw_follow = 0 → jaw 웨이트 0, skull 웨이트 1
            cmds.setDrivenKeyframe(constraint, at=w_jaw,   cd=driver, dv=0, v=0)
            cmds.setDrivenKeyframe(constraint, at=w_skull, cd=driver, dv=0, v=1)

        for const in [l_corner_ctrl_const, r_corner_ctrl_const]:
            _setup_follow_sdk(const)

        self.connect_trans(self.ctrl_offs['lip_corner_L'], self.jnt_offs['lip_corner_L'])
        self.connect_trans(self.ctrl_offs['lip_corner_R'], self.jnt_offs['lip_corner_R'])
        cmds.setAttr(f"{self.ctrls['jaw']}.jaw_follow", 0.5)


        up_surf_target = [self.jnts['lip_corner_R'], self.jnts['lip_upper_R_sec'], self.jnts['lip_upper_C'], self.jnts['lip_upper_L_sec'], self.jnts['lip_corner_L'],]
        lo_surf_target = [self.jnts['lip_corner_R'], self.jnts['lip_lower_R_sec'], self.jnts['lip_lower_C'], self.jnts['lip_lower_L_sec'], self.jnts['lip_corner_L'],]
        self.lip_surf['up'], up_fol_pos_jnts, up_fol_offs, up_follicle_grp_name, up_follicles = self.create_ribbon(up_surf_target, 'lip_upper_surf', 'lip_upper', self.u_span)
        self.lip_surf['lo'], lo_fol_pos_jnts, lo_fol_offs, lo_follicle_grp_name, lo_follicles = self.create_ribbon(lo_surf_target, 'lip_lower_surf', 'lip_lower', self.u_span)

        fol_r_dup = cmds.duplicate(up_follicles[0], name = up_follicles[0].replace('01', '00'),rc=True)[0]
        fol_l_dup = cmds.duplicate(up_follicles[-1], name = up_follicles[-1].replace('01', '00'),rc=True)[0]

        self.follicles = {
            'up': up_follicles,
            'lo': lo_follicles,
            'corner': [fol_r_dup, fol_l_dup],
        }

        r_childrens = cmds.listRelatives(fol_r_dup, shapes=False)
        l_childrens = cmds.listRelatives(fol_l_dup, shapes=False)
        for c in r_childrens+l_childrens:
            if cmds.objectType(c, isType='follicle'):
                pass
            else:
                cmds.delete(c)
        fol_r_shape = cmds.listRelatives(fol_r_dup, shapes=True)[0]
        fol_l_shape = cmds.listRelatives(fol_l_dup, shapes=True)[0]
        up_ribbon_surf_shape = cmds.listRelatives(self.lip_surf['up'], shapes=True, noIntermediate=True)[0]

        cmds.setAttr(f'{fol_r_dup}.translate', e=True, lock = False)
        cmds.setAttr(f'{fol_r_dup}.rotate', e=True, lock = False)
        cmds.setAttr(f'{fol_l_dup}.translate', e=True, lock = False)
        cmds.setAttr(f'{fol_l_dup}.rotate', e=True, lock = False)

        cmds.connectAttr(f'{up_ribbon_surf_shape}.local', f'{fol_r_shape}.inputSurface')
        cmds.connectAttr(f'{up_ribbon_surf_shape}.worldMatrix[0]', f'{fol_r_shape}.inputWorldMatrix')
        cmds.connectAttr(f'{fol_r_shape}.outTranslate', f'{fol_r_dup}.translate')
        cmds.connectAttr(f'{fol_r_shape}.outRotate', f'{fol_r_dup}.rotate')

        cmds.connectAttr(f'{up_ribbon_surf_shape}.local', f'{fol_l_shape}.inputSurface')
        cmds.connectAttr(f'{up_ribbon_surf_shape}.worldMatrix[0]', f'{fol_l_shape}.inputWorldMatrix')
        cmds.connectAttr(f'{fol_l_shape}.outTranslate', f'{fol_l_dup}.translate')
        cmds.connectAttr(f'{fol_l_shape}.outRotate', f'{fol_l_dup}.rotate')

        cmds.setAttr(f'{fol_r_shape}.parameterU', 0)
        cmds.setAttr(f'{fol_l_shape}.parameterU', 1)

        corner_fol_pos_jnt_r, corner_fol_offs_r = self.parent_jnts([fol_r_dup], 'lip_corner_R', jnt_suffix='pos')
        corner_fol_pos_jnt_l, corner_fol_offs_l = self.parent_jnts([fol_l_dup], 'lip_corner_L', jnt_suffix='pos')
        corner_fol_pos_jnts = corner_fol_pos_jnt_r + corner_fol_pos_jnt_l
        corner_fol_offs = corner_fol_offs_r + corner_fol_offs_l


        for f in up_fol_offs + lo_fol_offs + corner_fol_offs:
            cmds.setAttr(f'{f}.rotateX', 90)

        def _create_bnd_from_pos(corner_fol_pos_jnts, parent_grp):
            fol_bnd_jnts = []
            fol_bnd_jnts_offs = []

            for jnt in corner_fol_pos_jnts:
                bnd_jnt = cmds.duplicate(jnt, name = jnt.replace('pos', 'bnd'))[0]
                cmds.parent(bnd_jnt, parent_grp)

                bnd_jnt_offs = self.create_offset_grp(bnd_jnt)

                fol_bnd_jnts.append(bnd_jnt)
                fol_bnd_jnts_offs.append(bnd_jnt_offs)

                cmds.setAttr(f'{jnt}.visibility', 0)

                cmds.pointConstraint(jnt, bnd_jnt_offs, mo=True)

            return fol_bnd_jnts, fol_bnd_jnts_offs

        up_fol_bnd_jnts, up_fol_bnd_jnts_offs = _create_bnd_from_pos(up_fol_pos_jnts, up_follicle_grp_name)
        lo_fol_bnd_jnts, lo_fol_bnd_jnts_offs = _create_bnd_from_pos(lo_fol_pos_jnts, lo_follicle_grp_name)
        corner_fol_bnd_jnts, corner_fol_bnd_jnts_offs = _create_bnd_from_pos(corner_fol_pos_jnts, up_follicle_grp_name)

        fol_ctrl_grp = cmds.group(empty=True, name = 'lip_fol_ctrl_grp')
        fol_ctrls = {}
        for prefix, jnt_list, fol_list in (('up', up_fol_bnd_jnts, up_follicles),
                                           ('lo', lo_fol_bnd_jnts, lo_follicles),
                                           ('corner', corner_fol_bnd_jnts, [fol_r_dup, fol_l_dup])):
            fol_ctrls[prefix] = {}
            for jnt, fol in zip(jnt_list, fol_list):
                ctrl, ctrl_offs = self.create_ctrl_and_connect(jnt, radius=self.twk_ctrl_radius)

                cmds.connectAttr(f'{fol}.translate', f'{ctrl_offs}.translate', force=True)

                fol_ctrls[prefix][ctrl] = ctrl_offs
                self.register(ctrl.replace('_ctrl', ''), ctrl=ctrl, ctrl_offs=ctrl_offs)
                cmds.parent(ctrl_offs, fol_ctrl_grp)

        self.lip_surf_local['up'] = cmds.duplicate(self.lip_surf['up'], name = self.lip_surf['up']+'_local')[0]
        self.lip_surf_local['lo'] = cmds.duplicate(self.lip_surf['lo'], name = self.lip_surf['lo']+'_local')[0]

        lip_up_surf_skcluster = self.bind_ribbon(self.lip_surf['up'],[self.jnts['lip_corner_R'], self.jnts['lip_upper_C'], self.jnts['lip_corner_L']])
        lip_lo_surf_skcluster = self.bind_ribbon(self.lip_surf['lo'],[self.jnts['lip_corner_R'], self.jnts['lip_lower_C'], self.jnts['lip_corner_L']])

        local_lip_up_surf_skcluster = self.bind_ribbon(self.lip_surf_local['up'],[self.jnts['lip_upper_R_sec'], self.jnts['lip_upper_C_sec'], self.jnts['lip_upper_L_sec']],
                                                    mid_bias=0.3, head_accel=0.7, tail_accel=0.5)
        local_lip_lo_surf_skcluster = self.bind_ribbon(self.lip_surf_local['lo'],[self.jnts['lip_lower_R_sec'], self.jnts['lip_lower_C_sec'], self.jnts['lip_lower_L_sec']],
                                                    mid_bias=0.3, head_accel=0.7, tail_accel=0.5)

        cmds.select(clear=True)
        lip_dead_jnt = cmds.joint(name='lip_dead_jnt')

        self.add_dead_weights(local_lip_up_surf_skcluster, self.lip_surf_local['up'], lip_dead_jnt)
        self.add_dead_weights(local_lip_lo_surf_skcluster, self.lip_surf_local['lo'], lip_dead_jnt)

        local_lip_up_bs = cmds.blendShape(self.lip_surf_local['up'], self.lip_surf['up'], automatic=True, name = 'local_lip_up_bs', w = [0, 1.0])
        local_lip_lo_bs = cmds.blendShape(self.lip_surf_local['lo'], self.lip_surf['lo'], automatic=True, name = 'local_lip_lo_bs', w = [0, 1.0])

        lip_surf_grp = cmds.group(empty = True, name = 'lip_surf_grp')
        cmds.parent([self.lip_surf['up'], self.lip_surf['lo'], self.lip_surf_local['up'], self.lip_surf_local['lo'], lip_dead_jnt], lip_surf_grp)

        cmds.parent([lip_drv_jnt_grp, lip_ctrl_grp, lip_aux_ctrl_grp, fol_ctrl_grp, lip_surf_grp, up_follicle_grp_name, lo_follicle_grp_name, lip_dead_jnt], lip_rig_grp)

    def create_lip_zip(self):
        up_mid_surf = cmds.duplicate(self.lip_surf['up'], name=self.lip_surf['up'] + '_mid')[0]
        lo_mid_surf = cmds.duplicate(self.lip_surf['lo'], name=self.lip_surf['lo'] + '_mid')[0]

        corners = [self.jnts['lip_corner_R'], self.jnts['lip_corner_L']]
        up_jnt = self.jnts['lip_upper_C']
        lo_jnt = self.jnts['lip_lower_C']

        up_zip_skin = self.transfer_zip_weights(self.lip_surf['up'], up_mid_surf,
                                                corners, up_jnt, lo_jnt, mid_jnt=up_jnt)
        lo_zip_skin = self.transfer_zip_weights(self.lip_surf['lo'], lo_mid_surf,
                                                corners, up_jnt, lo_jnt, mid_jnt=lo_jnt)

        self.lip_surf_mid = {'up': up_mid_surf, 'lo': lo_mid_surf}

        up_mid_lip_bs = cmds.blendShape(self.lip_surf_local['up'], self.lip_surf_local['lo'], up_mid_surf, automatic=True, name = 'up_mid_lip_bs', w = [(0, 1.0), (1, 1.0)])
        lo_mid_lip_bs = cmds.blendShape(self.lip_surf_local['up'], self.lip_surf_local['lo'], lo_mid_surf, automatic=True, name = 'lo_mid_lip_bs', w = [(0, 1.0), (1, 1.0)])

        self.zip_bs = {
            'up': self.create_zip_blendshapes(self.lip_surf['up'], lo_mid_surf, 'up_lip_zip'),
            'lo': self.create_zip_blendshapes(self.lip_surf['lo'], up_mid_surf, 'lo_lip_zip'),
        }

        for side in ('L', 'R'):
            ctrl = self.ctrls[f'lip_corner_{side}']
            if not cmds.attributeQuery('zip', node=ctrl, exists=True):
                cmds.addAttr(ctrl, ln='zip', at='double', min=0, max=10, dv=0, k=True)

        driver_l = f"{self.ctrls['lip_corner_L']}.zip"
        driver_r = f"{self.ctrls['lip_corner_R']}.zip"

        num_u = cmds.getAttr(f"{self.lip_surf['up']}.spansU") + cmds.getAttr(f"{self.lip_surf['up']}.degreeU")

        self.setup_zip_sdk(self.zip_bs['up'], 'up_lip_zip', num_u, driver_l, driver_r)
        self.setup_zip_sdk(self.zip_bs['lo'], 'lo_lip_zip', num_u, driver_l, driver_r)

        self.refresh_follicle_inputs(self.lip_surf['up'], self.follicles['up'] + self.follicles['corner'])
        self.refresh_follicle_inputs(self.lip_surf['lo'], self.follicles['lo'])

        cmds.setAttr(f'{up_mid_surf}.visibility', 0)
        cmds.setAttr(f'{lo_mid_surf}.visibility', 0)

    def finalize(self):
        for part, ctrl in self.ctrls.items():
            self.set_curve_color([ctrl], self.SIDE_COLORS[self.get_side(part)])

        side_map = {'C': 0, 'L': 1, 'R': 2}
        for part, jnt in self.jnts.items():
            cmds.setAttr(f'{jnt}.side', side_map[self.get_side(part)])
            cmds.setAttr(f'{jnt}.type', 18)  # Other
            cmds.setAttr(f'{jnt}.otherType', part, type='string')

        hide_list = [
            self.lip_surf_local['up'],
            self.lip_surf_local['lo'],
            self.jnt_offs['lip_upper_C_sec'],
            self.jnt_offs['lip_lower_C_sec'],
            self.jnt_offs['lip_upper_L_sec'],
            self.jnt_offs['lip_lower_L_sec'],
            self.jnt_offs['lip_upper_R_sec'],
            self.jnt_offs['lip_lower_R_sec'],
        ]

        for node in hide_list:
            cmds.setAttr(f'{node}.visibility', 0)


    # =============== build steps =============== #

    def build(self):
        self.validate_inputs()
        self.create_offsets_and_ctrls()
        self.build_lips()
        self.create_lip_zip()
        self.finalize()

        # 메타 노드에 결과물 등록 (body rig BaseBuilder와 동일한 방식)
        self.register_outputs({f"{part}_ctrl": ctrl for part, ctrl in self.ctrls.items()})
        self.register_outputs({f"{part}_jnt": jnt for part, jnt in self.jnts.items()})
        self.save_settings({"input_joints": self.input_joints})

        cmds.select(clear=True)
        print('// Jaw build 완료:', self.ctrls)

# _________________UI_____________________ #

WINDOW_NAME = 'BuildJaw'
DEFAULT_JOINTS = {
    'jaw': 'jaw_bnd_jnt',
    'skull': 'skull_bnd_jnt',
    'lip_lower_C': 'lip_lower_C_drv_jnt',
    'lip_upper_C': 'lip_upper_C_drv_jnt',
    'lip_corner_L': 'lip_corner_L_drv_jnt',
    'lip_lower_L_sec': 'lip_lower_L_sec_drv_jnt',
    'lip_upper_L_sec': 'lip_upper_L_sec_drv_jnt',
}


def build_from_ui(fields, *args):
    """fields: dict {part_name: textField}  → FaceRig에 그대로 전달"""
    input_joints = {part: cmds.textField(f, q=True, text=True) for part, f in fields.items()}
    FaceRig(input_joints).build()

def get_average_position(components):
    flat = cmds.xform(components, q=True, ws=True, t=True)   # [x,y,z, x,y,z, ...]
    count = len(flat) // 3
    return [sum(flat[i::3]) / count for i in range(3)]


def create_joint_from_selection(field, joint_name, *args):
    sel = cmds.ls(selection=True, flatten=True)
    if not sel:
        cmds.warning(u'please select vertex/vertices.')
        return

    pos = get_average_position(sel)

    if cmds.objExists(joint_name):
        cmds.xform(joint_name, ws=True, t=pos)          # 이미 있으면 위치만 갱신
        cmds.warning(f"'{joint_name}' already exists — moved to new position.")
    else:
        cmds.select(clear=True)                          # 자동 페런트 방지
        jnt = cmds.joint(name=joint_name, p=pos)
        cmds.setAttr(f'{joint_name}.overrideEnabled', 1)
        cmds.setAttr(f'{joint_name}.overrideColor', 13)
        cmds.select(clear=True)

    cmds.textField(field, edit=True, text=joint_name)

def create_window():
    if cmds.window(WINDOW_NAME, exists=True):
        try:
            cmds.deleteUI(WINDOW_NAME, window=True)
        except RuntimeError:
            pass
    if cmds.windowPref(WINDOW_NAME, exists=True):
        cmds.windowPref(WINDOW_NAME, remove=True)

    cmds.window(WINDOW_NAME, title=u'Jaw Builder', widthHeight=(320, 300), sizeable=False)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=5, columnOffset=('both', 10))
    cmds.text(label=u'select each joint and press build jaw button', align='left', height=25)

    fields = {}
    for part in FaceRig.PARTS:
        cmds.rowLayout(numberOfColumns=3, columnWidth3=(80, 160, 40), adjustableColumn=2)
        cmds.text(label=part)
        field = cmds.textField(f'{part}_txField', text=DEFAULT_JOINTS[part], editable = False, bgc = (0.6, 0.6, 0.6))
        cmds.button(label='Set Joint',
                    command=partial(create_joint_from_selection, field, DEFAULT_JOINTS[part]))
        cmds.setParent('..')
        fields[part] = field

    cmds.separator(height=10)
    cmds.button(label=u'Build Jaw', command=partial(build_from_ui, fields))

    cmds.showWindow(WINDOW_NAME)


if __name__ == "__main__":
    create_window()
