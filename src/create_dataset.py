#!/usr/bin/env python3
"""
make_split.py  –  copy/organise corrected samples into YOLO train/val folders
---------------------------------------------------------------------------
Usage
    python make_split.py
    python make_split.py --train 0.85        # 85 % train, 15 % val
    python make_split.py --clean             # remove previous split first
---------------------------------------------------------------------------
Folder layout *before* running:

project/
├─ captured_dataset/
│   ├─ images/     img001.jpg ...
│   └─ labels/     img001.txt ...
└─ ragnarok-dataset/
    └─ (train/val folders will be created here)

The script copies files (not symlinks) so it works on Windows without
admin privileges.
"""
import argparse, random, shutil
from pathlib import Path

ROOT   = Path(__file__).resolve().parent
SRC_I  = ROOT / "../captured_dataset" / "images"
SRC_L  = ROOT / "../captured_dataset" / "labels"
DST    = ROOT / "../ragnarok-dataset-new"

def parse():
    ap = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument("--train", type=float, default=0.9,
                    help="fraction to go into train split")
    ap.add_argument("--seed",  type=int,   default=0,
                    help="random seed (reproducible shuffle)")
    ap.add_argument("--clean", action="store_true",
                    help="remove existing train/val folders before copying")
    return ap.parse_args()

def rm_tree(p: Path):
    if p.exists(): shutil.rmtree(p)

def ensure_dirs():
    for sub in ["images/train","images/val","labels/train","labels/val"]:
        (DST / sub).mkdir(parents=True, exist_ok=True)

def main():
    args = parse()
    train_frac = max(0.01, min(0.99, args.train))

    if args.clean:
        print("🧹  Removing previous split in ragnarok-dataset …")
        rm_tree(DST / "images" / "train")
        rm_tree(DST / "images" / "val")
        rm_tree(DST / "labels" / "train")
        rm_tree(DST / "labels" / "val")

    ensure_dirs()

    imgs = sorted(SRC_I.glob("*.jpg"))
    if not imgs:
        raise SystemExit("❌  No images found in captured_dataset/images")

    random.seed(args.seed)
    random.shuffle(imgs)
    split_at = int(len(imgs) * train_frac)
    train_set, val_set = imgs[:split_at], imgs[split_at:]

    def copy_set(files, split):
        for img in files:
            base = img.stem
            lbl  = SRC_L / f"{base}.txt"
            if not lbl.exists():
                print(f"⚠️   Skipping {base}: missing label")
                continue
            shutil.copy2(img,  DST / "images" / split / img.name)
            shutil.copy2(lbl,  DST / "labels" / split / lbl.name)

    print(f"📂  Copying {len(train_set)} → train, {len(val_set)} → val …")
    copy_set(train_set, "train")
    copy_set(val_set, "val")
    print("✅  Done.  Structure:")
    for sub in ["images/train","images/val","labels/train","labels/val"]:
        n = len(list((DST/sub).glob("*.jpg"))) if "images" in sub else len(list((DST/sub).glob("*.txt")))
        print(f"  {sub:18} : {n} files")

if __name__ == "__main__":
    main()
