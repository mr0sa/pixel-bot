#!/usr/bin/env python3
"""
ocr_hp_sp.py  –  mostra a Virtual Cam e lê HP/SP por OCR
────────────────────────────────────────────────────────
Uso:
    python ocr_hp_sp.py [index]
ESC fecha.
"""

import sys, time, re, cv2, pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

CAM_IDX   = int(sys.argv[1]) if len(sys.argv) > 1 else 0
W, H      = 1920, 1080
X1, Y1, X2, Y2 = 6, 37, 160, 50          # retângulo HP/SP
UPSCALE   = 3                            # amplia 3× antes do OCR
CFG_OCR   = r"--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789HPSPhpsp/|:."

cap = cv2.VideoCapture(CAM_IDX, cv2.CAP_DSHOW)
if not cap.isOpened():
    sys.exit("✖️  Não abriu a Virtual Cam")

cap.set(cv2.CAP_PROP_FRAME_WIDTH,  W)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
time.sleep(0.2)

print("✅ VirtualCam:", int(cap.get(3)), "×", int(cap.get(4)))

cv2.namedWindow("Cam",  cv2.WINDOW_NORMAL)
cv2.namedWindow("Crop", cv2.WINDOW_NORMAL)

pat = re.compile(r"HP[:\.]?\s*(\d+)\s*/\s*(\d+).*?SP[:\.]?\s*(\d+)\s*/\s*(\d+)",
                 flags=re.I)

while True:
    ok, frame = cap.read()
    if not ok:
        break
    cv2.imshow("Cam", frame)

    crop = frame[Y1:Y2, X1:X2]
    # ---------- pré-processamento ----------
    crop_up = cv2.resize(crop, None, fx=UPSCALE, fy=UPSCALE,
                         interpolation=cv2.INTER_LINEAR)
    gray = cv2.cvtColor(crop_up, cv2.COLOR_BGR2GRAY)
    _, bw = cv2.threshold(gray, 0, 255,
                          cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    cv2.imshow("Crop", bw)

    text = pytesseract.image_to_string(bw, config=CFG_OCR).strip()
    m = pat.search(text)
    if m:
        hp_cur, hp_max, sp_cur, sp_max = map(int, m.groups())
        print(f"HP {hp_cur}/{hp_max}  |  SP {sp_cur}/{sp_max}")
    else:
        print("HP/SP: --")

    if cv2.waitKey(1) & 0xFF == 27:   # ESC fecha
        break

cap.release()
cv2.destroyAllWindows()
