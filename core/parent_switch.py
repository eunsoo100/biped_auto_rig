import maya.cmds as cmds
from core import rig_utils as utils

def create_enum_attr(node, attr_name, enum_list):
    """지정된 노드에 Enum(드롭다운) 속성을 생성하거나 업데이트합니다."""
    enum_str = ":".join(enum_list)
    
    if cmds.attributeQuery(attr_name, node=node, exists=True):
        cmds.addAttr(f"{node}.{attr_name}", edit=True, enumName=enum_str)
    else:
        cmds.addAttr(node, longName=attr_name, attributeType='enum', enumName=enum_str, keyable=True)

def parent_switch(enum_list, parents, target, constrain_type='parent', attr_name='space'):
    """여러 부모(Parents) 사이를 전환할 수 있는 스페이스 스위칭(Space Switch) 시스템을 구축합니다."""
    if len(parents) != len(enum_list):
        cmds.error(f"[{target}] 부모 목록의 개수와 Enum 리스트의 개수가 일치하지 않습니다.")
        return
        
    create_enum_attr(target, attr_name, enum_list)
    driver_attr = f"{target}.{attr_name}"
    
    space_offs = cmds.group(empty=True, name=f"{target}_{attr_name}")

    cmds.parent(space_offs, target, relative=True)
    
    orig_parent = cmds.listRelatives(target, parent=True)
    if orig_parent:
        cmds.parent(space_offs, orig_parent[0])
    else:
        cmds.parent(space_offs, world=True)
        
    cmds.parent(target, space_offs)

    locators = []
    target_ws_scale = cmds.xform(space_offs, q=True, ws=True, s=True)
    
    for i, parent_node in enumerate(parents):
        loc_name = f"{target}_{enum_list[i]}_space_loc"
        loc = cmds.spaceLocator(name=loc_name)[0]
        
        cmds.matchTransform(loc, space_offs, pos=True, rot=True)
        cmds.parent(loc, parent_node)
        parent_ws_scale = cmds.xform(parent_node, q=True, ws=True, s=True)
        
        safe_p_sx = parent_ws_scale[0] if parent_ws_scale[0] != 0 else 1.0
        safe_p_sy = parent_ws_scale[1] if parent_ws_scale[1] != 0 else 1.0
        safe_p_sz = parent_ws_scale[2] if parent_ws_scale[2] != 0 else 1.0
        
        cmds.setAttr(f"{loc}.scaleX", target_ws_scale[0] / safe_p_sx)
        cmds.setAttr(f"{loc}.scaleY", target_ws_scale[1] / safe_p_sy)
        cmds.setAttr(f"{loc}.scaleZ", target_ws_scale[2] / safe_p_sz)
        
        cmds.setAttr(f"{loc}.visibility", 0)
        locators.append(loc)
        
    const_node = None
    if constrain_type == 'orient':
        const_node = cmds.orientConstraint(locators, space_offs, mo=True)[0]
        cmds.setAttr(f"{const_node}.interpType", 2)
    elif constrain_type == 'point':
        const_node = cmds.pointConstraint(locators, space_offs, mo=True)[0]
    elif constrain_type == 'parent':
        const_node = cmds.parentConstraint(locators, space_offs, mo=True)[0]
        cmds.setAttr(f"{const_node}.interpType", 2)
    else:
        cmds.error(f"[{constrain_type}] 지원하지 않는 Constraint 타입입니다.")
        return
        
    if constrain_type == 'orient':
        weight_attrs = cmds.orientConstraint(const_node, query=True, weightAliasList=True)
    elif constrain_type == 'point':
        weight_attrs = cmds.pointConstraint(const_node, query=True, weightAliasList=True)
    elif constrain_type == 'parent':
        weight_attrs = cmds.parentConstraint(const_node, query=True, weightAliasList=True)
        
    for i, enum_val in enumerate(enum_list):
        cmds.setAttr(driver_attr, i)
        for j, weight_attr in enumerate(weight_attrs):
            target_weight = 1 if i == j else 0
            cmds.setAttr(f"{const_node}.{weight_attr}", target_weight)
            cmds.setDrivenKeyframe(f"{const_node}.{weight_attr}", currentDriver=driver_attr)
            
    cmds.setAttr(driver_attr, 0)
    cmds.setAttr(f"{space_offs}.visibility", lock=True, keyable=False)