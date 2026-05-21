# Biped Auto Rig System for Autodesk Maya

A modular, production-ready auto-rigging tool for bipedal characters built with Python and Maya's API.

![Maya](https://img.shields.io/badge/Autodesk%20Maya-2024%2B-blue) ![Python](https://img.shields.io/badge/Python-3.10-green)

---

## Features

- **One-click full body rig** — builds a complete biped rig from a template skeleton
- **Modular architecture** — each body part (arm, leg, spine, neck, hand, foot) is an independent, reusable module
- **Spline IK spine** — advanced ribbon/spline-based spine with FK overlay controls
- **IK/FK switching** — seamless IK/FK blending on arms and legs with space switching
- **Space switching** — dynamic parent switching for wrist, foot, and head controls
- **Mirror support** — left/right symmetry via `MirrorManager`
- **PySide2 UI** — collapsible, dockable Maya panel with per-module build controls
- **Data-driven** — rig metadata stored and retrieved via `RigAssetManager` for post-build operations

## Tech Stack

| Area | Tools |
|---|---|
| Language | Python 3.10 |
| DCC | Autodesk Maya 2022+ |
| Maya API | `maya.cmds`, `maya.api.OpenMaya` |
| UI | PySide2 (Qt5) + `MayaQWidgetBaseMixin` |

## Project Structure

```
auto_rig_system/
├── core/               # Shared utilities and base classes
│   ├── base_builder.py     # Abstract base for all rig modules
│   ├── spline_builder.py   # Spline IK base (used by spine)
│   ├── joint_template.py   # Clean skeleton generation from template
│   ├── space_manager.py    # Cross-module space switching setup
│   ├── mirror_manager.py   # L/R mirror logic
│   ├── data_manager.py     # Rig metadata read/write
│   ├── parent_switch.py    # Parent constraint switching
│   ├── curve_utils.py      # Control curve shape utilities
│   ├── limb_builder.py     # Shared IK/FK limb logic
│   └── rig_utils.py        # General Maya helper functions
├── modules/            # Body part rig modules
│   ├── global_ctrl.py      # World / root control
│   ├── spine.py
│   ├── neck.py
│   ├── arm.py
│   ├── hand.py
│   ├── leg.py
│   └── foot.py
├── ui/
│   └── main_window.py      # PySide2 Maya dockable UI
└── lib/
    └── skeleton_template.ma  # Reference template skeleton
```

## How to Use

1. Open `lib/skeleton_template.ma` in Maya and position the joints to match your character.
2. Run the following in Maya's Script Editor:

```python
import importlib
import auto_rig_system.ui.main_window as mw
importlib.reload(mw)
mw.show()
```

3. In the UI, click **Build All** or build each module individually in order:
   `Global → Spine → Neck → Arm → Hand → Leg → Foot`
4. Run **Setup Spaces** to finalize space switching connections.

## About

Developed as part of a character rigging pipeline study at Emily Carr University of Art + Design.  
Focus: building a maintainable, artist-friendly rigging framework that mirrors production tool conventions.
