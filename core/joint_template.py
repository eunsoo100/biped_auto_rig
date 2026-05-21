import maya.cmds as cmds
import maya.api.OpenMaya as om

def shorten_name(name_list):
    new_name = []
    for x in name_list:
        short_name = x.split("|")[-1]
        new_name.append(short_name)
    return new_name

def build_clean_skeleton(template_root, prefix="cln_", bend_axis="z"):
    # 1. Get all joints under the template root (Sorted top-down)
    template_joints = cmds.listRelatives(template_root, allDescendents=True, type="joint", fullPath=True) or []
    template_joints.append(template_root)
    template_joints.reverse() 

    new_joints_map = {}
    
    shrt_name_tmplt_jnt = shorten_name(template_joints)

    for jnt in shrt_name_tmplt_jnt:
        # 2. Extract the world space position (Translation) of the template joint
        world_pos = cmds.xform(jnt, query=True, worldSpace=True, translation=True)
        
        # 3. Clear selection and create a new joint (Clean state with scale 1,1,1)
        cmds.select(clear=True)
        short_name = jnt.split("|")[-1]
        new_jnt = cmds.joint(name=prefix + short_name, position=world_pos)
        
        # 4. Match rotation and bake to Joint Orient
        cmds.matchTransform(new_jnt, jnt, rotation=True)
        cmds.makeIdentity(new_jnt, apply=True, translate=False, rotate=True, scale=False, normal=False)
        
        new_joints_map[jnt] = new_jnt
    
    clean_root = None
    for jnt in shrt_name_tmplt_jnt:
        parent = cmds.listRelatives(jnt, parent=True)
        
        if parent and parent[0] in new_joints_map:
            child_jnt = new_joints_map[jnt]
            parent_jnt = new_joints_map[parent[0]]
            
            new_path = cmds.parent(child_jnt, parent_jnt)[0]
            print('\nparent', child_jnt, 'to', parent_jnt )
            new_joints_map[jnt] = new_path
            
        elif not clean_root:
            clean_root = new_joints_map[jnt]
            print('this is clean root', clean_root)

# ---------------------------------------------------------
    # [Pass 3] 1-Axis Planar IK Solver (OM2 Vector Math)
    # ---------------------------------------------------------
    for jnt in shrt_name_tmplt_jnt:
        clean_jnt = new_joints_map[jnt]
        name_lower = clean_jnt.lower()
        
        # Target only IK limbs based on naming convention
        if "shoulder" in name_lower or "thigh" in name_lower:
            children = cmds.listRelatives(clean_jnt, children=True)
            if children:
                mid_jnt = children[0]
                grandchildren = cmds.listRelatives(mid_jnt, children=True)
                if grandchildren:
                    end_jnt = grandchildren[0]
                    
                    print(f"\nApplying OM2 Planar Math: {clean_jnt} -> {mid_jnt} -> {end_jnt}")
                    
                    # 1. Unparent children of end_jnt (hands/feet) to preserve their exact world position
                    temp_end_children = cmds.listRelatives(end_jnt, children=True) or []
                    if temp_end_children:
                        temp_end_children = cmds.parent(temp_end_children, world=True)
                        
                    # 2. Unparent mid and end to avoid hierarchy double-transforms during matrix application
                    mid_jnt = cmds.parent(mid_jnt, world=True)[0]
                    end_jnt = cmds.parent(end_jnt, world=True)[0]
                    
                    # 3. Get positions as OM2 vectors
                    pos_s = om.MVector(cmds.xform(clean_jnt, q=True, ws=True, t=True))
                    pos_m = om.MVector(cmds.xform(mid_jnt, q=True, ws=True, t=True))
                    pos_e = om.MVector(cmds.xform(end_jnt, q=True, ws=True, t=True))
                    
                    # 4. Calculate Aim and Normal Vectors
                    vec_aim_s = (pos_m - pos_s).normal()
                    vec_aim_m = (pos_e - pos_m).normal()
                    
                    # Cross product to get the perfect plane normal
                    vec_normal = (vec_aim_s ^ vec_aim_m).normal()
                    if vec_normal.length() < 0.001:
                        vec_normal = om.MVector(0, 1, 0) # Straight line fallback
                        
                    # 5. Matrix Construction helper function
                    def get_planar_matrix(pos, aim_v, norm_v, axis_choice):
                        aim_x = aim_v.normal()
                        if axis_choice.lower() == 'y':
                            norm_y = norm_v.normal()
                            cross_z = (aim_x ^ norm_y).normal()
                            return [aim_x.x, aim_x.y, aim_x.z, 0.0,
                                    norm_y.x, norm_y.y, norm_y.z, 0.0,
                                    cross_z.x, cross_z.y, cross_z.z, 0.0,
                                    pos.x, pos.y, pos.z, 1.0]
                        else: # Defaults to 'z' bend
                            norm_z = norm_v.normal()
                            cross_y = (norm_z ^ aim_x).normal()
                            return [aim_x.x, aim_x.y, aim_x.z, 0.0,
                                    cross_y.x, cross_y.y, cross_y.z, 0.0,
                                    norm_z.x, norm_z.y, norm_z.z, 0.0,
                                    pos.x, pos.y, pos.z, 1.0]
                                    
                    mat_s = get_planar_matrix(pos_s, vec_aim_s, vec_normal, bend_axis)
                    mat_m = get_planar_matrix(pos_m, vec_aim_m, vec_normal, bend_axis)
                    mat_e = get_planar_matrix(pos_e, vec_aim_m, vec_normal, bend_axis) # Wrist copies elbow orientation
                    
                    # 6. Apply Absolute Matrices back to joints
                    cmds.xform(clean_jnt, m=mat_s, ws=True)
                    cmds.xform(mid_jnt, m=mat_m, ws=True)
                    cmds.xform(end_jnt, m=mat_e, ws=True)
                    
                    # 7. Reparent Hierarchy
                    mid_jnt = cmds.parent(mid_jnt, clean_jnt)[0]
                    end_jnt = cmds.parent(end_jnt, mid_jnt)[0]
                    if temp_end_children:
                        cmds.parent(temp_end_children, end_jnt)
                        
                    # 8. Freeze Rotations to lock the 1-axis bend strictly into jointOrient
                    cmds.makeIdentity(clean_jnt, apply=True, translate=False, rotate=True, scale=False, normal=False)

    cmds.select(clean_root)
    print(f"Clean skeleton created successfully: {clean_root}")
    return clean_root


# User Execution Example: You can change bend_axis to 'y' or 'z'
if __name__ == "__main__":
    jnt = cmds.ls(sl=True)[0]
    build_clean_skeleton(jnt, bend_axis='z')