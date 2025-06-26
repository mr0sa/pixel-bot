# make_dataset_multi.py
import random, glob, os
from pathlib import Path
from PIL import Image

OUT_W, OUT_H = 1280, 720
N_IMAGES = 800     # total
TRAIN_SPLIT = 0.8

random.seed(42)
bg_list = glob.glob("../ragnarok-dataset/backgrounds/*")
class_dirs = sorted([d for d in glob.glob("../ragnarok-dataset/sprites/*") if os.path.isdir(d)])
class2idx = {os.path.basename(d): i for i, d in enumerate(class_dirs)}
print("Classes:", class2idx)

# saída
for sub in ("../ragnarok-dataset/images/train", "../ragnarok-dataset/images/val", "../ragnarok-dataset/labels/train", "../ragnarok-dataset/labels/val"):
    Path(sub).mkdir(parents=True, exist_ok=True)

def place_sprite(bg_img, sp_img):
    bg = bg_img.convert("RGBA").resize((OUT_W, OUT_H))
    scale = random.uniform(0.6, 1.1)
    sp = sp_img.resize((int(sp_img.width*scale), int(sp_img.height*scale)), Image.LANCZOS).convert("RGBA")
    max_x, max_y = OUT_W - sp.width, OUT_H - sp.height
    x0, y0 = random.randint(0, max_x), random.randint(0, max_y)
    bg.alpha_composite(sp, (x0, y0))
    cx, cy = (x0 + sp.width/2)/OUT_W, (y0 + sp.height/2)/OUT_H
    w, h = sp.width/OUT_W, sp.height/OUT_H
    return bg.convert("RGB"), (cx, cy, w, h)

for idx in range(N_IMAGES):
    bg = Image.open(random.choice(bg_list))
    cls_dir = random.choice(class_dirs)
    cls_name = os.path.basename(cls_dir)
    sp = Image.open(random.choice(glob.glob(f"{cls_dir}/*")))
    img, (cx, cy, w, h) = place_sprite(bg, sp)

    split = "train" if random.random() < TRAIN_SPLIT else "val"
    img_name = f"synt_{idx:05}.jpg"
    lbl_name = img_name.replace(".jpg", ".txt")

    img.save(f"../ragnarok-dataset/images/{split}/{img_name}", quality=90)
    with open(f"../ragnarok-dataset/labels/{split}/{lbl_name}", "w") as f:
        f.write(f"{class2idx[cls_name]} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")

print("✅ Dataset multi-classe gerado com", len(class_dirs), "classes.")
