"""Dark glass-inspired desktop primitives. No webview or backdrop blur runtime."""

import base64
import math
from importlib import resources
import sys
import tkinter as tk

BG = "#080f1d"
SURFACE = "#131e30"
INK = "#edf4ff"
MUTED = "#95a7c3"
LINE = "#2d3e58"
BLUE = "#8de7ee"
PALE = "#203c50"
FONT = "SF Pro Text" if sys.platform == "darwin" else "Segoe UI" if sys.platform == "win32" else "DejaVu Sans"


def rounded(canvas,x1,y1,x2,y2,radius=14,**kwargs):
    radius = max(0,min(radius,(x2-x1)/2,(y2-y1)/2))
    points = []
    for cx,cy,start in ((x2-radius,y1+radius,-90),(x2-radius,y2-radius,0),(x1+radius,y2-radius,90),(x1+radius,y1+radius,180)):
        for step in range(9):
            angle = math.radians(start+step*90/8)
            points.extend((cx+math.cos(angle)*radius,cy+math.sin(angle)*radius))
    return canvas.create_polygon(points,**kwargs)


def logo(master,size=64):
    data = resources.files("facetedit").joinpath(f"assets/logo-{size}.png").read_bytes()
    return tk.PhotoImage(master=master,data=base64.b64encode(data))


def label(parent,text,size=10,bold=False,color=INK,**kwargs):
    return tk.Label(parent,text=text,bg=parent.cget("bg"),fg=color,font=(FONT,size,"bold" if bold else "normal"),**kwargs)


class GlassPanel(tk.Canvas):
    def __init__(self,parent,width,height,**kwargs):
        super().__init__(parent,width=width,height=height,bg=BG,highlightthickness=0,**kwargs)
        self.body = tk.Frame(self,bg=SURFACE)
        self.window = self.create_window(16,15,window=self.body,anchor="nw",width=width-32,height=height-30)
        self.bind("<Configure>",self._draw)

    def _draw(self,event=None):
        self.delete("chrome")
        width,height = self.winfo_width(),self.winfo_height()
        rounded(self,4,7,width-1,height-1,25,fill="#040a14",outline="",tags="chrome")
        rounded(self,1,1,width-5,height-6,24,fill=SURFACE,outline="#354960",width=1,tags="chrome")
        self.create_line(24,2,width-29,2,fill="#66778e",width=1,tags="chrome")
        self.create_line(25,4,width-30,4,fill="#25364c",width=1,tags="chrome")
        for index,tint in enumerate(("#5e9ba9","#648dba","#777dba","#786d9e")):
            left = 24+(width-53)*index/4
            right = 24+(width-53)*(index+1)/4
            self.create_line(left,2,right,2,fill=tint,width=1,tags="chrome")
        self.coords(self.window,16,15)
        self.itemconfigure(self.window,width=max(1,width-36),height=max(1,height-34))
        self.tag_lower("chrome")


class Pill(tk.Canvas):
    def __init__(self,parent,text,command,primary=False,width=120,height=38,**kwargs):
        super().__init__(parent,width=width,height=height,bg=parent.cget("bg"),highlightthickness=0,takefocus=True,cursor="hand2",**kwargs)
        self.text,self.command,self.primary = text,command,primary
        self.enabled,self.hover = True,False
        self.selected = False
        self.bind("<Button-1>",self.invoke)
        self.bind("<Return>",self.invoke)
        self.bind("<space>",self.invoke)
        self.bind("<Enter>",lambda _:self._hover(True))
        self.bind("<Leave>",lambda _:self._hover(False))
        for event in ("<FocusIn>","<FocusOut>","<Configure>"):
            self.bind(event,lambda _:self.draw())
        self.draw()

    def _hover(self,value):
        self.hover = value
        self.draw()

    def invoke(self,event=None):
        if self.enabled:
            self.command()
        return "break"

    def state(self,enabled):
        self.enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self.draw()

    def draw(self):
        self.delete("all")
        w = self.winfo_width() if self.winfo_width()>1 else int(self.cget("width"))
        h = self.winfo_height() if self.winfo_height()>1 else int(self.cget("height"))
        fill = ("#b6f5f6" if self.hover else BLUE) if self.primary else ("#2b405a" if self.hover else "#203047")
        if not self.enabled:
            fill = "#172337"
        elif self.selected:
            fill = "#284b60"
        stroke = BLUE if self.focus_get() == self else ("#c5ffff" if self.primary else "#354960")
        rounded(self,1,1,w-2,h-2,min(17,h/2-2),fill=fill,outline=stroke if self.enabled else "#24334a",width=1)
        if self.enabled and not self.primary:
            self.create_line(13,3,w-15,3,fill="#4b5b73")
        self.create_text(w/2,h/2-1,text=self.text,font=(FONT,10,"bold" if self.primary else "normal"),fill=("#09202c" if self.primary else INK) if self.enabled else "#667a96")


class TabStack(tk.Frame):
    """Accessible segmented glass controls without platform notebook borders."""
    def __init__(self,parent):
        super().__init__(parent,bg=SURFACE)
        self.navigation = tk.Frame(self,bg=SURFACE)
        self.navigation.pack(fill="x",pady=(0,12))
        self.pages,self.buttons = [],[]
        self.current = -1

    def add(self,page,text):
        index = len(self.pages)
        self.pages.append(page)
        button = Pill(self.navigation,text,lambda:self.select(index),width=60,height=33)
        button.pack(side="left",padx=(0,2))
        self.buttons.append(button)
        if self.current < 0:
            self.select(0)

    def select(self,index=None):
        if index is None:
            return self.current
        index = int(index)
        if not 0<=index<len(self.pages):
            raise IndexError(index)
        if self.current >= 0:
            self.pages[self.current].pack_forget()
        self.current = index
        self.pages[index].pack(fill="both",expand=True)
        for i,button in enumerate(self.buttons):
            button.selected = i==index
            button.draw()

    def tabs(self):
        return tuple(self.pages)
