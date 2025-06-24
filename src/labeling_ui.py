#!/usr/bin/env python3
# Ragnarok dataset labelling – prettier UI (dark sidebar, paned window, scrollbars)

import os, glob, yaml, tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageDraw

# ── project paths ──────────────────────────────────────────────────────────────
ROOT       = os.path.dirname(os.path.abspath(__file__))
PREV_DIR   = os.path.join(ROOT, "captured_dataset", "preview")
IMG_DIR    = os.path.join(ROOT, "captured_dataset", "images")
LBL_DIR    = os.path.join(ROOT, "captured_dataset", "labels")
YAML_CFG   = os.path.join(ROOT, "ragnarok-dataset", "ragnarok_multi.yaml")

# ── class names from YAML ──────────────────────────────────────────────────────
with open(YAML_CFG, encoding="utf-8") as f:
    cfg = yaml.safe_load(f)
names = cfg.get("names", cfg.get("names", {}))
CLS_NAMES = [names[i] for i in range(len(names))] if isinstance(names, dict) else list(names)

# ── preview list ───────────────────────────────────────────────────────────────
preview_paths = sorted(glob.glob(os.path.join(PREV_DIR, "*.jpg")))
if not preview_paths:
    raise SystemExit("No preview images – run the bot first.")

# ── utility: YOLO txt helpers ──────────────────────────────────────────────────
def yolo_line(cls,x1,y1,x2,y2,w,h):
    cx,cy = (x1+x2)/2/w, (y1+y2)/2/h
    bw,bh = (x2-x1)/w, (y2-y1)/h
    return f"{cls} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n"

def load_boxes(lbl_path,w,h):
    boxes=[]
    if os.path.exists(lbl_path):
        for ln in open(lbl_path):
            p=ln.split();   # cls cx cy bw bh
            if len(p)!=5: continue
            cls,cx,cy,bw,bh=p; cls=int(cls); cx,cy,bw,bh= map(float,(cx,cy,bw,bh))
            x1,y1=int((cx-bw/2)*w),int((cy-bh/2)*h)
            x2,y2=int((cx+bw/2)*w),int((cy+bh/2)*h)
            boxes.append([cls,x1,y1,x2,y2])
    return boxes

# ── Pretty UI  ─────────────────────────────────────────────────────────────────
class LabelUI(tk.Tk):
    SIDEBAR_W = 330          # sidebar width

    def __init__(self):
        super().__init__()
        self.title("Ragnarok Labeling UI – v2")
        self.configure(background="#1e1e1e")
        total_w = 1920 + self.SIDEBAR_W
        self.geometry(f"{total_w}x1080")

        # ttk theme colours
        ttk.Style().theme_use("clam")
        style = ttk.Style()
        style.configure("TFrame",  background="#252526")
        style.configure("TLabel",  background="#252526", foreground="#d4d4d4")
        style.configure("TButton", background="#3c3c3c", foreground="#d4d4d4")
        style.map("TButton",
                  background=[("active","#505050")])
        style.configure("Class.TRadiobutton",
                        background="#252526", foreground="#d4d4d4",
                        font=("TkDefaultFont",12))
        style.map("Class.TRadiobutton",
                  background=[("active","#3a3d41")])

        # --- Two-pane layout using pack (canvas expands, sidebar fixed) ----
        # left: canvas
        self.canvas_frame = ttk.Frame(self, style="TFrame")
        self.canvas_frame.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(self.canvas_frame,
                                bg="black", highlightthickness=0,
                                cursor="tcross")
        self.canvas.pack(fill="both", expand=True)

        # right: sidebar
        sidebar = ttk.Frame(self, width=self.SIDEBAR_W, style="TFrame")
        sidebar.pack(side="right", fill="y")
        sidebar.pack_propagate(False)   # enforce exactly 330px width

        # --- sidebar widgets --------------------------------------------------
        sidebar.pack_propagate(False)
        title = ttk.Label(sidebar, text="Class selection", font=("Segoe UI",14,"bold"))
        title.pack(anchor="nw", pady=(10,4))

        self.cls_var = tk.IntVar()
        rb_frame = ttk.Frame(sidebar)
        rb_frame.pack(anchor="nw", padx=20)
        for i,n in enumerate(CLS_NAMES):
            ttk.Radiobutton(rb_frame, text=n, value=i, variable=self.cls_var,
                            style="Class.TRadiobutton").pack(anchor="nw", pady=1)

        # jump / navigation
        nav_fr = ttk.Frame(sidebar); nav_fr.pack(anchor="nw", pady=12, padx=8, fill="x")
        ttk.Label(nav_fr, text="Jump to index:").pack(side="left")
        self.jump_var = tk.IntVar()
        jump_ent = ttk.Entry(nav_fr, textvariable=self.jump_var, width=6)
        jump_ent.pack(side="left", padx=4); jump_ent.bind("<Return>", self.jump_to)
        ttk.Button(nav_fr, text="Go", command=self.jump_to).pack(side="left")

        ttk.Button(sidebar, text="Save  →", command=self.next_image
                   ).pack(fill="x", padx=8, pady=(4,0))
        ttk.Button(sidebar, text="Revert (Ctrl+Z)", command=self.revert
                   ).pack(fill="x", padx=8, pady=(0,10))

        # label viewers with scrollbars
        def scrolled_text(parent, label):
            ttk.Label(parent, text=label, font=("Segoe UI",12,"bold")
                      ).pack(anchor="nw", padx=8)
            fr = ttk.Frame(parent); fr.pack(padx=8, pady=(0,8), fill="both")
            txt = tk.Text(fr, width=46, height=7, font=("Consolas",9),
                          bg="#1e1e1e", fg="#d4d4d4", insertbackground="#d4d4d4",
                          relief="flat", wrap="none")
            ysb = ttk.Scrollbar(fr, orient="vertical",
                                command=txt.yview)
            txt.configure(yscrollcommand=ysb.set)
            ysb.pack(side="right", fill="y"); txt.pack(side="left", fill="both", expand=True)
            txt.config(state="disabled")
            return txt
        self.txt_orig = scrolled_text(sidebar, "Original label")
        self.txt_new  = scrolled_text(sidebar, "Current label")

        # status bar
        self.status = ttk.Label(sidebar, text="",
                                anchor="center", font=("Segoe UI",10,"bold"))
        self.status.pack(side="bottom", fill="x", pady=6)

        # key bindings
        self.bind("<Right>",      lambda e: self.next_image())
        self.bind("<Left>",       lambda e: self.prev_image())
        self.bind("<Control-z>",  lambda e: self.revert())
        self.bind("<BackSpace>",  self.del_box_under_cursor)
        self.bind("<Delete>",     self.delete_current_image)

        # canvas mouse bindings
        self.canvas.bind("<ButtonPress-1>",  self.on_press)
        self.canvas.bind("<B1-Motion>",      self.on_drag)
        self.canvas.bind("<ButtonRelease-1>",self.on_release)

        # state
        self.idx=0; self.img=None; self.tk_img=None
        self.start=None; self.rect=None
        self.boxes=[]; self.saved=[]
        self.load_image()

    # ── navigation & file ops ────────────────────────────────────────────────
    def load_image(self):
        self.canvas.delete("all"); self.boxes.clear()
        path = preview_paths[self.idx]
        self.img = Image.open(path)
        self.tk_img = ImageTk.PhotoImage(self.img)
        self.canvas.config(scrollregion=(0,0,self.tk_img.width(),self.tk_img.height()))
        self.canvas.create_image(0,0,anchor="nw",image=self.tk_img)

        w,h = self.img.size
        base = os.path.splitext(os.path.basename(path))[0]
        self.saved = load_boxes(os.path.join(LBL_DIR,f"{base}.txt"), w, h)
        for cls,x1,y1,x2,y2 in self.saved:
            cid=self.draw_box(cls,x1,y1,x2,y2)
            self.boxes.append([cls,x1,y1,x2,y2,cid])
        self.update_info()

    def save_labels(self):
        base=os.path.splitext(os.path.basename(preview_paths[self.idx]))[0]
        lblp=os.path.join(LBL_DIR,  base+".txt")
        imgp=os.path.join(IMG_DIR,  base+".jpg")
        if not os.path.exists(imgp): self.img.save(imgp, quality=90)

        w,h=self.img.size
        if self.boxes:
            with open(lblp,"w") as f:
                for cls,x1,y1,x2,y2,_ in self.boxes:
                    f.write(yolo_line(cls,x1,y1,x2,y2,w,h))
        elif os.path.exists(lblp):
            os.remove(lblp)

        # redraw preview with boxes
        prevp=os.path.join(PREV_DIR,base+".jpg")
        p=self.img.copy(); d=ImageDraw.Draw(p)
        col={0:(255,0,0),1:(0,255,0),2:(0,0,255)}
        for cls,x1,y1,x2,y2,_ in self.boxes:
            d.rectangle([x1,y1,x2,y2], outline=col.get(cls,(255,255,0)), width=2)
        p.save(prevp, quality=90)

    def next_image(self,*_):
        self.save_labels(); self.idx=(self.idx+1)%len(preview_paths); self.load_image()
    def prev_image(self,*_):
        self.save_labels(); self.idx=(self.idx-1)%len(preview_paths); self.load_image()

    def jump_to(self,*_):
        n=self.jump_var.get()-1
        if 0<=n<len(preview_paths):
            self.save_labels(); self.idx=n; self.load_image()

    # ── drawing ─────────────────────────────────────────────────────────────
    def on_press(self,e):
        self.start=(e.x,e.y)
        self.rect=self.canvas.create_rectangle(e.x,e.y,e.x,e.y,
                                               outline="yellow",width=2)
    def on_drag(self,e):
        if self.rect:
            self.canvas.coords(self.rect,*self.start,e.x,e.y)
    def on_release(self,e):
        if not self.rect: return
        x1,y1=self.start; x2,y2=e.x,e.y
        x1,x2 = sorted((x1,x2)); y1,y2 = sorted((y1,y2))
        if abs(x2-x1)>5 and abs(y2-y1)>5:
            cls=self.cls_var.get()
            self.canvas.coords(self.rect,x1,y1,x2,y2)
            self.boxes.append([cls,x1,y1,x2,y2,self.rect])
        else:
            self.canvas.delete(self.rect)
        self.rect=self.start=None
        self.update_info()

    def draw_box(self,cls,x1,y1,x2,y2):
        col=("red","orange","lime","cyan","magenta","yellow")[cls%6]
        return self.canvas.create_rectangle(x1,y1,x2,y2, outline=col, width=2)

    # ── deleting ────────────────────────────────────────────────────────────
    def del_box_under_cursor(self,*_):
        cur=self.canvas.find_withtag("current")
        if not cur: return
        cur=cur[0]
        for b in reversed(self.boxes):
            if b[5]==cur:
                self.canvas.delete(cur); self.boxes.remove(b); break
        self.update_info()

    def delete_current_image(self,*_):
        if not messagebox.askyesno("Delete image",
                "Delete current preview, image and label?"): return
        base=os.path.splitext(os.path.basename(preview_paths[self.idx]))[0]
        for p in [os.path.join(PREV_DIR,base+".jpg"),
                  os.path.join(IMG_DIR, base+".jpg"),
                  os.path.join(LBL_DIR, base+".txt")]:
            if os.path.exists(p): os.remove(p)
        preview_paths.pop(self.idx)
        if not preview_paths:
            messagebox.showinfo("Done","All images processed."); self.quit(); return
        self.idx %= len(preview_paths); self.load_image()

    # ── revert unsaved ──────────────────────────────────────────────────────
    def revert(self,*_):
        for _,_,_,_,_,cid in self.boxes: self.canvas.delete(cid)
        self.boxes.clear()
        for cls,x1,y1,x2,y2 in self.saved:
            cid=self.draw_box(cls,x1,y1,x2,y2)
            self.boxes.append([cls,x1,y1,x2,y2,cid])
        self.update_info()

    # ── update info boxes & status ─────────────────────────────────────────–
    def update_info(self):
        self.status.config(text=f"{self.idx+1}/{len(preview_paths)}   "
                                f"boxes:{len(self.boxes)}")
        w,h=self.img.size
        # original
        self.txt_orig.config(state="normal"); self.txt_orig.delete("1.0","end")
        for cls,x1,y1,x2,y2 in self.saved:
            self.txt_orig.insert("end", yolo_line(cls,x1,y1,x2,y2,w,h))
        self.txt_orig.config(state="disabled")
        # current
        self.txt_new.config(state="normal"); self.txt_new.delete("1.0","end")
        for cls,x1,y1,x2,y2,_ in self.boxes:
            self.txt_new.insert("end", yolo_line(cls,x1,y1,x2,y2,w,h))
        self.txt_new.config(state="disabled")


if __name__ == "__main__":
    LabelUI().mainloop()
