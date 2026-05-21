import maya.cmds as cmds
import json

class RigAssetManager:
    def __init__(self, node_name):
        # 1개의 메타 노드만 쓰지 않고, 파츠별로 노드를 관리할 수 있게 node_name을 받습니다.
        # 예: node_name = "Arm_L_Meta"
        self.node = node_name
        self.ensure_node()

    def ensure_node(self):
        """데이터를 저장할 네트워크 노드 생성"""
        if not cmds.objExists(self.node):
            cmds.createNode("network", name=self.node)
            # JSON 설정을 담을 속성만 문자열(string)로 만듭니다
            cmds.addAttr(self.node, ln="settings", dt="string")
            print(f"Created Rig Meta Node: {self.node}")

    def save_data(self, settings=None, object_map=None):
        """
        settings: 변하지 않는 정보 (dict) -> JSON으로 저장
        object_map: 씬 객체들 (dict) -> Message로 연결
        """
        # --- 1. JSON 저장 (설정값) ---
        if settings:
            current_str = cmds.getAttr(f"{self.node}.settings") or "{}"
            try:
                full_data = json.loads(current_str)
            except ValueError:
                full_data = {}
            
            full_data.update(settings)
            json_str = json.dumps(full_data, indent=4)
            cmds.setAttr(f"{self.node}.settings", json_str, type="string")
        
        # --- 2. Message 연결 (객체 추적) ---
        if object_map:
            for key, obj_name in object_map.items():
                if not cmds.objExists(obj_name):
                    cmds.warning(f"[{self.node}] Cannot find object: {obj_name}")
                    continue

                # 속성이 없으면 message 타입으로 생성
                if not cmds.attributeQuery(key, node=self.node, exists=True):
                    cmds.addAttr(self.node, ln=key, at="message")
                
                # 실제 객체 -> 메타 노드로 연결
                cmds.connectAttr(f"{obj_name}.message", f"{self.node}.{key}", force=True)
                print(f"Connected: {key} <--> {obj_name}")

    def get_data(self):
        """저장된 설정과 객체 정보를 반환"""
        # 1. JSON 설정 가져오기
        json_str = cmds.getAttr(f"{self.node}.settings")
        settings = json.loads(json_str) if json_str else {}
        
        # 2. 연결된 객체들 찾기
        objects = {}
        attrs = cmds.listAttr(self.node, userDefined=True) or []
        
        for attr in attrs:
            if attr == "settings": continue 
            
            # 연결된 원본 객체 추적
            conns = cmds.listConnections(f"{self.node}.{attr}", source=True, destination=False)
            if conns:
                objects[attr] = conns[0] # 현재의 실제 이름
            else:
                objects[attr] = None # 삭제되었거나 연결 끊김
                
        return settings, objects