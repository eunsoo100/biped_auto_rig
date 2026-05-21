import maya.cmds as cmds
import maya.api.OpenMaya as om 
import re

# Import curve_utils from the same core folder.
from . import curve_utils 

def mirror_joints(source_jnts, mirror_axis='YZ', mirror_behavior=True):
    mirrored = cmds.mirrorJoint(
        source_jnts[0],
        mirrorYZ=(mirror_axis == 'YZ'),
        mirrorXY=(mirror_axis == 'XY'), 
        mirrorXZ=(mirror_axis == 'XZ'),
        mirrorBehavior=mirror_behavior,
        searchReplace=['_L_', '_R_']
    )
    return mirrored

def mirror_curve_shape(ctrl, axis='X'):
    shapes = cmds.listRelatives(ctrl, shapes=True, fullPath=True)
    if not shapes: return
    
    for shape in shapes:
        cvs = cmds.ls(f"{shape}.cv[*]", flatten=True)
        if axis == 'X':
            cmds.scale(-1, 1, 1, cvs, relative=True, localSpace=True)
        elif axis == 'Y':
            cmds.scale(1, -1, 1, cvs, relative=True, localSpace=True)
        elif axis == 'Z':
            cmds.scale(1, 1, -1, cvs, relative=True, localSpace=True)

            
def get_number(s):
    match = re.search(r'(\d+)$', s)
    return int(match.group(1)) if match else -1


def create_offset_grp(target, suffix='_offs'):
    """
    Create an offset group that matches the target object's transform.
    Preserves the hierarchy if the target already has a parent.
    """
    offset_grp = cmds.group(empty=True, name=target + suffix)
    parent_grp = cmds.listRelatives(target, parent=True)
    
    cmds.matchTransform(offset_grp, target)
    
    if parent_grp:
        cmds.parent(offset_grp, parent_grp[0])
        
    cmds.parent(target, offset_grp)
    return offset_grp


def create_ctrl(name, radius=1.0, target=None, offs_grp=False, color=None, thickness=None, rot_offset=(0, 0, 0), normal =(0, 0, 1)):

    ctrl = cmds.circle(name=name, radius=radius, normal = normal)[0]
    cmds.delete(ctrl, constructionHistory=True)

    if color is not None or thickness is not None:
        curve_utils.style_curve(ctrl, color_index=color, thickness=thickness)
    
    if offs_grp:
        if target:
            cmds.matchTransform(ctrl, target)
        
        offset_group = create_offset_grp(ctrl, '_offs')
        
        if rot_offset != (0, 0, 0):
            cmds.rotate(rot_offset[0], rot_offset[1], rot_offset[2], offset_group, relative=True, objectSpace=True)
            
        return offset_group, ctrl
        
    return ctrl


def clean_transformation(target, is_joint=False):
    """Reset transform values to 0. If it's a joint, also reset jointOrient."""
    cmds.xform(target, objectSpace=True, translation=(0, 0, 0), rotation=(0, 0, 0))
    if is_joint and cmds.objectType(target, isType='joint'):
        cmds.setAttr(f'{target}.jointOrient', 0, 0, 0, type='double3')


def connect_transform_attrs(source, target, translate=True, rotate=True, scale=True):
    """Quickly and forcefully connect commonly used transform attributes."""
    axes = ['X', 'Y', 'Z']
    for axis in axes:
        if translate:
            cmds.connectAttr(f'{source}.translate{axis}', f'{target}.translate{axis}', force=True)
        if rotate:
            cmds.connectAttr(f'{source}.rotate{axis}', f'{target}.rotate{axis}', force=True)
        if scale:
            cmds.connectAttr(f'{source}.scale{axis}', f'{target}.scale{axis}', force=True)


def create_distance_measurement(start_obj, end_obj, name):
    """Create a Distance node to measure the distance between two objects."""
    locator_start_name = name + "_start_loc"
    locator_end_name = name + "_end_loc"
    distance_node_name = name + "_distance"

    start_point = cmds.xform(start_obj, query=True, worldSpace=True, translation=True)
    end_point = cmds.xform(end_obj, query=True, worldSpace=True, translation=True)
    
    distance_shape = cmds.distanceDimension(sp=(0,0,0), ep=(1,1,1))
    distance_transform = cmds.listRelatives(distance_shape, parent=True)[0]
    distance_transform = cmds.rename(distance_transform, distance_node_name)
    
    new_shape = cmds.listRelatives(distance_transform, children=True, shapes=True)[0]
    locators = cmds.listConnections(new_shape) or []
    
    if len(locators) >= 2:
        start_loc = cmds.rename(locators[0], locator_start_name)
        end_loc = cmds.rename(locators[1], locator_end_name)
        
        cmds.xform(start_loc, ws=True, t=start_point)
        cmds.xform(end_loc, ws=True, t=end_point)
        
        cmds.parent(start_loc, start_obj)
        cmds.parent(end_loc, end_obj)
        
    return distance_transform


def get_dynamic_scale_mapping(source, target):
    """
    두 오브젝트의 월드 매트릭스(World Matrix) 방향 벡터를 비교하여, 
    Target의 각 축(X,Y,Z)이 Source의 어떤 축과 가장 일치하는지 찾아냅니다.
    """
    s_mat = cmds.xform(source, q=True, matrix=True, ws=True)
    t_mat = cmds.xform(target, q=True, matrix=True, ws=True)

    def get_vec(mat, idx):
        v = [mat[idx*4], mat[idx*4+1], mat[idx*4+2]]
        mag = (v[0]**2 + v[1]**2 + v[2]**2) ** 0.5
        return [v[0]/mag, v[1]/mag, v[2]/mag] if mag > 0 else [0,0,0]

    s_axes = {'X': get_vec(s_mat, 0), 'Y': get_vec(s_mat, 1), 'Z': get_vec(s_mat, 2)}
    t_axes = {'X': get_vec(t_mat, 0), 'Y': get_vec(t_mat, 1), 'Z': get_vec(t_mat, 2)}

    mapping = {}
    for t_name, t_vec in t_axes.items():
        best_match = 'X'
        max_dot = -1.0
        for s_name, s_vec in s_axes.items():
            dot = abs(t_vec[0]*s_vec[0] + t_vec[1]*s_vec[1] + t_vec[2]*s_vec[2])
            if dot > max_dot:
                max_dot = dot
                best_match = s_name
        mapping[t_name] = best_match

    return mapping


def calculate_pole_vector_pos(root, mid, end, multiplier=0.5):
    """
    3개의 조인트(Root, Mid, End) 위치를 기반으로 
    관절 평면(Plane)상에 정확히 위치하는 IK 폴벡터 좌표를 계산합니다.
    (뼈가 꺾인 방향 그대로 뒤로 빠지므로, IK 전환 시 뼈가 튀지 않습니다.)
    """
    # 1. 조인트의 월드 좌표를 MVector로 변환
    root_pos = om.MVector(cmds.xform(root, q=True, ws=True, t=True))
    mid_pos  = om.MVector(cmds.xform(mid, q=True, ws=True, t=True))
    end_pos  = om.MVector(cmds.xform(end, q=True, ws=True, t=True))

    # 2. 어깨->손목 벡터와 어깨->팔꿈치 벡터 추출
    root_to_end = end_pos - root_pos
    root_to_mid = mid_pos - root_pos

    # 3. 투영(Projection) 수학: 팔꿈치에서 어깨-손목 선상으로 수직으로 내린 점 찾기
    dot = root_to_mid * root_to_end
    end_len_sq = root_to_end * root_to_end
    t = dot / end_len_sq if end_len_sq > 0.0001 else 0
    proj_point = root_pos + (root_to_end * t)

    # 4. 투영점에서 팔꿈치로 향하는 방향 벡터 구하기
    pv_dir = mid_pos - proj_point
    
    if pv_dir.length() < 0.001:
        pv_dir = om.MVector(0, 0, 1) # 만약 팔이 완벽한 일직선일 경우의 방어 코드
    else:
        pv_dir = pv_dir.normal()

    # 5. 팔 전체 길이에 비례(multiplier)하여 뒤로 빼주기
    arm_length = (mid_pos - root_pos).length() + (end_pos - mid_pos).length()
    pv_pos = mid_pos + (pv_dir * (arm_length * multiplier))

    return [pv_pos.x, pv_pos.y, pv_pos.z]


def lock_and_hide(node, lock=True, keyable=False, attrs=['tx', 'ty', 'tz', 'rx', 'ry', 'rz', 'sx', 'sy', 'sz', 'v']):
    """
    지정된 노드의 특정 속성(Attribute)들을 잠그고(Lock) 채널 박스에서 숨깁니다(Hide).
    """
    for attr in attrs:
        attr_path = f"{node}.{attr}"
        if cmds.objExists(attr_path):
            cmds.setAttr(attr_path, lock=lock, keyable=keyable, channelBox=False)

def set_joint_drawstyle_none(jnt):
    """
    조인트의 Draw Style을 'None(2)'으로 설정하여 뷰포트에서 보이지 않게 합니다.
    """
    try:
        cmds.setAttr(jnt + ".drawStyle", 2)
    except Exception as e:
        cmds.warning(f"Could not set drawStyle on {jnt}: {e}")


def snap_to_closest_world_axis(obj):
    mat = cmds.xform(obj, q=True, matrix=True, ws=True)
    
    # 1. 현재 오브젝트의 X, Y 방향 벡터 추출
    x_vec = om.MVector(mat[0], mat[1], mat[2]).normal()
    y_vec = om.MVector(mat[4], mat[5], mat[6]).normal()
    
    # 2. 6방향 월드 축 (X, -X, Y, -Y, Z, -Z)
    world_axes = [
        om.MVector(1, 0, 0), om.MVector(-1, 0, 0),
        om.MVector(0, 1, 0), om.MVector(0, -1, 0),
        om.MVector(0, 0, 1), om.MVector(0, 0, -1)
    ]
    
    # 3. 내적(Dot Product)을 통해 가장 가까운 월드 축 찾기
    def get_closest(vec):
        return max(world_axes, key=lambda wa: vec * wa)
        
    new_x = get_closest(x_vec)
    new_y = get_closest(y_vec)
    
    # 4. 외적(Cross Product)을 통해 직교하는 완벽한 Z축 계산
    new_z = new_x ^ new_y 
    
    # 5. 새로운 직교 매트릭스 조립 (위치는 그대로 유지)
    new_mat = [
        new_x.x, new_x.y, new_x.z, 0.0,
        new_y.x, new_y.y, new_y.z, 0.0,
        new_z.x, new_z.y, new_z.z, 0.0,
        mat[12], mat[13], mat[14], 1.0
    ]
    
    # 6. 월드 매트릭스로 덮어씌우기
    cmds.xform(obj, matrix=new_mat, ws=True)




def normalize_angle(angle):
    """각도를 -180 ~ 180 사이로 정규화합니다."""
    return ((angle + 180) % 360) - 180

def set_driven_key(driven, attr, drn_value, driver, drv_value):
    """간소화된 Set Driven Key 헬퍼 함수"""
    nodes = cmds.setDrivenKeyframe(driven, at=attr, v=drn_value, cd=driver, dv=drv_value)
    return nodes

def add_rotation(targets, value):
    for s in targets:
        curr_rot = cmds.getAttr(f"{s}.rotate")[0]
        result = []
        for x, y in zip(value, curr_rot):
            sum_xy = x + y      
            result.append(normalize_angle(sum_xy))

        new_rot = tuple(result)
        cmds.xform(s, ro=new_rot, os=True)

def simple_connect(driver, drv_attr, driven, drn_attr):
    """Driven 위에 전용 Offset 그룹을 만들고 속성을 직접 연결합니다."""
    drn_offs_grp = create_offset_grp(driven, '_' + drv_attr)
    cmds.connectAttr(f'{driver}.{drv_attr}', f'{drn_offs_grp}.{drn_attr}', force=True)

def simple_sdk(driver, attr, driven, axis, transform, drv_value, drn_value):
    """여러 타겟에 대한 Set Driven Key를 한 번에 구성하는 헬퍼 함수입니다."""
    driver_attr = f"{driver}.{attr}"
    drn_ofs_grp = []
    
    for drn in driven:
        ofs_grp = create_offset_grp(drn, '_' + attr)
        drn_ofs_grp.append(ofs_grp)
        
    for i, drn_node in enumerate(drn_ofs_grp):
        attr_name = f"{transform[i]}{axis[i]}"
        for j, drv_val in enumerate(drv_value):
            drn_val = drn_value[i][j]
            set_driven_key(drn_node, attr_name, drn_val, driver_attr, drv_val)


def get_aim_and_up_vectors(parent_node, child_node):
    # 자식의 로컬 위치값(Translate) 가져오기
    t_val = cmds.getAttr(f"{child_node}.translate")[0]
    
    # 절대값이 가장 큰 축이 뼈가 향하는(Aim) 방향입니다.
    abs_t = [abs(v) for v in t_val]
    max_idx = abs_t.index(max(abs_t))
    
    aim_vec = [0, 0, 0]
    aim_vec[max_idx] = 1.0 if t_val[max_idx] > 0 else -1.0
    
    # 직교하는 나머지 두 축 중 다음 축을 임의의 Up Vector로 지정합니다.
    up_vec = [0, 0, 0]
    up_idx = (max_idx + 1) % 3
    up_vec[up_idx] = 1.0
    
    return aim_vec, up_vec