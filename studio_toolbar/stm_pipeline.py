# -*- coding: utf-8 -*-
"""
stm_pipeline — shared pipeline navigation core for Studio Toolbar
Author: Javi Bravo (VFX)

Pure Python, no DCC imports. Used by the Houdini panel and the Blender add-on
(the 3ds Max toolbar has its own copy of these rules; both read the same config).

Folder convention (same as Studio Toolbar for MAX):
    <root>/<prefix><PROJECT>/<SEQ>/<PROJECT>_<SHOT>/3D/<TASK>/<sub_projects|sub_review|sub_publish>/

Config: ~/.studio-toolbar/pipeline_config.ini (JSON, written by the Max Setup dialog).
Last selection: ~/.studio-toolbar/pipeline_state.ini (shared with Max: keys project/sequence/shot/task).
"""

import os, re, json, sys, subprocess
from datetime import datetime

CORE_VERSION = "0.2.0"

# ── Defaults (mirror USER CONFIG in StudioToolbar-max.py) ─────────────────────
PIPELINE_DEFAULTS = {
    "root_drive":         "T:",
    "project_prefix":     "VFX-",
    "seq_exclude":        "3D,SOURCE,FOOTAGE,AUDIO,RENDER",
    "tasks":              "1_matchmove,2_model,3_retopo,4_rigging,5_shaders,6_animation,7_fx,8_lighting",
    "sub_projects":       "1_projects",
    "sub_review":         "2_review",
    "sub_publish":        "3_publish",
    "extra_subs":         "",
    "task_projects_subs": json.dumps({
        "1_matchmove": ["footage", "textures"],
        "2_model":     ["textures"],
        "3_retopo":    ["textures"],
        "4_rigging":   ["textures"],
        "5_shaders":   ["textures"],
        "6_animation": ["textures"],
        "7_fx":        ["textures", "cache"],
        "8_lighting":  ["textures", "cache", "import"],
    }),
    "thumb_subfolder":    "2_review",
    "thumb_subdir":       "",
    "snap_inc_maxfile":   True,
    "snap_inc_shot":      False,
    "snap_inc_task":      False,
    "snap_inc_camera":    True,
    "render_sep":         "_",
}

DEPT_FOLDER = "3D"     # department folder inside each shot (fixed in the Max toolbar too)

PIPE_DIR     = os.path.expanduser(os.path.join("~", ".studio-toolbar"))
STATE_PATH   = os.path.join(PIPE_DIR, "pipeline_state.ini")
CONFIG_PATH  = os.path.join(PIPE_DIR, "pipeline_config.ini")
PRESETS_PATH = os.path.join(PIPE_DIR, "pipeline_presets.json")
ICON_DIR     = os.path.join(PIPE_DIR, "icons")

IS_WIN = sys.platform.startswith("win")

# ── Config ────────────────────────────────────────────────────────────────────
_CFG_CACHE = {"mtime": None, "data": None}

def cfg():
    """Active config (pipeline_config.ini merged over defaults). Re-read only when the file changes."""
    try:    mtime = os.path.getmtime(CONFIG_PATH)
    except OSError: mtime = None
    if _CFG_CACHE["data"] is not None and _CFG_CACHE["mtime"] == mtime:
        return dict(_CFG_CACHE["data"])
    data = dict(PIPELINE_DEFAULTS)
    if mtime is not None:
        try:
            with open(CONFIG_PATH, "r") as f:
                data.update(json.load(f))
        except Exception as e:
            print(f"[STM] pipeline_config read error: {e}")
    # Optional per-machine root override (handy on Linux/macOS where T: doesn't exist)
    env_root = os.environ.get("STM_ROOT")
    if env_root:
        data["root_drive"] = env_root
    _CFG_CACHE.update(mtime=mtime, data=data)
    return dict(data)

def cfg_raw():
    """Config exactly as stored (defaults + file), without the STM_ROOT override.
    Use this to edit and save the shared file, so a machine override never leaks into it."""
    data = dict(PIPELINE_DEFAULTS)
    try:
        with open(CONFIG_PATH, "r") as f:
            data.update(json.load(f))
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[STM] pipeline_config read error: {e}")
    return data

def save_cfg(data):
    """Write pipeline_config.ini (shared with Max). Keys this tool doesn't know are kept."""
    merged = cfg_raw(); merged.update(data)
    os.makedirs(PIPE_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(merged, f, indent=2)
    _CFG_CACHE["data"] = None

def load_presets():
    try:
        with open(PRESETS_PATH, "r") as f: return json.load(f)
    except Exception: return {}

def save_presets(presets):
    os.makedirs(PIPE_DIR, exist_ok=True)
    with open(PRESETS_PATH, "w") as f: json.dump(presets, f, indent=2)

def prefix():
    return cfg().get("project_prefix", "VFX-")

def tasks_template():
    return [t.strip() for t in cfg()["tasks"].split(",") if t.strip()]

def subfolders():
    """Ordered task subfolders: projects, review, publish, extras."""
    c = cfg(); subs = []
    for key in ("sub_projects", "sub_review", "sub_publish"):
        v = c.get(key, "").strip()
        if v: subs.append(v)
    subs += [v.strip() for v in c.get("extra_subs", "").split(",") if v.strip()]
    return subs

def seq_exclude():
    return [s.strip().upper() for s in cfg()["seq_exclude"].split(",") if s.strip()]

def task_projects_subs(task):
    raw = cfg().get("task_projects_subs", "")
    if raw:
        try:
            mapping = json.loads(raw) if isinstance(raw, str) else raw
            if task in mapping: return list(mapping[task])
        except Exception: pass
    return ["textures"]

# ── State (shared with Max) ───────────────────────────────────────────────────
def load_state():
    try:
        with open(STATE_PATH, "r") as f: return json.load(f)
    except Exception: return {}

def save_state(data):
    try:
        os.makedirs(PIPE_DIR, exist_ok=True)
        cur = load_state(); cur.update(data)
        with open(STATE_PATH, "w") as f: json.dump(cur, f, indent=2)
    except Exception as e:
        print(f"[STM] state write error: {e}")

# ── Paths ─────────────────────────────────────────────────────────────────────
def _split(path):
    return [p for p in str(path or "").replace("\\", "/").split("/") if p]

def pipeline_base(hint_path=None):
    """Folder that contains the <prefix>XXX projects.
    If hint_path (the open scene) is inside a project, use the folder above it;
    otherwise the configured root_drive."""
    pfx = prefix()
    if hint_path:
        norm = str(hint_path).replace("\\", "/")
        parts = norm.split("/")
        for i, p in enumerate(parts):
            if p.startswith(pfx) and i > 0:
                base = "/".join(parts[:i])
                if base == "": base = "/"
                if re.fullmatch(r"[A-Za-z]:", base): base += "/"
                return os.path.normpath(base)
    root = str(cfg().get("root_drive", "T:")).rstrip("/\\")
    if re.fullmatch(r"[A-Za-z]:", root): root += os.sep      # "T:" → "T:\" (drive root, not cwd)
    return os.path.normpath(root or "/")

def listdirs(path):
    try:
        return sorted(d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d)))
    except Exception:
        return []

def project_dir(project, base=None):
    return os.path.join(base or pipeline_base(), f"{prefix()}{project}")

def shot_dir(project, seq, shot, base=None):
    if not all([project, seq, shot]): return None
    return os.path.join(project_dir(project, base), seq, shot)

def task_dir(project, seq, shot, task, sub=None, base=None):
    sd = shot_dir(project, seq, shot, base)
    if not sd or not task: return None
    d = os.path.join(sd, DEPT_FOLDER, task)
    return os.path.join(d, sub) if sub else d

def scenes_dir(project, seq, shot, task, base=None):
    return task_dir(project, seq, shot, task, cfg()["sub_projects"], base)

def review_dir(project, seq, shot, task, base=None):
    return task_dir(project, seq, shot, task, cfg()["sub_review"], base)

def publish_dir(project, seq, shot, task, base=None):
    return task_dir(project, seq, shot, task, cfg()["sub_publish"], base)

def snapshot_dir(project, seq, shot, task, base=None):
    c = cfg()
    d = task_dir(project, seq, shot, task, c.get("thumb_subfolder", c.get("sub_review")), base)
    sub = c.get("thumb_subdir", "").strip()
    return os.path.join(d, sub) if d and sub else d

# ── Listing (same filters as the Max toolbar) ─────────────────────────────────
def list_projects(base=None):
    pfx = prefix()
    return [d[len(pfx):] for d in listdirs(base or pipeline_base()) if d.startswith(pfx)]

def list_sequences(project, base=None):
    if not project: return []
    excl = seq_exclude()
    return [d for d in listdirs(project_dir(project, base))
            if d.upper() not in excl and d[:1].isdigit()]

def list_shots(project, seq, base=None):
    if not (project and seq): return []
    return [d for d in listdirs(os.path.join(project_dir(project, base), seq))
            if d.startswith(f"{project}_")]

def list_tasks(project, seq, shot, base=None):
    sd = shot_dir(project, seq, shot, base)
    return listdirs(os.path.join(sd, DEPT_FOLDER)) if sd else []

def missing_tasks(project, seq, shot, base=None):
    existing = set(list_tasks(project, seq, shot, base))
    return [t for t in tasks_template() if t not in existing]

# ── Parse a file path back into the pipeline ──────────────────────────────────
def parse_path(path):
    """…/<prefix>XXX/seq/shot/3D/task/… → dict(project, seq, shot, task) or None."""
    pfx = prefix()
    parts = _split(path)
    idx = next((i for i, p in enumerate(parts) if p.startswith(pfx)), None)
    if idx is None or len(parts) <= idx + 2: return None
    return {
        "project": parts[idx][len(pfx):],
        "seq":     parts[idx + 1],
        "shot":    parts[idx + 2],
        "task":    parts[idx + 4] if len(parts) > idx + 4 and parts[idx + 3].lower() == DEPT_FOLDER.lower() else "",
    }

def same_place(a, b, keys=("project", "seq", "shot", "task")):
    """Case-insensitive compare of two pipeline dicts (Windows paths are case-insensitive)."""
    if not a or not b: return False
    return all(str(a.get(k) or "").lower() == str(b.get(k) or "").lower() for k in keys)

# ── Scene versions ────────────────────────────────────────────────────────────
def task_clean(task):
    """'2_model' → 'model'"""
    return task.split("_", 1)[-1] if "_" in task else task

def scene_base_name(shot, task):
    return f"{shot}_{task_clean(task)}"

def list_scenes(folder, exts):
    """Scene files in folder (exts like ('.hip','.hiplc')), newest first."""
    if not folder or not os.path.isdir(folder): return []
    exts = tuple(e.lower() for e in exts)
    files = [f for f in os.listdir(folder) if f.lower().endswith(exts)]
    return sorted(files, key=lambda f: os.path.getmtime(os.path.join(folder, f)), reverse=True)

def latest_version(folder, base_name, exts):
    """Highest _v### for base_name with any of exts (0 if none)."""
    if not folder or not os.path.isdir(folder): return 0
    alt = "|".join(re.escape(e.lstrip(".")) for e in exts)
    rx = re.compile(r"^" + re.escape(base_name) + r"_v(\d+)\.(?:" + alt + r")$", re.IGNORECASE)
    best = 0
    for f in os.listdir(folder):
        m = rx.match(f)
        if m: best = max(best, int(m.group(1)))
    return best

def next_scene_path(project, seq, shot, task, ext, all_exts=None, base=None):
    """<scenes>/<shot>_<task>_v###<ext> with the next free version.
    all_exts: every extension that counts as a version (e.g. .hip/.hiplc/.hipnc)."""
    folder = scenes_dir(project, seq, shot, task, base)
    if not folder: return None
    name = scene_base_name(shot, task)
    v = latest_version(folder, name, all_exts or (ext,)) + 1
    return os.path.join(folder, f"{name}_v{v:03d}{ext}")

def render_target(publish_base, shot, task, scene_name, use_shot_name):
    """Max SET RENDER naming. Returns (prefix, version, pad):
    prefix  = <shot>_<task> (use_shot_name or no scene name) or the scene name without _v###
    version = always the open scene's _v### (1 if it has none)."""
    raw = os.path.splitext(os.path.basename(scene_name or ""))[0]
    if use_shot_name or not raw:
        pfx = scene_base_name(shot, task)
    else:
        m = re.match(r"^(.+?)(_v\d+)?$", raw)
        pfx = m.group(1) if m else raw
    mv = re.search(r"_v(\d+)$", raw)
    ver, pad = (int(mv.group(1)), len(mv.group(1))) if mv else (1, 3)
    return pfx, ver, pad

def next_free_render_version(publish_base, prefix, current, pad):
    rx = re.compile(r"^" + re.escape(prefix) + r"_v(\d+)$", re.IGNORECASE)
    used = []
    if os.path.isdir(publish_base):
        used = [int(m.group(1)) for d in os.listdir(publish_base) if (m := rx.match(d))]
    return f"{prefix}_v{max(used + [current]) + 1:0{pad}d}"

def describe_file(path):
    when = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%d %b %H:%M")
    return f"{os.path.basename(path)}      {when}"

# ── Folder creation ───────────────────────────────────────────────────────────
def create_task(project, seq, shot, task, base=None):
    """Create a task folder with the configured subfolders (same as the + button in Max)."""
    tdir = task_dir(project, seq, shot, task, base=base)
    if not tdir: return None
    subs = subfolders()
    proj_sub = subs[0] if subs else "1_projects"
    psubs = task_projects_subs(task)
    for ps in psubs:
        os.makedirs(os.path.join(tdir, proj_sub, ps), exist_ok=True)
    if not psubs:
        os.makedirs(os.path.join(tdir, proj_sub), exist_ok=True)
    for sub in subs[1:]:
        os.makedirs(os.path.join(tdir, sub), exist_ok=True)
    return tdir

# ── OS helpers ────────────────────────────────────────────────────────────────
def open_folder(path):
    """Open a folder in the OS file browser (Explorer / Finder / xdg-open)."""
    if not path or not os.path.isdir(path): return False
    try:
        if IS_WIN:                    os.startfile(path)
        elif sys.platform == "darwin": subprocess.Popen(["open", path])
        else:                         subprocess.Popen(["xdg-open", path])
        return True
    except Exception as e:
        print(f"[STM] open folder: {e}")
        return False
