"""Builds docs/screenshot.png from docs/screenshot_raw.png: the toolbar row with English callouts.
Usage:  python docs/annotate_screenshot.py docs/screenshot_raw.png docs/screenshot.png
Callout x-positions are measured on the 2068 px wide raw capture — update ITEMS / ROW if the layout changes.
Needs the Inter font (any OpenType path works — edit F). Same look as the Studio Toolbar for MAX infographic."""
import sys
from PIL import Image, ImageDraw, ImageFont

SRC, OUT = sys.argv[1], sys.argv[2]
F = "/usr/share/fonts/opentype/inter/"
f_title = ImageFont.truetype(F + "Inter-SemiBold.otf", 30)
f_sub   = ImageFont.truetype(F + "Inter-Regular.otf", 18)
f_head  = ImageFont.truetype(F + "Inter-Bold.otf", 17)
f_lbl   = ImageFont.truetype(F + "Inter-SemiBold.otf", 17)
f_desc  = ImageFont.truetype(F + "Inter-Regular.otf", 15)

BG, PANEL, TXT, DIM, LINE = "#1e1e1e", "#262626", "#e8e8e8", "#9a9a9a", "#6a6a6a"
SECT = ["#c97bd6", "#e07b6a", "#5aa9d9"]

X0, X1, ROW_Y0, ROW_Y1 = 210, 2068, 98, 136      # toolbar strip in the raw capture (v0.3 layout)
src = Image.open(SRC).convert("RGB")
strip = src.crop((X0, ROW_Y0, X1, ROW_Y1))
STRIP_H, PAD, TIER = ROW_Y1 - ROW_Y0, 40, 44

# (x in the raw capture, label, description, band "t"/"b", section)
ITEMS = [
    (262,  "Project",     "Projects on the root drive",          "t", 0),
    (380,  "Sequence",    "",                                     "b", 0),
    (560,  "Shot",        "",                                     "t", 0),
    (830,  "Task",        "Department folder",                    "b", 0),
    (935,  "+ Task",      "Create task folders",                  "t", 0),
    (1000, "GET",         "Shot/task from the .blend · red = mismatch", "b", 0),
    (1064, "Folders",     "Open shot / task / subfolders",        "t", 0),
    (1136, "OPEN",        "Browse the task · arrow: recent",      "b", 1),
    (1265, "SAVE",        "Dialog · arrow: next version now",     "t", 1),
    (1422, "SET RENDER",  "Output to publish folder",             "b", 1),
    (1569, "SHOT NAME",   "Render named after dropdowns",         "t", 1),
    (1700, "Status",      "Last action, fixed width",             "b", 2),
    (2000, "History",     "Last 25 actions",                      "t", 2),
    (2042, "Setup",       "Shared with Max & Houdini",            "b", 2),
]
SECTIONS = [(227, 1082, "PIPELINE", 0), (1118, 1600, "SCENE ACTIONS", 1), (1648, 2062, "STATUS · SETUP", 2)]

def text_w(t, f): return f.getbbox(t)[2] if t else 0

def layout(items, W):
    """Left-aligned labels on leader lines; tiers chosen so no label overlaps another
    and no leader line crosses label text (same rules as the Max infographic)."""
    placed = []
    for x, lbl, desc, band, ci in sorted(items, key=lambda i: -i[0]):
        cx = PAD + x - X0
        w = max(text_w(lbl, f_lbl), text_w(desc, f_desc)) + 4
        x0 = cx - 1 if cx + w < W - 10 else cx - w + 1     # flip to right-aligned at the edge
        box = (x0 - 8, x0 + w + 8)
        tier = 0
        while True:
            ok = True
            for p in placed:
                if p["band"] != band: continue
                if p["tier"] == tier and not (box[1] < p["x0"] or box[0] > p["x1"]): ok = False
                if p["tier"] < tier and p["x0"] <= cx <= p["x1"]: ok = False
                if p["tier"] > tier and box[0] <= p["lx"] <= box[1]: ok = False
                if not ok: break
            if ok or tier >= 6: break
            tier += 1
        placed.append(dict(band=band, tier=tier, x0=box[0], x1=box[1], lx=cx, tx=x0, lbl=lbl, desc=desc, ci=ci))
    return placed

W = strip.width + 2 * PAD
placed = layout(ITEMS, W)
nt = max([p["tier"] for p in placed if p["band"] == "t"] + [0]) + 1
nb = max([p["tier"] for p in placed if p["band"] == "b"] + [0]) + 1
top, bot = 36 + nt * TIER, 36 + nb * TIER
pn = Image.new("RGB", (W, top + STRIP_H + bot), PANEL)
d = ImageDraw.Draw(pn)
sy = top
pn.paste(strip, (PAD, sy))
d.rectangle((PAD - 1, sy - 1, PAD + strip.width, sy + STRIP_H), outline="#3a3a3a")
for a, b, name, ci in SECTIONS:
    d.rectangle((PAD + a - X0, sy + STRIP_H + 3, PAD + b - X0, sy + STRIP_H + 6), fill=SECT[ci])
for p in placed:
    cx, col = p["lx"], SECT[p["ci"]]
    if p["band"] == "t":
        ty = sy - 18 - (p["tier"] + 1) * TIER + 4
        d.line((cx, ty + 42, cx, sy - 4), fill=LINE)
        d.ellipse((cx - 3, sy - 7, cx + 3, sy - 1), fill=col)
    else:
        ty = sy + STRIP_H + 18 + p["tier"] * TIER
        d.line((cx, sy + STRIP_H + 8, cx, ty), fill=LINE)
        d.ellipse((cx - 3, sy + STRIP_H + 2, cx + 3, sy + STRIP_H + 8), fill=col)
    d.text((p["tx"], ty), p["lbl"], font=f_lbl, fill=TXT)
    if p["desc"]: d.text((p["tx"], ty + 20), p["desc"], font=f_desc, fill=DIM)

HEAD = 110
out = Image.new("RGB", (W, HEAD + pn.height + 40), BG)
d = ImageDraw.Draw(out)
d.text((PAD, 28), "Studio Toolbar for Blender", font=f_title, fill=TXT)
d.text((PAD, 68), "v0.3 — in the 3D View's tool settings bar, below the menus. "
                  "Same pipeline, config and Setup as Max and Houdini.", font=f_sub, fill=DIM)
lx = W - PAD
for name, ci in reversed([(n, c) for *_, n, c in SECTIONS]):
    w = text_w(name, f_head)
    lx -= w
    d.text((lx, 30), name, font=f_head, fill=TXT)
    d.rectangle((lx - 22, 36, lx - 8, 50), fill=SECT[ci])
    lx -= 46
out.paste(pn, (0, HEAD))
out.save(OUT, optimize=True)
print(out.size)
