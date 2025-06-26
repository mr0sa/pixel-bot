#!/usr/bin/env python3
"""
ragna_bot_v12.py  –  8-class model with per-class actions
────────────────────────────────────────────────────────────────────────────
Model class indices
  0 blue     – optional attack (F3+click)   → ATTACK_BLUE switch
  1 cyan     – optional attack (F3+click)   → ATTACK_CYAN
  2 green    – ignore
  3 orange   – optional attack (F3+click)   → ATTACK_ORANGE
  4 pink     – card  (left-click only)      → always
  5 purple   – count, ignore
  6 red      – avoid; if red_count ≥ RED_F2_THRESHOLD → press F2
  7 yellow   – optional attack (F3+click)   → ATTACK_YELLOW

All previous mechanics preserved:
  • HP-critical vs SP-critical states
  • Insert after safe room, F2 teleport, debounced by last F2
  • Dynamic timeout after walking
  • Dataset capture (samples + separate “cards” folder)
  • Live key prints, debug FPS print
"""

import cv2, time, random, threading, re, sys
import win32api, win32gui
import interception, pytesseract
from ultralytics import YOLO
from pathlib import Path
from collections import deque

# ─────────────── user switches ────────────────────────────────────────────
ATTACK_BLUE   = True   # class-0
ATTACK_CYAN   = True   # class-1
ATTACK_ORANGE = True   # class-3
ATTACK_YELLOW = True   # class-7
RED_F2_THRESHOLD = 4   # press F2 if ≥ this many red (class-6) blobs
# ──────────────────────────────────────────────────────────────────────────

# quick paths
TESS_PATH  = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
MODEL_PATH = "models/best_v12n2.pt"
pytesseract.pytesseract.tesseract_cmd = TESS_PATH

# ── BOT CONFIG (unchanged from v11) ───────────────────────────────────────
IMG_SZ = 416 
FRAME_SKIP = 1
CONF_THRES = 0.70 
IOU_THRES = 0.50
JITTER_PX  = 4
COOL_CARD, COOL_ATT = 0.10, 0.35        # debounce times
TIME_LONG, TIME_SHORT = 3.0, 1.0
FAILSAFE_PX = 10 
GAME_TITLE = "Ragnarok"
F2_COOLDOWN = 0.5
PROFILE_EVERY = 2.0
WALK_SPEED_PX = 90 
BASE_TO = 1.2 
MAX_TO = 5.0
INSERT_DELAY_AFTER_F2 = 0.6
# OCR
CROP=(6,37,160,50); UPSCALE=3; OCR_SKIP=6
OCR_CFG=r"--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789HPSPhpsp/|:."
HP_CRIT,  SP_CRIT  = 40, 20
HP_HYST,  SP_HYST  = HP_CRIT+10, SP_CRIT+10
# dataset capture
CAPTURE_DIR = Path("captured_dataset")
for sub in ("images","labels","preview",
            "cards/images","cards/preview","cards/labels"):
    (CAPTURE_DIR/sub).mkdir(parents=True, exist_ok=True)
CAPTURE_EVERY = 3.0        # seconds
# ──────────────────────────────────────────────────────────────────────────

# ═════════ interception helpers ══════════════════════════════════════════
interception.auto_capture_devices()
def click_abs(x,y):
    x+=random.randint(-JITTER_PX,JITTER_PX); y+=random.randint(-JITTER_PX,JITTER_PX)
    interception.move_to(int(x),int(y))
    interception.click(int(x),int(y),"left",delay=0.02)

def key_tap(k,ms=20):
    ts=time.strftime("%H:%M:%S",time.localtime())
    print(f"[KEY {ts}] {k.lower()}")
    if hasattr(interception,"press"): interception.press(k)
    elif hasattr(interception,"hold_key"): interception.hold_key(k,ms/1000)
    else: interception.key_down(k); time.sleep(ms/1000); interception.key_up(k)

# ═════════ Insert / F2 helpers ═══════════════════════════════════════════
sitting = False
last_f2 = 0.0
def do_insert():
    global sitting
    if time.time()-last_f2 < INSERT_DELAY_AFTER_F2: return False
    key_tap("insert"); sitting = not sitting; return True

current_timeout = TIME_LONG
last_event      = time.time()
def do_f2():
    global last_f2,current_timeout,last_event
    if time.time()-last_f2 < F2_COOLDOWN: return False
    if sitting: do_insert(); time.sleep(0.05)
    key_tap("f2")
    last_f2 = time.time(); current_timeout = TIME_SHORT; last_event = last_f2
    return True

# ═════════ click / attack helpers ════════════════════════════════════════
last_card = last_att = 0.0
def attack_target(scr_x,scr_y):
    global last_att,current_timeout,last_event
    if time.time()-last_att < COOL_ATT: return
    key_tap("f3"); time.sleep(0.05); click_abs(scr_x,scr_y)
    last_att=time.time()
    dx=abs(scr_x-(win_x0+GAME_W/2)); dy=abs(scr_y-(win_y0+GAME_H/2))
    walk=((dx*dx+dy*dy)**0.5)/WALK_SPEED_PX
    current_timeout = min(MAX_TO, BASE_TO+walk); last_event=time.time()

def click_card(scr_x,scr_y):
    global last_card,current_timeout,last_event
    if time.time()-last_card < COOL_CARD: return
    click_abs(scr_x,scr_y); last_card=time.time()
    current_timeout=TIME_LONG; last_event=last_card

# ═════════ window / model init ═══════════════════════════════════════════
def get_game_rect():
    hwnd=win32gui.FindWindow(None,GAME_TITLE)
    if not hwnd: raise RuntimeError("Game window not found")
    l,t,r,b=win32gui.GetClientRect(hwnd); ls,ts=win32gui.ClientToScreen(hwnd,(l,t))
    return ls,ts,r-l,b-t
win_x0,win_y0,GAME_W,GAME_H = get_game_rect()

model=YOLO(MODEL_PATH)
cap=cv2.VideoCapture(0,cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH,1920); cap.set(cv2.CAP_PROP_FRAME_HEIGHT,1080)
cap.set(cv2.CAP_PROP_BUFFERSIZE,1); time.sleep(0.2); assert cap.isOpened()
VCW,VCH=int(cap.get(3)),int(cap.get(4)); SX,SY=GAME_W/VCW, GAME_H/VCH
cx_mid,cy_mid=VCW/2,VCH/2; d_max=(VCW**2+VCH**2)**0.5; λ=0.4
def in_corner(): x,y=win32api.GetCursorPos(); return x<FAILSAFE_PX and y<FAILSAFE_PX

# ═════════ dataset-capture helpers ═══════════════════════════════════════
def save_sample(frame_bgr, detections, folder=""):
    ts=str(int(time.time()*1000))
    if folder: folder=f"{folder}/"
    img_p = CAPTURE_DIR/f"{folder}images"/f"{ts}.jpg"
    prev_p= CAPTURE_DIR/f"{folder}preview"/f"{ts}.jpg"
    lbl_p = CAPTURE_DIR/f"{folder}labels"/f"{ts}.txt"
    cv2.imwrite(str(img_p), frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY),90])
    prev=frame_bgr.copy(); h,w=prev.shape[:2]
    colors={0:(255,0,0),1:(255,128,0),2:(0,255,0),3:(0,128,255),
            4:(255,0,255),5:(128,0,255),6:(0,0,255),7:(255,255,0)}
    with lbl_p.open("w") as f:
        for cls,(x1,y1,x2,y2) in detections:
            cv2.rectangle(prev,(x1,y1),(x2,y2),colors.get(cls,(255,255,255)),2)
            f.write(f"{cls} {(x1+x2)/2/w:.6f} {(y1+y2)/2/h:.6f} {(x2-x1)/w:.6f} {(y2-y1)/h:.6f}\n")
    cv2.imwrite(str(prev_p),prev,[int(cv2.IMWRITE_JPEG_QUALITY),90])

# ═════════ OCR regex ═════════════════════════════════════════════════════
hp_crit=sp_crit=False; hp_cur=hp_max=sp_cur=sp_max=0
re_hp=re.compile(r"HP[:\.]?\s*(\d+)\s*/\s*(\d+)",re.I)
re_sp=re.compile(r"SP[:\.]?\s*(\d+)\s*/\s*(\d+)",re.I)

# ═════════ debug deques ══════════════════════════════════════════════════
cap_t,inf_t,log_t=deque(maxlen=120),deque(maxlen=120),deque(maxlen=120)
last_capture=0.0; card_count=0

# ═════════════════════════ MAIN LOOP ═════════════════════════════════════
def main():
    global hp_crit,sp_crit,sitting,last_event,current_timeout,last_capture,card_count
    fid,last_dbg=0,time.time()

    while True:
        if in_corner(): break
        t0=time.perf_counter(); ok,frame=cap.read()
        cap_t.append((time.perf_counter()-t0)*1000);  # capture time
        if not ok: continue

        # ─── OCR HP/SP every n frames ───────────────────────────────────
        if fid%(FRAME_SKIP*OCR_SKIP)==0:
            x1,y1,x2,y2=CROP
            crop=cv2.resize(frame[y1:y2,x1:x2],None,fx=UPSCALE,fy=UPSCALE,interpolation=cv2.INTER_LINEAR)
            gray=cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY)
            _,bw=cv2.threshold(gray,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
            txt=pytesseract.image_to_string(bw,config=OCR_CFG)
            m_hp,m_sp=re_hp.search(txt),re_sp.search(txt)
            if m_hp and m_sp:
                hp_cur,hp_max=map(int,m_hp.groups()); sp_cur,sp_max=map(int,m_sp.groups())
                hp_pct,sp_pct=hp_cur/hp_max*100, sp_cur/sp_max*100
                prev_hp,prev_sp=hp_crit,sp_crit
                hp_crit = hp_pct<HP_CRIT if not hp_crit else not (hp_pct>=HP_HYST)
                sp_crit = sp_pct<SP_CRIT if not sp_crit else not (sp_pct>=SP_HYST)
                if hp_crit!=prev_hp: print("⚠️ HP CRIT" if hp_crit else "✅ HP ok",f"({hp_pct:.0f}%)")
                if sp_crit!=prev_sp: print("⚠️ SP CRIT" if sp_crit else "✅ SP ok",f"({sp_pct:.0f}%)")

        # ─── Detection every FRAME_SKIP ─────────────────────────────────
        if fid%FRAME_SKIP==0:
            t1=time.perf_counter()
            res=model(frame,imgsz=IMG_SZ,conf=CONF_THRES,iou=IOU_THRES,verbose=False)[0]
            inf_t.append((time.perf_counter()-t1)*1000)   # inference time

            red_ct=0; purple_ct=0
            cards=[]; atks=[]; det_for_ds=[]
            for box,cls,conf in zip(res.boxes.xyxy,res.boxes.cls,res.boxes.conf):
                cls=int(cls); box=tuple(map(int,box))
                if   cls==4: cards.append((conf,box)); det_for_ds.append((cls,box))
                elif cls==6: red_ct+=1;                det_for_ds.append((cls,box))
                elif cls==5: purple_ct+=1;             det_for_ds.append((cls,box))
                elif cls==0 and ATTACK_BLUE  : atks.append((conf,box)); det_for_ds.append((cls,box))
                elif cls==1 and ATTACK_CYAN  : atks.append((conf,box)); det_for_ds.append((cls,box))
                elif cls==3 and ATTACK_ORANGE: atks.append((conf,box)); det_for_ds.append((cls,box))
                elif cls==7 and ATTACK_YELLOW: atks.append((conf,box)); det_for_ds.append((cls,box))

            # dataset capture (generic) every CAPTURE_EVERY
            if atks and time.time()-last_capture > CAPTURE_EVERY:
                save_sample(frame.copy(), det_for_ds)
                last_capture=time.time()

            # ── red swarm avoidance ────────────────────────────────────
            if red_ct >= RED_F2_THRESHOLD: do_f2()

            # ── CRITICAL HP logic ──────────────────────────────────────
            if hp_crit:
                if red_ct or atks: do_f2()
                elif not sitting:  do_insert()
            else:
                if sitting: do_insert()

                # ---- card (pink) first priority ----------------------
                if cards:
                    _,box=max(cards,key=lambda d:d[0]); x1,y1,x2,y2=box
                    click_card(win_x0+int(((x1+x2)//2)*SX),
                               win_y0+int(((y1+y2)//2)*SY))
                    card_count+=1
                    save_sample(frame.copy(), [(4,box)], folder="cards")

                # ---- attacks ----------------------------------------
                # ---- SP critical: ONLY simple click (no F3) ----------
                elif sp_crit and atks and not sitting:
                    # choose best target (nearest-strongest same as below)
                    if len(atks) > 1:
                        def score_sp(d):
                            conf, box = d
                            x1, y1, x2, y2 = box
                            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                            return conf - λ * ((cx - cx_mid) ** 2 + (cy - cy_mid) ** 2) ** 0.5 / d_max
                        _, box = max(atks, key=score_sp)
                    else:
                        _, box = atks[0]

                    x1, y1, x2, y2 = box
                    click_abs(
                        win_x0 + int(((x1 + x2) // 2) * SX),
                        win_y0 + int(((y1 + y2) // 2) * SY)
                    )
                    current_timeout = TIME_LONG
                    last_event      = time.time()

                # ---- normal attacks (F3 + click) ---------------------
                elif atks and not sitting:
                    if len(atks)>1:
                        def score(d):
                            conf,box=d; x1,y1,x2,y2=box
                            cx,cy=(x1+x2)/2,(y1+y2)/2
                            return conf-λ*((cx-cx_mid)**2+(cy-cy_mid)**2)**0.5/d_max
                        _,box=max(atks,key=score)
                    else: _,box=atks[0]
                    x1,y1,x2,y2=box
                    attack_target(win_x0+int(((x1+x2)//2)*SX),
                                  win_y0+int(((y1+y2)//2)*SY))

                # timeout teleport
                if time.time()-last_event > current_timeout: do_f2()

        # ─── periodic debug print ───────────────────────────────────────
        if time.time()-last_dbg > PROFILE_EVERY:
            ac=sum(cap_t)/len(cap_t) if cap_t else 0
            ai=sum(inf_t)/len(inf_t) if inf_t else 0
            al=sum(log_t)/len(log_t) if log_t else 0
            fps=1000/(ac+ai+al) if ac+ai+al else 0
            print(f"[DBG] fps={fps:4.1f} | cap={ac:4.1f} | inf={ai:6.1f} | "
                  f"HP={hp_cur}/{hp_max}({hp_crit}) SP={sp_cur}/{sp_max}({sp_crit}) | "
                  f"red={red_ct} purple={purple_ct} sit={sitting} cards={card_count}")
            last_dbg=time.time()

        fid+=1

    cap.release(); cv2.destroyAllWindows()

# ═════ entry ══════════════════════════════════════════════════════════════
if __name__=="__main__":
    print("🚀 BOT v12 – ESC or move mouse to corner to exit")
    threading.Thread(target=main, daemon=False).start()
