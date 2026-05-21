import maya.cmds as cmds
from core.data_manager import RigAssetManager
from core import rig_utils as utils
import importlib

class MirrorManager:
    def __init__(self, left_meta_node):
        self.left_meta_node = left_meta_node
        self.meta_mgr = RigAssetManager(self.left_meta_node)
        self.settings, self.left_objects = self.meta_mgr.get_data()
        
        # Extract part and side information from meta node name (e.g., "arm_L_meta" -> prefix="arm", side="L")
        self.prefix = self.left_meta_node.split('_')[0]
        self.side = self.left_meta_node.split('_')[1]

    def process_mirror(self):
        if not self.settings or not self.left_objects:
            cmds.warning(f"[{self.left_meta_node}] Meta data not found, mirroring aborted.")
            return

        print(f"\n--- [{self.prefix.upper()}] Right side mirroring process start ---")
        
        # 1. Dynamically load module and instantiate Builder
        builder_class = self._get_builder_class()
        if not builder_class: return
        right_builder = builder_class(side="R")

        # 2. Reconstruct parameters and mirror base joints
        build_kwargs = self._prepare_build_kwargs()
        if not build_kwargs: return

        # 3. Build right side module
        print(f"[{self.prefix}] Generating right rig...")
        right_builder.build(**build_kwargs)

        if hasattr(self, 'temp_mirror_locs') and self.temp_mirror_locs:
            locs_to_delete = [loc for loc in self.temp_mirror_locs if cmds.objExists(loc)]
            if locs_to_delete:
                cmds.delete(locs_to_delete)
            self.temp_mirror_locs = []
        
        # 4. Copy controller sh                 Wapes and mirror left-right
        self._mirror_ctrl_shapes()
        
        print(f"[{self.prefix.upper()}] Mirroring process completed!\n")

        self._trigger_child_mirror()

    def _trigger_child_mirror(self):
        child_map = {
            'arm': 'hand',
            'leg': 'foot'
        }
        
        child_prefix = child_map.get(self.prefix)
        if not child_prefix:
            return 
            
        child_meta = f"{child_prefix}_{self.side}_meta"
        
        if cmds.objExists(child_meta):
            print(f"[{self.prefix.upper()}] Starting chained mirroring for dependent [{child_prefix.upper()}] part.")
            child_manager = MirrorManager(child_meta)
            child_manager.process_mirror()
        else:
            print(f"Child part meta node ({child_meta}) does not exist, ending with standalone mirroring.")

    def _get_builder_class(self):
        # Map part name to class name (automated according to rules)
        class_name = f"{self.prefix.capitalize()}Builder" 
        try:
            # e.g.: import module.arm -> ArmBuilder
            module = importlib.import_module(f"modules.{self.prefix}")
            return getattr(module, class_name)
        except (ImportError, AttributeError) as e:
            cmds.warning(f"[{self.prefix}] Failed to load Builder module: {e}")
            return None

    def _prepare_build_kwargs(self):
        kwargs = self.settings.copy()
        
        jnt_key = None
        for key in ['arm_jnts', 'leg_jnts', 'hand_jnts', 'foot_jnts']:
            if key in kwargs:
                jnt_key = key
                break
                
        if jnt_key and kwargs[jnt_key]:
            # Copy the list to prevent damage to the original.
            left_jnts = list(kwargs[jnt_key])
            
            if self.prefix == 'leg':
                ankle_jnt = left_jnts[-1] # Leg's last joint is Ankle.
                if cmds.objExists(ankle_jnt):
                    ball_jnts = cmds.listRelatives(ankle_jnt, children=True, type='joint', fullPath=True)
                    if ball_jnts:
                        left_jnts.append(ball_jnts[0])
                        toe_jnts = cmds.listRelatives(ball_jnts[0], children=True, type='joint', fullPath=True)
                        if toe_jnts:
                            left_jnts.append(toe_jnts[0])
                            
            # 1. Create temporary chain for world axis mirroring
            temp_left_jnts = []
            for i, jnt in enumerate(left_jnts):
                if not cmds.objExists(jnt): continue
                
                # [Error fix] Restore to parentOnly=True to prevent name conflicts and multiple duplications.
                dup = cmds.duplicate(jnt, parentOnly=True, name=f"TMP_{self.prefix}_{i}_L")[0]
                if cmds.listRelatives(dup, parent=True):
                    cmds.parent(dup, world=True)
                
                if i > 0:
                    cmds.parent(dup, temp_left_jnts[i-1])
                temp_left_jnts.append(dup)
                
            if not temp_left_jnts: return None

            # 2. Mirror temporary chain
            mirrored_jnts = cmds.mirrorJoint(
                temp_left_jnts[0], 
                mirrorYZ=True, 
                mirrorBehavior=True, 
                searchReplace=['_L', '_R']
            )
            
            # 3. Final renaming and cleanup of mirrored joints
            right_jnts = []
            for i, m_jnt in enumerate(mirrored_jnts):
                # Extract only the last name from fullPath name and replace cleanly.
                final_name = left_jnts[i].replace('_L_', '_R_').replace('_l_', '_r_').split('|')[-1]
                
                if cmds.objExists(final_name):
                    cmds.delete(final_name)
                
                renamed = cmds.rename(m_jnt, final_name)
                right_jnts.append(renamed)
                
            # 4. Delete temporary original chain after use
            cmds.delete(temp_left_jnts[0])
            kwargs[jnt_key] = right_jnts
        
        # Remove existing data keys that might conflict during build
        for exclude_key in ['drv_jnts', 'ik_jnts', 'fk_jnts', 'ribbon_bnd_jnts']:
            kwargs.pop(exclude_key, None)
            
        # Locator auto generation and replacement logic (maintain previously added part)
        foot_loc_keys = ['loc_heel', 'loc_toetip', 'loc_outer', 'loc_inner']
        for k, v in kwargs.items():
            if isinstance(v, str) and k not in foot_loc_keys:
                kwargs[k] = v.replace('_L_', '_R_').replace('_l_', '_r_')
                
        if self.prefix == 'foot':
            self.temp_mirror_locs = []
            loc_to_ctrl_map = {
                'loc_heel': 'heel_ctrl',
                'loc_toetip': 'toetip_ctrl',
                'loc_outer': 'outer_ctrl',
                'loc_inner': 'inner_ctrl'
            }
            
            for loc_key, ctrl_key in loc_to_ctrl_map.items():
                if loc_key in kwargs:
                    left_ctrl = self.left_objects.get(ctrl_key)
                    if left_ctrl and cmds.objExists(left_ctrl):
                        pos = cmds.xform(left_ctrl, q=True, ws=True, t=True)
                        pos[0] = -pos[0] # X-axis inversion
                        
                        temp_loc = cmds.spaceLocator(name=f"TMP_R_{loc_key}")[0]
                        cmds.xform(temp_loc, ws=True, t=pos)
                        
                        self.temp_mirror_locs.append(temp_loc)
                        kwargs[loc_key] = temp_loc
                        
        return kwargs
    
    def _mirror_ctrl_shapes(self):
        print(f"[{self.prefix}] Matching controller shape mirrors...")
        ctrl_keys = [k for k in self.left_objects.keys() if 'ctrl' in k]
        
        for key in ctrl_keys:
            left_ctrl = self.left_objects[key]
            if not left_ctrl or not cmds.objExists(left_ctrl): 
                continue
            
            # Text replacement (case sensitive)
            right_ctrl = left_ctrl.replace('_L_', '_R_').replace('_l_', '_r_')
            if not cmds.objExists(right_ctrl):
                continue
                
            # 1. Delete existing shapes from right controller
            old_shapes = cmds.listRelatives(right_ctrl, shapes=True, fullPath=True)
            if old_shapes:
                cmds.delete(old_shapes)
                
            # 2. Copy left shapes (Target only Shape nodes directly)
            left_shapes = cmds.listRelatives(left_ctrl, shapes=True, fullPath=True)
            if not left_shapes: 
                continue
                
            new_shapes = []
            for i, l_shape in enumerate(left_shapes):
                # Duplicate only shape nodes (Maya automatically creates new temporary Transform when duplicating shapes)
                dup_nodes = cmds.duplicate(l_shape)
                dup_transform = dup_nodes[0]
                dup_shape = cmds.listRelatives(dup_transform, shapes=True, fullPath=True)[0]
                
                # Extract only the actual shape node and parent to target
                new_shape = cmds.parent(dup_shape, right_ctrl, shape=True, relative=True)[0]
                new_shape = cmds.rename(new_shape, f"{right_ctrl.split('|')[-1]}Shape{i+1:02d}")
                new_shapes.append(new_shape)
                
                # Completely delete temporary transform shell (prevent name conflicts)
                cmds.delete(dup_transform)
            
            # 3. Mirror CV positions based on 'world coordinates' not local scale
            for l_shape, r_shape in zip(left_shapes, new_shapes):
                cvs = cmds.ls(f"{l_shape}.cv[*]", flatten=True)
                for i in range(len(cvs)):
                    # Extract left CV's actual world coordinates
                    pos = cmds.xform(f"{l_shape}.cv[{i}]", query=True, worldSpace=True, translation=True)
                    
                    # Global YZ plane mirroring (X-axis absolute value inversion)
                    mirrored_pos = [-pos[0], pos[1], pos[2]]
                    
                    # Insert directly into right CV with world coordinates
                    cmds.xform(f"{r_shape}.cv[{i}]", worldSpace=True, translation=mirrored_pos)
            
            # 4. Overwrite right controller color
            from core import curve_utils
            color_id = 13 if 'tweak' not in right_ctrl and 'curl' not in right_ctrl else 20
            curve_utils.style_curve(right_ctrl, color_index=color_id)