import re
import maya.cmds as cmds
import maya.mel as mel
from functools import partial
import math

class FaceRig(object):

    SIDE_COLORS = {'L': 6, 'R': 13, 'C': 17}   # blue / red / yellow
    PARTS = ['jaw', 'skull', 'lip_lower_C', 'lip_upper_C', 'lip_corner_L', 'lip_lower_L_sec', 'lip_upper_L_sec',]

    def __init__(self, input_joints):
        """input_joints: dict {part_name: joint_name}
        e.g. {'jaw': 'jaw_bnd_jnt', 'lip_corner_L': 'lip_corner_L_drv_jnt', ...}
        """
        self.u_span = 11
        self.reg_ctrl_radius = 1
        self.twk_ctrl_radius = 0.4
        self.sec_ctrl_radius = 0.7 
        self.normal = (0, 0, 1)

        # ---------- registry ----------
        # 모든 키는 semantic part 이름으로 통일 ('jaw', 'lip_corner_R' 등)
        self.jnts = dict(input_joints)   # part -> joint
        self.jnt_offs = {}                 # part -> joint offset grp
        self.ctrls = {}                    # part -> ctrl
        self.ctrl_offs = {}                # part -> ctrl offset grp
        
        self.follicles = {}
        
        self.lip_surf = {}
        self.lip_surf_local = {}

    # =============== utils =============== #

    @staticmethod
    def get_side(name):
        if '_L_' in name or name.endswith('_L'):
            return 'L'
        if '_R_' in name or name.endswith('_R'):
            return 'R'
        return 'C'
    
    @staticmethod     
    def get_number(s):
        match = re.search(r'(\d+)$', s)
        return int(match.group(1)) if match else -1
        
    @staticmethod
    def get_side_label(i, total):
        
        mid = (total - 1) / 2.0
        if i < mid:
            return f'R_{i + 1:02d}'         # 오른쪽 끝(첫 번째)이 R_01
        elif i > mid:
            return f'L_{total - i:02d}'     # 왼쪽 끝(마지막)이 L_01
        
        return 'C_01'   
    
    @staticmethod
    def get_skin_cluster(surf):
        skins = cmds.ls(cmds.listHistory(surf), type='skinCluster')
        return skins[0] if skins else None

    @staticmethod
    def get_deformed_shape(surf):
        """디포머 체인의 최종 출력 셰이프 (Deformed 노드가 생겼으면 그것)"""
        shapes = cmds.listRelatives(surf, shapes=True, noIntermediate=True, fullPath=True) or []
        return shapes[0] if shapes else None

    def refresh_follicle_inputs(self, surf, follicles):
        shape = self.get_deformed_shape(surf)
        for fol in follicles:
            fol_shape = cmds.listRelatives(fol, shapes=True, type='follicle')[0]
            cmds.connectAttr(f'{shape}.local', f'{fol_shape}.inputSurface', force=True)
            cmds.connectAttr(f'{shape}.worldMatrix[0]', f'{fol_shape}.inputWorldMatrix', force=True)
            
            
    def parent_jnts(self, targets, name, jnt_suffix='bnd', name_list=None):

        joints = []
        twk_offs_list = []

        for i, target in enumerate(targets):
            token = name_list[i] if name_list else f'{i + 1:02d}'
            twk_offs = f'{name}_fol_{token}_twk_offs'
            cmds.group(empty=True, name=twk_offs)
            cmds.matchTransform(twk_offs, target)
            cmds.parent(twk_offs, target)

            jnt_name = f'{name}_fol_{token}_{jnt_suffix}_jnt'
            cmds.joint(n=jnt_name, rad=0.1)
            cmds.matchTransform(jnt_name, twk_offs)
            cmds.makeIdentity(jnt_name, apply=True, t=1, r=1, s=1)

            joints.append(jnt_name)
            twk_offs_list.append(twk_offs)
            cmds.select(clear=True)
        return joints, twk_offs_list
            
    def create_ribbon(self, joints, surf_name, name, u_span):
        positions = [cmds.xform(jnt, query=True, worldSpace=True, translation=True) for jnt in joints]
        first_crv = cmds.curve(p=positions, degree=3, name=surf_name+'_01_crv')
        second_crv = cmds.duplicate(first_crv, name=surf_name+'_02_crv')[0]

        # cmds.setAttr(f'{first_crv}.translateZ', 0.2)
        cmds.setAttr(f'{first_crv}.scale', 1.05, 1, 1.05,type='double3')
        # cmds.setAttr(f'{second_crv}.translateZ', -0.2)
        cmds.setAttr(f'{second_crv}.scale', 0.95, 1, 0.95,type='double3')
        
        ribbon_surf = cmds.loft(first_crv, second_crv, constructionHistory=False, name=surf_name,
                                uniform=True, close=False, ar=True, d=3, ss=0, rn=False, po=0, rsn=True)[0]
        cmds.rebuildSurface(ribbon_surf, ch=1, rpo=1, rt=0, end=1, kr=0, kcp=0, kc=0, su=u_span, du=3, sv=1, dv=1, tol=0.01, fr=0, dir=2)
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
        
        follicles = [n for n in set(loftSystem)
             if cmds.listRelatives(n, shapes=True, type='follicle')]
        follicle_list_inOrder = sorted(follicles, key=self.get_number)
        
        if 'initialShadingGroup' in follicle_list_inOrder:
            follicle_list_inOrder.remove('initialShadingGroup')
            
        follicle_list_renamed = []
        total = len(follicle_list_inOrder)
        for i, fol in enumerate(follicle_list_inOrder):
            follicle_name = f'{name}_follicle_{self.get_side_label(i, total)}'
            cmds.rename(fol, follicle_name)
            cmds.delete(cmds.listRelatives(follicle_name)[1])
            follicle_list_renamed.append(follicle_name)

        follicle_grp_name = name + '_follicle_grp'
        cmds.rename(cmds.listRelatives(follicle_list_renamed[0], ap=True)[0], follicle_grp_name)
        
        total = len(follicle_list_renamed)
        labels = []
        for i in range(total):
            labels.append(self.get_side_label(i, total))
        bnd_jnts, twk_offs_list = self.parent_jnts(follicle_list_renamed, name, jnt_suffix='pos', name_list=labels)
                                                   
        return ribbon_surf, bnd_jnts, twk_offs_list, follicle_grp_name, follicle_list_renamed

    def bind_ribbon(self, surf, bind_joints, mid_bias=0.83,
                    head_accel=2.5, tail_accel=0.5):
        """mid_bias:   구간 중간에서 mid 웨이트 (0.5 = linear)
        head_accel: mid_bias 도달 전 웨이트가 차오르는 속도
                    1.0 = 기존, >1 이면 천천히 출발했다 급가속 (ease-in)
                    <1 이면 초반부터 빠르게 차오름
        tail_accel: mid_bias 이후 잔여 웨이트 소멸 속도 (<1 = fast ease-out)
        """
        skin = cmds.skinCluster(bind_joints, surf, toSelectedBones=True,
                                maximumInfluences=2, name=surf + '_skc')[0]
        num_u = cmds.getAttr(f'{surf}.spansU') + cmds.getAttr(f'{surf}.degreeU')
        num_v = cmds.getAttr(f'{surf}.spansV') + cmds.getAttr(f'{surf}.degreeV')
        j_start, j_mid, j_end = bind_joints

        gamma = math.log(mid_bias) / math.log(0.5)

        def mid_weight(local_t):
            local = local_t ** gamma
            if local <= mid_bias:                          # front part : 0 → mid_bias
                r = local / mid_bias                       # 0~1로 정규화
                r = r ** head_accel                        # 가속 커브
                return r * mid_bias
            else:                                          # back part: mid_bias → 1
                r = (local - mid_bias) / (1.0 - mid_bias)
                r = r ** tail_accel
                return mid_bias + r * (1.0 - mid_bias)

        for i in range(num_u):
            t = i / (num_u - 1.0)
            if t <= 0.5:
                local = mid_weight(t * 2)
                w = [(j_start, 1 - local), (j_mid, local), (j_end, 0)]
            else:
                local = mid_weight((1 - t) * 2)
                w = [(j_start, 0), (j_mid, local), (j_end, 1 - local)]

            for v in range(num_v):
                cmds.skinPercent(skin, f'{surf}.cv[{i}][{v}]', transformValue=w)
        return skin
    
    def add_dead_weights(self, skin, surf, dead_jnt, falloff=(1.0, 0.4, 0.1)):
        """양 끝에서 안쪽으로 falloff 순서대로 dead_jnt 웨이트를 심음"""
        # dead 조인트를 인플루언스로 추가 (웨이트 0으로 시작, 기존 웨이트 유지)
        cmds.skinCluster(skin, edit=True, addInfluence=dead_jnt, weight=0.0, lockWeights=True)
        cmds.setAttr(f'{dead_jnt}.liw', 0)   # 락 해제

        num_u = cmds.getAttr(f'{surf}.spansU') + cmds.getAttr(f'{surf}.degreeU')
        num_v = cmds.getAttr(f'{surf}.spansV') + cmds.getAttr(f'{surf}.degreeV')

        for offset, w in enumerate(falloff):
            for i in (offset, num_u - 1 - offset):        # 왼쪽 끝, 오른쪽 끝 대칭
                for v in range(num_v):
                    cmds.skinPercent(skin, f'{surf}.cv[{i}][{v}]',
                                     transformValue=[(dead_jnt, w)])
        return skin
        
    def connect_trans(self, driver, driven):
        transformation = ['translate', 'rotate', 'scale']
        for f in transformation:
            
            axis = [
                'X','Y','Z'
            ]
            
            for x in axis:
                cmds.connectAttr(f'{driver}.{f}{x}', f'{driven}.{f}{x}', force=True)

    
    def set_curve_color(self, curves, color_index):
        for curve in curves:
            cmds.setAttr(f'{curve}.overrideEnabled', 1)
            cmds.setAttr(f'{curve}.overrideColor', color_index)

    def mirror_obj(self, target, mirror_axis, ltor=True, utob=False):
        dup = cmds.duplicate(target, returnRootsOnly=True)[0]
        temp_grp = cmds.group(empty=True)
        dup = cmds.parent(dup, temp_grp)[0]
        cmds.setAttr(f'{temp_grp}.scale', *mirror_axis, type='double3')
        dup = cmds.parent(dup, world=True)[0]

        def _rename_hierarchy(root, old, new):
            children = cmds.listRelatives(root, allDescendents=True, fullPath=True) or []
            for c in children: 
                short = c.split('|')[-1]
                if old in short:
                    cmds.rename(c, short.replace(old, new))
            return cmds.rename(root, root.split('|')[-1].replace(old, new))

        if ltor:
            dup = _rename_hierarchy(dup, '_L_', '_R_')
        if utob:
            dup = _rename_hierarchy(dup, 'upper', 'lower')

        new_dup = cmds.rename(dup, re.sub(r'\d+$', '', dup))
        child = cmds.listRelatives(new_dup, children=True)[0]
        cmds.delete(temp_grp)

        return new_dup, child

    def create_offset_grp(self, target, suffix='_offs'):
        offset_grp = cmds.group(empty=True, n=target + suffix)
        parent_grp = cmds.listRelatives(target, parent=True)

        cmds.matchTransform(offset_grp, target)

        if parent_grp:
            cmds.parent(offset_grp, parent_grp[0])
        cmds.parent(target, offset_grp)

        if cmds.objectType(target, isType='joint'):
            cmds.setAttr(f'{target}.jointOrient', 0, 0, 0, type='double3')
            cmds.setAttr(f'{target}.rotate', 0, 0, 0, type='double3')

        return offset_grp
        
    def duplicate_and_rename(self, source, old, new):
        """계층 전체를 복제하고 이름의 old 토큰을 new로 치환"""
        dup = cmds.duplicate(source, returnRootsOnly=True)[0]

        children = cmds.listRelatives(dup, allDescendents=True, fullPath=True) or []
        for c in children:
            short = c.split('|')[-1]
            if old in short:
                cmds.rename(c, short.replace(old, new))

        dup = cmds.rename(dup, re.sub(r'\d+$', '', dup.replace(old, new)))
        child = cmds.listRelatives(dup, children=True)[0]
        return dup, child
    
    def create_ctrl_and_connect(self, target, radius, ctrl_con=True, offs_con=False):
        for jnt_suffix in ('drv_jnt', 'bnd_jnt', 'pos_jnt'):
            if jnt_suffix in target:
                break
        else:
            cmds.error(f"'{target}' doesn't have drv_jnt / bnd_jnt suffix in its name.")

        parent_grp = cmds.listRelatives(target, parent=True)[0]

        offset_grp = cmds.group(empty=True, n=target.replace(jnt_suffix, 'ctrl_offs'))
        cmds.matchTransform(offset_grp, parent_grp)
        ctrl = cmds.circle(radius=radius, normal=self.normal,
                           name=target.replace(jnt_suffix, 'ctrl'))[0]

        cmds.parent(ctrl, offset_grp)
        cmds.xform(ctrl, t=(0, 0, 0), ro=(0, 0, 0), s=(1, 1, 1), ws=False)

        if ctrl_con:
            for attr in ('translate', 'rotate', 'scale'):
                cmds.connectAttr(f'{ctrl}.{attr}', f'{target}.{attr}')
        if offs_con:
            for attr in ('translate', 'rotate', 'scale'):
                cmds.connectAttr(f'{offset_grp}.{attr}', f'{parent_grp}.{attr}')

        return ctrl, offset_grp

    def register(self, part, jnt=None, jnt_offs=None, ctrl=None, ctrl_offs=None):
        if jnt:
            self.jnts[part] = jnt
        if jnt_offs:
            self.jnt_offs[part] = jnt_offs
        if ctrl:
            self.ctrls[part] = ctrl
        if ctrl_offs:
            self.ctrl_offs[part] = ctrl_offs

    def validate_inputs(self):
        for part in self.PARTS:
            jnt = self.jnts.get(part)
            if not jnt or not cmds.objExists(jnt):
                cmds.error(f"'{part}' 조인트가 비어있거나 씬에 없습니다: {jnt}")
            if not cmds.objectType(jnt, isType='joint'):
                cmds.error(f"'{jnt}' 는 조인트가 아닙니다.")

    def create_offsets_and_ctrls(self):
        for part in self.PARTS:
            jnt = self.jnts[part]
            jnt_offs = self.create_offset_grp(jnt)
            ctrl, ctrl_offs = self.create_ctrl_and_connect(jnt, radius = self.reg_ctrl_radius)
            self.register(part, jnt_offs=jnt_offs, ctrl=ctrl, ctrl_offs=ctrl_offs)
    
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
    
    
    def transfer_zip_weights(self, src_surf, dst_surf, corner_jnts, up_jnt, lo_jnt, mid_jnt):
        """src_surf의 웨이트를 dst_surf로 옮기되, mid_jnt 웨이트만 up/lo에 50%씩 분배"""
        src_skin = self.get_skin_cluster(src_surf)
        dst_skin = cmds.skinCluster(corner_jnts + [up_jnt, lo_jnt], dst_surf,
                                    toSelectedBones=True, maximumInfluences=3,
                                    name=dst_surf + '_skc')[0]

        src_infs = cmds.skinCluster(src_skin, q=True, influence=True)
        num_u = cmds.getAttr(f'{dst_surf}.spansU') + cmds.getAttr(f'{dst_surf}.degreeU')
        num_v = cmds.getAttr(f'{dst_surf}.spansV') + cmds.getAttr(f'{dst_surf}.degreeV')

        for i in range(num_u):
            for v in range(num_v):
                cv = f'[{i}][{v}]'
                src_w = cmds.skinPercent(src_skin, f'{src_surf}.cv{cv}',
                                         q=True, value=True)   # influence 순서와 동일

                new_w = []
                for inf, w in zip(src_infs, src_w):
                    if inf == mid_jnt:                    # 미들 조인트 → 반씩 분배
                        new_w.append((up_jnt, w * 0.5))
                        new_w.append((lo_jnt, w * 0.5))
                    elif inf in corner_jnts:              # 코너는 그대로
                        new_w.append((inf, w))
                    # 그 외(dead 등)는 무시

                cmds.skinPercent(dst_skin, f'{dst_surf}.cv{cv}', transformValue=new_w)

        return dst_skin

                    
    def create_zip_blendshapes(self, base_surf, target_surf, bs_name):
            """target_surf를 num_u개의 타겟으로 등록하고, 타겟 i는 CV[i]열에만 반응"""
            num_u = cmds.getAttr(f'{base_surf}.spansU') + cmds.getAttr(f'{base_surf}.degreeU')
            num_v = cmds.getAttr(f'{base_surf}.spansV') + cmds.getAttr(f'{base_surf}.degreeV')

            # post-deformation (스킨클러스터 뒤에 배치)
            bs = cmds.blendShape(target_surf, base_surf, name=bs_name, after=True)[0]

            # 같은 셰이프를 인덱스 1~num_u-1 에 추가 등록
            for i in range(1, num_u):
                cmds.blendShape(bs, edit=True, target=(base_surf, i, target_surf, 1.0))

            for i in range(num_u):
                alias = f'{bs_name}_{i:02d}'
                cmds.aliasAttr(alias, f'{bs}.weight[{i}]')
                cmds.setAttr(f'{bs}.{alias}', 0)

                # 타겟 i는 U 인덱스가 i인 CV들만 웨이트 1
                for u in range(num_u):
                    for v in range(num_v):
                        pt = u * num_v + v          # NURBS CV의 평탄화 인덱스
                        cmds.setAttr(
                            f'{bs}.inputTarget[0].inputTargetGroup[{i}].targetWeights[{pt}]',
                            1.0 if u == i else 0.0)

            return bs
 
 
    def setup_zip_sdk(self, bs, bs_name, num_targets, driver_l, driver_r, overlap=0.5):
            # driver_l: from lower index / driver_r: from higher index
            half = num_targets // 2
            groups = (
                (list(range(half)), driver_r),                              # 0 -> half-1
                (list(range(num_targets - 1, half - 1, -1)), driver_l),     # N-1 -> half
            )

            for indices, driver in groups:
                n = len(indices)
                for k, i in enumerate(indices):
                    attr = f'{bs}.{bs_name}_{i:02d}'
                    start = 10.0 * k / n
                    end = 10.0 * (k + 1) / n
                    start = max(0.0, start - (end - start) * overlap)

                    if start > 0:
                        cmds.setDrivenKeyframe(attr, cd=driver, dv=0.0, v=0)
                    cmds.setDrivenKeyframe(attr, cd=driver, dv=start, v=0)
                    cmds.setDrivenKeyframe(attr, cd=driver, dv=end, v=1)
                    if end < 10.0:
                        cmds.setDrivenKeyframe(attr, cd=driver, dv=10.0, v=1)

                    cmds.keyTangent(attr, edit=True, itt='linear', ott='linear')
                           
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


def load_selected_joint(field, *args):
    sel = cmds.ls(selection=True, type='joint')
    if not sel:
        cmds.warning(u'please select joints.')
        return
    cmds.textField(field, edit=True, text=sel[0])


def build_from_ui(fields, *args):
    """fields: dict {part_name: textField}  → FaceRig에 그대로 전달"""
    input_joints = {part: cmds.textField(f, q=True, text=True) for part, f in fields.items()}
    FaceRig(input_joints).build()


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
        field = cmds.textField(f'{part}_txField', text=DEFAULT_JOINTS[part])
        cmds.button(label='<<', command=partial(load_selected_joint, field))
        cmds.setParent('..')
        fields[part] = field

    cmds.separator(height=10)
    cmds.button(label=u'Build Jaw', command=partial(build_from_ui, fields))

    cmds.showWindow(WINDOW_NAME)


create_window()