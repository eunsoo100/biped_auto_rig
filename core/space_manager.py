import maya.cmds as cmds
from core.data_manager import RigAssetManager
from core.parent_switch import parent_switch as setup_parent_switch

class SpaceManager:
    def __init__(self):
        self.arm_l = self._get_meta_data("arm_L_meta")
        self.arm_r = self._get_meta_data("arm_R_meta")
        self.leg_l = self._get_meta_data("leg_L_meta")
        self.leg_r = self._get_meta_data("leg_R_meta")
        self.spine = self._get_meta_data("spine_C_meta")
        self.neck = self._get_meta_data("neck_C_meta")
        self.global_c = self._get_meta_data("global_C_meta")

    def _get_meta_data(self, meta_node):
        if cmds.objExists(meta_node):
            mgr = RigAssetManager(meta_node)
            return mgr.get_data()[1] or {}
        return {}

    def _get_node(self, part_dict, key):
        node = part_dict.get(key)
        if node and cmds.objExists(node):
            return node
        return None

    def get_space_definitions(self):
        """Return a list of space-switch definitions that the UI can display/edit.

        Each entry is a dict:
            {
                "label":           <human-readable name shown in UI>,
                "target":          <Maya ctrl that receives the space attr>,
                "enum_list":       [<space names>],
                "parents":         [<Maya nodes>],
                "constrain_type":  'parent' | 'orient' | 'point',
                "attr_name":       'space'
            }
        Entries whose target or required parents are missing are silently skipped.
        """
        global_ctrl = self._get_node(self.global_c, "global_ctrl")
        cog_ctrl = self._get_node(self.spine, "cog_ctrl")
        chest_ctrl = self._get_node(self.spine, "up_ik_ctrl")
        hip_ctrl = self._get_node(self.spine, "hip_ctrl")
        neck_base_ctrl = self._get_node(self.neck, "lo_ctrl")
        head_ctrl = self._get_node(self.neck, "head_ctrl")

        defs = []

        # --- Arms ---
        for side, arm_data in [("L", self.arm_l), ("R", self.arm_r)]:
            ik_wrist = self._get_node(arm_data, "ik_ctrl")
            ik_pv = self._get_node(arm_data, "ik_pv_ctrl")
            clavicle_ctrl = self._get_node(arm_data, "clavicle_ctrl")
            fk_shoulder = self._get_node(arm_data, "fk_shoulder_ctrl")

            if ik_wrist and global_ctrl and chest_ctrl and hip_ctrl and clavicle_ctrl and cog_ctrl:
                defs.append({
                    "label": f"Arm {side} IK Wrist",
                    "target": ik_wrist,
                    "enum_list": ["Global", "COG", "Chest", "Clavicle", "Hip"],
                    "parents": [global_ctrl, cog_ctrl, chest_ctrl, clavicle_ctrl, hip_ctrl],
                    "constrain_type": "parent",
                    "attr_name": "space",
                })

            if ik_pv and global_ctrl and chest_ctrl and ik_wrist and cog_ctrl:
                defs.append({
                    "label": f"Arm {side} IK PV",
                    "target": ik_pv,
                    "enum_list": ["Global", "COG", "Chest", "Wrist"],
                    "parents": [global_ctrl, cog_ctrl, chest_ctrl, ik_wrist],
                    "constrain_type": "parent",
                    "attr_name": "space",
                })

            if fk_shoulder and clavicle_ctrl and chest_ctrl and global_ctrl:
                defs.append({
                    "label": f"Arm {side} FK Shoulder",
                    "target": fk_shoulder,
                    "enum_list": ["Clavicle", "Chest", "Global"],
                    "parents": [clavicle_ctrl, chest_ctrl, global_ctrl],
                    "constrain_type": "parent",
                    "attr_name": "space",
                })

        # --- Legs ---
        for side, leg_data in [("L", self.leg_l), ("R", self.leg_r)]:
            ik_ankle = self._get_node(leg_data, "ik_ctrl")
            ik_pv = self._get_node(leg_data, "ik_pv_ctrl")
            leg_pelvis_ctrl = self._get_node(leg_data, "pelvis_ctrl")

            if ik_ankle and global_ctrl and leg_pelvis_ctrl and cog_ctrl:
                defs.append({
                    "label": f"Leg {side} IK Ankle",
                    "target": ik_ankle,
                    "enum_list": ["Global", "COG", "Pelvis"],
                    "parents": [global_ctrl, cog_ctrl, leg_pelvis_ctrl],
                    "constrain_type": "parent",
                    "attr_name": "space",
                })

            if ik_pv and global_ctrl and leg_pelvis_ctrl and ik_ankle and cog_ctrl:
                defs.append({
                    "label": f"Leg {side} IK PV",
                    "target": ik_pv,
                    "enum_list": ["Global", "COG", "Pelvis", "Ankle"],
                    "parents": [global_ctrl, cog_ctrl, leg_pelvis_ctrl, ik_ankle],
                    "constrain_type": "parent",
                    "attr_name": "space",
                })

        # --- Head / Neck ---
        if neck_base_ctrl and chest_ctrl and global_ctrl:
            defs.append({
                "label": "Neck",
                "target": neck_base_ctrl,
                "enum_list": ["Chest", "Global"],
                "parents": [chest_ctrl, global_ctrl],
                "constrain_type": "orient",
                "attr_name": "space",
            })

        if head_ctrl and neck_base_ctrl and chest_ctrl and global_ctrl:
            defs.append({
                "label": "Head",
                "target": head_ctrl,
                "enum_list": ["Neck", "Chest", "Global"],
                "parents": [neck_base_ctrl, chest_ctrl, global_ctrl],
                "constrain_type": "orient",
                "attr_name": "space",
            })

        return defs

    def apply_spaces(self, definitions):
        """Apply parent switch for a list of definition dicts (same format
        returned by *get_space_definitions*).  Each dict must have at least
        two parent entries to be valid."""
        print("\n--- [Space Manager] Applying selected space switches ---")
        for d in definitions:
            if len(d["parents"]) < 2:
                cmds.warning(f"Skipping '{d['label']}': need at least 2 parent spaces.")
                continue
            setup_parent_switch(
                d["enum_list"], d["parents"], d["target"],
                constrain_type=d["constrain_type"], attr_name=d["attr_name"]
            )
        print("Selected space switching applied successfully!\n")

    def apply_all_spaces(self):
        """Convenience wrapper – apply every available space definition."""
        defs = self.get_space_definitions()
        self.apply_spaces(defs)