"""Headless test of the Blender add-on with the `bpy` module (pip install bpy, Python 3.11).
    python3.11 dev/test_blender.py
"""
import os, sys, tempfile, types
HERE = os.path.dirname(os.path.abspath(__file__))
home = tempfile.mkdtemp(); os.environ["HOME"] = home; os.environ["USERPROFILE"] = home
root = tempfile.mkdtemp(); os.environ["STM_ROOT"] = root
sys.path.insert(0, HERE); import make_tree; make_tree.make(root)
sys.path.insert(0, os.path.join(HERE, ".."))

import bpy
import studio_toolbar as A
A.register()
P = A.P
ok = 0
def check(c, msg):
    global ok
    assert c, msg; ok += 1

A._on_load_post()
props = bpy.context.window_manager.stm
check(A.sel()[0] == "MOR" and A.sel()[2] == "MOR_010_0010", A.sel())

# cascade: change project → seq/shot/task valid
props.project = "SHR"
check(A.sel()[:3] == ("SHR", "100", "SHR_100_0010"), A.sel())
props.project = "MOR"; props.seq = "020"
check(A.sel()[1:3] == ("020", "MOR_020_0010"), A.sel())

# save next version into a task
A.apply_selection("MOR", "010", "MOR_010_0010", "7_fx")
check(A.sel() == ("MOR", "010", "MOR_010_0010", "7_fx"), A.sel())
check(os.path.basename(A.next_path()) == "MOR_010_0010_fx_v002.blend", A.next_path())
r = bpy.ops.stm.save_next()
check(r == {"FINISHED"} and bpy.data.filepath.endswith("MOR_010_0010_fx_v002.blend"), bpy.data.filepath)
check(A.next_path().endswith("_v003.blend"), "next after save")

# mismatch → GET
props.shot = "MOR_010_0030"
check(A.file_mismatch(), "mismatch detected")
bpy.ops.stm.get()
check(not A.file_mismatch() and A.sel()[2] == "MOR_010_0010", A.sel())

# reopen another file → load_post GET
props.shot = "MOR_010_0020"
bpy.ops.wm.open_mainfile(filepath=bpy.data.filepath); props = bpy.context.window_manager.stm  # wm is replaced on load
check(A.sel()[2] == "MOR_010_0010" and A.sel()[3] == "7_fx", A.sel())

# create task
bpy.ops.stm.create_task(task="8_lighting")
check(A.sel()[3] == "8_lighting" and os.path.isdir(P.publish_dir("MOR", "010", "MOR_010_0010", "8_lighting")), A.sel())

# OPEN starts in the task's scenes folder; bar hooked into the 3D View tool settings bar
start = A.STM_OT_open_dialog.start_dir(bpy.context)
check(start == P.scenes_dir(*A.sel()) and os.path.isdir(start), start)
check(A._toolheader_draw in bpy.types.VIEW3D_HT_tool_header._dyn_ui_initialize(), "tool header hook")

# draw code paths with a recording fake layout (no UI in background mode)
class L:
    def __getattr__(self, n):
        if n in ("alert", "enabled", "ui_units_x", "scale_x"): return None
        return lambda *a, **k: L() if n in ("row", "column", "split", "box") else types.SimpleNamespace(task="", path="", filepath="")
    def __setattr__(self, n, v): pass
for vertical in (False, True):
    A.draw_bar(L(), bpy.context, vertical=vertical)
props = bpy.context.window_manager.stm; props.task = "7_fx"
for M in (A.STM_MT_new_task, A.STM_MT_folders, A.STM_MT_open_recent, A.STM_MT_save):
    M.draw(types.SimpleNamespace(layout=L()), bpy.context)
check(True, "draw paths run")

# SET RENDER (Max rules): version from the .blend, retargets compositor File Output nodes
import json
A.apply_selection("MOR", "010", "MOR_010_0010", "7_fx")
blend = bpy.data.filepath                                          # .../MOR_010_0010_fx_v002.blend
check(blend.endswith("_v002.blend"), blend)
sc = bpy.context.scene
sc.render.image_settings.file_format = "PNG"
ng = bpy.data.node_groups.new("comp", "CompositorNodeTree"); sc.compositing_node_group = ng
fo = ng.nodes.new("CompositorNodeOutputFile")
props = bpy.context.window_manager.stm; props.shot_name = False
check(bpy.ops.stm.set_render() == {"FINISHED"}, "set render runs")
pub = P.publish_dir("MOR", "010", "MOR_010_0010", "7_fx")
want = os.path.join(pub, "MOR_010_0010_fx_v002", "MOR_010_0010_fx_v002_")
check(sc.render.filepath == want, sc.render.filepath)
check(sc.render.image_settings.file_format == "OPEN_EXR", "format → EXR")
check(fo.directory == os.path.join(pub, "MOR_010_0010_fx_v002") and fo.file_name == "MOR_010_0010_fx_v002_", (fo.directory, fo.file_name))
check(A._STATUS["text"] == "Render set · EXR · +1 output", A._STATUS["text"])
open(want + "0001.exr", "w").close()
bpy.ops.stm.set_render(mode="NEW")
check(sc.render.filepath.endswith(os.path.join("MOR_010_0010_fx_v003", "MOR_010_0010_fx_v003_")), sc.render.filepath)
bpy.ops.stm.set_render(mode="OVERWRITE")
check(sc.render.filepath == want, "overwrite keeps v002")
props.shot = "MOR_010_0020"; props.task = "7_fx"; props.shot_name = True
check(P.load_state()["render_shot_name"] is True, "SHOT NAME shared state")
json.dump({"render_sep": "."}, open(P.CONFIG_PATH, "w"))
bpy.ops.stm.set_render()
check(sc.render.filepath.endswith(os.path.join("MOR_010_0020_fx_v002", "MOR_010_0020_fx_v002.")), sc.render.filepath)
os.remove(P.CONFIG_PATH); props.shot_name = False

# Setup (native dialog): same file + presets as Max/Houdini, keeps unknown keys, never writes STM_ROOT
from studio_toolbar import setup_ui as SU
json.dump({"vp_color_presets": ["#123456"], "tasks": "1_matchmove,7_fx",
           "task_projects_subs": json.dumps({"7_fx": ["textures", "cache"]})}, open(P.CONFIG_PATH, "w"))
st = bpy.context.window_manager.stm_setup
SU.load_into(st, P.cfg_raw())
check([t.name for t in st.tasks] == ["1_matchmove", "7_fx"] and st.tasks[1].subs == "textures, cache"
      and st.tasks[0].subs == "textures", [(t.name, t.subs) for t in st.tasks])
check(st.root == "T:" and [x.name for x in st.subs] == ["1_projects", "2_review", "3_publish"], st.root)
bpy.ops.stm.setup_list(target="TASKS", action="ADD"); st.tasks[-1].name = "9_comp"; st.tasks[-1].subs = "plates, renders"
bpy.ops.stm.setup_list(target="TASKS", action="UP")
check([t.name for t in st.tasks] == ["1_matchmove", "9_comp", "7_fx"], [t.name for t in st.tasks])
bpy.ops.stm.setup_list(target="SUBS", action="ADD"); st.subs[-1].name = "4_temp"
check(bpy.ops.stm.setup() == {"FINISHED"}, "setup saves")
saved = json.load(open(P.CONFIG_PATH))
check(saved["tasks"] == "1_matchmove,9_comp,7_fx" and saved["vp_color_presets"] == ["#123456"]
      and saved["root_drive"] == "T:" and saved["extra_subs"] == "4_temp", saved)
check(json.loads(saved["task_projects_subs"])["9_comp"] == ["plates", "renders"], saved["task_projects_subs"])
check(P.task_projects_subs("9_comp") == ["plates", "renders"], "core sees it")
st.preset_name = "studio"; bpy.ops.stm.setup_preset(action="SAVE")
check("studio" in P.load_presets(), "preset saved")
st.tasks.clear(); st.preset = "studio"; bpy.ops.stm.setup_preset(action="LOAD")
check(len(st.tasks) == 3, "preset loaded")
bpy.ops.stm.setup_preset(action="DELETE"); check("studio" not in P.load_presets(), "preset deleted")
fake = types.SimpleNamespace(layout=L())
fake._hint = SU.STM_OT_setup._hint
for name in ("_list", "_draw_project", "_draw_tasks", "_draw_folders", "_draw_output"):
    setattr(fake, name, types.MethodType(getattr(SU.STM_OT_setup, name), fake))
for tab in ("PROJECT", "TASKS", "FOLDERS", "OUTPUT"):
    st.tab = tab; SU.STM_OT_setup.draw(fake, bpy.context)
check(True, "setup pages draw")
os.remove(P.CONFIG_PATH)

# no projects → placeholder item, no crash
os.environ["STM_ROOT"] = tempfile.mkdtemp(); P._CFG_CACHE["data"] = None
bpy.ops.wm.read_homefile(); A._on_load_post()
check(A.sel() == ("", "", "", ""), A.sel())
A.unregister()
print(f"blender {bpy.app.version_string}: {ok} checks passed")
