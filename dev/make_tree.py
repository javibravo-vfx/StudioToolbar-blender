"""Build a fake pipeline tree for tests:  <root>/VFX-MOR/010/MOR_010_0010/3D/2_model/…"""
import os, sys, time
def make(root):
    for proj, seqs in {"MOR": ["010", "020"], "SHR": ["100"]}.items():
        pdir = os.path.join(root, f"VFX-{proj}")
        for x in ("3D", "FOOTAGE"): os.makedirs(os.path.join(pdir, x), exist_ok=True)
        for s in seqs:
            for n in (10, 20, 30):
                shot = os.path.join(pdir, s, f"{proj}_{s}_{n:04d}")
                os.makedirs(os.path.join(shot, "comp"), exist_ok=True)
                for t in ("2_model", "7_fx"):
                    for sub in ("1_projects/textures", "2_review", "3_publish"):
                        os.makedirs(os.path.join(shot, "3D", t, sub), exist_ok=True)
    os.makedirs(os.path.join(root, "VFX-MOR", "010", "notashot"), exist_ok=True)
    sc = os.path.join(root, "VFX-MOR", "010", "MOR_010_0010", "3D", "7_fx", "1_projects")
    for i, f in enumerate(["MOR_010_0010_fx_v001.hip", "MOR_010_0010_fx_v002.hiplc",
                           "MOR_010_0010_fx_v001.blend", "MOR_010_0010_fx_v003.max"]):
        p = os.path.join(sc, f); open(p, "w").close(); os.utime(p, (time.time() + i, time.time() + i))
    return root
if __name__ == "__main__": make(sys.argv[1])
