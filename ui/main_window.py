import os
import sys
from functools import partial

# Ensure auto_rig_system root is on sys.path regardless of how this file is loaded
_UI_DIR = os.path.dirname(os.path.abspath(__file__))   # .../ui
_ROOT = os.path.dirname(_UI_DIR)                        # .../auto_rig_system
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Purge any stale cached 'modules' or 'core' namespace packages from Maya's env
# so our packages at _ROOT take priority over any shadowing directories.
for _k in list(sys.modules.keys()):
    if _k in ('modules', 'core') or _k.startswith(('modules.', 'core.')):
        del sys.modules[_k]

import maya.cmds as cmds
try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from shiboken6 import wrapInstance
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui
    from shiboken2 import wrapInstance
from maya.app.general.mayaMixin import MayaQWidgetBaseMixin

try:
    from core.joint_template import build_clean_skeleton
except ImportError as e:
    cmds.warning(f"Failed to import joint_template: {e}")
    build_clean_skeleton = None

try:
    from modules.global_ctrl import GlobalBuilder
    from modules.spine import SpineBuilder
    from modules.neck import NeckBuilder
    from modules.arm import ArmBuilder
    from modules.hand import HandBuilder
    from modules.leg import LegBuilder
    from modules.foot import FootBuilder
    from core.space_manager import SpaceManager
except ImportError as e:
    cmds.warning(f"Failed to import modules: {e}")

try:
    from modules.face_rig.jaw import FaceRig
except ImportError as e:
    cmds.warning(f"Failed to import face_rig.jaw: {e}")
    FaceRig = None


class CollapsibleSection(QtWidgets.QWidget):
    """A collapsible section widget with a clickable header."""
    def __init__(self, title, parent=None):
        super(CollapsibleSection, self).__init__(parent)
        self._is_collapsed = False

        self._toggle_btn = QtWidgets.QToolButton()
        self._toggle_btn.setStyleSheet("QToolButton { border: none; font-weight: bold; }")
        self._toggle_btn.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self._toggle_btn.setArrowType(QtCore.Qt.DownArrow)
        self._toggle_btn.setText(title)
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.setChecked(False)
        self._toggle_btn.clicked.connect(self._toggle)

        self._content = QtWidgets.QWidget()
        self._content_layout = QtWidgets.QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(10, 4, 0, 0)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self._toggle_btn)
        main_layout.addWidget(self._content)

    def _toggle(self, checked):
        self._is_collapsed = checked
        self._toggle_btn.setArrowType(
            QtCore.Qt.RightArrow if checked else QtCore.Qt.DownArrow
        )
        self._content.setVisible(not checked)

    def content_layout(self):
        return self._content_layout


class AutoRigUI(MayaQWidgetBaseMixin, QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(AutoRigUI, self).__init__(parent)
        self.setWindowTitle("Auto Rig System v2.0")
        self.setMinimumSize(550, 650)
        
        self.main_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.main_widget)
        self.main_layout = QtWidgets.QVBoxLayout(self.main_widget)

        # 최상위 탭: Body Rig / Build Corrective Joints / Face Rig
        self.main_tabs = QtWidgets.QTabWidget()
        # objectName으로 스코프를 한정해서 하위(Body Rig 서브) 탭에는 영향 없음
        self.main_tabs.tabBar().setObjectName("mainTabBar")
        self.main_tabs.setStyleSheet("""
            QTabBar#mainTabBar::tab {
                font-size: 10pt;
                font-weight: regular;
                min-width: 95px;
                min-height: 22px;
                padding: 2px 8px;
            }
            QTabBar#mainTabBar::tab:selected {
                background: #c99c14;
                color: #ffffff;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-size: 10pt;
                font-weight: bold;
            }
        """)
        self.main_layout.addWidget(self.main_tabs)

        self._setup_body_rig_tab()
        self._setup_corrective_joints_tab()
        self._setup_face_rig_tab()

    def _setup_body_rig_tab(self):
        """Body Rig 최상위 탭: 기존 Prep/Build/Post 서브 탭을 포함."""
        body_rig_widget = QtWidgets.QWidget()
        body_rig_layout = QtWidgets.QVBoxLayout(body_rig_widget)
        body_rig_layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setTabPosition(QtWidgets.QTabWidget.West)
        body_rig_layout.addWidget(self.tabs)

        self._setup_prep_tab()
        self._setup_build_tab()
        self._setup_post_tab()

        self.main_tabs.addTab(body_rig_widget, "Body Rig")

    def _setup_corrective_joints_tab(self):
        """Build Corrective Joints 최상위 탭 (placeholder)."""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        placeholder = QtWidgets.QLabel("Build Corrective Joints - Coming Soon")
        placeholder.setAlignment(QtCore.Qt.AlignCenter)
        placeholder.setStyleSheet("color: #808080;")
        layout.addWidget(placeholder)
        self.main_tabs.addTab(tab, "Build Corrective Joints")

    # Jaw Rig 파트 이름 -> 기본 조인트 이름 (modules/face_rig/jaw.py의 FaceRig.PARTS / DEFAULT_JOINTS와 동일)
    JAW_RIG_PARTS = ['jaw', 'skull', 'lip_lower_C', 'lip_upper_C',
                     'lip_corner_L', 'lip_lower_L_sec', 'lip_upper_L_sec']
    JAW_RIG_DEFAULT_JOINTS = {
        'jaw': 'jaw_bnd_jnt',
        'skull': 'skull_bnd_jnt',
        'lip_lower_C': 'lip_lower_C_drv_jnt',
        'lip_upper_C': 'lip_upper_C_drv_jnt',
        'lip_corner_L': 'lip_corner_L_drv_jnt',
        'lip_lower_L_sec': 'lip_lower_L_sec_drv_jnt',
        'lip_upper_L_sec': 'lip_upper_L_sec_drv_jnt',
    }

    def _setup_face_rig_tab(self):
        """Face Rig 최상위 탭: Jaw Rig 서브 섹션 포함."""
        tab = QtWidgets.QWidget()
        tab_layout = QtWidgets.QVBoxLayout(tab)

        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)

        content_widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(content_widget)
        layout.setSpacing(20)

        layout.addWidget(self._build_jaw_rig_section())
        layout.addStretch()

        scroll_area.setWidget(content_widget)
        tab_layout.addWidget(scroll_area)

        self.main_tabs.addTab(tab, "Face Rig")

    def _build_jaw_rig_section(self):
        jaw_group = CollapsibleSection("Jaw Rig")
        jaw_layout = jaw_group.content_layout()

        desc_label = QtWidgets.QLabel(
            "<b>How to use:</b><br>"
            "1. Select vertex/vertices in Maya for each part below.<br>"
            "2. Click <b>'Set Joint'</b> to create/move that part's joint to the average position.<br>"
            "3. Once all joints are set, click <b>'Build Jaw'</b>."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #b0b0b0; padding: 5px;")
        jaw_layout.addWidget(desc_label)

        self.jaw_fields = {}
        for part in self.JAW_RIG_PARTS:
            row = QtWidgets.QHBoxLayout()

            label = QtWidgets.QLabel(part)
            label.setMinimumWidth(110)
            row.addWidget(label)

            field = QtWidgets.QLineEdit(self.JAW_RIG_DEFAULT_JOINTS[part])
            field.setReadOnly(True)
            field.setStyleSheet("background-color: #999999; color: black;")
            row.addWidget(field)

            btn_set = QtWidgets.QPushButton("Set Joint")
            btn_set.setMaximumWidth(90)
            btn_set.clicked.connect(partial(self._face_rig_set_joint, field, self.JAW_RIG_DEFAULT_JOINTS[part]))
            row.addWidget(btn_set)

            jaw_layout.addLayout(row)
            self.jaw_fields[part] = field

        self.btn_build_jaw = QtWidgets.QPushButton("Build Jaw")
        self.btn_build_jaw.setMinimumHeight(35)
        self.btn_build_jaw.setStyleSheet("background-color: #8a5a7a; color: white; font-weight: bold;")
        self.btn_build_jaw.clicked.connect(self._build_jaw)
        jaw_layout.addWidget(self.btn_build_jaw)

        return jaw_group

    # =====================================================================
    # 헬퍼 함수: 마야에서 선택한 오브젝트를 QLineEdit에 문자열로 입력
    # =====================================================================
    def _load_selection(self, line_edit):
        selected = cmds.ls(selection=True, flatten=True)
        if selected:
            # Display each joint on a new line for clarity
            line_edit.setPlainText("\n".join(selected))
        else:
            cmds.warning("No objects selected in Maya.")

    def _create_input_row(self, label_text):
        """[라벨] - [디스플레이 필드] - [Load 버튼] 조합의 레이아웃을 생성하여 반환합니다. (세로 정렬)"""
        layout = QtWidgets.QVBoxLayout()
        
        # 라벨 + Load 버튼을 가로로 배치
        header_layout = QtWidgets.QHBoxLayout()
        label = QtWidgets.QLabel(label_text)
        label.setMinimumWidth(80)
        
        btn_load = QtWidgets.QPushButton("Load Selection")
        btn_load.setMinimumWidth(130)
        
        header_layout.addWidget(label)
        header_layout.addStretch()
        header_layout.addWidget(btn_load)
        
        # 디스플레이 필드 (읽기 전용, QTextEdit 사용, 스크롤 가능)
        text_display = QtWidgets.QTextEdit()
        text_display.setReadOnly(True)
        text_display.setMinimumHeight(60)
        text_display.setMaximumHeight(100)
        text_display.setWordWrapMode(QtGui.QTextOption.WordWrap)
        text_display.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        text_display.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        
        btn_load.clicked.connect(lambda: self._load_selection(text_display))
        
        layout.addLayout(header_layout)
        layout.addWidget(text_display)
        return layout, text_display

    # =====================================================================
    # 탭 1: Preparing Rig
    # =====================================================================
    def _setup_prep_tab(self):
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        
        # --- 1. Import Template Section ---
        layout.addWidget(QtWidgets.QLabel("1. Import Template"))
        self.btn_import_skeleton = QtWidgets.QPushButton("Import Base Skeleton")
        self.btn_import_skeleton.setMinimumHeight(30)
        self.btn_import_skeleton.setStyleSheet("background-color: #4a6a8a; color: white;")
        self.btn_import_skeleton.clicked.connect(self._import_skeleton_template)
        layout.addWidget(self.btn_import_skeleton)
        
        # --- 2. Joint Orientation Section ---
        orient_group = QtWidgets.QGroupBox("2. Joint Orientation (Clean Skeleton)")
        orient_layout = QtWidgets.QVBoxLayout(orient_group)
        
        # Description
        desc_label = QtWidgets.QLabel(
            "<b>How to use:</b><br>"
            "1. Select the <b>root joint</b> of your template skeleton in Maya.<br>"
            "2. Set the <b>Prefix</b> for the new clean joints (default: 'cln_').<br>"
            "3. Choose the <b>Bend Axis</b> for IK limbs (Y or Z).<br>"
            "4. Click <b>'Build Clean Skeleton'</b> to create oriented joints.<br><br>"
            "<b>Features:</b><br>"
            "• Creates a duplicate skeleton with clean joint orientations.<br>"
            "• Auto-detects shoulder/thigh joints and applies planar IK math.<br>"
            "• Ensures 1-axis bending for proper IK solver behavior.<br>"
            "• Preserves world positions while resetting rotations to jointOrient."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #b0b0b0; padding: 5px;")
        orient_layout.addWidget(desc_label)
        
        # Prefix Input
        prefix_layout = QtWidgets.QHBoxLayout()
        prefix_layout.addWidget(QtWidgets.QLabel("Prefix:"))
        self.joint_prefix_input = QtWidgets.QLineEdit()
        self.joint_prefix_input.setText("cln_")
        self.joint_prefix_input.setPlaceholderText("e.g., cln_, rig_, drv_")
        self.joint_prefix_input.setMaximumWidth(150)
        prefix_layout.addWidget(self.joint_prefix_input)
        prefix_layout.addStretch()
        orient_layout.addLayout(prefix_layout)
        
        # Bend Axis Input
        axis_layout = QtWidgets.QHBoxLayout()
        axis_layout.addWidget(QtWidgets.QLabel("Bend Axis:"))
        self.bend_axis_combo = QtWidgets.QComboBox()
        self.bend_axis_combo.addItems(["z", "y"])
        self.bend_axis_combo.setToolTip("Axis for IK limb bending (elbow/knee)")
        self.bend_axis_combo.setMaximumWidth(80)
        axis_layout.addWidget(self.bend_axis_combo)
        axis_layout.addStretch()
        orient_layout.addLayout(axis_layout)
        
        # Build Button
        self.btn_build_clean_skeleton = QtWidgets.QPushButton("Build Clean Skeleton")
        self.btn_build_clean_skeleton.setMinimumHeight(35)
        self.btn_build_clean_skeleton.setStyleSheet("background-color: #5a8a5a; color: white; font-weight: bold;")
        self.btn_build_clean_skeleton.clicked.connect(self._build_clean_skeleton)
        orient_layout.addWidget(self.btn_build_clean_skeleton)
        
        layout.addWidget(orient_group)
        layout.addStretch()
        self.tabs.addTab(tab, "1. Prep Rig")

    # =====================================================================
    # 탭 2: Body Rig Building (Spine, Arm, Leg UI 추가)
    # =====================================================================
    def _setup_build_tab(self):
        tab = QtWidgets.QWidget()
        tab_layout = QtWidgets.QVBoxLayout(tab)
        
        # Scroll Area
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        # Content widget for scroll area
        content_widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(content_widget)
        layout.setSpacing(20)
        
        # 1. Base System
        global_group = CollapsibleSection("1. Base System")
        global_layout = global_group.content_layout()
        self.btn_build_global = QtWidgets.QPushButton("Build Global Control")
        self.btn_build_global.setMinimumHeight(35)
        self.btn_build_global.setStyleSheet("background-color: #2b5c5c; color: white;")
        self.btn_build_global.clicked.connect(self._build_global)
        global_layout.addWidget(self.btn_build_global)
        layout.addWidget(global_group)

        # 2. Center Modules (Spine, Neck)
        center_group = CollapsibleSection("2. Center Modules")
        center_layout = center_group.content_layout()
        
        spine_row, self.spine_input = self._create_input_row("Spine Jnts:")
        center_layout.addLayout(spine_row)
        
        self.btn_build_spine = QtWidgets.QPushButton("Build Spine")
        self.btn_build_spine.setStyleSheet("background-color: #4a5f8f; color: white;")
        self.btn_build_spine.clicked.connect(self._build_spine)
        center_layout.addWidget(self.btn_build_spine)
        
        # Separator
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        center_layout.addWidget(separator)
        
        neck_jnts_row, self.neck_jnts_input = self._create_input_row("Neck Jnts:")
        center_layout.addLayout(neck_jnts_row)
        
        head_jnt_row, self.head_jnt_input = self._create_input_row("Head Jnt:")
        center_layout.addLayout(head_jnt_row)
        
        self.btn_build_neck = QtWidgets.QPushButton("Build Neck")
        self.btn_build_neck.setStyleSheet("background-color: #5a7aaa; color: white;")
        self.btn_build_neck.clicked.connect(self._build_neck)
        center_layout.addWidget(self.btn_build_neck)
        
        layout.addWidget(center_group)

        # 3. Limb Modules (Arm & Leg)
        limb_group = CollapsibleSection("3. Limb Modules (L / R)")
        limb_layout = limb_group.content_layout()
        
        side_layout = QtWidgets.QHBoxLayout()
        side_layout.addWidget(QtWidgets.QLabel("Target Side:"))
        self.side_combo = QtWidgets.QComboBox()
        self.side_combo.addItems(["L", "R"])
        side_layout.addWidget(self.side_combo)
        side_layout.addStretch()
        limb_layout.addLayout(side_layout)
        
        # Arm Input
        arm_row, self.arm_input = self._create_input_row("Arm Jnts:")
        limb_layout.addLayout(arm_row)
        
        # Arm Options
        arm_options_layout = QtWidgets.QVBoxLayout()
        
        # Stretch Axis, PV Multiplier, and Number of Follicles (horizontal)
        settings_layout = QtWidgets.QHBoxLayout()
        
        settings_layout.addWidget(QtWidgets.QLabel("Stretch Axis:"))
        self.arm_stretch_axis = QtWidgets.QComboBox()
        self.arm_stretch_axis.addItems(["X", "Y", "Z"])
        self.arm_stretch_axis.setCurrentText("Y")
        self.arm_stretch_axis.setMaximumWidth(60)
        settings_layout.addWidget(self.arm_stretch_axis)
        
        settings_layout.addWidget(QtWidgets.QLabel("PV Mult:"))
        self.arm_pv_mult = QtWidgets.QLineEdit()
        self.arm_pv_mult.setText("0.6")
        self.arm_pv_mult.setMaximumWidth(50)
        settings_layout.addWidget(self.arm_pv_mult)
        
        settings_layout.addWidget(QtWidgets.QLabel("Follicles:"))
        self.arm_num_fol = QtWidgets.QLineEdit()
        self.arm_num_fol.setText("12")
        self.arm_num_fol.setMaximumWidth(50)
        settings_layout.addWidget(self.arm_num_fol)
        
        settings_layout.addStretch()
        arm_options_layout.addLayout(settings_layout)
        
        # Rotation Offsets Group
        rot_offsets_group = QtWidgets.QGroupBox("Rotation Offsets")
        rot_offsets_layout = QtWidgets.QVBoxLayout(rot_offsets_group)
        
        # Control Rotation Offset
        ctrl_rot_layout = QtWidgets.QHBoxLayout()
        ctrl_rot_layout.addWidget(QtWidgets.QLabel("Ctrl (X, Y, Z):"))
        self.arm_ctrl_rot_x = QtWidgets.QLineEdit()
        self.arm_ctrl_rot_x.setText("0")
        self.arm_ctrl_rot_x.setMaximumWidth(50)
        self.arm_ctrl_rot_y = QtWidgets.QLineEdit()
        self.arm_ctrl_rot_y.setText("0")
        self.arm_ctrl_rot_y.setMaximumWidth(50)
        self.arm_ctrl_rot_z = QtWidgets.QLineEdit()
        self.arm_ctrl_rot_z.setText("-90")
        self.arm_ctrl_rot_z.setMaximumWidth(50)
        ctrl_rot_layout.addWidget(self.arm_ctrl_rot_x)
        ctrl_rot_layout.addWidget(self.arm_ctrl_rot_y)
        ctrl_rot_layout.addWidget(self.arm_ctrl_rot_z)
        ctrl_rot_layout.addStretch()
        rot_offsets_layout.addLayout(ctrl_rot_layout)
        
        # PV Rotation Offset
        pv_rot_layout = QtWidgets.QHBoxLayout()
        pv_rot_layout.addWidget(QtWidgets.QLabel("PV (X, Y, Z):"))
        self.arm_pv_rot_x = QtWidgets.QLineEdit()
        self.arm_pv_rot_x.setText("0")
        self.arm_pv_rot_x.setMaximumWidth(50)
        self.arm_pv_rot_y = QtWidgets.QLineEdit()
        self.arm_pv_rot_y.setText("0")
        self.arm_pv_rot_y.setMaximumWidth(50)
        self.arm_pv_rot_z = QtWidgets.QLineEdit()
        self.arm_pv_rot_z.setText("0")
        self.arm_pv_rot_z.setMaximumWidth(50)
        pv_rot_layout.addWidget(self.arm_pv_rot_x)
        pv_rot_layout.addWidget(self.arm_pv_rot_y)
        pv_rot_layout.addWidget(self.arm_pv_rot_z)
        pv_rot_layout.addStretch()
        rot_offsets_layout.addLayout(pv_rot_layout)
        
        arm_options_layout.addWidget(rot_offsets_group)
        
        # Connect to Spine
        connect_spine_layout = QtWidgets.QHBoxLayout()
        connect_spine_layout.addWidget(QtWidgets.QLabel("Connect to Spine:"))
        self.arm_connect_spine = QtWidgets.QCheckBox()
        self.arm_connect_spine.setChecked(True)
        connect_spine_layout.addWidget(self.arm_connect_spine)
        connect_spine_layout.addStretch()
        arm_options_layout.addLayout(connect_spine_layout)
        
        limb_layout.addLayout(arm_options_layout)
        
        self.btn_build_arm = QtWidgets.QPushButton("Build Arm")
        self.btn_build_arm.setStyleSheet("background-color: #4a7a5f; color: white;")
        self.btn_build_arm.clicked.connect(self._build_arm)
        limb_layout.addWidget(self.btn_build_arm)
        
        # Separator between Arm and Hand
        arm_hand_separator = QtWidgets.QFrame()
        arm_hand_separator.setFrameShape(QtWidgets.QFrame.HLine)
        arm_hand_separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        limb_layout.addWidget(arm_hand_separator)
        
        # Spacing
        limb_layout.addSpacing(10)
        
        # ===== HAND SECTION =====
        # Hand Input
        hand_row, self.hand_input = self._create_input_row("Hand Jnts:")
        limb_layout.addLayout(hand_row)
        
        # Hand Options
        hand_options_layout = QtWidgets.QVBoxLayout()
        
        # Curl Axis and Spread Axis (horizontal)
        hand_axes_layout = QtWidgets.QHBoxLayout()
        
        hand_axes_layout.addWidget(QtWidgets.QLabel("Curl Axis:"))
        self.hand_curl_axis = QtWidgets.QComboBox()
        self.hand_curl_axis.addItems(["X", "Y", "Z"])
        self.hand_curl_axis.setCurrentText("Z")
        self.hand_curl_axis.setMaximumWidth(60)
        hand_axes_layout.addWidget(self.hand_curl_axis)
        
        hand_axes_layout.addWidget(QtWidgets.QLabel("Spread Axis:"))
        self.hand_spread_axis = QtWidgets.QComboBox()
        self.hand_spread_axis.addItems(["X", "Y", "Z"])
        self.hand_spread_axis.setCurrentText("Y")
        self.hand_spread_axis.setMaximumWidth(60)
        hand_axes_layout.addWidget(self.hand_spread_axis)
        
        hand_axes_layout.addStretch()
        hand_options_layout.addLayout(hand_axes_layout)
        
        # Connect to Wrist
        connect_wrist_layout = QtWidgets.QHBoxLayout()
        connect_wrist_layout.addWidget(QtWidgets.QLabel("Connect to Wrist:"))
        self.hand_connect_wrist = QtWidgets.QCheckBox()
        self.hand_connect_wrist.setChecked(True)
        connect_wrist_layout.addWidget(self.hand_connect_wrist)
        connect_wrist_layout.addStretch()
        hand_options_layout.addLayout(connect_wrist_layout)
        
        limb_layout.addLayout(hand_options_layout)
        
        self.btn_build_hand = QtWidgets.QPushButton("Build Hand")
        self.btn_build_hand.setStyleSheet("background-color: #6a7f9f; color: white;")
        self.btn_build_hand.clicked.connect(self._build_hand)
        limb_layout.addWidget(self.btn_build_hand)
        
        # Separator between Hand and Leg
        hand_leg_separator = QtWidgets.QFrame()
        hand_leg_separator.setFrameShape(QtWidgets.QFrame.HLine)
        hand_leg_separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        limb_layout.addWidget(hand_leg_separator)
        
        # Spacing
        limb_layout.addSpacing(10)
        
        # Leg Input

        # Leg Side Selector
        leg_side_layout = QtWidgets.QHBoxLayout()
        leg_side_layout.addWidget(QtWidgets.QLabel("Leg Side:"))
        self.leg_side_combo = QtWidgets.QComboBox()
        self.leg_side_combo.addItems(["L", "R"])
        self.leg_side_combo.setMaximumWidth(60)
        leg_side_layout.addWidget(self.leg_side_combo)
        leg_side_layout.addStretch()
        limb_layout.addLayout(leg_side_layout)

        leg_row, self.leg_input = self._create_input_row("Leg Jnts:")
        limb_layout.addLayout(leg_row)

        # Leg Options
        leg_options_layout = QtWidgets.QVBoxLayout()

        # Stretch Axis, PV Multiplier, and Number of Follicles (horizontal)
        leg_settings_layout = QtWidgets.QHBoxLayout()

        leg_settings_layout.addWidget(QtWidgets.QLabel("Stretch Axis:"))
        self.leg_stretch_axis = QtWidgets.QComboBox()
        self.leg_stretch_axis.addItems(["X", "Y", "Z"])
        self.leg_stretch_axis.setCurrentText("Y")
        self.leg_stretch_axis.setMaximumWidth(60)
        leg_settings_layout.addWidget(self.leg_stretch_axis)

        leg_settings_layout.addWidget(QtWidgets.QLabel("PV Mult:"))
        self.leg_pv_mult = QtWidgets.QLineEdit()
        self.leg_pv_mult.setText("0.6")
        self.leg_pv_mult.setMaximumWidth(50)
        leg_settings_layout.addWidget(self.leg_pv_mult)

        leg_settings_layout.addWidget(QtWidgets.QLabel("Follicles:"))
        self.leg_num_fol = QtWidgets.QLineEdit()
        self.leg_num_fol.setText("12")
        self.leg_num_fol.setMaximumWidth(50)
        leg_settings_layout.addWidget(self.leg_num_fol)

        leg_settings_layout.addStretch()
        leg_options_layout.addLayout(leg_settings_layout)
        
        # Rotation Offsets Group
        leg_rot_offsets_group = QtWidgets.QGroupBox("Rotation Offsets")
        leg_rot_offsets_layout = QtWidgets.QVBoxLayout(leg_rot_offsets_group)
        
        # Control Rotation Offset
        leg_ctrl_rot_layout = QtWidgets.QHBoxLayout()
        leg_ctrl_rot_layout.addWidget(QtWidgets.QLabel("Ctrl (X, Y, Z):"))
        self.leg_ctrl_rot_x = QtWidgets.QLineEdit()
        self.leg_ctrl_rot_x.setText("180")
        self.leg_ctrl_rot_x.setMaximumWidth(50)
        self.leg_ctrl_rot_y = QtWidgets.QLineEdit()
        self.leg_ctrl_rot_y.setText("0")
        self.leg_ctrl_rot_y.setMaximumWidth(50)
        self.leg_ctrl_rot_z = QtWidgets.QLineEdit()
        self.leg_ctrl_rot_z.setText("0")
        self.leg_ctrl_rot_z.setMaximumWidth(50)
        leg_ctrl_rot_layout.addWidget(self.leg_ctrl_rot_x)
        leg_ctrl_rot_layout.addWidget(self.leg_ctrl_rot_y)
        leg_ctrl_rot_layout.addWidget(self.leg_ctrl_rot_z)
        leg_ctrl_rot_layout.addStretch()
        leg_rot_offsets_layout.addLayout(leg_ctrl_rot_layout)
        
        # PV Rotation Offset
        leg_pv_rot_layout = QtWidgets.QHBoxLayout()
        leg_pv_rot_layout.addWidget(QtWidgets.QLabel("PV (X, Y, Z):"))
        self.leg_pv_rot_x = QtWidgets.QLineEdit()
        self.leg_pv_rot_x.setText("0")
        self.leg_pv_rot_x.setMaximumWidth(50)
        self.leg_pv_rot_y = QtWidgets.QLineEdit()
        self.leg_pv_rot_y.setText("0")
        self.leg_pv_rot_y.setMaximumWidth(50)
        self.leg_pv_rot_z = QtWidgets.QLineEdit()
        self.leg_pv_rot_z.setText("0")
        self.leg_pv_rot_z.setMaximumWidth(50)
        leg_pv_rot_layout.addWidget(self.leg_pv_rot_x)
        leg_pv_rot_layout.addWidget(self.leg_pv_rot_y)
        leg_pv_rot_layout.addWidget(self.leg_pv_rot_z)
        leg_pv_rot_layout.addStretch()
        leg_rot_offsets_layout.addLayout(leg_pv_rot_layout)
        
        # Ankle Rotation Offset
        leg_ankle_rot_layout = QtWidgets.QHBoxLayout()
        leg_ankle_rot_layout.addWidget(QtWidgets.QLabel("Ankle (X, Y, Z):"))
        self.leg_ankle_rot_x = QtWidgets.QLineEdit()
        self.leg_ankle_rot_x.setText("180")
        self.leg_ankle_rot_x.setMaximumWidth(50)
        self.leg_ankle_rot_y = QtWidgets.QLineEdit()
        self.leg_ankle_rot_y.setText("0")
        self.leg_ankle_rot_y.setMaximumWidth(50)
        self.leg_ankle_rot_z = QtWidgets.QLineEdit()
        self.leg_ankle_rot_z.setText("0")
        self.leg_ankle_rot_z.setMaximumWidth(50)
        leg_ankle_rot_layout.addWidget(self.leg_ankle_rot_x)
        leg_ankle_rot_layout.addWidget(self.leg_ankle_rot_y)
        leg_ankle_rot_layout.addWidget(self.leg_ankle_rot_z)
        leg_ankle_rot_layout.addStretch()
        leg_rot_offsets_layout.addLayout(leg_ankle_rot_layout)
        
        leg_options_layout.addWidget(leg_rot_offsets_group)
        
        # Connect to Hip
        connect_hip_layout = QtWidgets.QHBoxLayout()
        connect_hip_layout.addWidget(QtWidgets.QLabel("Connect to Hip:"))
        self.leg_connect_hip = QtWidgets.QCheckBox()
        self.leg_connect_hip.setChecked(True)
        connect_hip_layout.addWidget(self.leg_connect_hip)
        connect_hip_layout.addStretch()
        leg_options_layout.addLayout(connect_hip_layout)
        
        limb_layout.addLayout(leg_options_layout)
        
        self.btn_build_leg = QtWidgets.QPushButton("Build Leg")
        self.btn_build_leg.setStyleSheet("background-color: #8a6a4f; color: white;")
        self.btn_build_leg.clicked.connect(self._build_leg)
        limb_layout.addWidget(self.btn_build_leg)
        
        # Separator between Leg and Foot
        leg_foot_separator = QtWidgets.QFrame()
        leg_foot_separator.setFrameShape(QtWidgets.QFrame.HLine)
        leg_foot_separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        limb_layout.addWidget(leg_foot_separator)
        
        # Spacing
        limb_layout.addSpacing(10)
        
        # ===== FOOT SECTION =====
        foot_info = QtWidgets.QLabel(
            "<b>Foot Rig:</b><br>"
            "• Uses locators named <b>loc_heel</b>, <b>loc_toetip</b>, <b>loc_outer</b>, <b>loc_inner</b> in the scene.<br>"
            "• Locator names must match exactly.<br>"
            "• Ankle joints are auto-loaded from Leg build."
        )
        foot_info.setWordWrap(True)
        foot_info.setStyleSheet("color: #999; font-style: italic;")
        limb_layout.addWidget(foot_info)

        self.btn_build_foot = QtWidgets.QPushButton("Build Foot")
        self.btn_build_foot.setStyleSheet("background-color: #7a5a6f; color: white;")
        self.btn_build_foot.clicked.connect(self._build_foot)
        limb_layout.addWidget(self.btn_build_foot)
        
        layout.addWidget(limb_group)
        layout.addStretch()
        
        # Set content widget for scroll area
        scroll_area.setWidget(content_widget)
        tab_layout.addWidget(scroll_area)
        self.tabs.addTab(tab, "2. Body Build")

    # =====================================================================
    # Tab 3: Post-Processing
    # =====================================================================
    def _setup_post_tab(self):
        tab = QtWidgets.QWidget()
        tab_layout = QtWidgets.QVBoxLayout(tab)

        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        content_widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(content_widget)

        post_group = QtWidgets.QGroupBox("Finalization")
        post_layout = QtWidgets.QVBoxLayout(post_group)

        # Mirror Arm Button
        mirror_arm_layout = QtWidgets.QHBoxLayout()
        mirror_arm_layout.addWidget(QtWidgets.QLabel("Mirror Arm (L → R):"))
        self.mirror_arm_side = QtWidgets.QComboBox()
        self.mirror_arm_side.addItems(["L", "R"])
        mirror_arm_layout.addWidget(self.mirror_arm_side)
        self.btn_mirror_arm = QtWidgets.QPushButton("Mirror Arm")
        self.btn_mirror_arm.clicked.connect(self._mirror_arm)
        mirror_arm_layout.addWidget(self.btn_mirror_arm)
        post_layout.addLayout(mirror_arm_layout)

        # Mirror Leg Button
        mirror_leg_layout = QtWidgets.QHBoxLayout()
        mirror_leg_layout.addWidget(QtWidgets.QLabel("Mirror Leg (L → R):"))
        self.mirror_leg_side = QtWidgets.QComboBox()
        self.mirror_leg_side.addItems(["L", "R"])
        mirror_leg_layout.addWidget(self.mirror_leg_side)
        self.btn_mirror_leg = QtWidgets.QPushButton("Mirror Leg")
        self.btn_mirror_leg.clicked.connect(self._mirror_leg)
        mirror_leg_layout.addWidget(self.btn_mirror_leg)
        post_layout.addLayout(mirror_leg_layout)

        # Separator
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.HLine)
        sep.setFrameShadow(QtWidgets.QFrame.Sunken)
        post_layout.addWidget(sep)

        # ---- Apply Parent Switches Button ----
        self.btn_space_switch = QtWidgets.QPushButton("Apply Parent Switches")
        self.btn_space_switch.setMinimumHeight(35)
        self.btn_space_switch.setStyleSheet("background-color: #5a6a8a; color: white; font-weight: bold;")
        self.btn_space_switch.clicked.connect(self._apply_space_switches)
        post_layout.addWidget(self.btn_space_switch)

        # ---- Refresh button to reload definitions from scene ----
        self.btn_refresh_spaces = QtWidgets.QPushButton("Refresh From Scene")
        self.btn_refresh_spaces.setToolTip("Re-scan meta nodes and rebuild the space list below.")
        self.btn_refresh_spaces.clicked.connect(self._refresh_space_definitions)
        post_layout.addWidget(self.btn_refresh_spaces)

        # ---- Advanced Settings (collapsible) ----
        self._space_advanced = CollapsibleSection("Advanced Parent Switch Settings")
        self._space_adv_layout = self._space_advanced.content_layout()

        # Container that holds the per-control rows (rebuilt on refresh)
        self._space_rows_widget = QtWidgets.QWidget()
        self._space_rows_layout = QtWidgets.QVBoxLayout(self._space_rows_widget)
        self._space_rows_layout.setContentsMargins(0, 0, 0, 0)
        self._space_rows_layout.setSpacing(4)
        self._space_adv_layout.addWidget(self._space_rows_widget)

        # Internal list that mirrors the UI rows
        # Each element: {"def": <space def dict>, "checkbox": QCheckBox, "parent_widgets": [...]}
        self._space_row_data = []

        post_layout.addWidget(self._space_advanced)
        layout.addWidget(post_group)
        layout.addStretch()

        scroll_area.setWidget(content_widget)
        tab_layout.addWidget(scroll_area)
        self.tabs.addTab(tab, "3. Post-Process")

    # -----------------------------------------------------------------
    # Advanced parent-switch helpers
    # -----------------------------------------------------------------
    def _refresh_space_definitions(self):
        """Re-scan the scene meta nodes and rebuild the advanced rows."""
        try:
            manager = SpaceManager()
            defs = manager.get_space_definitions()
        except Exception as e:
            cmds.warning(f"Failed to read space definitions: {e}")
            return

        # Clear old rows
        self._space_row_data.clear()
        while self._space_rows_layout.count():
            item = self._space_rows_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not defs:
            lbl = QtWidgets.QLabel("No space definitions found. Build rig parts first.")
            lbl.setStyleSheet("color: #999; font-style: italic;")
            self._space_rows_layout.addWidget(lbl)
            return

        for d in defs:
            row_widget = self._create_space_row(d)
            self._space_rows_layout.addWidget(row_widget)

    def _create_space_row(self, space_def):
        """Build one collapsible row for a single space definition.

        Layout:
            [✓] Arm L IK Wrist  (target: arm_L_ik_ctrl)   [parent]
              ▼ Parent Spaces
                 [✓] Global    (global_ctrl)               [✕]
                 [✓] COG       (spine_C_cog_ctrl)           [✕]
                 ...
                 [ Add Parent ]   (pick from scene)
        """
        frame = QtWidgets.QGroupBox()
        frame.setStyleSheet("QGroupBox { border: 1px solid #555; margin-top: 2px; padding: 6px; }")
        frame_layout = QtWidgets.QVBoxLayout(frame)
        frame_layout.setContentsMargins(6, 6, 6, 6)
        frame_layout.setSpacing(4)

        # --- Header row: checkbox + label ---
        header = QtWidgets.QHBoxLayout()
        cb = QtWidgets.QCheckBox(space_def["label"])
        cb.setChecked(True)
        cb.setStyleSheet("font-weight: bold;")
        header.addWidget(cb)
        header.addStretch()
        target_lbl = QtWidgets.QLabel(f"<i>{space_def['target']}</i>")
        target_lbl.setStyleSheet("color: #8ab4f8;")
        header.addWidget(target_lbl)
        type_lbl = QtWidgets.QLabel(f"[{space_def['constrain_type']}]")
        type_lbl.setStyleSheet("color: #999;")
        header.addWidget(type_lbl)
        frame_layout.addLayout(header)

        # --- Parent list (inside a collapsible-like container) ---
        parent_container = QtWidgets.QWidget()
        parent_v_layout = QtWidgets.QVBoxLayout(parent_container)
        parent_v_layout.setContentsMargins(20, 0, 0, 0)
        parent_v_layout.setSpacing(2)

        parent_widgets = []  # list of {"name": str, "node": str, "checkbox": QCheckBox, "row": QWidget}

        for name, node in zip(space_def["enum_list"], space_def["parents"]):
            pw = self._create_parent_entry(name, node, parent_v_layout, parent_widgets)
            parent_widgets.append(pw)
            parent_v_layout.addWidget(pw["row"])

        # Add-parent button
        btn_add = QtWidgets.QPushButton("+ Add Parent From Selection")
        btn_add.setMaximumWidth(220)
        btn_add.setStyleSheet("color: #8ade8a;")
        btn_add.clicked.connect(lambda: self._add_parent_from_selection(
            parent_v_layout, parent_widgets, btn_add))
        parent_v_layout.addWidget(btn_add)

        frame_layout.addWidget(parent_container)

        # Store row data for apply
        row_data = {
            "def": space_def,
            "checkbox": cb,
            "parent_widgets": parent_widgets,
        }
        self._space_row_data.append(row_data)

        return frame

    def _create_parent_entry(self, name, node, container_layout, parent_widgets_list):
        """Create a single parent-space entry row with checkbox and delete button."""
        row = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)

        pcb = QtWidgets.QCheckBox(f"{name}")
        pcb.setChecked(True)
        h.addWidget(pcb)

        node_lbl = QtWidgets.QLabel(f"<span style='color:#aaa;'>({node})</span>")
        h.addWidget(node_lbl)
        h.addStretch()

        btn_del = QtWidgets.QPushButton("✕")
        btn_del.setMaximumWidth(24)
        btn_del.setStyleSheet("color: #ff6666; border: none; font-weight: bold;")
        btn_del.setToolTip("Remove this parent space")
        pw_entry = {"name": name, "node": node, "checkbox": pcb, "row": row}
        btn_del.clicked.connect(lambda: self._remove_parent_entry(pw_entry, parent_widgets_list))
        h.addWidget(btn_del)

        return pw_entry

    def _remove_parent_entry(self, pw_entry, parent_widgets_list):
        """Delete a parent-space entry from its list and UI."""
        if pw_entry in parent_widgets_list:
            parent_widgets_list.remove(pw_entry)
        pw_entry["row"].deleteLater()

    def _add_parent_from_selection(self, container_layout, parent_widgets_list, add_btn):
        """Add a new parent space from the current Maya selection."""
        sel = cmds.ls(selection=True, flatten=True)
        if not sel:
            cmds.warning("Select a Maya control/transform to add as a parent space.")
            return
        node = sel[0]
        # Derive a short display name from the node
        short = node.replace("_ctrl", "").replace("_", " ").title()

        # Prompt for a custom enum label
        result = QtWidgets.QInputDialog.getText(
            self, "Parent Space Name",
            f"Enter the enum label for '{node}':",
            text=short
        )
        if not result[1] or not result[0].strip():
            return
        label = result[0].strip()

        # Check duplicate
        for pw in parent_widgets_list:
            if pw["node"] == node:
                cmds.warning(f"'{node}' is already in the parent list.")
                return

        pw = self._create_parent_entry(label, node, container_layout, parent_widgets_list)
        parent_widgets_list.append(pw)
        # Insert before the add button
        idx = container_layout.indexOf(add_btn)
        container_layout.insertWidget(idx, pw["row"])
    def _mirror_arm(self):
        side = self.mirror_arm_side.currentText()
        meta_node = f"arm_{side}_meta"
        cmds.undoInfo(openChunk=True)
        try:
            from core.mirror_manager import MirrorManager
            MirrorManager(meta_node).process_mirror()
        except Exception as e:
            cmds.error(f"Failed to mirror Arm: {e}")
        finally:
            cmds.undoInfo(closeChunk=True)

    def _mirror_leg(self):
        side = self.mirror_leg_side.currentText()
        meta_node = f"leg_{side}_meta"
        cmds.undoInfo(openChunk=True)
        try:
            from core.mirror_manager import MirrorManager
            MirrorManager(meta_node).process_mirror()
        except Exception as e:
            cmds.error(f"Failed to mirror Leg: {e}")
        finally:
            cmds.undoInfo(closeChunk=True)

    # =====================================================================
    # 실행 로직 (Slots)
    # =====================================================================
    def _import_skeleton_template(self):
        """Import the base skeleton template from lib folder."""
        print("\n--- Import Skeleton Template Triggered ---")
        
        # Get the directory where this module is located
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up one level to auto_rig_system, then into lib
        template_path = os.path.join(current_dir, "..", "lib", "skeleton_template.ma")
        template_path = os.path.normpath(template_path)
        
        if not os.path.exists(template_path):
            cmds.warning(f"Skeleton template not found: {template_path}")
            return
        
        try:
            # Import the template file
            imported_nodes = cmds.file(
                template_path,
                i=True,  # Import
                type="mayaAscii",
                ignoreVersion=True,
                renameAll=False,
                mergeNamespacesOnClash=False,
                options="v=0;",
                preserveReferences=True,
                returnNewNodes=True
            )
            
            cmds.inViewMessage(
                amg="<span style='color:#00ff00;'>Skeleton template imported successfully!</span>",
                pos='midCenter',
                fade=True
            )
            print(f"Imported {len(imported_nodes)} nodes from: {template_path}")
            
        except Exception as e:
            cmds.error(f"Failed to import skeleton template: {e}")

    def _build_clean_skeleton(self):
        """Build a clean skeleton from the selected template root joint."""
        print("\n--- Clean Skeleton Build Triggered ---")
        cmds.undoInfo(openChunk=True)
        try:
            # Get selected joint
            selection = cmds.ls(selection=True, type="joint")
            if not selection:
                cmds.warning("Please select the root joint of your template skeleton.")
                return
            template_root = selection[0]
            if build_clean_skeleton is None:
                cmds.error("build_clean_skeleton module failed to load. Check script editor for import errors.")
                return
            # Get parameters from UI
            prefix = self.joint_prefix_input.text().strip()
            if not prefix:
                prefix = "cln_"
            bend_axis = self.bend_axis_combo.currentText()
            result = build_clean_skeleton(template_root, prefix=prefix, bend_axis=bend_axis)
            cmds.inViewMessage(
                amg=f"<span style='color:#00ff00;'>Clean skeleton created: {result}</span>",
                pos='midCenter',
                fade=True
            )
        except Exception as e:
            cmds.error(f"Failed to build clean skeleton: {e}")
        finally:
            cmds.undoInfo(closeChunk=True)

    def _build_global(self):
        print("\\n--- Global Build Triggered ---")
        cmds.undoInfo(openChunk=True)
        try:
            builder = GlobalBuilder()
            builder.build()
        except Exception as e:
            cmds.error(f"Failed to build Global control: {e}")
        finally:
            cmds.undoInfo(closeChunk=True)

    def _build_spine(self):
        print("\n--- Spine Build Triggered ---")
        cmds.undoInfo(openChunk=True)
        try:
            jnts_str = self.spine_input.toPlainText()
            if not jnts_str:
                cmds.warning("Please load Spine joints first.")
                return
            spine_jnts = [j.strip() for j in jnts_str.splitlines() if j.strip()]
            builder = SpineBuilder()
            builder.build(spine_jnts)
        except Exception as e:
            cmds.error(f"Failed to build Spine: {e}")
        finally:
            cmds.undoInfo(closeChunk=True)

    def _build_neck(self):
        print("\n--- Neck Build Triggered ---")
        cmds.undoInfo(openChunk=True)
        try:
            neck_jnts_str = self.neck_jnts_input.toPlainText()
            head_jnt_str = self.head_jnt_input.toPlainText()
            if not neck_jnts_str or not head_jnt_str:
                cmds.warning("Please load Neck joints and Head joint first.")
                return
            neck_jnts = [j.strip() for j in neck_jnts_str.splitlines() if j.strip()]
            head_jnt = head_jnt_str.strip()
            builder = NeckBuilder()
            builder.build(neck_jnts, head_jnt)
        except Exception as e:
            cmds.error(f"Failed to build Neck: {e}")
        finally:
            cmds.undoInfo(closeChunk=True)

    def _build_arm(self):
        side = self.side_combo.currentText()
        print(f"\n--- Arm ({side}) Build Triggered ---")
        cmds.undoInfo(openChunk=True)
        try:
            jnts_str = self.arm_input.toPlainText()
            if not jnts_str:
                cmds.warning("Please load Arm joints first.")
                return
            arm_jnts = [j.strip() for j in jnts_str.splitlines() if j.strip()]
            # Gather parameters
            stretch_axis = self.arm_stretch_axis.currentText()
            try:
                pv_multiplier = float(self.arm_pv_mult.text())
                number_of_fol = int(self.arm_num_fol.text())
            except ValueError:
                cmds.warning("PV Multiplier and Follicles must be valid numbers.")
                return
            try:
                ctrl_rot_x = float(self.arm_ctrl_rot_x.text())
                ctrl_rot_y = float(self.arm_ctrl_rot_y.text())
                ctrl_rot_z = float(self.arm_ctrl_rot_z.text())
            except ValueError:
                cmds.warning("Control Rotation Offset values must be valid numbers.")
                return
            try:
                pv_rot_x = float(self.arm_pv_rot_x.text())
                pv_rot_y = float(self.arm_pv_rot_y.text())
                pv_rot_z = float(self.arm_pv_rot_z.text())
            except ValueError:
                cmds.warning("PV Rotation Offset values must be valid numbers.")
                return
            ctrl_rot_offset = (ctrl_rot_x, ctrl_rot_y, ctrl_rot_z)
            pv_rot_offset = (pv_rot_x, pv_rot_y, pv_rot_z)
            wrist_rot_offset = ctrl_rot_offset  # Same as control rotation offset
            connect_to_spine = self.arm_connect_spine.isChecked()
            builder = ArmBuilder(side=side)
            builder.build(arm_jnts, pv_multiplier=pv_multiplier, number_of_fol=number_of_fol, 
                         stretch_axis=stretch_axis, ctrl_rot_offset=ctrl_rot_offset, 
                         pv_rot_offset=pv_rot_offset, wrist_rot_offset=wrist_rot_offset,
                         connect_to_spine=connect_to_spine)
        except Exception as e:
            cmds.error(f"Failed to build Arm: {e}")
        finally:
            cmds.undoInfo(closeChunk=True)

    def _build_hand(self):
        side = self.side_combo.currentText()
        print(f"\n--- Hand ({side}) Build Triggered ---")
        cmds.undoInfo(openChunk=True)
        try:
            jnts_str = self.hand_input.toPlainText()
            if not jnts_str:
                cmds.warning("Please load Hand joints first.")
                return
            hand_jnts = [j.strip() for j in jnts_str.splitlines() if j.strip()]
            # Gather parameters
            curl_axis = self.hand_curl_axis.currentText()
            spread_axis = self.hand_spread_axis.currentText()
            connect_to_wrist = self.hand_connect_wrist.isChecked()
            builder = HandBuilder(side=side)
            builder.build(hand_jnts, curl_axis=curl_axis, spread_axis=spread_axis, 
                         connect_to_wrist=connect_to_wrist)
        except Exception as e:
            cmds.error(f"Failed to build Hand: {e}")
        finally:
            cmds.undoInfo(closeChunk=True)

    def _build_leg(self):
        side = self.leg_side_combo.currentText()
        print(f"\n--- Leg ({side}) Build Triggered ---")
        cmds.undoInfo(openChunk=True)
        try:
            jnts_str = self.leg_input.toPlainText()
            if not jnts_str:
                cmds.warning("Please load Leg joints first.")
                return
            leg_jnts = [j.strip() for j in jnts_str.splitlines() if j.strip()]
            # Gather parameters
            stretch_axis = self.leg_stretch_axis.currentText()
            try:
                pv_multiplier = float(self.leg_pv_mult.text())
                number_of_fol = int(self.leg_num_fol.text())
            except ValueError:
                cmds.warning("PV Multiplier and Follicles must be valid numbers.")
                return
            try:
                ctrl_rot_x = float(self.leg_ctrl_rot_x.text())
                ctrl_rot_y = float(self.leg_ctrl_rot_y.text())
                ctrl_rot_z = float(self.leg_ctrl_rot_z.text())
            except ValueError:
                cmds.warning("Control Rotation Offset values must be valid numbers.")
                return
            try:
                pv_rot_x = float(self.leg_pv_rot_x.text())
                pv_rot_y = float(self.leg_pv_rot_y.text())
                pv_rot_z = float(self.leg_pv_rot_z.text())
            except ValueError:
                cmds.warning("PV Rotation Offset values must be valid numbers.")
                return
            try:
                ankle_rot_x = float(self.leg_ankle_rot_x.text())
                ankle_rot_y = float(self.leg_ankle_rot_y.text())
                ankle_rot_z = float(self.leg_ankle_rot_z.text())
            except ValueError:
                cmds.warning("Ankle Rotation Offset values must be valid numbers.")
                return
            ctrl_rot_offset = (ctrl_rot_x, ctrl_rot_y, ctrl_rot_z)
            pv_rot_offset = (pv_rot_x, pv_rot_y, pv_rot_z)
            ankle_rot_offset = (ankle_rot_x, ankle_rot_y, ankle_rot_z)
            connect_to_hip = self.leg_connect_hip.isChecked()
            builder = LegBuilder(side=side)
            builder.build(leg_jnts, pv_multiplier=pv_multiplier, number_of_fol=number_of_fol,
                         stretch_axis=stretch_axis, ctrl_rot_offset=ctrl_rot_offset,
                         pv_rot_offset=pv_rot_offset, ankle_rot_offset=ankle_rot_offset,
                         connect_to_hip=connect_to_hip)
        except Exception as e:
            cmds.error(f"Failed to build Leg: {e}")
        finally:
            cmds.undoInfo(closeChunk=True)

    def _build_foot(self):
        side = self.side_combo.currentText()
        print(f"\n--- Foot ({side}) Build Triggered ---")
        cmds.undoInfo(openChunk=True)
        try:
            # Auto-detect locators by name
            locator_names = ["loc_heel", "loc_toetip", "loc_outer", "loc_inner"]
            found_locators = [name for name in locator_names if cmds.objExists(name)]
            if len(found_locators) != 4:
                cmds.warning("Foot rig requires 4 locators named: loc_heel, loc_toetip, loc_outer, loc_inner.")
                return
            loc_heel, loc_toetip, loc_outer, loc_inner = locator_names
            # Ankle joints from leg meta data
            from core.data_manager import RigAssetManager
            dam = RigAssetManager(f"leg_{side}_meta")
            settings, objects = dam.get_data()
            if not settings or 'drv_jnts' not in settings or 'ik_jnts' not in settings or 'fk_jnts' not in settings:
                cmds.warning("Leg must be built first. Ankle joint data not found.")
                return
            ankle_drv_jnt = settings['drv_jnts'][-1]
            ankle_ik_jnt = settings['ik_jnts'][-1]
            ankle_fk_jnt = settings['fk_jnts'][-1]
            builder = FootBuilder(side=side)
            builder.build(ankle_drv_jnt, ankle_fk_jnt, ankle_ik_jnt,
                         loc_heel, loc_toetip, loc_outer, loc_inner)
        except Exception as e:
            cmds.error(f"Failed to build Foot: {e}")
        finally:
            cmds.undoInfo(closeChunk=True)

    def _apply_space_switches(self):
        print("\n--- Parent Switch Triggered ---")
        cmds.undoInfo(openChunk=True)
        try:
            manager = SpaceManager()

            # If user has NOT opened advanced settings (no rows), apply everything.
            if not self._space_row_data:
                manager.apply_all_spaces()
                return

            # Otherwise, build a filtered definition list from the UI state.
            filtered_defs = []
            for row in self._space_row_data:
                if not row["checkbox"].isChecked():
                    continue
                # Collect only checked parents
                enum_list = []
                parents = []
                for pw in row["parent_widgets"]:
                    if pw["checkbox"].isChecked():
                        enum_list.append(pw["name"])
                        parents.append(pw["node"])
                if len(parents) < 2:
                    cmds.warning(
                        f"Skipping '{row['def']['label']}': "
                        f"need at least 2 parent spaces (got {len(parents)})."
                    )
                    continue
                filtered_defs.append({
                    "label": row["def"]["label"],
                    "target": row["def"]["target"],
                    "enum_list": enum_list,
                    "parents": parents,
                    "constrain_type": row["def"]["constrain_type"],
                    "attr_name": row["def"]["attr_name"],
                })
            if not filtered_defs:
                cmds.warning("No parent switches selected to apply.")
                return
            manager.apply_spaces(filtered_defs)
        except Exception as e:
            cmds.error(f"Failed to apply Parent Switches: {e}")
        finally:
            cmds.undoInfo(closeChunk=True)

    # =====================================================================
    # Face Rig 탭: Jaw Rig
    # =====================================================================
    def _face_rig_set_joint(self, field, joint_name):
        """선택한 vertex들의 평균 위치에 조인트를 생성(또는 이동)하고 필드에 표시."""
        sel = cmds.ls(selection=True, flatten=True)
        if not sel:
            cmds.warning("Please select vertex/vertices.")
            return

        flat = cmds.xform(sel, query=True, worldSpace=True, translation=True)
        count = len(flat) // 3
        pos = [sum(flat[i::3]) / count for i in range(3)]

        if cmds.objExists(joint_name):
            cmds.xform(joint_name, worldSpace=True, translation=pos)
            cmds.warning(f"'{joint_name}' already exists — moved to new position.")
        else:
            cmds.select(clear=True)
            cmds.joint(name=joint_name, position=pos)
            cmds.setAttr(f'{joint_name}.overrideEnabled', 1)
            cmds.setAttr(f'{joint_name}.overrideColor', 13)
            cmds.select(clear=True)

        field.setText(joint_name)

    def _build_jaw(self):
        print("\n--- Jaw Build Triggered ---")
        if FaceRig is None:
            cmds.error("FaceRig module failed to import. Check the script editor for details.")
            return
        cmds.undoInfo(openChunk=True)
        try:
            input_joints = {part: field.text() for part, field in self.jaw_fields.items()}
            FaceRig(input_joints).build()
        except Exception as e:
            cmds.error(f"Failed to build Jaw: {e}")
        finally:
            cmds.undoInfo(closeChunk=True)

def show_ui():
    if cmds.workspaceControl('AutoRigUIWorkspaceControl', exists=True):
        cmds.deleteUI('AutoRigUIWorkspaceControl', control=True)
        
    global auto_rig_window
    if 'auto_rig_window' in globals():
        try:
            auto_rig_window.close()
            auto_rig_window.deleteLater()
        except:
            pass
        
    auto_rig_window = AutoRigUI()
    auto_rig_window.show()