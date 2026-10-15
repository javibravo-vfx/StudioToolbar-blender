# -*- coding: utf-8 -*-
"""
Pipeline Setup for Studio Toolbar in Blender — the same settings as the Setup dialog in
Max and Houdini, written to the same files:
    ~/.studio-toolbar/pipeline_config.ini      (keys this dialog doesn't know are kept)
    ~/.studio-toolbar/pipeline_presets.json
Blender has no Qt, so it's a native dialog with the same four pages.
"""

import os, sys, json, time
import bpy
from bpy.props import (StringProperty, BoolProperty, EnumProperty, IntProperty,
                       CollectionProperty, PointerProperty)

try:
    from . import stm_pipeline as P
except ImportError:
    import stm_pipeline as P


def _pkg():
    return sys.modules[__package__]


# ── data ──────────────────────────────────────────────────────────────────────
class STM_SetupItem(bpy.types.PropertyGroup):
    name: StringProperty(name="Name")
    subs: StringProperty(name="Subfolders",
                         description="Subfolders created inside this task's scenes folder, comma-separated")


_PRESET_ITEMS = {"items": []}

def _preset_items(self, context):
    names = sorted(P.load_presets())
    items = [(n, n, "") for n in names] or [("__none__", "(no presets saved)", "")]
    _PRESET_ITEMS["items"] = items                       # keep the strings alive for Blender
    return items


class STM_Setup(bpy.types.PropertyGroup):
    tab: EnumProperty(items=[("PROJECT", "Project", "Where your projects live"),
                             ("TASKS", "Tasks", "Department folders and their scene subfolders"),
                             ("FOLDERS", "Folders", "Subfolders inside every task"),
                             ("OUTPUT", "Output", "Snapshots and render frame numbering")],
                      default="PROJECT")
    root:    StringProperty(name="Root path", description="Root drive or path where projects live  (e.g.  T:  or  //server/projects)")
    prefix:  StringProperty(name="Project prefix", description="Prefix that identifies project folders (e.g. VFX- → VFX-MOR…)")
    exclude: StringProperty(name="Not sequences",
                            description="Folders inside a project that are not sequences — comma-separated, case-insensitive")
    tasks: CollectionProperty(type=STM_SetupItem)
    task_index: IntProperty()
    subs: CollectionProperty(type=STM_SetupItem)
    sub_index: IntProperty()
    thumb_subfolder: StringProperty(name="Save into", description="Which task subfolder receives the viewport snapshots")
    thumb_subdir: StringProperty(name="Inside folder", description="Optional folder inside it, e.g. captures")
    snap_maxfile: BoolProperty(name="Scene filename", default=True)
    snap_shot:    BoolProperty(name="Shot", default=False)
    snap_task:    BoolProperty(name="Task", default=False)
    snap_camera:  BoolProperty(name="Camera / view", default=True)
    render_sep: EnumProperty(name="Frame separator",
                             items=[("_", "Underscore   shot_v001_0001.exr", ""), (".", "Dot   shot_v001.0001.exr", "")])
    preset: EnumProperty(name="Preset", items=_preset_items)
    preset_name: StringProperty(name="Name", description="Name for the new preset")


def _bool(cfg, key, default):
    v = cfg.get(key, default)
    return v if isinstance(v, bool) else (str(v).lower() != "false" if default else str(v).lower() == "true")

def load_into(st, cfg):
    st.root    = str(cfg.get("root_drive", "T:"))
    st.prefix  = str(cfg.get("project_prefix", "VFX-"))
    st.exclude = str(cfg.get("seq_exclude", ""))
    raw = cfg.get("task_projects_subs", "")
    try:    mapping = (json.loads(raw) if isinstance(raw, str) else dict(raw)) if raw else {}
    except Exception: mapping = {}
    st.tasks.clear()
    for t in [t.strip() for t in str(cfg.get("tasks", "")).split(",") if t.strip()]:
        it = st.tasks.add(); it.name = t; it.subs = ", ".join(mapping.get(t, ["textures"]))
    st.subs.clear()
    subs = [str(cfg.get(k, "")).strip() for k in ("sub_projects", "sub_review", "sub_publish")]
    subs = [s for s in subs if s] + [v.strip() for v in str(cfg.get("extra_subs", "")).split(",") if v.strip()]
    for s in subs:
        it = st.subs.add(); it.name = s
    st.task_index = 0; st.sub_index = 0
    st.thumb_subfolder = str(cfg.get("thumb_subfolder", subs[1] if len(subs) > 1 else ""))
    st.thumb_subdir = str(cfg.get("thumb_subdir", ""))
    st.snap_maxfile = _bool(cfg, "snap_inc_maxfile", True)
    st.snap_shot    = _bool(cfg, "snap_inc_shot", False)
    st.snap_task    = _bool(cfg, "snap_inc_task", False)
    st.snap_camera  = _bool(cfg, "snap_inc_camera", True)
    st.render_sep   = "." if cfg.get("render_sep", "_") == "." else "_"

def form_data(st):
    tasks = [t.name.strip() for t in st.tasks if t.name.strip()]
    subs  = [s.name.strip() for s in st.subs if s.name.strip()]
    mapping = {t.name.strip(): [x.strip() for x in t.subs.split(",") if x.strip()]
               for t in st.tasks if t.name.strip()}
    return {
        "root_drive":         st.root.strip().rstrip("\\"),
        "project_prefix":     st.prefix.strip(),
        "seq_exclude":        st.exclude.strip(),
        "tasks":              ",".join(tasks),
        "sub_projects":       subs[0] if len(subs) > 0 else "1_projects",
        "sub_review":         subs[1] if len(subs) > 1 else "2_review",
        "sub_publish":        subs[2] if len(subs) > 2 else "3_publish",
        "extra_subs":         ",".join(subs[3:]),
        "task_projects_subs": json.dumps(mapping) if mapping else "",
        "thumb_subfolder":    st.thumb_subfolder,
        "thumb_subdir":       st.thumb_subdir.strip(),
        "snap_inc_maxfile":   st.snap_maxfile,
        "snap_inc_shot":      st.snap_shot,
        "snap_inc_task":      st.snap_task,
        "snap_inc_camera":    st.snap_camera,
        "render_sep":         st.render_sep,
    }

_FOUND = {"key": None, "t": 0, "val": None}

def _found_projects(root, prefix):
    """Projects under root (cached a few seconds: the dialog redraws a lot)."""
    key = (root, prefix)
    if _FOUND["key"] == key and time.monotonic() - _FOUND["t"] < 3:
        return _FOUND["val"]
    scan = root + os.sep if root.endswith(":") else root
    val = None if not os.path.isdir(scan) else sorted(d[len(prefix):] for d in P.listdirs(scan) if d.startswith(prefix))
    _FOUND.update(key=key, t=time.monotonic(), val=val)
    return val


# ── list ──────────────────────────────────────────────────────────────────────
class STM_UL_setup(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        if active_propname == "task_index":
            split = row.split(factor=0.42, align=True)
            split.prop(item, "name", text="", emboss=False, icon="FILE_FOLDER")
            split.prop(item, "subs", text="", emboss=False, icon="FOLDER_REDIRECT")
        else:
            roles = {0: "scenes", 1: "review", 2: "publish / renders"}
            split = row.split(factor=0.6, align=True)
            split.prop(item, "name", text="", emboss=False, icon="FILE_FOLDER")
            tag = roles.get(index, "")
            if item.name == data.thumb_subfolder:
                tag = (tag + " · snapshots").strip(" ·")
            split.label(text=tag)


class STM_OT_setup_list(bpy.types.Operator):
    bl_idname = "stm.setup_list"
    bl_label = "Edit list"
    bl_options = {"INTERNAL"}
    target: EnumProperty(items=[("TASKS", "Tasks", ""), ("SUBS", "Subfolders", "")])
    action: EnumProperty(items=[("ADD", "Add", ""), ("REMOVE", "Remove", ""), ("UP", "Up", ""), ("DOWN", "Down", "")])

    @classmethod
    def description(cls, context, props):
        what = "task" if props.target == "TASKS" else "subfolder"
        return {"ADD": f"Add a {what}", "REMOVE": f"Delete the selected {what}",
                "UP": "Move up", "DOWN": "Move down"}[props.action]

    def execute(self, context):
        st = context.window_manager.stm_setup
        coll, idx_name = (st.tasks, "task_index") if self.target == "TASKS" else (st.subs, "sub_index")
        idx = getattr(st, idx_name)
        if self.action == "ADD":
            it = coll.add()
            it.name = "new_task" if self.target == "TASKS" else "new_folder"
            if self.target == "TASKS": it.subs = "textures"
            setattr(st, idx_name, len(coll) - 1)
        elif self.action == "REMOVE" and 0 <= idx < len(coll):
            coll.remove(idx); setattr(st, idx_name, max(0, min(idx, len(coll) - 1)))
        elif self.action == "UP" and idx > 0:
            coll.move(idx, idx - 1); setattr(st, idx_name, idx - 1)
        elif self.action == "DOWN" and idx < len(coll) - 1:
            coll.move(idx, idx + 1); setattr(st, idx_name, idx + 1)
        return {"FINISHED"}


class STM_OT_setup_preset(bpy.types.Operator):
    bl_idname = "stm.setup_preset"
    bl_label = "Preset"
    bl_options = {"INTERNAL"}
    action: EnumProperty(items=[("LOAD", "Load", ""), ("SAVE", "Save", ""), ("DELETE", "Delete", "")])

    @classmethod
    def description(cls, context, props):
        return {"LOAD": "Load the selected preset into this dialog (applied when you press Save & Apply)",
                "SAVE": "Save the current settings as a preset with this name (shared with Max and Houdini)",
                "DELETE": "Delete the selected preset"}[props.action]

    def execute(self, context):
        st = context.window_manager.stm_setup
        presets = P.load_presets()
        if self.action == "LOAD":
            if st.preset in presets:
                load_into(st, dict(P.cfg_raw(), **presets[st.preset]))
        elif self.action == "SAVE":
            name = st.preset_name.strip()
            if not name:
                self.report({"WARNING"}, "Type a name for the preset"); return {"CANCELLED"}
            presets[name] = form_data(st)
            P.save_presets(presets)
            st.preset_name = ""
            try: st.preset = name
            except TypeError: pass
            self.report({"INFO"}, f"Preset '{name}' saved")
        elif self.action == "DELETE" and st.preset in presets:
            presets.pop(st.preset); P.save_presets(presets)
        return {"FINISHED"}


class STM_OT_setup(bpy.types.Operator):
    bl_idname = "stm.setup"
    bl_label = "Pipeline Setup"
    bl_description = "Pipeline Setup — root, prefix, tasks and folder names (shared with Max and Houdini)"

    def invoke(self, context, event):
        load_into(context.window_manager.stm_setup, P.cfg_raw())
        kw = {"width": 720}
        try:
            return context.window_manager.invoke_props_dialog(self, confirm_text="Save & Apply", **kw)
        except TypeError:                                  # Blender < 4.1
            return context.window_manager.invoke_props_dialog(self, **kw)

    def draw(self, context):
        st = context.window_manager.stm_setup
        lay = self.layout
        lay.row().prop(st, "tab", expand=True)
        lay.separator()
        getattr(self, "_draw_" + st.tab.lower())(lay, st)
        lay.separator()
        box = lay.box()
        row = box.row(align=True)
        row.label(text="Preset", icon="PRESET")
        row.prop(st, "preset", text="")
        row.operator("stm.setup_preset", text="Load").action = "LOAD"
        row.operator("stm.setup_preset", text="", icon="TRASH").action = "DELETE"
        row.separator()
        try:
            row.prop(st, "preset_name", text="", placeholder="new preset name")
        except TypeError:
            row.prop(st, "preset_name", text="")
        row.operator("stm.setup_preset", text="Save as").action = "SAVE"
        box.label(text=f"Saved to {P.CONFIG_PATH}  ·  shared with Max and Houdini", icon="INFO")

    @staticmethod
    def _hint(col, text, icon="NONE"):
        r = col.row(); r.scale_y = 0.8; r.enabled = False; r.label(text=text, icon=icon)

    def _draw_project(self, lay, st):
        col = lay.column()
        col.use_property_split = True; col.use_property_decorate = False
        col.prop(st, "root"); col.prop(st, "prefix"); col.prop(st, "exclude")
        col = lay.column()
        self._hint(col, "Folders inside a project that should not be listed as sequences — comma-separated.")
        root = st.root.strip().rstrip("\\/") or "T:"
        pfx = st.prefix.strip() or "VFX-"
        col.separator()
        col.label(text=f"Project folders look like:   {root}{os.sep if ':' in root else '/'}{pfx}MYPROJECT")
        found = _found_projects(root, pfx)
        if found is None:
            col.label(text="Root path not found on this machine", icon="ERROR")
        elif found:
            more = f"  +{len(found) - 10} more" if len(found) > 10 else ""
            col.label(text=f"{len(found)} project{'s' if len(found) != 1 else ''} found:  " + ", ".join(found[:10]) + more,
                      icon="CHECKMARK")
        else:
            col.label(text=f"No folders starting with “{pfx}” in this root", icon="QUESTION")
        if os.environ.get("STM_ROOT"):
            self._hint(col, f"This machine overrides the root with STM_ROOT = {os.environ['STM_ROOT']}", "INFO")

    def _list(self, lay, st, coll, idx, target, rows=8):
        row = lay.row()
        row.template_list("STM_UL_setup", target, st, coll, st, idx, rows=rows)
        col = row.column(align=True)
        for action, icon in (("ADD", "ADD"), ("REMOVE", "REMOVE")):
            op = col.operator("stm.setup_list", text="", icon=icon); op.target = target; op.action = action
        col.separator()
        for action, icon in (("UP", "TRIA_UP"), ("DOWN", "TRIA_DOWN")):
            op = col.operator("stm.setup_list", text="", icon=icon); op.target = target; op.action = action

    def _draw_tasks(self, lay, st):
        scenes = st.subs[0].name if len(st.subs) else "1_projects"
        hdr = lay.row().split(factor=0.42)
        hdr.label(text="Task folder (+ button)")
        hdr.label(text=f"Subfolders inside  task / {scenes}  (comma-separated)")
        self._list(lay, st, "tasks", "task_index", "TASKS", rows=9)
        self._hint(lay.column(), "Double-click to rename · new tasks get  textures  by default.")

    def _draw_folders(self, lay, st):
        self._list(lay, st, "subs", "sub_index", "SUBS", rows=6)
        self._hint(lay.column(), "1st = scenes · 2nd = review · 3rd = publish (renders) · extras are optional.")
        box = lay.box(); col = box.column(align=True)
        root = st.root.strip().rstrip("\\/") or "T:"; pfx = st.prefix.strip() or "VFX-"
        task = st.tasks[st.task_index] if 0 <= st.task_index < len(st.tasks) else None
        col.label(text=f"{root}\\{pfx}PROJ\\101\\PROJ_101_010\\3D\\{task.name if task else 'task'}\\", icon="FILE_FOLDER")
        for i, sb in enumerate(st.subs):
            col.label(text=f"      {sb.name}\\", icon="BLANK1")
            if i == 0 and task:
                for ps in [x.strip() for x in task.subs.split(",") if x.strip()]:
                    col.label(text=f"            {ps}\\", icon="BLANK1")

    def _draw_output(self, lay, st):
        box = lay.box(); box.label(text="Viewport snapshots", icon="IMAGE_DATA")
        col = box.column(); col.use_property_split = True; col.use_property_decorate = False
        col.prop_search(st, "thumb_subfolder", st, "subs")
        col.prop(st, "thumb_subdir")
        row = box.row(align=True)
        for k in ("snap_maxfile", "snap_shot", "snap_task", "snap_camera"):
            row.prop(st, k, toggle=True)
        parts = [n for k, n in (("snap_maxfile", "scenefile"), ("snap_shot", "shot"),
                                ("snap_task", "task"), ("snap_camera", "cam1")) if getattr(st, k)]
        self._hint(box.column(), f"Example:  {'_'.join(parts or ['snapshot'])}_v001.jpg")
        box = lay.box(); box.label(text="Render frames", icon="RENDER_ANIMATION")
        col = box.column(); col.use_property_split = True; col.use_property_decorate = False
        col.prop(st, "render_sep")

    def execute(self, context):
        st = context.window_manager.stm_setup
        data = form_data(st)
        if not data["tasks"]:
            self.report({"ERROR"}, "At least one task is required"); return {"CANCELLED"}
        if not [s for s in st.subs if s.name.strip()]:
            self.report({"ERROR"}, "At least one subfolder is required"); return {"CANCELLED"}
        try:
            P.save_cfg(data)                  # merges: keeps keys only Max knows about
        except Exception as e:
            self.report({"ERROR"}, f"Could not save the config: {e}"); return {"CANCELLED"}
        pkg = _pkg()
        try:
            pkg.refresh_after_setup(context)
        except Exception as e:
            print(f"[STM] refresh after setup: {e}")
        self.report({"INFO"}, "Pipeline setup saved")
        return {"FINISHED"}


classes = (STM_SetupItem, STM_Setup, STM_UL_setup, STM_OT_setup_list, STM_OT_setup_preset, STM_OT_setup)

def register():
    for c in classes: bpy.utils.register_class(c)
    bpy.types.WindowManager.stm_setup = PointerProperty(type=STM_Setup)

def unregister():
    del bpy.types.WindowManager.stm_setup
    for c in reversed(classes): bpy.utils.unregister_class(c)
