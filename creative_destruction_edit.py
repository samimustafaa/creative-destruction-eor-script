"""CD Quick Edit: a Windows desktop helper for Creative Destruction.

Install: py -m pip install -r requirements.txt
Run the Windows app: QuickEdit.exe
Source version: py creative_destruction_edit.py
Click Start, return to the game, press your configured edit key and move to a highlighted edit.
F6 starts/pauses; F10 exits. No game files or memory are modified.

Native region capture, cached text alignment, configurable short delays,
foreground-process gating and one select/apply sequence per edit entry.
360 Hz, Fast, Balanced and Careful presets are available in the UI.
360 Hz is a scan target; actual scan speed is shown in the UI and depends on
capture/detection cost. Static JPG/PNG backgrounds are painted only when changed. Lower click hold
can miss inputs on some clients: increase it if a click does not register.
The processing time shown in the UI excludes game rendering/network delay.
Auto reset confirms/applies the top/default choice after you move to it in the edit menu.
It uses the same automatic timing as editing; no extra reset button is needed.

Use windowed/borderless mode and the normal centered HUD. Detection has been
checked against supplied images and video; no competitive latency guarantee.
Disable Pre-edit is not implemented. Close older helper instances first.
"""
import argparse
import ctypes as C
from ctypes import wintypes as W
import os
import threading
import time
import queue


TEXT_MASK = 'eJydkrGO2zAMhqmqsDr45I4eCBz6Bho5BMjY11DfQN06BLWMAJetz6RDhjxGFWS9waMHIyql2D6cx3KQqd8C+fGXAP43DgC7D8IIMD2y7p5X4Z9j+xBS+SEhRSN8TpsiV/IarCypLmutwIeqpFjWFrlMXVIS09MEhrhMd+Re4JrpeQIboYLUZCEi7QheA9RgOQERwFgSRw8tBMeC9OCCk0oNRvTBAShQVx8r3UQrpY8ZozuLUGMTQqUgMIa4vUjfkux9rTM7KcWUhpRkuMzuULcarNMVq3mMSGiQGyJjEGYM98s54QdqITqXMbohBXaDMcYuZIz7NeUxvBVDV6Z1suUxiBHC7CHb0mZTV7/ZFpNNXaMtl/L7XTDlUg7vgn18aHuXbivEzZ6t/BjSbwS1LaGXk+P+9a/f9yPOQjOmY/JJjQsGfTueLvIFacGIoLTS4Excu1eoEeLPsHY/ELKntxmjAjU6ijJd5hI17AwfV+nPLCDYH+HGb2nBIBHO/dnj6oaT/UmeeLtguO+MoT4TxLltd7mjbqb99bYIzRuhGvb9Zeb4+inTwRexdeMR/wD9uZBT'

BUILD_MASK = 'eJyV071u2zAQB/ATWJQjHyBF+BoZArFv0lfo6AKCJCODRr8SDQ0e+wihkaErDQ1lEFbX/1H+ytDWJWBbJn+kjscj0Q3NrNMtbGnK32XFzLfpr0JvxVR17/DnPzEJ95FItDxzwB7GQA2RY6qu3gakmRRnMrKyyniOZ9zJUH/G6DHcC5Z2p2eMpmus2V9je8GYiFHgDyrQqmAjUV2wY19Wk2YN6SATgdHVoufpPTa+BFbhc2964I+WBv+Qlveuo+mxtUSfynTtyanw7WcwsQb2qbVm8PmIq9CFuq1m4n7pIafDG0eXBW9T68yw5SUMh1xGx5qf2KMnFxwnTm4WzLEBHidksMvA1T45Z56Hl3DEnT4Ad21rvGHfODuMe2CsjpUp1Yhrtz1jdXg55OyOuLZ6OOJWcGOtNusDepLz1KppPPzKrjE9Eptlpe0ZO8E4pwt+A2ZubG/GeMZljxU2cQ/MBXfAFe9OeJ3SFa5JHSLiwkEX/KUXPOwLlktTEg0sNVir3XbBfSUYJ9QIfs30iE7gkrtQsNPAK2DTK+AsmFjvXxPVNdkxJQR9wnazGQWbBbeuR/pYT6+5dRmxRQbWP4BZ/m52EZt41jtMRx0KnnFyPNuE0cCSaF6wwUmH1BqMS/25NzmYGfnlbCKwn4HVFMoF0rOeQmo0Lj/KluwkuAHujlX9IF+nMo5VWP6u5EeVS9aY77271Pnf28r4f5pzS/+BTbQSzW9Un5U9'

def unpack_mask(encoded, shape):
    import base64, zlib
    data = np.frombuffer(zlib.decompress(base64.b64decode(encoded)), dtype=np.uint8)
    return np.unpackbits(data)[:shape[0]*shape[1]].reshape(shape).astype(bool)


LABEL_OFFSETS = {}

def label_score(bright, mask, top, left, dx_range, dy_range):
    """Reuse a successful alignment; search only if that alignment no longer fits."""
    height, width = mask.shape
    positives = int(np.count_nonzero(mask))
    negatives = mask.size-positives
    key = (top, left)
    cached = LABEL_OFFSETS.get(key, (0,0))
    def score(dx,dy):
        crop = bright[top+dy:top+dy+height,left+dx:left+dx+width]
        hits = int(np.count_nonzero(crop & mask))
        positive = hits/positives
        return positive-(int(np.count_nonzero(crop))-hits)/negatives, positive
    current = score(*cached)
    # Keep a valid alignment, including the translucent stair prompt.
    threshold = .18 if top == 243 else .35
    minimum_positive = .60 if top == 243 else .65
    if current[0] > threshold and current[1] > minimum_positive:
        return current
    best = current
    for dy in dy_range:
        for dx in dx_range:
            if (dx,dy)==cached:continue
            candidate = score(dx,dy)
            if candidate[0] > best[0]:
                best = candidate
                LABEL_OFFSETS[key] = (dx,dy)
            if best[0] > .70:
                return best
    return best


def top_marker(gray):
    best=(0,0,0,0)
    offsets=getattr(top_marker,"offsets",(0,0))
    candidates=[offsets]+[(dx,dy) for dy in range(-8,9,2) for dx in range(-8,9,2) if (dx,dy)!=offsets]
    # Dark outline of the standard full/default icon. Its interior can contain
    # the stair arrow, so compare the edge against a broad central square.
    for dx,dy in candidates:
        horizontal=np.concatenate([gray[32+dy:34+dy,198+dx:251+dx].ravel(),gray[87+dy:89+dy,198+dx:251+dx].ravel()])
        vertical=np.concatenate([gray[35+dy:87+dy,196+dx:198+dx].ravel(),gray[35+dy:87+dy,251+dx:253+dx].ravel()])
        edge=np.concatenate([horizontal,vertical]);inside=gray[38+dy:84+dy,202+dx:247+dx]
        fraction=float((edge<155).mean());contrast=float(inside.mean()-edge.mean())
        if fraction>.80 and contrast>30:
            top_marker.offsets=(dx,dy)
            return True,(fraction,contrast,dx,dy)
        if fraction>best[0]:best=(fraction,contrast,dx,dy)
    return False,best

def detect(image, cropped=False):
    """Return wheel, yellow selection, build prompt, diagnostic scores."""
    width, height = image.size
    scale = height / 1080
    cx, cy = width / 2, height / 2
    box = tuple(round(v) for v in (cx-225*scale, cy-225*scale, cx+225*scale, cy+225*scale))
    roi = image if cropped else image.crop(box)
    if roi.size != (450,450):
        roi = roi.resize((450,450))
    rgb = np.asarray(roi).astype(np.int16)
    red,green,blue=rgb[:,:,0],rgb[:,:,1],rgb[:,:,2]
    low=np.minimum(np.minimum(red,green),blue)
    high=np.maximum(np.maximum(red,green),blue)
    bright = (low > 195) & ((high-low) < 55)
    if not hasattr(detect, "masks"):
        detect.masks = unpack_mask(TEXT_MASK, (52,135)), unpack_mask(BUILD_MASK, (29,360))
        yy,xx = np.ogrid[-225:225,-225:225]
        radius = np.sqrt(xx*xx+yy*yy)
        detect.ring = (radius > 155) & (radius < 200)
        detect.band = (radius > 125) & (radius < 155)
        detect.axis = np.arange(450)
    text_contrast, text_positive = label_score(bright, detect.masks[0], 243,163,range(-10,11,2),range(-12,13,2))
    ring_score = float(((low>155)&((high-low)<65))[detect.ring].mean())
    wheel = ring_score > .40 and text_contrast > .18 and text_positive > .60
    yellow = ((rgb[:,:,0]>180)&(rgb[:,:,1]>175)&(rgb[:,:,0]-rgb[:,:,2]>22)&(rgb[:,:,1]-rgb[:,:,2]>18)&detect.band)
    count = int(yellow.sum())
    sector = -1
    if count:
        rows, columns = yellow.sum(axis=1), yellow.sum(axis=0)
        dy = float(rows @ detect.axis)/count-225
        dx = float(columns @ detect.axis)/count-225
        sector = int(np.floor((np.arctan2(dy,dx)+np.pi)/(np.pi/4))) % 8
    if not wheel and ring_score > .60 and count >= 60:
        # Bright full-shape previews can wash out the cancel text.
        marker_found,_ = top_marker((red+green+blue)/3)
        wheel = marker_found
    is_default = bool(wheel and count >= 60 and dy < -65 and abs(dx) < -dy*.45)
    build_contrast, build_positive = (0.0, 0.0)
    if not wheel:
        build_contrast, build_positive = label_score(bright, detect.masks[1],132,45,range(-8,9,2),range(-8,9,2))
    build = not wheel and build_contrast > .35 and build_positive > .65
    return wheel, wheel and count >= 60, build, {
        "text": round(text_contrast,2), "ring": round(ring_score,2),
        "yellow": count, "sector": sector, "default": is_default, "build": round(build_contrast,2)}


EDIT_KEY_NAMES={"Enter":0x0D,"Backspace":0x08,"Tab":0x09,"Space":0x20,"CapsLock":0x14,"Shift":0x10,"Ctrl":0x11,"Alt":0x12,
    "Insert":0x2D,"Delete":0x2E,"Home":0x24,"End":0x23,"PageUp":0x21,"PageDown":0x22,
    "Up":0x26,"Down":0x28,"Left":0x25,"Right":0x27}
EDIT_KEY_NAMES.update({"F"+str(i):0x6F+i for i in range(1,13) if i not in (6,10)})
def parse_edit_key(value):
    """Normalize a keyboard edit bind to its Windows virtual-key code."""
    key=value.strip()
    if key.casefold() in ("f6","f10","esc","escape"):
        raise ValueError("F6, F10 and Esc are reserved. Choose another edit key.")
    if len(key)==1 and key.isascii() and key.isalnum():return key.upper(),ord(key.upper())
    for name,vk in EDIT_KEY_NAMES.items():
        if name.casefold()==key.casefold():return name,vk
    raise ValueError("Use a keyboard key such as G, E, V, 1, Tab, Space or F1.")
def edit_key_matches(vk,configured):
    return vk==configured or vk in {0x10:(0xA0,0xA1),0x11:(0xA2,0xA3),0x12:(0xA4,0xA5)}.get(configured,())
def edit_settings_path():
    from pathlib import Path
    return Path(os.environ.get("LOCALAPPDATA",str(Path.home())))/"CDQuickEdit"/"settings.json"
def load_edit_key():
    import json
    try:return parse_edit_key(json.loads(edit_settings_path().read_text(encoding="utf-8"))["edit_key"])[0]
    except (OSError,ValueError,TypeError,KeyError):return "G"
def save_edit_key(key):
    import json
    path=edit_settings_path()
    try:
        saved=json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(saved,dict):saved={}
    except (OSError,ValueError):saved={}
    saved["edit_key"]=key
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(".tmp")
    try:
        temporary.write_text(json.dumps(saved,indent=2),encoding="utf-8")
        os.replace(temporary,path)
    finally:temporary.unlink(missing_ok=True)

UI_FONT = "Segoe UI" if os.name == "nt" else "DejaVu Sans"

def resource_path(name):
    from pathlib import Path
    import sys
    return Path(getattr(sys,"_MEIPASS",Path(__file__).resolve().parent))/name


def rounded(canvas,x1,y1,x2,y2,radius=16,**kwargs):
    points=[x1+radius,y1,x2-radius,y1,x2,y1,x2,y1+radius,x2,y2-radius,x2,y2,x2-radius,y2,x1+radius,y2,x1,y2,x1,y2-radius,x1,y1+radius,x1,y1]
    return canvas.create_polygon(points,smooth=True,splinesteps=24,**kwargs)


class AppUI:
    PRESETS={"360 Hz":(0,0,8,360),"Fast":(10,8,8,144),"Balanced":(24,24,12,120),"Careful":(60,60,20,90)}
    BG="#090a0d";CARD="#18191d";TEXT="#f4f4f6";MUTED="#b6b6c2";LIME="#ededed"
    def __init__(self,root,state,stats,args,reset,foreground_game,stop,events):
        import tkinter as tk
        from tkinter import messagebox
        from PIL import Image,ImageTk
        self.tk=tk;self.root=root;self.state=state;self.stats=stats;self.args=args;self.reset=reset
        self.foreground_game=foreground_game;self.stop=stop;self.events=events;self.messagebox=messagebox
        self.scale_x=self.scale_y=1.0;self.hover=None;self.pressed=None;self.animations={};self.hover_timer=None
        self.tray=None;self.tray_thread=None;self.tray_ready=False;self.tray_starting=False;self.tray_enabled=None;self.closing=False
        self.success_message=None
        self.last=tk.StringVar(value="Use borderless or windowed mode.")
        self.values=[tk.IntVar(value=v) for v in (args.stable_ms,args.apply_delay_ms,args.click_ms,args.scan_hz)]
        self.auto_reset=tk.BooleanVar(value=getattr(args,"auto_reset",True));self.select_only=tk.BooleanVar(value=args.select_only)
        self.process=tk.StringVar(value=args.process)
        self.edit_key=tk.StringVar(value=getattr(args,"edit_key","G"))
        self.entries=[];self.focused_input=None;self.hitboxes=[];self.button_shapes={};self.last_source=None
        self.background_photo=None;self.header_icon=None;self.cd_logo=None;self.app_art=None;self.cd_art=None;self.wallpaper_error=None
        self.overlay_cache=None;self.paint_cache={};self.last_enabled=None;self.last_canvas_size=None
        root.title("Quick Edit • sg0hann");root.geometry("1200x720");root.resizable(False,False);root.configure(bg=self.BG)
        try:
            with Image.open(resource_path("assets/app.png")) as image:self.app_art=image.convert("RGBA")
            self.window_icons=[ImageTk.PhotoImage(self.app_art.resize((size,size),Image.Resampling.LANCZOS)) for size in (16,32,48,256)]
            root.iconphoto(True,*self.window_icons)
            if os.name=="nt":root.iconbitmap(str(resource_path("assets/app.ico")))
            with Image.open(resource_path("assets/cd-logo.png")) as image:self.cd_art=image.convert("RGBA")
        except Exception:pass
        self.canvas=tk.Canvas(root,bg=self.BG,highlightthickness=0,bd=0,takefocus=True);self.canvas.pack(fill="both",expand=True)
        self.background_item=self.canvas.create_image(0,0,anchor="nw")
        for i,var in enumerate(self.values):
            validate=(root.register(lambda text:text=="" or (text.isdecimal() and len(text)<=3)),"%P")
            entry=tk.Entry(self.canvas,textvariable=var,validate="key",validatecommand=validate,bg="#111115",fg=self.TEXT,insertbackground="white",selectbackground="#555564",relief="flat",bd=0,highlightthickness=0,font=(UI_FONT,14))
            entry.bind("<FocusIn>",lambda e,index=i:self.input_focus(index));entry.bind("<FocusOut>",lambda e:self.input_focus(None))
            entry.bind("<Up>",lambda e,index=i:self.increment(index,1));entry.bind("<Down>",lambda e,index=i:self.increment(index,-1))
            self.entries.append(entry)
        self.process_entry=tk.Entry(self.canvas,textvariable=self.process,bg="#111115",fg="#d8d8e0",insertbackground="white",relief="flat",bd=0,highlightthickness=0,font=(UI_FONT,10))
        self.key_entry=tk.Entry(self.canvas,textvariable=self.edit_key,bg="#111115",fg=self.TEXT,insertbackground="white",relief="flat",bd=0,font=(UI_FONT,13),justify="center")
        self.key_entry.bind("<Return>",lambda event:self.apply())
        self.canvas.bind("<Configure>",self.resize);self.canvas.bind("<Motion>",self.motion)
        self.canvas.bind("<Leave>",lambda e:self.set_hover(None));self.canvas.bind("<Button-1>",self.mouse_down);self.canvas.bind("<ButtonRelease-1>",self.mouse_up)
        self.canvas.bind("<KeyRelease-space>",lambda e:self._toggle_reset())
        self.auto_reset.trace_add("write",lambda *unused:self.paint_reset())
        self.select_only.trace_add("write",lambda *unused:self.paint_select_only())
        self.last.trace_add("write",lambda *unused:self.update_last())
        self.load_wallpaper()
        root.protocol("WM_DELETE_WINDOW",self.hide_to_tray);root.after(50,self.draw_ui);root.after(80,self.style_titlebar);root.after(100,self.refresh)
        self.start_tray()

    def rect(self,box):
        x,y,w,h=box;return x*self.scale_x,y*self.scale_y,(x+w)*self.scale_x,(y+h)*self.scale_y
    def text(self,x,y,value,size=10,color=None,bold=False,tag=None,width=None):
        options=dict(text=value,anchor="nw",fill=color or self.TEXT,font=(UI_FONT,max(8,round(size*min(self.scale_x,self.scale_y))),"bold" if bold else "normal"),tags=("ui",tag) if tag else ("ui",))
        if width:options.update(width=width*self.scale_x)
        return self.canvas.create_text(x*self.scale_x,y*self.scale_y,**options)
    def shape(self,box,fill,outline="#41414c",tag=None,radius=12):
        tags=("ui",tag) if tag else ("ui",)
        return rounded(self.canvas,*self.rect(box),radius*min(self.scale_x,self.scale_y),fill=fill,outline=outline,tags=tags)
    def button(self,key,box,caption,command,primary=False):
        fill="#eeeeef" if primary else "#2c2c34";fg="#111114" if primary else self.TEXT
        if primary and self.state["enabled"]:fill="#4ed27c";fg="#062512"
        shape=self.shape(box,fill,"#9d9da6" if primary else "#555560",tag="button_"+key)
        x,y,w,h=box
        label=self.canvas.create_text((x+w/2)*self.scale_x,(y+h/2)*self.scale_y,text=caption,fill=fg,font=(UI_FONT,10,"bold"),tags=("ui","label_"+key))
        self.button_shapes[key]=(shape,label,primary)
        self.hitboxes.append((key,box,command))
    def draw_ui(self):
        if not self.root.winfo_exists():return
        from PIL import Image,ImageOps,ImageTk
        c=self.canvas;c.delete("ui");self.hitboxes=[];self.button_shapes={};self.paint_cache.clear();self.last_enabled=None
        self.text(100,7,"QUICK EDIT",22,bold=True)
        try:
            self.header_icon=ImageTk.PhotoImage(self.app_art.resize((round(64*self.scale_x),round(64*self.scale_y)),Image.Resampling.LANCZOS))
            c.create_image(23*self.scale_x,8*self.scale_y,anchor="nw",image=self.header_icon,tags=("ui","app_brand"))
            self.cd_logo=ImageTk.PhotoImage(ImageOps.contain(self.cd_art,(round(155*self.scale_x),round(32*self.scale_y)),Image.Resampling.LANCZOS))
            c.create_image(193*self.scale_x,45*self.scale_y,anchor="n",image=self.cd_logo,tags=("ui","cd_brand"))
        except Exception:pass
        self.text(1050,30,"BY SG0HANN",9,bold=True)
        self.dot=c.create_oval(*self.rect((48,112,9,9)),fill="#a6a6b0",outline="",tags="ui")
        self.text(69,105,"Paused",18,bold=True,tag="status")
        self.text(49,145,"Waiting for client.exe",9,tag="process_status")
        self.text(49,172,"Start the helper, return to your game, then press G.",10,width=350,tag="detail")
        self.button("start",(28,260,410,46),"Start helper  /  F6",self.toggle,True)
        self.text(29,330,"Processing —",9,tag="metrics",width=380)
        self.text(29,374,self.last.get(),10,tag="last",width=380)
        self.text(29,425,"F6  Start / pause   ·   F10  Exit",9)
        self.text(29,453,f"{getattr(self.args,'edit_key','G')} → choose shape → automatic apply",9,tag="edit_hint")
        self.text(29,485,"Close window → system tray. Right-click → Quit.",9,color=self.MUTED)
        self.text(29,532,"Edit key",10,bold=True)
        self.shape((29,558,140,38),"#111115")
        c.create_window(99*self.scale_x,577*self.scale_y,window=self.key_entry,width=112*self.scale_x,height=27*self.scale_y,tags="ui")
        self.text(185,558,"Match your in-game edit bind.\nThen click Apply settings.",9,width=230)
        self.text(490,109,"Response",14,bold=True);self.text(920,112,"Less waiting. More control.",9)
        for i,name in enumerate(self.PRESETS):
            self.button("preset_"+name,(490+i*163,137,154,35),name,lambda n=name:self.preset(n))
        labels=["Selection dwell","Apply delay","Click hold","Scan limit"]
        for i,label in enumerate(labels):
            x=490+(i%2)*332;y=193+(i//2)*83
            self.text(x,y,label,9)
            self.shape((x,y+24,310,47),"#111115","#888895" if self.focused_input==i else "#4a4a56",tag="input_"+str(i))
            c.create_window((x+13)*self.scale_x,(y+47)*self.scale_y,window=self.entries[i],anchor="w",width=160*self.scale_x,height=28*self.scale_y,tags="ui")
            self.text(x+210,y+40,"Hz" if i==3 else "ms",9,color="#bdbdca")
            self.button("minus_"+str(i),(x+237,y+32,29,30),"−",lambda index=i:self.increment(index,-1))
            self.button("plus_"+str(i),(x+274,y+32,29,30),"+",lambda index=i:self.increment(index,1))
        self.text(490,376,"Auto reset (top/default)",11,bold=True)
        self.hitboxes.append(("reset",(1030,369,116,36),self._toggle_reset));self.paint_reset()
        self.hitboxes.append(("select_only",(489,418,310,27),lambda:self.select_only.set(not self.select_only.get())));self.paint_select_only()
        self.shape((490,463,490,38),"#111115")
        c.create_window(503*self.scale_x,482*self.scale_y,window=self.process_entry,anchor="w",width=459*self.scale_x,height=26*self.scale_y,tags="ui")
        self.button("apply",(995,463,151,38),"Apply settings",self.apply)
        self.text(490,530,"Choose your pace. Make it yours.",9,color="#babac6")
        self.text(29,681,"Made by sg0hann",10)
        self.shape((1039,680,24,17),"#ff4147",outline="",radius=5)
        c.create_polygon(1048*self.scale_x,684*self.scale_y,1048*self.scale_x,693*self.scale_y,1056*self.scale_x,688.5*self.scale_y,fill="white",tags="ui")
        self.text(1072,679,"YouTube ↗",10)
        self.hitboxes.append(("youtube",(1035,670,130,33),self.open_youtube))
        c.tag_raise("ui");self.update_last();self.paint_presets();self.refresh(schedule=False)
        if self.last_source is not None:self.render_wallpaper(self.last_source)

    def paint_reset(self):
        c=self.canvas;c.delete("reset_ui");enabled=self.auto_reset.get()
        x1,y1,x2,y2=self.rect((1033,373,58,28));rounded(c,x1,y1,x2,y2,13,fill="#eeeeef" if enabled else "#45454e",outline="#9696a3",tags=("ui","reset_ui"))
        x=1064 if enabled else 1038;c.create_oval(*self.rect((x,378,18,18)),fill="#17171c" if enabled else "#ceced6",outline="",tags=("ui","reset_ui"))
        self.text(1103,379,"ON" if enabled else "OFF",10,bold=True,tag="reset_ui")
    def paint_select_only(self):
        c=self.canvas;c.delete("select_ui");on=self.select_only.get()
        self.shape((491,423,13,13),"#eeeeef" if on else "#19191f",tag="select_ui",radius=1)
        self.text(515,420,"Select shape only",9,tag="select_ui")
    def _toggle_reset(self):
        enabled=not self.auto_reset.get();self.auto_reset.set(enabled);self.args.auto_reset=enabled
        if not enabled and self.state.get("reset_choice"):self.reset()
        self.last.set("Auto reset ON: choose the top/default shape." if enabled else "Auto reset OFF: default-shape selection is manual.")
    def input_focus(self,index):
        self.focused_input=index
        for i in range(4):self.canvas.itemconfigure("input_"+str(i),outline="#a7a7b4" if i==index else "#4a4a56")
    def increment(self,index,direction):
        low,high=[(0,200),(0,200),(4,40),(60,360)][index]
        try:value=self.values[index].get()
        except Exception:value=low
        self.values[index].set(max(low,min(high,value+direction)));return "break"
    def hit(self,event):
        x,y=event.x/self.scale_x,event.y/self.scale_y
        for key,(left,top,w,h),command in reversed(self.hitboxes):
            if left<=x<=left+w and top<=y<=top+h:return key,command
        return None,None
    def motion(self,event):
        key,_=self.hit(event);self.set_hover(key);self.canvas.configure(cursor="hand2" if key else "")
    def set_hover(self,key):
        if self.hover==key:return
        self.hover=key
        if self.hover_timer is None:self.animate_hover()
    def animate_hover(self):
        pending=False
        for key,(shape,label,primary) in self.button_shapes.items():
            value=self.animations.get(key,0);target=1 if key==self.hover else 0;value+=(target-value)*.3
            if abs(value-target)<.02:value=target
            else:pending=True
            self.animations[key]=value
            if primary:
                a,b=((78,210,124),(119,236,157)) if self.state["enabled"] else ((238,238,239),(210,210,218))
                fg="#062512" if self.state["enabled"] else "#111114"
            else:a,b=(44,44,52),(76,76,90);fg=self.TEXT
            color="#"+"".join(f"{round(x+(y-x)*value):02x}" for x,y in zip(a,b))
            self.canvas.itemconfigure(shape,fill=color);self.canvas.itemconfigure(label,fill=fg)
        self.hover_timer=self.root.after(16,self.animate_hover) if pending else None
    def mouse_down(self,event):
        self.pressed=self.hit(event)[0];self.canvas.focus_set()
    def mouse_up(self,event):
        key,command=self.hit(event)
        if key is not None and key==self.pressed and command:command()
        self.pressed=None
    def toggle(self):
        self.state["enabled"]=not self.state["enabled"];self.reset();self.refresh(schedule=False)
    def preset(self,name):
        for var,value in zip(self.values,self.PRESETS[name]):var.set(value)
        if self.apply():self.show_success(name+" applied.\nStart or press F6 to resume.")
    def paint_presets(self):
        try:values=tuple(v.get() for v in self.values)
        except Exception:return
        for name,preset in self.PRESETS.items():
            button=self.button_shapes.get("preset_"+name)
            if button:
                self.canvas.itemconfigure(button[0],outline="#eeeeef" if values==preset else "#555560")
    def apply(self):
        try:
            values=[v.get() for v in self.values]
            for v,(lo,hi) in zip(values,[(0,200),(0,200),(4,40),(60,360)]):
                if not lo<=v<=hi:raise ValueError("A response setting is outside its allowed range.")
            key_name,key_vk=parse_edit_key(self.edit_key.get())
            process=self.process.get().strip()
            if not process.lower().endswith(".exe") or any(x in process for x in ("/","\\")):raise ValueError("Use an executable filename, such as client.exe.")
            save_edit_key(key_name)
        except Exception as error:self.messagebox.showerror("Check settings",str(error),parent=self.root);return False
        self.state["enabled"]=False;self.reset()
        self.args.stable_ms,self.args.apply_delay_ms,self.args.click_ms,self.args.scan_hz=values
        self.args.edit_key,self.args.edit_vk=key_name,key_vk;self.edit_key.set(key_name)
        self.args.select_only=self.select_only.get();self.args.auto_reset=self.auto_reset.get();self.args.process=process
        self.paint_presets();self.show_success("Settings applied.\nStart or press F6 to resume.");self.refresh(schedule=False)
        return True
    def paint_text(self,tag,value):
        if self.paint_cache.get(tag)!=value:
            self.canvas.itemconfigure(tag,text=value);self.paint_cache[tag]=value
    def show_success(self,message):
        self.success_message=message;self.last.set(message)
    def update_last(self):
        if self.canvas.winfo_exists():
            success=self.last.get()==self.success_message
            size=14 if success else 10
            self.canvas.itemconfigure("last",text=self.last.get(),fill="#4ee38a" if success else self.TEXT,
                font=(UI_FONT,max(8,round(size*min(self.scale_x,self.scale_y))),"bold" if success else "normal"))
    def refresh(self,schedule=True):
        while True:
            try:kind,value=self.events.get_nowait()
            except queue.Empty:break
            if kind=="quit":self.close();return
            if kind=="show":self.show_window();continue
            if kind=="toggle":self.toggle();continue
            if kind=="tray_ready":
                self.tray_ready=True;self.tray_starting=False;self.update_tray();continue
            if kind=="tray_error":
                self.tray_ready=False;self.tray_starting=False
                self.show_window();self.last.set("Tray unavailable: "+str(value)+". F10 exits.");continue
            self.last.set(str(value))
        self.update_tray()
        if self.root.state() in ("iconic","withdrawn"):
            # Drain tray/hotkey events, but skip UI painting and process lookups while hidden.
            if schedule and not self.stop.is_set():self.root.after(200,self.refresh)
            return
        enabled=self.state["enabled"];phase=self.state["stage"];game=self.foreground_game() if enabled else None
        status="Paused" if not enabled else "Restoring default" if self.state.get("reset_choice") else "Choosing edit" if self.state["editing"] and phase=="select" else "Applying edit" if self.state["editing"] else "Ready to edit"
        self.paint_text("status",status)
        changed=self.last_enabled!=enabled
        if changed and hasattr(self,"dot"):
            self.canvas.itemconfigure(self.dot,fill="#4ee38a" if enabled else "#a6a6b0")
        self.paint_text("process_status","Focused / "+self.args.process if game else "Waiting for "+self.args.process)
        edit_key=getattr(self.args,"edit_key","G")
        self.paint_text("detail",f"Press {edit_key} and move to your edit. The clicks are automatic." if enabled else f"Start the helper, return to your game, then press {edit_key}.")
        self.paint_text("edit_hint",f"{edit_key} → choose shape → automatic apply")
        self.paint_text("label_start","Pause helper  /  F6" if enabled else "Start helper  /  F6")
        self.paint_text("metrics",f"Processing {self.stats['processing_ms']:.1f} ms  /  Scan {self.stats.get('actual_hz',0):.0f} Hz\nApply clicks {self.stats['applied']}")
        if changed and self.hover_timer is None:self.animate_hover()
        self.last_enabled=enabled
        if schedule and not self.stop.is_set():self.root.after(150 if self.root.focus_displayof() else 750,self.refresh)
    def resize(self,event):
        size=(event.width,event.height)
        if size==self.last_canvas_size:return
        self.last_canvas_size=size
        self.scale_x=event.width/1200;self.scale_y=event.height/720
        self.draw_ui()
    def open_youtube(self):
        import webbrowser
        webbrowser.open("https://www.youtube.com/@sg0hann")

    def style_titlebar(self):
        if os.name!="nt":return
        try:
            native=C.WinDLL("user32");dwm=C.WinDLL("dwmapi")
            native.GetAncestor.argtypes=[W.HWND,W.UINT];native.GetAncestor.restype=W.HWND
            dwm.DwmSetWindowAttribute.argtypes=[W.HWND,W.DWORD,C.c_void_p,W.DWORD]
            dwm.DwmSetWindowAttribute.restype=C.c_long
            hwnd=native.GetAncestor(self.root.winfo_id(),2)
            dark=C.c_int(1)
            if dwm.DwmSetWindowAttribute(hwnd,20,C.byref(dark),C.sizeof(dark))!=0:
                dwm.DwmSetWindowAttribute(hwnd,19,C.byref(dark),C.sizeof(dark))
            # Windows 11 caption/border/text colors; older versions retain dark mode.
            for attribute,color in ((34,0x000000),(35,0x000000),(36,0xFFFFFF)):
                value=W.DWORD(color)
                dwm.DwmSetWindowAttribute(hwnd,attribute,C.byref(value),C.sizeof(value))
        except (OSError,AttributeError):pass
    def load_wallpaper(self):
        from PIL import Image,ImageOps
        # A fixed bundled background: previous custom-wallpaper settings are ignored.
        with Image.open(resource_path("assets/wallpaper.jpg")) as image:
            self.last_source=ImageOps.exif_transpose(image).convert("RGB")
            self.last_source.thumbnail((1200,720),Image.Resampling.LANCZOS)
    def render_wallpaper(self,frame):
        from PIL import Image,ImageOps,ImageDraw,ImageTk
        w=max(1,self.canvas.winfo_width());h=max(1,self.canvas.winfo_height())
        image=ImageOps.fit(frame,(w,h),method=Image.Resampling.BILINEAR).convert("RGB")
        if self.overlay_cache is None or self.overlay_cache[0]!=(w,h):
            # Compile darkness and panel opacity once; blend one RGB pass per frame.
            base=Image.new("RGBA",(w,h),(0,0,0,92))
            layer=Image.new("RGBA",(w,h));draw=ImageDraw.Draw(layer)
            draw.rounded_rectangle(self.rect((28,90,410,150)),radius=16,fill=(18,18,22,196),outline=(140,140,155,95))
            draw.rounded_rectangle(self.rect((462,90,710,506)),radius=16,fill=(18,18,22,178),outline=(160,160,175,110))
            draw.rectangle((0,0,w,80*self.scale_y),fill=(5,5,8,125))
            draw.rectangle((0,658*self.scale_y,w,h),fill=(5,5,8,175))
            overlay=Image.alpha_composite(base,layer)
            self.overlay_cache=((w,h),overlay.convert("RGB"),overlay.getchannel("A"))
        _,foreground,alpha=self.overlay_cache
        image=Image.composite(foreground,image,alpha)
        if self.background_photo is not None and self.background_photo.width()==w and self.background_photo.height()==h:
            self.background_photo.paste(image)
        else:
            self.background_photo=ImageTk.PhotoImage(image);self.canvas.itemconfigure(self.background_item,image=self.background_photo)
            self.canvas.tag_lower(self.background_item)
    def start_tray(self):
        if os.name!="nt":return
        try:
            import pystray
            self.tray_starting=True
            menu=pystray.Menu(
                pystray.MenuItem("Open Quick Edit",lambda icon,item:self.events.put(("show",None)),default=True),
                pystray.MenuItem(lambda item:"Pause helper" if self.state["enabled"] else "Start helper",
                    lambda icon,item:self.events.put(("toggle",None))),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit",lambda icon,item:self.events.put(("quit",None))))
            self.tray=pystray.Icon("sg0hann.QuickEdit",self.app_art.resize((64,64)),"Quick Edit • Paused",menu)
            def setup(icon):
                if self.stop.is_set():icon.stop();return
                try:
                    icon.visible=True;self.events.put(("tray_ready",None))
                except Exception as error:
                    self.events.put(("tray_error",str(error)));icon.stop()
            def run():
                try:
                    self.tray.run(setup=setup)
                    if not self.stop.is_set():self.events.put(("tray_error","Tray icon stopped"))
                except Exception as error:
                    if not self.stop.is_set():self.events.put(("tray_error",str(error)))
            self.tray_thread=threading.Thread(target=run,name="QuickEdit-Tray",daemon=True)
            self.tray_thread.start()
        except Exception as error:
            self.tray_starting=False;self.events.put(("tray_error",str(error)))
    def update_tray(self):
        enabled=bool(self.state["enabled"])
        if not self.tray_ready or not self.tray or self.tray_enabled==enabled:return
        try:
            self.tray.title="Quick Edit • "+("Running" if enabled else "Paused")
            self.tray.update_menu();self.tray_enabled=enabled
        except Exception as error:
            self.tray_ready=False;self.events.put(("tray_error",str(error)))
    def hide_to_tray(self):
        if self.tray_ready:
            self.root.withdraw()
        elif self.tray_starting:
            self.last.set("Tray icon is starting. Try again in a moment.")
        else:
            self.close()  # Never strand a running app without a working tray icon.
    def show_window(self):
        self.root.deiconify();self.root.lift();self.root.focus_force()
    def close(self):
        if self.closing:return
        self.closing=True
        self.state["enabled"]=False;self.reset();self.stop.set()
        if self.tray:
            try:self.tray.stop()
            except Exception:pass
        self.root.destroy()




def main():
    if os.name != "nt":
        raise SystemExit("This helper requires Windows.")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--edit-key",default=load_edit_key(),help="Keyboard edit bind, for example G, E, V, Tab or Space")
    parser.add_argument("--process", default="client.exe", help="Foreground game executable filename")
    parser.add_argument("--apply-delay-ms", type=int, default=8, help="Wait before applying, 0-200 ms")
    parser.add_argument("--select-only", action="store_true")
    parser.add_argument("--no-auto-reset",dest="auto_reset",action="store_false",default=True)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--stable-ms", type=int, default=10, help="Yellow selection dwell time, 0-200 ms")
    parser.add_argument("--click-ms",type=int,default=8)
    parser.add_argument("--scan-hz",type=int,default=144)
    args = parser.parse_args()
    try:args.edit_key,args.edit_vk=parse_edit_key(args.edit_key)
    except ValueError as error:parser.error(str(error))
    if not 0 <= args.stable_ms <= 200:
        parser.error("--stable-ms must be between 0 and 200")
    if not 4 <= args.click_ms <= 40 or not 60 <= args.scan_hz <= 360:
        parser.error("Click hold must be 4-40 ms; scan limit must be 60-360 Hz")
    try:
        global np
        import numpy as np
        from PIL import ImageGrab, Image
        import mss
        import tkinter as tk
    except ImportError:
        raise SystemExit("Install dependencies: py -m pip install -r requirements.txt")
    if not 0 <= args.apply_delay_ms <= 200:
        parser.error("--apply-delay-ms must be between 0 and 200")

    try:
        shell=C.WinDLL("shell32")
        shell.SetCurrentProcessExplicitAppUserModelID.argtypes=[W.LPCWSTR]
        shell.SetCurrentProcessExplicitAppUserModelID("sg0hann.QuickEdit")
    except (OSError,AttributeError):
        pass
    user = C.WinDLL("user32", use_last_error=True)
    kernel = C.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes=[C.c_void_p,W.BOOL,W.LPCWSTR]
    kernel.CreateMutexW.restype=W.HANDLE
    mutex=kernel.CreateMutexW(None,False,"Local\\CDQuickEditDesktopHelper")
    if not mutex:
        raise C.WinError(C.get_last_error())
    if C.get_last_error()==183:
        from tkinter import messagebox
        messagebox.showinfo("CD Quick Edit","The helper is already running. Close the older window first.")
        kernel.CloseHandle.argtypes=[W.HANDLE]
        kernel.CloseHandle(mutex)
        return
    ULONG_PTR = C.c_size_t
    LRESULT = C.c_ssize_t
    HOOKPROC = C.WINFUNCTYPE(LRESULT, C.c_int, W.WPARAM, W.LPARAM)

    class MouseHook(C.Structure):
        _fields_ = [("pt", W.POINT), ("mouseData", W.DWORD), ("flags", W.DWORD),
                    ("time", W.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class KeyboardHook(C.Structure):
        _fields_ = [("vkCode", W.DWORD), ("scanCode", W.DWORD), ("flags", W.DWORD),
                    ("time", W.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class MouseInput(C.Structure):
        _fields_ = [("dx", W.LONG), ("dy", W.LONG), ("mouseData", W.DWORD),
                    ("dwFlags", W.DWORD), ("time", W.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class KeyboardInput(C.Structure):
        _fields_ = [("wVk", W.WORD), ("wScan", W.WORD), ("dwFlags", W.DWORD),
                    ("time", W.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class HardwareInput(C.Structure):
        _fields_ = [("uMsg", W.DWORD), ("wParamL", W.WORD), ("wParamH", W.WORD)]

    class Payload(C.Union):
        _fields_ = [("mi", MouseInput), ("ki", KeyboardInput), ("hi", HardwareInput)]

    class Input(C.Structure):
        _anonymous_ = ("data",)
        _fields_ = [("type", W.DWORD), ("data", Payload)]

    try:
        C.WinDLL("shcore").SetProcessDpiAwareness(2)
    except (OSError, AttributeError):
        user.SetProcessDPIAware()
    user.GetCursorPos.argtypes = [C.POINTER(W.POINT)]
    user.GetClientRect.argtypes = [W.HWND, C.POINTER(W.RECT)]
    user.ClientToScreen.argtypes = [W.HWND, C.POINTER(W.POINT)]
    user.IsIconic.argtypes = [W.HWND]
    user.SetWindowsHookExW.argtypes = [C.c_int, HOOKPROC, W.HINSTANCE, W.DWORD]
    user.SetWindowsHookExW.restype = W.HANDLE
    user.CallNextHookEx.argtypes = [W.HANDLE, C.c_int, W.WPARAM, W.LPARAM]
    user.CallNextHookEx.restype = LRESULT
    user.UnhookWindowsHookEx.argtypes = [W.HANDLE]
    user.GetForegroundWindow.restype = W.HWND
    user.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
    user.SendInput.argtypes = [W.UINT, C.POINTER(Input), C.c_int]
    user.SendInput.restype = W.UINT
    user.GetMessageW.argtypes = [C.POINTER(W.MSG), W.HWND, W.UINT, W.UINT]
    user.GetMessageW.restype = W.BOOL
    user.PostThreadMessageW.argtypes = [W.DWORD, W.UINT, W.WPARAM, W.LPARAM]
    kernel.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
    kernel.OpenProcess.restype = W.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD)]
    kernel.CloseHandle.argtypes = [W.HANDLE]
    kernel.GetModuleHandleW.argtypes = [W.LPCWSTR]
    kernel.GetModuleHandleW.restype = W.HMODULE
    kernel.GetCurrentThreadId.restype = W.DWORD

    state = {"enabled": False, "editing": False, "window": None, "seen": False, "motion": 0, "last_pos": None, "generation": 0, "stage": "select", "manual_held": False, "started": 0, "reset_choice": False, "hover_default": False}
    state_lock = threading.RLock()
    ui_events = queue.Queue()
    stats = {"processing_ms":0.0,"applied":0,"actual_hz":0.0}
    def report(message):
        ui_events.put(("message",message))
    keys_down = set()
    jobs = queue.Queue()
    stop = threading.Event()
    wake = threading.Event()
    hook_control={"id":None}
    hook_ready=threading.Event()
    def notify_hooks():
        if hook_control["id"]:
            user.PostThreadMessageW(hook_control["id"],0x8001,0,0)

    foreground_cache = {}
    def foreground_game():
        hwnd = user.GetForegroundWindow()
        if not hwnd:
            return None
        pid = W.DWORD()
        user.GetWindowThreadProcessId(hwnd, C.byref(pid))
        now = time.monotonic()
        key = (hwnd,pid.value,args.process.casefold())
        cached = foreground_cache.get(key)
        if cached and now-cached[0] < 2:
            return hwnd if cached[1] else None
        handle = kernel.OpenProcess(0x1000, False, pid.value)
        if not handle:
            return None
        try:
            size = W.DWORD(32768)
            path = C.create_unicode_buffer(size.value)
            if kernel.QueryFullProcessImageNameW(handle, 0, path, C.byref(size)):
                matched=os.path.basename(path.value).casefold() == args.process.casefold()
                foreground_cache.clear()
                foreground_cache[key]=(now,matched)
                return hwnd if matched else None
        finally:
            kernel.CloseHandle(handle)
        return None

    def reset():
        with state_lock:
            state["editing"] = False
            state["window"] = None
            state["stage"] = "select"
            state["started"] = time.monotonic()
            state["seen"] = False
            state["reset_choice"] = False
            state["hover_default"] = False
            state["motion"] = 0
            state["last_pos"] = None
            state["generation"] += 1
            state["manual_held"] = False
        wake.set()
        notify_hooks()


    def worker():
        while not stop.is_set():
            try:
                job = jobs.get()
                if job is None:return
                hwnd, generation, action = job
            except queue.Empty:
                continue
            with state_lock:
                if stop.is_set() or not state["enabled"] or foreground_game() != hwnd or state["generation"] != generation:
                    continue
                if action.endswith("_reset") and not args.auto_reset:
                    continue
                events = (Input * 2)()
                events[0].type = events[1].type = 0
                events[0].mi.dwFlags, events[1].mi.dwFlags = 0x0002, 0x0004
            if user.SendInput(1, C.byref(events[0]), C.sizeof(Input)) != 1:
                report("Input blocked; paused. Check game/helper privilege levels.")
                state["enabled"] = False
                reset()
                continue
            precise=winmm.timeBeginPeriod(1)==0
            try:
                stop.wait(args.click_ms/1000)
            finally:
                user.SendInput(1, C.byref(events[1]), C.sizeof(Input))
                if precise:winmm.timeEndPeriod(1)
            if action.startswith("apply"):
                stats["applied"] += 1
            report({"select":"Selected edit shape.","select_reset":"Selected the default shape.","apply":"Sent final edit click.","apply_reset":"Sent reset click for the default shape."}[action])

    @HOOKPROC
    def keyboard(code, message, data):
        # Ignore unrelated keys without acquiring the engine lock.
        if code < 0:return user.CallNextHookEx(None,code,message,data)
        quick=C.cast(data,C.POINTER(KeyboardHook)).contents
        if quick.flags & 0x10:return user.CallNextHookEx(None,code,message,data)
        # Always release old key state, even when the bind changed while a key was held.
        if message in (0x101,0x105):
            keys_down.discard(quick.vkCode)
            return user.CallNextHookEx(None,code,message,data)
        if quick.vkCode not in (0x79,0x75,0x1B,0x45,0x31,0x32,0x33,0x34,0x35,0x46,0x58,0x43) and not edit_key_matches(quick.vkCode,args.edit_vk):
            return user.CallNextHookEx(None,code,message,data)
        with state_lock:
            if code >= 0:
                info = C.cast(data, C.POINTER(KeyboardHook)).contents
                if not info.flags & 0x10:  # Ignore injected keyboard events.
                    vk = info.vkCode
                    if message in (0x101, 0x105):
                        keys_down.discard(vk)
                    elif message in (0x100, 0x104) and vk not in keys_down:
                        keys_down.add(vk)
                        if vk == 0x79:  # F10
                            ui_events.put(("quit",None))
                        elif vk == 0x75:  # F6
                            state["enabled"] = not state["enabled"]
                            reset()
                            report("Running." if state["enabled"] else "Paused.")
                        elif edit_key_matches(vk,args.edit_vk) and state["enabled"]:
                            hwnd = foreground_game()
                            if hwnd:
                                was_editing = state["editing"]
                                reset()
                                state["editing"] = not was_editing
                                state["window"] = hwnd if state["editing"] else None
                                cursor = W.POINT()
                                if user.GetCursorPos(C.byref(cursor)):
                                    state["last_pos"] = (cursor.x,cursor.y)
                                state["manual_held"]=bool(user.GetAsyncKeyState(1)&0x8000)
                                wake.set();notify_hooks()
                        elif vk in (0x1B, 0x45, 0x31, 0x32, 0x33, 0x34, 0x35):
                            reset()
                        elif vk in (0x46, 0x58, 0x43):  # F, X, C select builds
                            reset()
        return user.CallNextHookEx(None, code, message, data)


    @HOOKPROC
    def mouse(code, message, data):
        # Never wait on the engine lock for input directed at the desktop/taskbar.
        if code < 0 or not state["editing"] or state["window"]!=user.GetForegroundWindow():
            return user.CallNextHookEx(None,code,message,data)
        with state_lock:
            if code >= 0:
                info = C.cast(data, C.POINTER(MouseHook)).contents
                if not info.flags & 1:
                    if message == 0x200 and state["editing"]:
                        pos = (info.pt.x, info.pt.y)
                        old = state["last_pos"]
                        if old:
                            state["motion"] += abs(pos[0]-old[0]) + abs(pos[1]-old[1])
                        state["last_pos"] = pos
                    elif message == 0x201:
                        state["manual_held"] = True
                        if state["editing"] and state["seen"] and state["stage"] == "select":
                            if state["hover_default"] and not args.auto_reset:
                                reset()  # With Auto reset OFF, both default/reset clicks stay manual.
                            else:
                                state["reset_choice"] = state["hover_default"]
                                state["stage"] = "wait_preview"
                                state["started"] = time.monotonic()
                        elif state["editing"] and state["stage"] == "wait_preview":
                            reset()  # The player supplied the final click manually.
                    elif message == 0x202:
                        state["manual_held"] = False
                    elif message == 0x204:
                        reset()
        return user.CallNextHookEx(None, code, message, data)


    def vision_worker():
        yellow_since = preview_since = None
        previous_generation = -1
        previous_sector = None
        last_debug = 0
        capture = None
        try:
            capture = mss.MSS()
        except Exception as error:
            report("Native capture unavailable; using Pillow: "+str(error))
        timer_active=False
        try:
            previous_tick = time.perf_counter()
            while not stop.is_set():
                if not state["editing"] or not state["enabled"]:
                    if timer_active:
                        winmm.timeEndPeriod(1);timer_active=False
                    wake.wait()
                    wake.clear()
                    previous_tick = 0
                    yellow_since = preview_since = None
                    continue
                if not timer_active:timer_active=winmm.timeBeginPeriod(1)==0
                period = 1/args.scan_hz
                remaining = period-(time.perf_counter()-previous_tick)
                if remaining > 0 and stop.wait(remaining):
                    break
                tick = time.perf_counter()
                if previous_tick > 0:
                    stats["actual_hz"] = .8*stats["actual_hz"]+.2/max(tick-previous_tick,.0001)
                previous_tick = tick
                if not state["enabled"] or not state["editing"]:
                    yellow_since = preview_since = None
                    continue
                hwnd = foreground_game()
                if not hwnd or hwnd != state["window"] or user.IsIconic(hwnd):
                    reset()
                    continue
                generation = state["generation"]
                if generation != previous_generation:
                    yellow_since = preview_since = None
                    previous_sector = None
                    previous_generation = generation
                rect, point = W.RECT(), W.POINT(0,0)
                if not user.GetClientRect(hwnd,C.byref(rect)) or not user.ClientToScreen(hwnd,C.byref(point)):
                    continue
                if rect.right < 400 or rect.bottom < 300:
                    continue
                try:
                    processing_start = time.perf_counter()
                    side = round(450*rect.bottom/1080)
                    left = round(point.x+rect.right/2-side/2)
                    top = round(point.y+rect.bottom/2-side/2)
                    if capture is not None:
                        shot=capture.grab({"left":left,"top":top,"width":side,"height":side})
                        frame=Image.frombytes("RGB",shot.size,shot.bgra,"raw","BGRX")
                    else:
                        frame=ImageGrab.grab(bbox=(left,top,left+side,top+side),all_screens=True).convert("RGB")
                    wheel, selected, build, details = detect(frame,cropped=True)
                    elapsed=(time.perf_counter()-processing_start)*1000
                    stats["processing_ms"] = .8*stats["processing_ms"]+.2*elapsed
                except Exception as error:
                    report("Capture failed; paused: "+str(error))
                    state["enabled"] = False
                    reset()
                    continue
                with state_lock:
                    if generation != state["generation"] or foreground_game() != hwnd:
                        continue
                    now = time.monotonic()
                    if args.debug and now-last_debug > .5:
                        report(str((state["stage"],details)))
                        last_debug = now
                    if wheel:
                        state["seen"] = True
                        state["hover_default"] = details["default"]
                    if state["stage"] == "wait_preview":
                        if now-state["started"] > 2.5:
                            report("No apply prompt detected; stopped this edit.")
                            reset()
                            continue
                        if not wheel and build and not state["manual_held"]:
                            preview_since = preview_since or now
                            if now-preview_since >= args.apply_delay_ms/1000:
                                is_reset=state["reset_choice"]
                                reset()
                                jobs.put((hwnd,state["generation"],"apply_reset" if is_reset else "apply"))
                        else:
                            preview_since = None
                        continue
                    if now-state["started"] > 12:
                        reset()
                        continue
                    if selected and (args.auto_reset or not details["default"]) and state["motion"] >= 5 and not state["manual_held"]:
                        if details["sector"] != previous_sector:
                            yellow_since = None
                        previous_sector = details["sector"]
                        yellow_since = yellow_since or now
                        if now-yellow_since >= args.stable_ms/1000:
                            is_reset=details["default"]
                            state["reset_choice"]=is_reset
                            if args.select_only:
                                reset()
                            else:
                                state["stage"] = "wait_preview"
                                state["started"] = now
                            jobs.put((hwnd,state["generation"],"select_reset" if is_reset else "select"))
                            yellow_since = None
                    else:
                        yellow_since = None
        finally:
            if timer_active:winmm.timeEndPeriod(1)
            if capture is not None:capture.close()

    def hook_worker():
        # Windows input hooks have their own message thread, independent of Tk.
        keyboard_hook=mouse_hook=None;timer=0;message=W.MSG()
        try:
            user.PeekMessageW(C.byref(message),None,0,0,0)
            hook_control["id"]=kernel.GetCurrentThreadId()
            keyboard_hook=user.SetWindowsHookExW(13,keyboard,module,0)
            if not keyboard_hook:raise C.WinError(C.get_last_error())
            timer=user.SetTimer(None,0,250,None)
            if not timer:raise C.WinError(C.get_last_error())
            hook_ready.set()
            while not stop.is_set():
                result=user.GetMessageW(C.byref(message),None,0,0)
                if result==0:break
                if result<0:raise C.WinError(C.get_last_error())
                wanted=state["enabled"] and state["editing"] and state["window"]==user.GetForegroundWindow()
                if wanted and not mouse_hook:
                    mouse_hook=user.SetWindowsHookExW(14,mouse,module,0)
                    if not mouse_hook:raise C.WinError(C.get_last_error())
                elif not wanted and mouse_hook:
                    user.UnhookWindowsHookEx(mouse_hook);mouse_hook=None
        finally:
            if mouse_hook:user.UnhookWindowsHookEx(mouse_hook)
            if keyboard_hook:user.UnhookWindowsHookEx(keyboard_hook)
            if timer:user.KillTimer(None,timer)
            hook_control["id"]=None;hook_ready.set()

    def run_guarded(function):
        try:
            function()
        except Exception as error:
            state["enabled"] = False
            reset()
            report("Engine paused: "+str(error))

    root = tk.Tk()
    app = AppUI(root,state,stats,args,reset,foreground_game,stop,ui_events)
    winmm = C.WinDLL("winmm")
    winmm.timeBeginPeriod.argtypes=[W.UINT];winmm.timeBeginPeriod.restype=W.UINT
    winmm.timeEndPeriod.argtypes=[W.UINT];winmm.timeEndPeriod.restype=W.UINT
    user.SetTimer.argtypes=[W.HWND,C.c_size_t,W.UINT,C.c_void_p];user.SetTimer.restype=C.c_size_t
    user.KillTimer.argtypes=[W.HWND,C.c_size_t];user.KillTimer.restype=W.BOOL
    user.PeekMessageW.argtypes=[C.POINTER(W.MSG),W.HWND,W.UINT,W.UINT,W.UINT]
    user.GetAsyncKeyState.argtypes=[C.c_int];user.GetAsyncKeyState.restype=C.c_short
    module = kernel.GetModuleHandleW(None)
    threads = []
    try:
        threads = [threading.Thread(target=run_guarded,args=(function,),daemon=True) for function in (hook_worker,worker,vision_worker)]
        for thread in threads:thread.start()
        root.mainloop()
    finally:
        stop.set()
        wake.set()
        jobs.put(None)
        if hook_control["id"]:user.PostThreadMessageW(hook_control["id"],0x0012,0,0)
        for thread in threads:
            thread.join(timeout=.5)
        kernel.CloseHandle(mutex)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        error=traceback.format_exc()
        from pathlib import Path
        folder=Path(os.environ.get("LOCALAPPDATA",str(Path.home())))/"CDQuickEdit"
        folder.mkdir(parents=True,exist_ok=True)
        log=folder/"error.log"
        log.write_text(error,encoding="utf-8")
        try:
            from tkinter import messagebox
            messagebox.showerror("CD Quick Edit", "Could not start the helper.\n\n"+error.splitlines()[-1]+"\n\nDetails: "+str(log))
        except Exception:
            print(error)


