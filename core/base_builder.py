import maya.cmds as cmds
from .data_manager import RigAssetManager
from . import rig_utils as utils

class BaseBuilder:
    """
    모든 리깅 모듈(Arm, Leg, Spine 등)의 뼈대가 되는 부모 클래스입니다.
    이 클래스를 상속받으면 네이밍, 데이터 저장, 색상 지정 기능이 자동으로 따라옵니다.
    """
    def __init__(self, prefix, side="C"):
        self.prefix = prefix       # 예: "arm", "leg", "spine"
        self.side = side.upper()   # "L", "R", "C" (항상 대문자로 통일)
        
        # 1. 파츠의 고유 이름 생성 (예: "arm_L", "spine_C")
        self.part_name = f"{self.prefix}_{self.side}"
        
        # 2. 전용 데이터 매니저(메타 노드) 자동 생성 및 연결 (예: "arm_L_meta")
        self.data_mgr = RigAssetManager(f"{self.part_name}_meta")
        
        # 3. 방향(Side)에 따른 자동 변수 세팅 (미러링 계수 및 컨트롤러 색상)
        self.mirror_val = -1 if self.side == "R" else 1
        
        # 마야 기본 색상 가이드: L = 파랑(6), R = 빨강(13), C = 노랑(17)
        if self.side == "L":
            self.color = 6
            self.sc_color = 18
        elif self.side == "R":
            self.color = 13
            self.sc_color = 20
        else:
            self.color = 17

    def get_name(self, suffix):
        """
        일관된 네이밍 규칙을 적용해주는 헬퍼 함수입니다.
        사용 예: self.get_name("ik_ctrl") -> "arm_L_ik_ctrl"
        """
        return f"{self.prefix}_{self.side}_{suffix}"

    def register_outputs(self, object_map):
        """생성된 마야 객체들을 자신의 메타 노드에 한 번에 등록(Message 연결)합니다."""
        self.data_mgr.save_data(object_map=object_map)

    def save_settings(self, settings_dict):
        """해당 파츠의 설정값(JSON)을 저장합니다."""
        self.data_mgr.save_data(settings=settings_dict)

    def get_dependency(self, target_part, key):
        """
        다른 파츠(예: spine_C)의 특정 컨트롤러나 조인트 정보가 필요할 때 가져옵니다.
        사용 예: self.get_dependency("spine_C", "end_joint")
        """
        # 타겟 파츠의 메타 노드를 임시로 연결해서 정보를 빼옵니다
        temp_mgr = RigAssetManager(f"{target_part}_meta")
        _, objects = temp_mgr.get_data()
        
        obj = objects.get(key)
        if not obj or not cmds.objExists(obj):
            cmds.warning(f"Dependency error : 'cannot find '{key}' of {target_part}'")
            return None
        return obj

    def build(self):
        """
        실제 리깅 로직이 들어갈 함수입니다.
        자식 클래스(Arm, Spine 등)에서 무조건 이 함수를 덮어써서(Override) 구현해야 합니다.
        """
        raise NotImplementedError("이 모듈은 아직 build() 함수가 구현되지 않았습니다.")