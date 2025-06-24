# remove_bg.py
#
# Varre a pasta sprites/ , cria sprites_clean/ com fundo transparente.
# Ajuste WHITE_THR se o fundo não for totalmente #FFFFFF.

import glob, os
from pathlib import Path
from PIL import Image

SRC_DIR  = "sprites"
DST_DIR  = "sprites_clean"
WHITE_THR = 240        # pixel é considerado branco se R,G,B ≥ 240 (0–255)

Path(DST_DIR).mkdir(exist_ok=True)

for p in glob.glob(os.path.join(SRC_DIR, "*.png")):
    img = Image.open(p).convert("RGBA")
    data = img.getdata()

    new_data = []
    for r, g, b, a in data:
        if r >= WHITE_THR and g >= WHITE_THR and b >= WHITE_THR:
            # torna 100 % transparente
            new_data.append((r, g, b, 0))
        else:
            new_data.append((r, g, b, a))

    img.putdata(new_data)
    out_path = os.path.join(DST_DIR, os.path.basename(p))
    img.save(out_path)

print("✅ Sprites limpos salvos em", DST_DIR)
