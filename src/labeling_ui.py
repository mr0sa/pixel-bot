#!/usr/bin/env python3
# Ragnarok dataset labelling – coloured boxes + text + real images

import os, glob, yaml, tkinter as tk, cv2, numpy as np
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont
from ultralytics import YOLO

MODEL_PATH   = "models/YOLOV12N_5090.pt"   # ← set your trained model here
CONF_THRES   = 0.5        # confidence threshold for auto-detect

# ── project paths ─────────────────────────────────────────────────────────────
ROOT      = os.path.dirname(os.path.abspath(__file__))
# IMG_DIR   = os.path.join(ROOT, "captured_dataset", "images")
# PREV_DIR  = os.path.join(ROOT, "captured_dataset", "preview")
# LBL_DIR   = os.path.join(ROOT, "captured_dataset", "labels")
# YAML_CFG  = os.path.join(ROOT, "ragnarok-dataset", "ragnarok_multi.yaml")

PREV_DIR   = "ss\preview"
IMG_DIR    = "ss\images"
LBL_DIR    = "ss\labels"
YAML_CFG   = "ragnarok-dataset\\ragnarok_multi.yaml"
# ── class names & colours ────────────────────────────────────────────────────
with open(YAML_CFG, encoding="utf-8") as f:
    cfg = yaml.safe_load(f)
names  = cfg.get("names", cfg.get("names", {}))
CLS_NAMES = [names[i] for i in range(len(names))] if isinstance(names, dict) else list(names)

# explicit RGB for Tk / PIL
CLS_COL = {
    0: "#0000ff",  # blue
    1: "#00ffff",  # cyan
    2: "#00ff00",  # green
    3: "#ffa500",  # orange
    4: "#ff69b4",  # pink
    5: "#800080",  # purple
    6: "#ff0000",  # red
    7: "#ffff00"   # yellow
}

# ── image list (FULL-RES images) ─────────────────────────────────────────────
img_paths = sorted(glob.glob(os.path.join(IMG_DIR, "*.jpg")))
if not img_paths:
    raise SystemExit("No images found – run the bot first.")

# ── helpers ──────────────────────────────────────────────────────────────────
def yolo_line(cls,x1,y1,x2,y2,w,h):
    cx,cy = (x1+x2)/2/w, (y1+y2)/2/h
    bw,bh = (x2-x1)/w, (y2-y1)/h
    return f"{cls} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n"

def load_boxes(lbl_path,w,h):
    out=[]
    if os.path.exists(lbl_path):
        for ln in open(lbl_path):
            p=ln.split()
            if len(p)!=5: continue
            cls,cx,cy,bw,bh = p; cls=int(cls)
            cx,cy,bw,bh = map(float,(cx,cy,bw,bh))
            x1=int((cx-bw/2)*w); y1=int((cy-bh/2)*h)
            x2=int((cx+bw/2)*w); y2=int((cy+bh/2)*h)
            out.append([cls,x1,y1,x2,y2])
    return out

# ── main UI class ────────────────────────────────────────────────────────────
class LabelUI(tk.Tk):
    SIDEBAR_W = 330
    def __init__(self):
        super().__init__()
        self.title("Ragnarok Labeling UI")
        self.configure(bg="#1e1e1e")
        self.geometry(f"{1920+self.SIDEBAR_W}x1080")
        ttk.Style().theme_use("clam")
        # dark style
        st = ttk.Style()
        st.configure(".", background="#252526", foreground="#d4d4d4")
        st.configure("Class.TRadiobutton", font=("TkDefaultFont",12))
        st.map("TButton", background=[("active","#505050")])

        # layout
        self.canvas = tk.Canvas(self, bg="black", highlightthickness=0, cursor="tcross")
        self.canvas.pack(side="left", fill="both", expand=True)
        sb = ttk.Frame(self, width=self.SIDEBAR_W); sb.pack(side="right", fill="y")
        sb.pack_propagate(False)

        ttk.Label(sb,text="Class selection",font=("Segoe UI",14,"bold")).pack(anchor="nw",pady=(8,4))
        self.cls_var = tk.IntVar()
        fr = ttk.Frame(sb); fr.pack(anchor="nw", padx=18)
        for i,n in enumerate(CLS_NAMES):
            ttk.Radiobutton(fr,text=f"{i}: {n}",value=i,variable=self.cls_var,
                            style="Class.TRadiobutton").pack(anchor="nw", pady=1)

        # jump
        nav = ttk.Frame(sb); nav.pack(anchor="nw",padx=8,pady=10,fill="x")
        ttk.Label(nav,text="Go to").pack(side="left")
        self.jump_var=tk.IntVar()
        ent=ttk.Entry(nav,textvariable=self.jump_var,width=6)
        ent.pack(side="left",padx=4); ent.bind("<Return>",self.jump_to)
        ttk.Button(nav,text="OK",command=self.jump_to,width=4).pack(side="left")

        ttk.Button(sb,text="Save  →",command=self.next_img).pack(fill="x",padx=8,pady=2)
        ttk.Button(sb,text="Revert (Ctrl+Z)",command=self.revert
                   ).pack(fill="x",padx=8,pady=(0,10))

        # ── NEW: auto-classify toggle ────────────────────────────────────
        self.auto_cls = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            sb,
            text="Auto-classify on next (→)",
            variable=self.auto_cls,
            style="Class.TRadiobutton"
        ).pack(anchor="nw", padx=18, pady=(0,8))

        # Auto-detect button
        ttk.Button(sb,text="Auto-detect",
                   command=self.auto_detect
                   ).pack(fill="x",padx=8,pady=(0,10))

        self.txt_orig = self.make_box(sb,"Original")
        self.txt_new  = self.make_box(sb,"Current")
        self.status   = ttk.Label(sb,anchor="center",font=("Segoe UI",10,"bold"))
        self.status.pack(side="bottom",fill="x",pady=6)

        # events
        self.canvas.bind("<ButtonPress-1>",self.on_press)
        self.canvas.bind("<B1-Motion>",self.on_drag)
        self.canvas.bind("<ButtonRelease-1>",self.on_release)
        for k,f in { "<Right>":self.next_img,"<Left>":self.prev_img,
                     "<Control-z>":self.revert,"<BackSpace>":self.del_box_cursor,
                     "<Delete>":self.del_current_img }.items():
            self.bind(k, lambda e,f=f: f())

        # state
        self.idx=0; self.start=None; self.rect=None
        self.img=None; self.tk_img=None
        self.boxes=[]; self.saved=[]

        self.yolo = YOLO(MODEL_PATH) if os.path.exists(MODEL_PATH) else None
        self.auto_classify = self.auto_detect
        self.load_img()

    # text widget helper
    def make_box(self,parent,label):
        ttk.Label(parent,text=label,font=("Segoe UI",12,"bold")
                  ).pack(anchor="nw",padx=8)
        fr=ttk.Frame(parent); fr.pack(padx=8,pady=(0,8),fill="both")
        txt=tk.Text(fr,width=46,height=7,font=("Consolas",9),
                    bg="#1e1e1e",fg="#d4d4d4",relief="flat",wrap="none")
        y=ttk.Scrollbar(fr,orient="vertical",command=txt.yview)
        txt['yscrollcommand']=y.set; y.pack(side="right",fill="y"); txt.pack(side="left",fill="both",expand=True)
        txt.config(state="disabled"); return txt

    # ── load / save ---------------------------------------------------------
    def load_img(self):
        self.canvas.delete("all"); self.boxes.clear()
        path = img_paths[self.idx]
        self.img = Image.open(path)
        self.tk_img = ImageTk.PhotoImage(self.img)
        self.canvas.config(scrollregion=(0,0,*self.img.size))
        self.canvas.create_image(0,0,anchor="nw",image=self.tk_img)

        base=os.path.splitext(os.path.basename(path))[0]
        self.saved = load_boxes(os.path.join(LBL_DIR,f"{base}.txt"),*self.img.size)
        for cls,x1,y1,x2,y2 in self.saved:
            self.add_box(cls,x1,y1,x2,y2)
        self.refresh_info()

    def save_labels(self):
        base=os.path.splitext(os.path.basename(img_paths[self.idx]))[0]
        lblp = os.path.join(LBL_DIR,  base + ".txt")
        # make sure destination folders exist
        os.makedirs(LBL_DIR,  exist_ok=True)
        os.makedirs(PREV_DIR, exist_ok=True)
        if not os.path.exists(lblp) and not self.boxes and not self.saved:
            return  # nothing

        w,h=self.img.size
        if self.boxes:
            with open(lblp,"w") as f:
                for cls,x1,y1,x2,y2,*_ in self.boxes:
                    f.write(yolo_line(cls,x1,y1,x2,y2,w,h))
        elif os.path.exists(lblp):
            os.remove(lblp)

        # redraw preview with coloured boxes + text
        prevp = os.path.join(PREV_DIR, base + ".jpg")
        p=self.img.copy(); d=ImageDraw.Draw(p)
        font=ImageFont.load_default()
        for cls,x1,y1,x2,y2,*_ in self.boxes:
            col_hex = CLS_COL.get(cls, "#ffffff")
            col_rgb = tuple(int(col_hex[i:i+2], 16) for i in (1, 3, 5))

            # ── clamp inside image then re-sort so x1≤x2, y1≤y2 ──────────
            x1c = max(0, min(x1, w-1));  x2c = max(0, min(x2, w-1))
            y1c = max(0, min(y1, h-1));  y2c = max(0, min(y2, h-1))
            if x2c < x1c: x1c, x2c = x2c, x1c
            if y2c < y1c: y1c, y2c = y2c, y1c

            d.rectangle([x1c, y1c, x2c, y2c], outline=col_rgb, width=2)
            txt=f"{cls}-{CLS_NAMES[cls]}"
            # outline: draw white shadows around main text
            for off in ((-1,0),(1,0),(0,-1),(0,1)):
                d.text((x1+4+off[0], y1+2+off[1]), txt, fill=(255,255,255), font=font)
            for off in ((-1,0),(1,0),(0,-1),(0,1)):
                d.text((x1c+4+off[0], y1c+2+off[1]), txt,
                       fill=(255,255,255), font=font)
            d.text((x1c+4, y1c+2), txt, fill=(0,0,0), font=font)
        p.save(prevp, quality=90)

    # ── navigation ----------------------------------------------------------
    def next_img(self):
        self.save_labels()
        self.idx = (self.idx + 1) % len(img_paths)
        self.load_img()
        # auto-classify if the toggle is active
        if self.auto_cls.get():
            self.auto_detect()
    def prev_img(self): self.save_labels(); self.idx=(self.idx-1)%len(img_paths); self.load_img()
    def jump_to(self,*_):
        n=self.jump_var.get()-1
        if 0<=n<len(img_paths): self.save_labels(); self.idx=n; self.load_img()

    # ── drawing -------------------------------------------------------------
    def on_press(self,e):
        self.start=(e.x,e.y)
        self.rect=self.canvas.create_rectangle(e.x,e.y,e.x,e.y,outline="#ffff00",width=2)
    def on_drag(self,e):
        if self.rect: self.canvas.coords(self.rect,*self.start,e.x,e.y)
    def on_release(self,e):
        if not self.rect: return
        x1,y1=self.start; x2,y2=e.x,e.y
        if abs(x2-x1)>5 and abs(y2-y1)>5:
            cls=self.cls_var.get()
            self.canvas.coords(self.rect,x1,y1,x2,y2)
            self.add_box(cls,x1,y1,x2,y2,self.rect)
        else: self.canvas.delete(self.rect)
        self.rect=self.start=None; self.refresh_info()

    def add_box(self,cls,x1,y1,x2,y2,rect_id=None):
        col=CLS_COL.get(cls,"#ffffff")
        if rect_id is None:
            rect_id=self.canvas.create_rectangle(x1,y1,x2,y2,outline=col,width=2)
        # bold black text with white outline (draw 4 white shadows first)
        txt=f"{cls}-{CLS_NAMES[cls]}"
        for dx,dy in ((-1,0),(1,0),(0,-1),(0,1)):
            self.canvas.create_text(x1+4+dx, y1+10+dy, anchor="nw",
                                    text=txt, fill="white",
                                    font=("Consolas",12,"bold"))
        txt_id=self.canvas.create_text(x1+4, y1+10, anchor="nw",
                                       text=txt, fill="black",
                                       font=("Consolas",12,"bold"))
        self.boxes.append([cls,x1,y1,x2,y2,rect_id,txt_id])

    # ── delete --------------------------------------------------------------
    def del_box_cursor(self):
        cur=self.canvas.find_withtag("current")
        if not cur: return
        cur=cur[0]
        for b in list(self.boxes):
            if b[5]==cur or b[6]==cur:
                self.canvas.delete(b[5]); self.canvas.delete(b[6]); self.boxes.remove(b)
        self.refresh_info()

    def del_current_img(self):
        if not messagebox.askyesno("Delete image","Delete image & label?"): return
        base=os.path.splitext(os.path.basename(img_paths[self.idx]))[0]
        for p in [os.path.join(IMG_DIR,base+".jpg"),
                  os.path.join(PREV_DIR,base+".jpg"),
                  os.path.join(LBL_DIR,base+".txt")]:
            if os.path.exists(p): os.remove(p)
        img_paths.pop(self.idx)
        if not img_paths: self.quit(); return
        self.idx%=len(img_paths); self.load_img()

    # ── revert --------------------------------------------------------------
    def revert(self):
        for _,_,_,_,_,r,t in self.boxes: self.canvas.delete(r); self.canvas.delete(t)
        self.boxes.clear()
        for cls,x1,y1,x2,y2 in self.saved: self.add_box(cls,x1,y1,x2,y2)
        self.refresh_info()

    # ── info boxes ----------------------------------------------------------
    def refresh_info(self):
        self.status.config(text=f"{self.idx+1}/{len(img_paths)}  boxes:{len(self.boxes)}")
        w,h=self.img.size
        # original
        self.txt_orig.config(state="normal"); self.txt_orig.delete("1.0","end")
        for cls,x1,y1,x2,y2 in self.saved:
            self.txt_orig.insert("end",yolo_line(cls,x1,y1,x2,y2,w,h))
        self.txt_orig.config(state="disabled")
        # current
        self.txt_new.config(state="normal"); self.txt_new.delete("1.0","end")
        for cls,x1,y1,x2,y2,*_ in self.boxes:
            self.txt_new.insert("end",yolo_line(cls,x1,y1,x2,y2,w,h))
        self.txt_new.config(state="disabled")
    
    # ── AUTO-DETECT ---------------------------------------------------------
    def auto_detect(self):
        """Run YOLO on current image and add its detections."""
        if self.yolo is None:
            messagebox.showwarning("Model missing",
                                   f"Can't find model at '{MODEL_PATH}'.\n"
                                   "Set MODEL_PATH and restart.")
            return

        img_arr = cv2.cvtColor(np.array(self.img), cv2.COLOR_RGB2BGR)
        res = self.yolo(img_arr, conf=CONF_THRES, verbose=False)[0]
        h, w = img_arr.shape[:2]

        for box, cls, conf in zip(res.boxes.xyxy, res.boxes.cls, res.boxes.conf):
            cls_i = int(cls)
            x1, y1, x2, y2 = map(int, box)
            # clamp just in case
            x1 = max(0, min(x1, w-1)); x2 = max(0, min(x2, w-1))
            y1 = max(0, min(y1, h-1)); y2 = max(0, min(y2, h-1))
            if x2 <= x1 or y2 <= y1:
                continue
            self.add_box(cls_i, x1, y1, x2, y2)

        self.refresh_info()

# ── run ──────────────────────────────────────────────────────────────────────
if __name__=="__main__":
    LabelUI().mainloop()
