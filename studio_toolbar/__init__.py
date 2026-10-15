# -*- coding: utf-8 -*-
"""
Studio Toolbar for BLENDER — pipeline navigation
Author: Javi Bravo (VFX)

Same folder rules and config as Studio Toolbar for MAX (~/.studio-toolbar/pipeline_config.ini).

Shows in the top bar (right side) and in the 3D View sidebar ▸ Studio tab:
  PROJECT / SEQ / SHOT / TASK   dropdowns, filled from disk
  +                             create a missing task folder (with its subfolders)
  GET                           fill the dropdowns from the open .blend (red when they differ)
  folder ▾                      open shot / task / subfolders in the OS file browser
  OPEN ▾                        browse the task's scenes · arrow: recent versions
  SAVE ▾                        save dialog with the next version name · arrow: one-click next version
  SET RENDER                    render output → publish/<name>_v###/  (version from the .blend, like Max)
  SHOT NAME                     name renders after the dropdowns instead of the .blend
  ⚙                             Pipeline Setup (same pipeline_config.ini and presets as Max / Houdini)
"""

bl_info = {
    "name": "Studio Toolbar",
    "author": "Javi Bravo (VFX)",
    "version": (0, 3, 0),
    "blender": (4, 2, 0),
    "location": "3D View ▸ Tool Settings bar · 3D View ▸ Sidebar ▸ Studio",
    "description": "Pipeline navigation: project, sequence, shot, task and versioned scenes",
    "category": "Pipeline",
}

import os, re, sys, time, zlib
import bpy
from bpy.props import EnumProperty, StringProperty, BoolProperty, PointerProperty
from bpy.app.handlers import persistent

try:
    from . import stm_pipeline as P
except ImportError:                                   # running from the repo: use ../../core
    _core = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "core"))
    if _core not in sys.path: sys.path.insert(0, _core)
    import stm_pipeline as P
from . import setup_ui

VERSION    = "0.3.0"
BLEND_EXTS = (".blend",)
NONE_ID    = "__none__"

# ── runtime state ─────────────────────────────────────────────────────────────
_BASE      = None             # folder that holds the <prefix>XXX projects
_STATUS    = {"text": "Ready", "icon": "INFO", "log": []}
_LIST      = {}               # listing cache: key -> (time, list)
_ITEMS     = {}               # enum items kept alive (Blender needs the references)
_BUSY      = {"cascade": False}
CACHE_SEC  = 3.0


def _base():
    global _BASE
    if _BASE is None:
        _BASE = P.pipeline_base(bpy.data.filepath or None)
    return _BASE

def _cached(key, fn):
    now = time.monotonic()
    hit = _LIST.get(key)
    if hit and now - hit[0] < CACHE_SEC: return hit[1]
    val = fn(); _LIST[key] = (now, val); return val

def _clear_cache():
    _LIST.clear()

def _status(text, icon="INFO", detail=None):
    _STATUS["text"], _STATUS["icon"] = text, icon
    _STATUS["log"].insert(0, (time.strftime("%H:%M:%S"), text, detail or ""))
    del _STATUS["log"][25:]
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type in {"TOPBAR", "VIEW_3D"}: area.tag_redraw()

def _props(context=None):
    return (context or bpy.context).window_manager.stm

def _val(v):
    return "" if (not v or v == NONE_ID) else v

def sel(context=None):
    p = _props(context)
    return _val(p.project), _val(p.seq), _val(p.shot), _val(p.task)

# ── dynamic enum items ────────────────────────────────────────────────────────
def _make_items(key, names, empty_label):
    # Stable numbers (crc of the name) so the stored value survives list changes.
    # Every list ever returned stays referenced: Blender keeps pointers to these strings.
    ck = (key, tuple(names))
    items = _ITEMS.get(ck)
    if items is None:
        items = [(n, n, n, zlib.crc32(n.encode()) & 0x7FFFFFFF) for n in names]
        if not items:
            items = [(NONE_ID, empty_label, "", 0)]
        _ITEMS[ck] = items
    return items

def _project_items(self, context):
    return _make_items("project", _cached(("p", _base()), lambda: P.list_projects(_base())), "— no projects —")

def _seq_items(self, context):
    pr = _val(self.project)
    return _make_items("seq", _cached(("s", _base(), pr), lambda: P.list_sequences(pr, _base())), "— no sequences —")

def _shot_items(self, context):
    pr, sq = _val(self.project), _val(self.seq)
    return _make_items("shot", _cached(("sh", _base(), pr, sq), lambda: P.list_shots(pr, sq, _base())), "— no shots —")

def _task_items(self, context):
    pr, sq, sh = _val(self.project), _val(self.seq), _val(self.shot)
    return _make_items("task", _cached(("t", _base(), pr, sq, sh), lambda: P.list_tasks(pr, sq, sh, _base())), "— no tasks —")

def _set_enum(props, name, value):
    try:
        setattr(props, name, value); return True
    except TypeError:
        return False

def _pick(props, name, items, wanted):
    """Select wanted if present, else keep the current value if valid, else the first item."""
    ids = [i[0] for i in items]
    cur = getattr(props, name)
    target = wanted if wanted in ids else (cur if cur in ids else ids[0])
    _set_enum(props, name, target)

# cascade: project → seq → shot → task (each update picks a valid child)
def _on_project(self, context):
    if _BUSY["cascade"]: return
    st = P.load_state()
    _pick(self, "seq", _seq_items(self, context), st.get("sequence"))

def _on_seq(self, context):
    if _BUSY["cascade"]: return
    st = P.load_state()
    _pick(self, "shot", _shot_items(self, context), st.get("shot"))

def _on_shot(self, context):
    if _BUSY["cascade"]: return
    st = P.load_state()
    _pick(self, "task", _task_items(self, context), st.get("task"))

def _on_task(self, context):
    if _BUSY["cascade"]: return
    p, s, sh, t = _val(self.project), _val(self.seq), _val(self.shot), _val(self.task)
    if p: P.save_state({"project": p, "sequence": s, "shot": sh, "task": t})


class STM_Props(bpy.types.PropertyGroup):
    project: EnumProperty(name="Project",  description="Project",  items=_project_items, update=_on_project)
    seq:     EnumProperty(name="Sequence", description="Sequence", items=_seq_items,     update=_on_seq)
    shot:    EnumProperty(name="Shot",     description="Shot",     items=_shot_items,    update=_on_shot)
    task:    EnumProperty(name="Task",     description="Task (department folder inside the shot's 3D folder)",
                          items=_task_items, update=_on_task)
    shot_name: BoolProperty(
        name="SHOT NAME", default=False,
        description="SET RENDER naming\n"
                    "ON → render named after the dropdowns: shot_task_v###\n"
                    "OFF → render named after the open .blend\n"
                    "The version always comes from the .blend. Use ON to render several shots from one .blend",
        update=lambda self, ctx: P.save_state({"render_shot_name": bool(self.shot_name)}))


def apply_selection(project, seq, shot, task, context=None):
    """Set the four dropdowns in one go (no intermediate cascade jumps)."""
    props = _props(context)
    _BUSY["cascade"] = True
    try:
        _pick(props, "project", _project_items(props, context), project)
        _pick(props, "seq",     _seq_items(props, context),     seq)
        _pick(props, "shot",    _shot_items(props, context),    shot)
        _pick(props, "task",    _task_items(props, context),    task)
    finally:
        _BUSY["cascade"] = False
    p, s, sh, t = sel(context)
    if p: P.save_state({"project": p, "sequence": s, "shot": sh, "task": t})

def get_from_file(quiet=False):
    global _BASE
    path = bpy.data.filepath
    info = P.parse_path(path) if path else None
    if not info:
        if not quiet: _status("File not in pipeline", "ERROR", path or None)
        return False
    _BASE = P.pipeline_base(path); _clear_cache()
    if info["project"] not in P.list_projects(_BASE):
        if not quiet: _status("Project not listed", "ERROR")
        return False
    apply_selection(info["project"], info["seq"], info["shot"], info["task"] or P.load_state().get("task"))
    _status("GET OK", "CHECKMARK")
    return True

def file_mismatch(context=None):
    path = bpy.data.filepath
    info = P.parse_path(path) if path else None
    if not info: return False
    p, s, sh, t = sel(context)
    keys = ("project", "seq", "shot") + (("task",) if info.get("task") else ())
    return not P.same_place(info, {"project": p, "seq": s, "shot": sh, "task": t}, keys)

def _dirs(context=None):
    p, s, sh, t = sel(context); b = _base()
    return {
        "shot":    P.shot_dir(p, s, sh, b),
        "task":    P.task_dir(p, s, sh, t, base=b),
        "scenes":  P.scenes_dir(p, s, sh, t, b),
        "publish": P.publish_dir(p, s, sh, t, b),
    }

def next_path(context=None):
    p, s, sh, t = sel(context)
    if not all([p, s, sh, t]): return None
    return P.next_scene_path(p, s, sh, t, ".blend", BLEND_EXTS, _base())

def refresh_after_setup(context=None):
    """Called by the Setup dialog after saving: re-read root/prefix/folders."""
    global _BASE
    _BASE = None; _clear_cache()
    p, s, sh, t = sel(context)
    apply_selection(p, s, sh, t, context)
    _status("Setup saved", "CHECKMARK", P.CONFIG_PATH)

# ── operators ─────────────────────────────────────────────────────────────────
class STM_OT_get(bpy.types.Operator):
    bl_idname = "stm.get"
    bl_label = "GET"
    bl_description = "GET — fills Project / Sequence / Shot / Task from the open file's folder"

    def execute(self, context):
        if not get_from_file():
            self.report({"WARNING"}, _STATUS["text"]); return {"CANCELLED"}
        return {"FINISHED"}


class STM_OT_refresh(bpy.types.Operator):
    bl_idname = "stm.refresh"
    bl_label = "Refresh"
    bl_description = "Re-read the pipeline folders"

    def execute(self, context):
        global _BASE
        _BASE = None; _clear_cache()
        p, s, sh, t = sel(context)
        apply_selection(p, s, sh, t, context)
        _status("Refreshed")
        return {"FINISHED"}


class STM_OT_create_task(bpy.types.Operator):
    bl_idname = "stm.create_task"
    bl_label = "Create Task"
    bl_description = "Create this task folder for the shot, with its subfolders"
    task: StringProperty()

    def execute(self, context):
        p, s, sh, _ = sel(context)
        try:
            d = P.create_task(p, s, sh, self.task, _base())
        except Exception as e:
            self.report({"ERROR"}, f"Create task: {e}"); return {"CANCELLED"}
        _clear_cache()
        apply_selection(p, s, sh, self.task, context)
        _status("Task created", "CHECKMARK", d)
        return {"FINISHED"}


class STM_OT_open_folder(bpy.types.Operator):
    bl_idname = "stm.open_folder"
    bl_label = "Open Folder"
    bl_description = "Open this folder in the file browser"
    path: StringProperty()

    def execute(self, context):
        if not os.path.isdir(self.path):
            self.report({"WARNING"}, "Folder not found"); return {"CANCELLED"}
        bpy.ops.wm.path_open(filepath=self.path)
        return {"FINISHED"}


class STM_OT_open_scene(bpy.types.Operator):
    bl_idname = "stm.open_scene"
    bl_label = "Open Scene"
    bl_description = "Open this version (asks to save changes first)"
    filepath: StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        bpy.ops.wm.open_mainfile("INVOKE_DEFAULT", filepath=self.filepath, display_file_selector=False)
        return {"FINISHED"}


class STM_OT_open_dialog(bpy.types.Operator):
    """OPEN — browse the scenes of this task.
    Uses its own file browser: Blender's Open always starts in the last folder used,
    whatever folder it is given."""
    bl_idname = "stm.open_dialog"
    bl_label = "Open Scene"
    bl_description = "OPEN — browse the scenes of this task"
    filepath:    StringProperty(subtype="FILE_PATH")
    directory:   StringProperty(subtype="DIR_PATH")
    filter_glob: StringProperty(default="*.blend", options={"HIDDEN"})
    filter_blender: BoolProperty(default=True, options={"HIDDEN"})
    filter_folder:  BoolProperty(default=True, options={"HIDDEN"})

    @staticmethod
    def start_dir(context):
        d = _dirs(context)
        if not d["scenes"]: return None
        for cand in (d["scenes"], d["task"], d["shot"]):
            if cand and os.path.isdir(cand): return cand
        return None

    def invoke(self, context, event):
        start = self.start_dir(context)
        if not start:
            self.report({"WARNING"}, "Select a task first"); return {"CANCELLED"}
        self.directory = os.path.join(start, "")
        self.filepath  = os.path.join(start, "")
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        if not self.filepath or not os.path.isfile(self.filepath):
            self.report({"WARNING"}, "Pick a .blend file"); return {"CANCELLED"}
        # opens through Blender's own operator → asks to save changes first
        bpy.ops.wm.open_mainfile("INVOKE_DEFAULT", filepath=self.filepath, display_file_selector=False)
        return {"FINISHED"}


class STM_OT_save_next(bpy.types.Operator):
    bl_idname = "stm.save_next"
    bl_label = "Save Next Version"
    bl_description = "Save the next version of this task in one click"

    def execute(self, context):
        nxt = next_path(context)
        if not nxt:
            self.report({"WARNING"}, "Select a task first"); return {"CANCELLED"}
        os.makedirs(os.path.dirname(nxt), exist_ok=True)
        res = bpy.ops.wm.save_as_mainfile(filepath=nxt)
        if "FINISHED" not in res:
            _status("Save error", "ERROR"); return {"CANCELLED"}
        _clear_cache()
        m = re.search(r"_v(\d+)\.blend$", nxt)
        _status(f"Saved v{m.group(1)}" if m else "Saved", "CHECKMARK", nxt)
        return {"FINISHED"}


class STM_OT_save_dialog(bpy.types.Operator):
    bl_idname = "stm.save_dialog"
    bl_label = "SAVE"
    bl_description = "SAVE — save dialog with the next version name ready"

    def execute(self, context):
        nxt = next_path(context)
        if not nxt:
            self.report({"WARNING"}, "Select a task first"); return {"CANCELLED"}
        os.makedirs(os.path.dirname(nxt), exist_ok=True)
        bpy.ops.wm.save_as_mainfile("INVOKE_DEFAULT", filepath=nxt)
        return {"FINISHED"}


class STM_OT_status_log(bpy.types.Operator):
    bl_idname = "stm.status_log"
    bl_label = "History"
    bl_description = "Last actions"

    def invoke(self, context, event):
        def draw(menu, ctx):
            col = menu.layout.column()
            if not _STATUS["log"]: col.label(text="No actions yet")
            for when, text, detail in _STATUS["log"]:
                col.label(text=f"{when}   {text}" + (f"   {detail}" if detail else ""))
        context.window_manager.popup_menu(draw, title="Studio Toolbar — history", icon="TIME")
        return {"FINISHED"}

# ── SET RENDER (= Max's SET RENDER) ───────────────────────────────────────────
EXR_FORMATS = ("OPEN_EXR", "OPEN_EXR_MULTILAYER")

def _compositor_tree(scene):
    tree = getattr(scene, "compositing_node_group", None)       # Blender 5+
    if tree is None and getattr(scene, "use_nodes", False):
        tree = getattr(scene, "node_tree", None)                 # Blender 4.x
    return tree

def render_plan(context):
    """(publish_base, prefix, version, pad) for the open .blend and the dropdowns, or None."""
    p, s, sh, t = sel(context)
    if not all([p, s, sh, t]): return None
    pub = _dirs(context)["publish"]
    prefix, ver, pad = P.render_target(pub, sh, t, os.path.basename(bpy.data.filepath),
                                       _props(context).shot_name)
    return pub, prefix, ver, pad

def apply_render(context, folder_name):
    """Point the render output (and enabled compositor File Output nodes) to publish/<folder_name>/.
    Only retargets outputs that are already there — never adds or enables anything."""
    scene = context.scene
    pub = _dirs(context)["publish"]
    sep = P.cfg().get("render_sep", "_")
    out_dir = os.path.join(pub, folder_name)
    os.makedirs(out_dir, exist_ok=True)
    r = scene.render
    r.filepath = os.path.join(out_dir, f"{folder_name}{sep}")       # Blender adds the frame + extension
    r.use_file_extension = True
    notes = []
    fmt = r.image_settings
    if fmt.file_format not in EXR_FORMATS:
        if getattr(fmt, "media_type", None) == "VIDEO":
            fmt.media_type = "IMAGE"
        fmt.file_format = "OPEN_EXR"
        notes.append("EXR")
    extra = 0
    tree = _compositor_tree(scene)
    if tree is not None:
        for node in tree.nodes:
            if node.bl_idname != "CompositorNodeOutputFile" or node.mute: continue
            if hasattr(node, "directory"):                            # Blender 5+
                node.directory = out_dir
                node.file_name = f"{folder_name}_"
            elif hasattr(node, "base_path"):                          # Blender 4.x
                node.base_path = os.path.join(out_dir, "")
            extra += 1
    if extra: notes.append(f"+{extra} output{'s' if extra > 1 else ''}")
    _status(" · ".join(["Render set"] + notes), "CHECKMARK", r.filepath)
    return r.filepath


class STM_OT_set_render(bpy.types.Operator):
    bl_idname = "stm.set_render"
    bl_label = "SET RENDER"
    bl_description = ("SET RENDER — render output to the task's publish folder: "
                      "publish/<name>_v###/<name>_v###_####.exr. The version is the .blend's. "
                      "Asks before overwriting existing renders. Also retargets compositor File Output nodes")
    mode: EnumProperty(items=[("ASK", "Ask", ""), ("OVERWRITE", "Overwrite", ""), ("NEW", "New version", "")],
                       default="ASK", options={"SKIP_SAVE"})

    def invoke(self, context, event):
        plan = render_plan(context)
        if not plan:
            self.report({"WARNING"}, "Select a task first"); return {"CANCELLED"}
        pub, prefix, ver, pad = plan
        folder = f"{prefix}_v{ver:0{pad}d}"
        target = os.path.join(pub, folder)
        if self.mode == "ASK" and os.path.isdir(target) and any(os.scandir(target)):
            def draw(menu, ctx):
                col = menu.layout.column()
                col.label(text=f"{folder} already has renders.")
                col.label(text="Overwrite them, or render to the next free version?")
                col.separator()
                row = col.row()
                op = row.operator("stm.set_render", text="New version", icon="ADD"); op.mode = "NEW"
                op = row.operator("stm.set_render", text="Overwrite", icon="ERROR"); op.mode = "OVERWRITE"
            context.window_manager.popup_menu(draw, title="Set Render", icon="RENDER_STILL")
            return {"CANCELLED"}
        return self.execute(context)

    def execute(self, context):
        plan = render_plan(context)
        if not plan:
            self.report({"WARNING"}, "Select a task first"); return {"CANCELLED"}
        pub, prefix, ver, pad = plan
        folder = f"{prefix}_v{ver:0{pad}d}"
        if self.mode == "NEW":
            folder = P.next_free_render_version(pub, prefix, ver, pad)
        try:
            path = apply_render(context, folder)
        except Exception as e:
            _status("SET RENDER Error", "ERROR"); self.report({"ERROR"}, str(e)); return {"CANCELLED"}
        self.report({"INFO"}, f"Render → {path}")
        return {"FINISHED"}

# ── menus ─────────────────────────────────────────────────────────────────────
class STM_MT_new_task(bpy.types.Menu):
    bl_idname = "STM_MT_new_task"
    bl_label = "Create Task"

    def draw(self, context):
        p, s, sh, _ = sel(context)
        if not all([p, s, sh]):
            self.layout.label(text="Select a shot first"); return
        missing = P.missing_tasks(p, s, sh, _base())
        if not missing: self.layout.label(text="All tasks already exist")
        for t in missing:
            self.layout.operator("stm.create_task", text=t).task = t


class STM_MT_folders(bpy.types.Menu):
    bl_idname = "STM_MT_folders"
    bl_label = "Folders"

    def draw(self, context):
        lay = self.layout; d = _dirs(context)
        if not d["shot"]:
            lay.label(text="Select a shot first"); return
        def add(label, path):
            row = lay.row(); row.enabled = bool(path) and os.path.isdir(path)
            row.operator("stm.open_folder", text=label, icon="FILE_FOLDER").path = path or ""
        add("Shot folder", d["shot"])
        if d["task"]:
            add("Task folder", d["task"])
            lay.separator()
            for sub in P.subfolders():
                add(sub, os.path.join(d["task"], sub))


class STM_MT_open_recent(bpy.types.Menu):
    bl_idname = "STM_MT_open_recent"
    bl_label = "Recent in this task"

    def draw(self, context):
        folder = _dirs(context)["scenes"]
        files = P.list_scenes(folder, BLEND_EXTS)
        if not files:
            self.layout.label(text="No scenes in this task yet"); return
        cur = os.path.normcase(os.path.normpath(bpy.data.filepath)) if bpy.data.filepath else ""
        for f in files[:12]:
            full = os.path.join(folder, f)
            icon = "CHECKMARK" if os.path.normcase(os.path.normpath(full)) == cur else "BLANK1"
            self.layout.operator("stm.open_scene", text=P.describe_file(full), icon=icon).filepath = full


class STM_MT_save(bpy.types.Menu):
    bl_idname = "STM_MT_save"
    bl_label = "Save"

    def draw(self, context):
        nxt = next_path(context)
        if not nxt:
            self.layout.label(text="Select a task first"); return
        self.layout.operator("stm.save_next", text=f"Save next version now  →  {os.path.basename(nxt)}",
                             icon="FILE_TICK")

# ── drawing ───────────────────────────────────────────────────────────────────
STATUS_UNITS = 11      # fixed width: fits "Render set · EXR · +2 outputs"; longer text ends in …

def _draw_status(row):
    """Status with a fixed width so the bar doesn't jump; the clock opens the history."""
    sub = row.row(align=True)
    sub.ui_units_x = STATUS_UNITS
    sub.label(text=_STATUS["text"], icon=_STATUS["icon"])
    row.operator("stm.status_log", text="", icon="TIME", emboss=False)

def draw_bar(layout, context, vertical=False):
    props = _props(context)
    if vertical:
        col = layout.column(align=True)
        for name in ("project", "seq", "shot", "task"):
            col.prop(props, name, text="")
        row = layout.row(align=True)
        row.menu("STM_MT_new_task", text="Task", icon="ADD")
        sub = row.row(align=True); sub.alert = file_mismatch(context)
        sub.operator("stm.get", text="GET", icon="IMPORT")
        row.menu("STM_MT_folders", text="", icon="FILE_FOLDER")
        row.operator("stm.refresh", text="", icon="FILE_REFRESH")
        row = layout.row(align=True)
        row.operator("stm.open_dialog", text="OPEN", icon="FILE_FOLDER")
        row.menu("STM_MT_open_recent", text="", icon="DOWNARROW_HLT")
        row.operator("stm.save_dialog", text="SAVE", icon="FILE_TICK")
        row.menu("STM_MT_save", text="", icon="DOWNARROW_HLT")
        row = layout.row(align=True)
        row.operator("stm.set_render", text="SET RENDER", icon="RENDER_STILL")
        row.prop(props, "shot_name", text="SHOT NAME", toggle=True)
        row = layout.row(align=True)
        _draw_status(row)
        row.operator("stm.setup", text="", icon="PREFERENCES")
        return

    row = layout.row(align=False)
    grp = row.row(align=True)
    for name, w in (("project", 4), ("seq", 3.5), ("shot", 11), ("task", 5.5)):
        c = grp.row(align=True); c.ui_units_x = w
        c.prop(props, name, text="")
    grp.menu("STM_MT_new_task", text="", icon="ADD")
    sub = row.row(align=True); sub.alert = file_mismatch(context)
    sub.operator("stm.get", text="GET")
    row.menu("STM_MT_folders", text="", icon="FILE_FOLDER")
    grp = row.row(align=True)
    grp.operator("stm.open_dialog", text="OPEN")
    grp.menu("STM_MT_open_recent", text="", icon="DOWNARROW_HLT")
    grp = row.row(align=True)
    grp.operator("stm.save_dialog", text="SAVE")
    grp.menu("STM_MT_save", text="", icon="DOWNARROW_HLT")
    grp = row.row(align=True)
    grp.operator("stm.set_render", text="SET RENDER")
    grp.prop(props, "shot_name", text="SHOT NAME", toggle=True)
    _draw_status(row)
    row.operator("stm.setup", text="", icon="PREFERENCES")


def _prefs(context):
    try:
        return context.preferences.addons[__package__].preferences
    except (KeyError, AttributeError):
        return None

def _topbar_draw(self, context):
    if context.region.alignment != "RIGHT": return
    prefs = _prefs(context)
    if not (prefs and prefs.show_topbar): return
    self.layout.separator()
    draw_bar(self.layout, context)

def _main_view3d(context):
    """The biggest 3D View of the screen — the bar is drawn only there (not in every split)."""
    areas = [a for a in context.screen.areas if a.type == "VIEW_3D"]
    return max(areas, key=lambda a: a.width * a.height) if areas else None

def _toolheader_draw(self, context):
    """Tool settings bar of the 3D View: right below the menus, above the viewport."""
    if context.region.type != "TOOL_HEADER": return
    prefs = _prefs(context)
    if prefs is not None and not prefs.show_viewport: return
    if context.area != _main_view3d(context): return
    self.layout.separator()
    draw_bar(self.layout, context)


class STM_PT_sidebar(bpy.types.Panel):
    bl_idname = "STM_PT_sidebar"
    bl_label = f"Studio Toolbar {VERSION}"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Studio"

    def draw(self, context):
        draw_bar(self.layout, context, vertical=True)


class STM_Prefs(bpy.types.AddonPreferences):
    bl_idname = __package__
    show_viewport: BoolProperty(name="Show above the viewport", default=True,
                                description="Pipeline bar in the 3D View's tool settings bar, below the menus "
                                            "(turn it on with View ▸ Tool Settings if it's hidden)")
    show_topbar: BoolProperty(name="Show in the top bar", default=False,
                              description="Also show the pipeline bar in the top bar, next to the scene selector")

    def draw(self, context):
        self.layout.prop(self, "show_viewport")
        self.layout.prop(self, "show_topbar")
        self.layout.label(text="The 3D View sidebar ▸ Studio tab is always available.")
        self.layout.label(text=f"Config: {P.CONFIG_PATH}")
        self.layout.label(text=f"Projects root: {_base()}")

# ── handlers / init ───────────────────────────────────────────────────────────
@persistent
def _on_load_post(*_):
    global _BASE
    _BASE = None; _clear_cache()
    try:
        _props().shot_name = bool(P.load_state().get("render_shot_name", False))
    except Exception:
        pass
    if not get_from_file(quiet=True):
        _init_selection()

@persistent
def _on_save_post(*_):
    _clear_cache()

def _init_selection():
    try:
        st = P.load_state()
        apply_selection(st.get("project"), st.get("sequence"), st.get("shot"), st.get("task"))
    except Exception as e:
        print(f"[STM] init: {e}")
    return None                                       # one-shot timer

classes = (STM_Props, STM_OT_get, STM_OT_refresh, STM_OT_create_task, STM_OT_open_folder,
           STM_OT_open_scene, STM_OT_open_dialog, STM_OT_save_next, STM_OT_save_dialog,
           STM_OT_status_log, STM_OT_set_render, STM_MT_new_task, STM_MT_folders, STM_MT_open_recent, STM_MT_save,
           STM_PT_sidebar, STM_Prefs)

def register():
    for c in classes: bpy.utils.register_class(c)
    setup_ui.register()
    bpy.types.WindowManager.stm = PointerProperty(type=STM_Props)
    bpy.types.TOPBAR_HT_upper_bar.append(_topbar_draw)
    bpy.types.VIEW3D_HT_tool_header.append(_toolheader_draw)
    bpy.app.handlers.load_post.append(_on_load_post)
    bpy.app.handlers.save_post.append(_on_save_post)
    bpy.app.timers.register(lambda: (_on_load_post(), None)[1], first_interval=0.2)

def unregister():
    for h, f in ((bpy.app.handlers.load_post, _on_load_post), (bpy.app.handlers.save_post, _on_save_post)):
        if f in h: h.remove(f)
    bpy.types.TOPBAR_HT_upper_bar.remove(_topbar_draw)
    bpy.types.VIEW3D_HT_tool_header.remove(_toolheader_draw)
    del bpy.types.WindowManager.stm
    for c in reversed(classes): bpy.utils.unregister_class(c)
    setup_ui.unregister()
