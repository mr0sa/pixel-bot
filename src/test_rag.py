#!/usr/bin/env python3
"""
ragna_bot_v11b.py — debug de teclas em tempo real
─────────────────────────────────────────────────
Idêntico ao v11a, mas:
  • key_tap() faz print imediato: [KEY 12:34:56] f3
  • Mantém coleta, OCR, crítico, timeout, INSERT debounce, etc.
"""

import cv2, time, random, threading, re, sys
import win32api, win32gui
import interception, pytesseract
from ultralytics import YOLO
from pathlib import Path
from collections import deque

# ANSI colors for debug
RED    = "\033[31m"
BLUE   = "\033[34m"
RESET  = "\033[0m"


# ───────── ajustes rápidos ────────
TESS_PATH  = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
MODEL_PATH = "best.pt"
# ──────────────────────────────────

pytesseract.pytesseract.tesseract_cmd = TESS_PATH

# ── BOT CONFIG ─────────────────────────────────
IMG_SZ = 416; FRAME_SKIP = 2
CONF_THRES = 0.70; IOU_THRES = 0.50
JITTER_PX = 4
COOL_CARD, COOL_BAPH = 0.10, 0.35
TIME_LONG, TIME_SHORT = 3.0, 1.0
FAILSAFE_PX = 10; GAME_TITLE = "Ragnarok"
F2_COOLDOWN = 0.5
PROFILE_EVERY = 2.0
# Timeout dinâmico
WALK_SPEED_PX = 150; BASE_TO = 1.2; MAX_TO = 5.0
# INSERT debounce
INSERT_COOLDOWN = 2.0
# OCR
CROP=(6,37,160,50); UPSCALE=3; OCR_SKIP=6
OCR_CFG=r"--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789HPSPhpsp/|:."
HP_CRIT,SP_CRIT = 40, 20
HP_HYST = HP_CRIT + 10
SP_HYST = SP_CRIT + 10
# Dataset capture
CAPTURE_DIR=Path("captured_dataset")
for sub in ("images","labels","preview"):
    (CAPTURE_DIR/sub).mkdir(parents=True,exist_ok=True)
CAPTURE_EVERY=15.0; last_capture=0.0

# card counter for debug
card_count = 0
# ───────────────────────────────────────────────

# ========== Interception & real-time key log ==========
interception.auto_capture_devices()

def click_abs(x,y):
    x+=random.randint(-JITTER_PX,JITTER_PX); y+=random.randint(-JITTER_PX,JITTER_PX)
    interception.move_to(int(x),int(y))
    interception.click(int(x),int(y),"left",delay=0.02)

def key_tap(k,ms=20):
    k=k.lower()
    # print em tempo real
    ts = time.strftime("%H:%M:%S", time.localtime())
    print(f"[KEY {ts}] {k}")
    if hasattr(interception,"press"):
        interception.press(k)
    elif hasattr(interception,"hold_key"):
        interception.hold_key(k,ms/1000)
    else:
        interception.key_down(k)
        time.sleep(ms/1000)
        interception.key_up(k)

# INSERT helper
last_insert=0.0; sitting=False
def do_insert():
    global last_insert,sitting
    if time.time()-last_insert >= INSERT_COOLDOWN:
        key_tap("insert")
        last_insert = time.time()
        sitting = not sitting
        return True
    return False

# ========== Janela & YOLO setup ==========
def get_game_rect():
    hwnd=win32gui.FindWindow(None,GAME_TITLE)
    if not hwnd: raise RuntimeError("Janela não encontrada")
    l,t,r,b=win32gui.GetClientRect(hwnd)
    ls,ts=win32gui.ClientToScreen(hwnd,(l,t))
    return ls,ts,r-l,b-t

win_x0,win_y0,GAME_W,GAME_H = get_game_rect()

model = YOLO(MODEL_PATH)
cap = cv2.VideoCapture(0,cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH,1920)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT,1080)
cap.set(cv2.CAP_PROP_BUFFERSIZE,1); time.sleep(0.2)
assert cap.isOpened()

VCW,VCH = int(cap.get(3)), int(cap.get(4))
SX,SY   = GAME_W/VCW, GAME_H/VCH
cx_mid,cy_mid = VCW/2, VCH/2
d_max = (VCW**2 + VCH**2)**0.5
λ = 0.4

def in_corner():
    x,y=win32api.GetCursorPos()
    return x<FAILSAFE_PX and y<FAILSAFE_PX

# ---------- F2 & click logic ----------
last_f2=0.0
def do_f2():
    global last_f2,current_timeout,last_event
    if time.time()-last_f2 < F2_COOLDOWN:
        return False
    if sitting:
        do_insert(); time.sleep(0.05)
    key_tap("f2")
    last_f2 = time.time()
    current_timeout = TIME_SHORT
    last_event = last_f2
    return True

last_card=last_baph=0.0
def do_click(cx,cy,is_card):
    global last_card,last_baph,last_event,current_timeout
    now = time.time()
    if is_card:
        if now-last_card < COOL_CARD: return
        click_abs(cx,cy); last_card=now; current_timeout=TIME_LONG
    else:
        if now-last_baph < COOL_BAPH: return
        key_tap("f3"); time.sleep(0.05); click_abs(cx,cy); last_baph=now
        dx = abs(cx - (win_x0+GAME_W/2))
        dy = abs(cy - (win_y0+GAME_H/2))
        walk = ((dx*dx+dy*dy)**0.5)/WALK_SPEED_PX
        current_timeout = min(MAX_TO, BASE_TO+walk)
    last_event = now

# ---------- dataset capture ----------
def save_sample(frame_bgr, detections):
    ts = str(int(time.time()*1000))
    img_p = CAPTURE_DIR/"images"/f"{ts}.jpg"
    prev_p = CAPTURE_DIR/"preview"/f"{ts}.jpg"
    lbl_p = CAPTURE_DIR/"labels"/f"{ts}.txt"
    cv2.imwrite(str(img_p), frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY),90])
    prev = frame_bgr.copy()
    colors = {0:(255,0,0),1:(0,255,0),2:(0,0,255)}
    h,w = frame_bgr.shape[:2]
    with lbl_p.open("w") as f:
        for cls,(x1,y1,x2,y2) in detections:
            cv2.rectangle(prev,(x1,y1),(x2,y2),colors[cls],2)
            cv2.putText(prev,str(cls),(x1,y1-4),cv2.FONT_HERSHEY_SIMPLEX,0.5,colors[cls],1)
            cx=(x1+x2)/2/w; cy=(y1+y2)/2/h; bw=(x2-x1)/w; bh=(y2-y1)/h
            f.write(f"{cls} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
    cv2.imwrite(str(prev_p), prev, [int(cv2.IMWRITE_JPEG_QUALITY),90])

def save_sample_card(frame_bgr, detections):
    ts = str(int(time.time()*1000))
    img_p = CAPTURE_DIR/"cards/images"/f"{ts}.jpg"
    prev_p = CAPTURE_DIR/"cards/preview"/f"{ts}.jpg"
    lbl_p = CAPTURE_DIR/"cards/labels"/f"{ts}.txt"
    cv2.imwrite(str(img_p), frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY),90])
    prev = frame_bgr.copy()
    colors = {0:(255,0,0),1:(0,255,0),2:(0,0,255)}
    h,w = frame_bgr.shape[:2]
    with lbl_p.open("w") as f:
        for cls,(x1,y1,x2,y2) in detections:
            cv2.rectangle(prev,(x1,y1),(x2,y2),colors[cls],2)
            cv2.putText(prev,str(cls),(x1,y1-4),cv2.FONT_HERSHEY_SIMPLEX,0.5,colors[cls],1)
            cx=(x1+x2)/2/w; cy=(y1+y2)/2/h; bw=(x2-x1)/w; bh=(y2-y1)/h
            f.write(f"{cls} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
    cv2.imwrite(str(prev_p), prev, [int(cv2.IMWRITE_JPEG_QUALITY),90])

# ---------- state & regex ----------
last_event = time.time()
current_timeout = TIME_LONG
critical=False
hp_cur=hp_max=sp_cur=sp_max=0

re_hp = re.compile(r"HP[:\.]?\s*(\d+)\s*/\s*(\d+)", re.I)
re_sp = re.compile(r"SP[:\.]?\s*(\d+)\s*/\s*(\d+)", re.I)

cap_t,inf_t,log_t = deque(maxlen=120), deque(maxlen=120), deque(maxlen=120)

def main():
    global critical,sitting,last_event,current_timeout,last_capture, card_count
    fid, last_print = 0, time.time()

    while True:
        if in_corner(): break
        t0 = time.perf_counter()
        ok, frame = cap.read()
        cap_t.append((time.perf_counter()-t0)*1000)
        if not ok: continue

        # OCR
        if fid % (FRAME_SKIP*OCR_SKIP) == 0:
            x1,y1,x2,y2 = CROP
            crop = cv2.resize(frame[y1:y2,x1:x2], None, fx=UPSCALE, fy=UPSCALE,
                              interpolation=cv2.INTER_LINEAR)
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            _, bw = cv2.threshold(gray,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
            txt = pytesseract.image_to_string(bw, config=OCR_CFG)
            m_hp, m_sp = re_hp.search(txt), re_sp.search(txt)
            if m_hp and m_sp:
                hp_cur,hp_max = map(int,m_hp.groups())
                sp_cur,sp_max = map(int,m_sp.groups())
                hp_pct = hp_cur/hp_max*100
                sp_pct = sp_cur/sp_max*100
                prev = critical
                if not prev:
                    # entra em crítico se ultrapassar limite original
                    critical = (hp_pct < HP_CRIT) or (sp_pct < SP_CRIT)
                else:
                    # sai do crítico apenas se acima do limite com histerese
                    critical = not (hp_pct >= HP_HYST and sp_pct >= SP_HYST)
                if critical != prev:
                    print(("⚠️ CRÍTICO" if critical else "✅ RECUPERADO"),
                          f"HP {hp_pct:.0f}% SP {sp_pct:.0f}%")

        # Detection + logic
        if fid % FRAME_SKIP == 0:
            t1 = time.perf_counter()
            res = model(frame, imgsz=IMG_SZ, conf=CONF_THRES, iou=IOU_THRES, verbose=False)[0]
            inf_t.append((time.perf_counter()-t1)*1000)

            baph_ct=fly_ct=0
            card_dets=[]; baph_dets=[]; fly_dets=[]
            for box,cls,conf in zip(res.boxes.xyxy, res.boxes.cls, res.boxes.conf):
                cls_i = int(cls); tup=(float(conf),box)
                if cls_i==1: card_dets.append(tup)
                elif cls_i==0: baph_dets.append(tup); baph_ct+=1
                elif cls_i==2: fly_dets.append(tup); fly_ct+=1
            total_ct = baph_ct + fly_ct

            # dataset capture
            if baph_ct>0 and (card_dets or fly_dets) and time.time()-last_capture>CAPTURE_EVERY:
                dets = []
                for c,b in baph_dets: dets.append((0,tuple(map(int,b))))
                for c,b in card_dets: dets.append((1,tuple(map(int,b))))
                for c,b in fly_dets:  dets.append((2,tuple(map(int,b))))
                save_sample(frame.copy(), dets)
                last_capture = time.time()

            # main logic
            if critical:
                # Enquanto houver monstros, só teleporta (do_f2 já levanta se preciso)
                if total_ct > 0:
                    do_f2()
                # Quando a sala estiver vazia, senta uma única vez
                elif not sitting:
                    do_insert()
            else:
                if sitting: do_insert()
                if (baph_ct>=3 or fly_ct>=5 or total_ct>=6): do_f2()

                if card_dets:
                    conf,box = max(card_dets, key=lambda d:d[0])
                    x1,y1,x2,y2 = map(int,box)
                    do_click(win_x0+int(((x1+x2)//2)*SX),
                             win_y0+int(((y1+y2)//2)*SY), True)

                    card_count += 1
                    dets_cards = [(1, (x1,y1,x2,y2))]
                    save_sample_card(frame.copy(), dets_cards)

                elif baph_dets:
                    if len(baph_dets)>1:
                        def score(d):
                            conf,box=d
                            x1,y1,x2,y2=map(int,box)
                            cx,cy=(x1+x2)/2,(y1+y2)/2
                            return conf - λ*((cx-cx_mid)**2+(cy-cy_mid)**2)**0.5/d_max
                        conf,box = max(baph_dets, key=score)
                    else:
                        conf,box = baph_dets[0]
                    x1,y1,x2,y2 = map(int,box)
                    do_click(win_x0+int(((x1+x2)//2)*SX),
                             win_y0+int(((y1+y2)//2)*SY), False)

                if time.time()-last_event>current_timeout:
                    do_f2()

        # DEBUG periodic
        if time.time()-last_print > PROFILE_EVERY:
            ac=sum(cap_t)/len(cap_t) if cap_t else 0
            ai=sum(inf_t)/len(inf_t) if inf_t else 0
            al=sum(log_t)/len(log_t) if log_t else 0
            fps=1000/(ac+ai+al) if ac+ai+al else 0
            print(
                f"[DBG] fps={fps:4.1f} | cap={ac:4.1f}ms | infer={ai:6.1f}ms | "
                f"log={al:5.1f}ms | HP={hp_cur}/{hp_max} ({hp_pct:.0f}%) | "
                f"SP={sp_cur}/{sp_max} ({sp_pct:.0f}%) | crit={critical} "
                f"sit={sitting} | cards={card_count}"
            )
            last_print=time.time()

        fid += 1

    cap.release()
    cv2.destroyAllWindows()

if __name__=="__main__":
    print("🚀 BOT v11b – ESC ou cursor ≤10 px canto encerra")
    threading.Thread(target=main, daemon=False).start()
