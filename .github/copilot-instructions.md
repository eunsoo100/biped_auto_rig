# Auto Rig System

This repository is a Python‑based rigging toolkit written for Autodesk Maya. All code **must run inside Maya's Python environment** (uses `maya.cmds` and `maya.api.OpenMaya`). Copilot agents should treat the Maya API as a given and not attempt to re‑implement it.

---

## Big picture

- `auto_rig_system` is a package with two high‑level packages:
  - `core/` contains reusable base classes (`BaseBuilder`, `LimbBaseBuilder`, `SplineBaseBuilder`),
    a lightweight JSON/message data manager (`RigAssetManager`), and a grab‑bag of
    `rig_utils` helpers (controller creation, mirror/scale math, SDK helpers, etc.).
  - `modules/` implements concrete rig parts (global, spine, arm, leg, foot, hand,
    neck, etc.).  Each module exports a `*Builder` class with a `build()` method that
    performs all Maya operations for that sub‑rig.

- **Workflow**: you usually run `GlobalBuilder().build()` first to create the master
  groups and meta node.  Subsequent modules call `get_dependency("global_C", "...")`
  to look up the global controller groups created by the global builder.  Many parts
  also depend on each other (e.g. `ArmBuilder` reads `spine_C.up_ik_ctrl`).

- Naming convention is central: every `Builder` has a `prefix` and `side` (`L`, `R`,
  or `C`) passed to `BaseBuilder`.  Use `self.get_name(suffix)` to produce names like
  `arm_L_ik_ctrl` or `spine_C_fk_01_ctrl`.  This helps ensure consistent search/replaces
  when mirroring.

- The data manager (`RigAssetManager`) keeps a network node per part (`<part>_meta`),
  stores a JSON `settings` string, and connects message attributes to Maya objects.  
  Builders call `self.register_outputs(...)` and optionally `self.save_settings(...)`.
  Other parts can call `get_dependency(part_name, key)` to query saved objects.

- Base classes provide helpers:
  - `LimbBaseBuilder` has IK/FK switching, pole‑vector control creation, stretch/squash
    routines and ribbon/twist setup used by arms/legs/hand.
  - `SplineBaseBuilder` adds spline IK helpers, advanced twist, dynamic control position,
    stretch‑and‑squash on curves, and other spine/neck‑specific logic.

- Utility patterns: `utils.create_ctrl`, `utils.create_offset_grp`,
  `utils.create_distance_measurement`, `utils.mirror_joints`, `utils.simple_sdk`, etc.
  Refer to `core/rig_utils.py` for a catalog of helpers.  Agents should look there
  before duplicating repeated node‑graph logic.

---

## Project‑specific conventions

- **Color scheme**: left = 6 (blue), right = 13 (red), centre = 17 (yellow).  `BaseBuilder`
  sets `self.color` and `self.sc_color` automatically.

- All controller creation goes through `utils.create_ctrl` (even inside builders).  This
  function handles offsets, color/thickness styling, and optional rotation/normal offsets.

- IK/FK switching is handled consistently: each limb builder calls
  `self.setup_ikfk_switch(...)` and `self.setup_ikfk_visibility(...)`; attributes are
  named `Ik_Fk_Switch` and are always float, 0–1.

- Mirroring is performed by `rig_utils.mirror_joints` or manually via naming search‑replace
  (`_L_` ↔ `_R_`).  Side‑dependent mirror values are stored in `self.mirror_val`.

- Builders rarely query the scene directly; they accept joint lists, locators, or
  other Maya nodes as parameters.  The caller (script/UI) is responsible for selecting
  the correct objects and passing them in.

- Runtime errors are usually emitted via `cmds.warning()`; constructors do not validate
  Maya availability.

- `global_C` is the only part with side "C" and must be built before any other part.

- Most builders add their output under three master groups created by `GlobalBuilder`:
  `CTRL`, `JOINT`, and `DO_NOT_TOUCH` (with names stored in the meta node).  Animators
  are expected to use the `CTRL` hierarchy; riggers can hide the `DO_NOT_TOUCH` group.

- Names of driver joints often contain `_drv_jnt` suffix.  IK duplicates use `_ik_jnt`,
  FK duplicates use `_fk_jnt`.


## Developer workflows

- **Launching**: open Maya, open the Script Editor, and add the repo root to `sys.path`:
  ```python
  import sys
  sys.path.append(r"C:/.../auto_rig_system")  # adjust path
  from modules.global_ctrl import GlobalBuilder
  from modules.arm import ArmBuilder
  …
  GlobalBuilder().build()
  ArmBuilder(side="L").build(selected_joints)
  ```
  There is no `setup.py`; the package is imported directly.

- The code is not intended to be run outside Maya; unit tests are manual.  If you
  need to run Python lints/formatters, ignore Maya imports or mock them.

- When editing a builder, look for similar code in other modules to copy patterns
  (e.g. `ArmBuilder` ⇆ `LegBuilder` for IK/FK, `SplineBaseBuilder` features for any
  spline controller).  Naming collisions are a common source of bugs; reuse `get_name`
  consistently.

- The `core/` utilities are the safest place to add new generic helpers.  Avoid
  polluting module namespaces; import with `from core import rig_utils as utils`.

- Data stored in meta nodes persists across building runs; to reset, delete the
  `<part>_meta` node in Maya or use `RigAssetManager` API.

- Builds are idempotent only to a degree; many methods rename joints in place rather
  than recreating them.  It is easiest to start with a clean scene or delete existing
  rig groups before rerunning.

---

## Integration & external dependencies

- Strict dependency on Maya 2022‑2024 Python API (`maya.cmds`, `maya.api.OpenMaya`).
  No other third‑party packages are used.

- The only external script is `joint_template.py` at the workspace root; it is a
  standalone helper used to generate a "clean" skeleton from a template joint tree.
  It is not part of the package and may be run from Maya directly with `import joint_template`.

- There are no build/test/CI scripts in the repo; riggers generally iterate inside
  Maya and save `ma` or `mb` files.

---

## Tips for AI agents

1. **Read `core/base_builder.py` first.** It defines the naming, color and metadata
   conventions used everywhere.
2. Use `grep` on `get_name(` or `self.register_outputs` to find similar usage patterns.
3. When answering questions about rig behavior, mimic existing naming such as
   `shoulder_drv_jnt` → `shoulder_ik_ctrl`.  Avoid inventing new suffixes.
4. For modifications to a module, check the sibling files in `modules/` for a
   comparable feature (e.g. adding pole‑vector offset to `ArmBuilder` after it was
   added to `LegBuilder`).
5. Unknown utilities usually live in `core/rig_utils.py`; search there before coding
   new node‑graph logic.
6. The UI is currently empty ‒ there is no high‑level GUI code to follow.  Any
   interface can simply import and call the builders as shown above.
7. When referring to Maya objects, always treat names as strings and use
   `cmds.objExists()` before operating.
8. For any new builder, remember to call `self.save_settings(...)` if you need to
   persist parameters (other parts might later read them via `get_dependency`).

---

Let me know if any part of the system feels unclear or you need additional examples.