# Studio Toolbar for Blender

Pipeline toolbar for Blender: project / sequence / shot / task navigation, versioned open and
save, and render output — with the same folder rules, config and Setup as
[Studio Toolbar for MAX](https://github.com/javibravo-vfx/StudioToolbar-max) and the Houdini version.

Blender 4.2+ (tested on 5.x) · version 0.3.0 · Author: Javi Bravo (VFX)

```
<root>/<prefix><PROJECT>/<SEQ>/<PROJECT>_<SHOT>/3D/<TASK>/1_projects | 2_review | 3_publish
e.g.  T:\VFX-MOR\010\MOR_010_0010\3D\7_fx\1_projects\MOR_010_0010_fx_v003.blend
```

## What's in the bar

The bar sits in the 3D View's tool settings bar — below the menus, above the viewport
(if it's hidden: **View ▸ Tool Settings**). It is also in the sidebar ▸ **Studio** tab, and can be
added to the top bar from the add-on preferences.

| Control | What it does |
|---|---|
| **PROJECT / SEQ / SHOT / TASK** | Dropdowns filled from disk, same filters as Max. The last selection is shared with Max and Houdini. |
| **+** | Creates a missing task folder with its subfolders (from the Setup). |
| **GET** | Fills the dropdowns from the open .blend. Turns red when the open file is in another shot/task. Runs by itself when a file is opened. |
| **Folder** | Opens the shot, the task or any of its subfolders in the file browser. |
| **OPEN ▾** | File browser that starts in the task's scenes folder · ▾ recent versions of the task. Asks to save changes first. |
| **SAVE ▾** | Save dialog with the next version ready (`<shot>_<task>_v###.blend`) · ▾ saves the next version in one click. |
| **SET RENDER** | Render output → `3_publish/<name>_v###/<name>_v###_####.exr` (see below). |
| **SHOT NAME** | Names renders after the dropdowns instead of the .blend. |
| **Status** | Last action, fixed width · the clock opens the history. |
| **⚙** | Pipeline Setup, shared with Max and Houdini. |

### SET RENDER

Same rules as Max:

- The **version** is always the open .blend's (`…_v003.blend` → `…_v003/`).
- The **name** is the .blend's, or `<shot>_<task>` with **SHOT NAME** on — to render several shots
  from one .blend.
- If that version already has renders it asks: **New version** or **Overwrite**.
- The frame separator (`_0001` or `.0001`) comes from the Setup.
- A format that isn't EXR is switched to OpenEXR (multilayer EXR is kept).
- Enabled compositor **File Output** nodes are pointed to the same folder. Nothing is added or enabled.

### ⚙ Pipeline Setup

Project (root, prefix, folders that aren't sequences) · Tasks (task folders and the subfolders
inside each task's scenes folder) · Folders (task subfolders: scenes, review, publish, extras) ·
Output (snapshots, frame separator) · named presets.

## Shared config

Everything lives in `~/.studio-toolbar/` and is shared with Max and Houdini:

| File | Contents |
|---|---|
| `pipeline_config.ini` | Root, prefix, tasks, subfolders… (the Setup). Keys this add-on doesn't use are kept. |
| `pipeline_presets.json` | Named Setup presets. |
| `pipeline_state.ini` | Last Project / Sequence / Shot / Task and SHOT NAME. |

On a machine where the projects aren't under `T:` (Linux, macOS), set the environment variable
`STM_ROOT` to the folder that holds the `VFX-XXX` projects — it's never written to the shared config.

## Install

Studio install, from the share (updates are picked up on the next Blender start):

1. Copy the `studio_toolbar` folder to `T:\.studio-toolbar\blender\` (next to `max\` and `houdini\`).
2. In Blender: **Edit ▸ Preferences ▸ Get Extensions ▸ Repositories (▾) ▸ + ▸ Add Local Repository**.
3. Turn on **Custom Directory** and pick `T:\.studio-toolbar\blender` — the folder *above* `studio_toolbar`.
4. Enable **Studio Toolbar** in the list.

If Blender reports a path under `…\Blender\<version>\extensions\…` that can't be found, the repository
was added without **Custom Directory**: select it, turn it on and set the path.

Single machine: zip the contents of `studio_toolbar/` and use **Install from Disk**.

## Blender and projects

Blender (up to 5.2) has no project folders like Max, Maya or Houdini: paths in a .blend are relative
to the file (`//`). Since the toolbar saves into `task/1_projects/`, relative paths such as
`//textures/` or `//cache/` already stay inside the task. Blender 5.3 introduces an optional
project system; the toolbar doesn't depend on it.

## Repository

```
studio_toolbar/
    __init__.py            toolbar, operators, SET RENDER
    setup_ui.py            Pipeline Setup dialog (native, Blender has no Qt)
    stm_pipeline.py        shared pipeline rules (same module as Max/Houdini)
    blender_manifest.toml  extension manifest
dev/
    test_blender.py        headless tests:  pip install bpy  →  python3.11 dev/test_blender.py
    make_tree.py           fake pipeline folder tree for the tests
```

`stm_pipeline.py` is shared with the Houdini toolbar; change it in both places together.
