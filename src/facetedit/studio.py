"""FacetEdit's floating studio layout, separate from editor commands."""

import tkinter as tk
from tkinter import ttk

from .chrome import BG,SURFACE,INK,MUTED,LINE,BLUE,PALE,FONT,GlassPanel,Pill,TabStack,label
from .render import VoxelView


class StudioLayout:
    def _build_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TEntry",fieldbackground="#0b1525",foreground=INK,insertcolor=BLUE,bordercolor=LINE,lightcolor=LINE,darkcolor=LINE,padding=7)
        style.configure("TCombobox",fieldbackground="#18273c",background="#18273c",foreground=INK,arrowcolor=BLUE,bordercolor=LINE,lightcolor=LINE,darkcolor=LINE,padding=6)
        style.map("TCombobox",fieldbackground=[("readonly","#18273c")],selectbackground=[("readonly","#18273c")],selectforeground=[("readonly",INK)])
        self.option_add("*TCombobox*Listbox.background",SURFACE)
        self.option_add("*TCombobox*Listbox.foreground",INK)
        self.option_add("*TCombobox*Listbox.selectBackground",PALE)
        style.configure("TCheckbutton",background=SURFACE,foreground=MUTED,font=(FONT,9))
        style.map("TCheckbutton",background=[("active",SURFACE)],foreground=[("active",INK)])
        style.configure('Treeview',background='#0b1627',fieldbackground='#0b1627',foreground=INK,
                        bordercolor=LINE,lightcolor=LINE,darkcolor=LINE,borderwidth=0,rowheight=32,font=(FONT,10))
        style.map('Treeview',background=[('selected',PALE)],foreground=[('selected',BLUE)])
        style.configure('Treeview.Heading',background='#1b2c42',foreground=MUTED,
                        bordercolor=LINE,lightcolor=LINE,darkcolor=LINE,relief='flat',font=(FONT,9,'bold'),padding=(10,8))
        style.map('Treeview.Heading',background=[('active','#24394c')],foreground=[('active',INK)])
        style.configure("TNotebook",background=SURFACE,borderwidth=0,tabmargins=(0,0,0,10))
        style.configure("TNotebook.Tab",background="#111c2c",foreground=MUTED,padding=(9,8),font=(FONT,9),borderwidth=0)
        style.map("TNotebook.Tab",background=[("selected","#24394c")],foreground=[("selected",BLUE)])
        style.layout("Vertical.TScrollbar",[("Vertical.Scrollbar.trough",{"sticky":"ns","children":[("Vertical.Scrollbar.thumb",{"expand":"1","sticky":"nswe"})]})])
        style.configure("Vertical.TScrollbar",background="#374a63",troughcolor=SURFACE,bordercolor=SURFACE,lightcolor="#374a63",darkcolor="#374a63",borderwidth=0,width=7,gripcount=0)
        style.map("Vertical.TScrollbar",background=[("disabled",SURFACE),("active","#53677f"),("!active","#374a63")],lightcolor=[("disabled",SURFACE)],darkcolor=[("disabled",SURFACE)])

    def _build_header(self):
        header = tk.Frame(self,bg=BG,height=86)
        header.pack(fill="x")
        header.pack_propagate(False)
        brand = tk.Frame(header,bg=BG)
        brand.pack(side="left",padx=(20,16))
        tk.Label(brand,image=self.app_logo,bg=BG).pack(side="left",padx=(0,7))
        word = tk.Frame(brand,bg=BG)
        word.pack(side="left")
        title = tk.Frame(word,bg=BG)
        title.pack(anchor="w")
        label(title,"Facet",22,True).pack(side="left")
        label(title,"Edit",22,False,BLUE).pack(side="left")
        label(word,"S H A P E   W H A T ' S   N E X T",7,color="#7389a8").pack(anchor="w",pady=(2,0))
        actions = tk.Frame(header,bg=BG)
        actions.pack(side="right",padx=20)
        self.save_button = Pill(actions,"Save copy  ↗",self.save_copy,True,132,40)
        self.save_button.pack(side="right",padx=(8,0))
        Pill(actions,"Open world",self.open_dialog,width=110,height=40).pack(side="right",padx=5)
        Pill(actions,"⌘ K" if self.tk.call('tk','windowingsystem')=='aqua' else "⌕  K",self.command_palette,width=55,height=40).pack(side="right",padx=5)
        name = tk.Frame(header,bg=BG)
        name.pack(side="left",padx=17)
        self.world_title = label(name,self.document.world.name,12,True)
        self.world_title.pack(anchor="w")
        self.edition_label = label(name,"Editable sample · Local workspace",8,color=MUTED)
        self.edition_label.pack(anchor="w",pady=(4,0))
        tk.Frame(self,bg="#253149",height=1).pack(fill="x")

    def _build_workspace(self):
        self.workspace = tk.Frame(self,bg=BG)
        self.workspace.pack(fill="both",expand=True)
        self.viewport = VoxelView(self.workspace,self.document,self._pick,self._render_error)
        self.viewport.radius = self.settings.data["radius"]
        self.viewport.grid = self.settings.data["grid"]
        self.viewport.glass = self.settings.data["glass"]
        from .navigation import apply_navigation
        apply_navigation(self.viewport,self.settings.data['navigation'])
        self.viewport.pack(fill="both",expand=True)
        self.scene_badge = tk.Frame(self.workspace,bg=BG)
        label(self.scene_badge,"WORLD STUDIO",8,True,BLUE).pack(anchor="w")
        self.view_label = label(self.scene_badge,"OVERWORLD  /  ORBIT",10,color=MUTED)
        self.view_label.pack(anchor="w",pady=(6,0))
        self.camera_button=Pill(self.scene_badge,'Enter flight  ·  F5',self.toggle_camera,width=167,height=29)
        self.camera_button.pack(anchor='w',pady=(10,0))
        self.scene_badge.place(x=110,y=24)
        self.tool_rail = GlassPanel(self.workspace,70,450)
        self.tool_rail.place(x=21,y=24)
        rail = self.tool_rail.body
        self.rail_buttons = []
        for symbol,text,callback in (("⌖","Select",lambda:self.inspector_tabs.select(0)),("▦","Blocks",self.material_dialog),("⧉","Clone",self.clone_dialog),("⊞","Chunks",self.chunks_dialog),("≈","Biome",self.biome_dialog),("{ }","NBT",self.nbt_dialog),("◷","History",lambda:self.inspector_tabs.select(3))):
            button = Pill(rail,symbol,callback,width=36,height=33)
            button.pack(pady=(0,1))
            label(rail,text,7,color=MUTED).pack(pady=(0,8))
            self.rail_buttons.append(button)
        self._build_material_tray()
        self._build_inspector()
        self._build_action_dock()
        self.view_controls = GlassPanel(self.workspace,174,67)
        row = self.view_controls.body
        for text,fn,width in (("−",lambda:self.viewport.zoom(1/1.15),32),("⌖",self.viewport.reset,43),("+",lambda:self.viewport.zoom(1.15),32)):
            Pill(row,text,fn,width=width,height=32).pack(side="left",padx=3)
        self.preferences_button = Pill(self.workspace,"⚙  Studio",self.preferences,width=98,height=34)
        self.workspace.bind("<Configure>",self._layout_panels)
        self.bind("<MouseWheel>",self._inspector_wheel,add="+")
        self.bind("<Button-4>",self._inspector_wheel,add="+")
        self.bind("<Button-5>",self._inspector_wheel,add="+")

    def _inspector_wheel(self,event):
        widget = event.widget
        while widget is not None and widget != self:
            if isinstance(widget,tk.Canvas) and getattr(widget,"inspector_page",False):
                delta = -1 if getattr(event,"num",None)==4 or getattr(event,"delta",0)>0 else 1
                widget.yview_scroll(delta*3,"units")
                return "break"
            widget = getattr(widget,"master",None)

    def _layout_panels(self,event=None):
        w,h = self.workspace.winfo_width(),self.workspace.winfo_height()
        self.inspector_panel.place(x=w-318,y=22,width=296,height=max(300,min(622,h-134)))
        self.action_dock.place(x=max(104,w//2-350),y=h-92,width=500,height=72)
        self.view_controls.place(x=w-198,y=h-90)
        self.preferences_button.place(x=22,y=h-52)
        if w>=1200 and h>=620:
            self.material_tray.place(x=22,y=h-275,width=240,height=201)
        else:
            self.material_tray.place_forget()
        self.viewport.stage_right = 330
        self.viewport.schedule()

    def _section_label(self,parent,text):
        label(parent,text,8,True,MUTED).pack(anchor="w",pady=(14,8))

    def _build_material_tray(self):
        self.material_tray = GlassPanel(self.workspace,240,230)
        inner = self.material_tray.body
        label(inner,"MATERIALS",8,True,BLUE).pack(anchor="w",pady=(0,8))
        ttk.Entry(inner,textvariable=self.search_var).pack(fill="x",pady=(0,9))
        frame = tk.Frame(inner,bg=SURFACE)
        frame.pack(fill="both",expand=True)
        scrollbar = ttk.Scrollbar(frame,orient="vertical")
        scrollbar.pack(side="right",fill="y")
        self.block_list = tk.Listbox(frame,bg=SURFACE,fg=INK,selectbackground=PALE,selectforeground=BLUE,highlightthickness=0,borderwidth=0,activestyle="none",height=3,font=(FONT,10),exportselection=False,yscrollcommand=scrollbar.set)
        self.block_list.pack(side="left",fill="both",expand=True)
        scrollbar.configure(command=self.block_list.yview)
        self.block_list.bind("<<ListboxSelect>>",self._choose_block)
        self.search_var.trace_add("write",lambda *_:self._refresh_blocks())
        self._refresh_blocks()

    def _scroll_tab(self,text):
        page = tk.Frame(self.inspector_tabs,bg=SURFACE)
        self.inspector_tabs.add(page,text=text)
        canvas = tk.Canvas(page,bg=SURFACE,highlightthickness=0)
        canvas.inspector_page = True
        scroll = ttk.Scrollbar(page,orient="vertical",command=canvas.yview)
        scroll.pack(side="right",fill="y")
        canvas.pack(side="left",fill="both",expand=True)
        canvas.configure(yscrollcommand=scroll.set)
        body = tk.Frame(canvas,bg=SURFACE)
        window = canvas.create_window(0,0,anchor="nw",window=body)
        body.bind("<Configure>",lambda _:canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",lambda e:canvas.itemconfigure(window,width=e.width))
        inner = tk.Frame(body,bg=SURFACE)
        inner.pack(fill="both",expand=True,padx=(0,4))
        return inner,canvas

    def _build_inspector(self):
        self.inspector_panel = GlassPanel(self.workspace,296,622)
        parent = self.inspector_panel.body
        heading = tk.Frame(parent,bg=SURFACE)
        heading.pack(fill="x",pady=(1,13))
        label(heading,"Make your mark.",13,True).pack(side="left")
        label(heading,"◈",14,color=BLUE).pack(side="right")
        self.inspector_tabs = TabStack(parent)
        self.inspector_tabs.pack(fill="both",expand=True)
        select,self.inspector_scroll = self._scroll_tab("Select")
        self.selection_label = label(select,"No blocks selected",11,True,BLUE)
        self.selection_label.pack(anchor="w",pady=(9,4))
        label(select,"Click a block, then Shift-click another.\nOr shape the bounds below.",8,color=MUTED,justify="left").pack(anchor="w",pady=(0,10))
        for row in range(2):
            self._section_label(select,"CORNER A" if row==0 else "CORNER B")
            line = tk.Frame(select,bg=SURFACE)
            line.pack(fill="x")
            for col,axis in enumerate("XYZ"):
                cell = tk.Frame(line,bg=SURFACE)
                cell.pack(side="left",fill="x",expand=True,padx=(0 if col==0 else 4,0))
                label(cell,axis,8,color=MUTED).pack(anchor="w",pady=(0,3))
                ttk.Entry(cell,textvariable=self.selection_vars[row*3+col],width=5).pack(fill="x")
        buttons = tk.Frame(select,bg=SURFACE)
        buttons.pack(fill="x",pady=13)
        Pill(buttons,"Set bounds",self.set_selection,width=135,height=34).pack(side="left")
        Pill(buttons,"Clear",self.clear_selection,width=79,height=34).pack(side="right")
        move = tk.Frame(select,bg=SURFACE)
        move.pack(fill="x")
        Pill(move,"Expand +1",lambda:self.resize_selection(1),width=105,height=30).pack(side="left")
        Pill(move,"Shrink −1",lambda:self.resize_selection(-1),width=109,height=30).pack(side="right")
        self._section_label(select,"ACTIVE MATERIAL")
        material = tk.Frame(select,bg=SURFACE)
        material.pack(fill="x",pady=(0,5))
        self.swatch = tk.Canvas(material,width=36,height=32,bg=SURFACE,highlightthickness=0)
        self.swatch.pack(side="left",padx=(0,8))
        self.material_label = label(material,"Stone",11,True)
        self.material_label.pack(side="left")
        ttk.Entry(select,textvariable=self.block_var).pack(fill="x",pady=(5,6))
        self.block_var.trace_add("write",lambda *_:self._refresh_material())
        Pill(select,"Browse materials…",self.material_dialog,width=218,height=33).pack(fill="x",pady=(2,7))
        label(select,"Custom states: oak_log[axis=y]",8,color=MUTED).pack(anchor="w")
        Pill(select,'Manage selection regions…',self.regions_dialog,width=218,height=36).pack(fill='x',pady=12)
        paste,_ = self._scroll_tab("Paste")
        self._section_label(paste,"CLIPBOARD")
        row = tk.Frame(paste,bg=SURFACE)
        row.pack(fill="x")
        for text,fn in (("Copy",self.copy),("Cut",self.cut),("Paste",self.paste)):
            Pill(row,text,fn,width=69,height=34).pack(side="left",padx=(0,5))
        self.clip_label = label(paste,"Nothing copied yet",9,color=MUTED,wraplength=210,justify="left")
        self.clip_label.pack(anchor="w",pady=14)
        self._section_label(paste,"TRANSFORM")
        self.rotation_box = ttk.Combobox(paste,values=("0°","90°","180°","270°"),state="readonly",width=12)
        self.rotation_box.current(0)
        self.rotation_box.pack(fill="x",pady=(0,10))
        Pill(paste,'Free transform & preview…',self.transform_dialog,width=218,height=34).pack(fill='x',pady=(0,10))
        ttk.Checkbutton(paste,text="Mirror on X axis",variable=self.mirror).pack(anchor="w",pady=5)
        ttk.Checkbutton(paste,text="Include air",variable=self.include_air).pack(anchor="w",pady=5)
        ttk.Checkbutton(paste,text='Include water',variable=self.include_water).pack(anchor='w',pady=5)
        ttk.Checkbutton(paste,text='Include lava',variable=self.include_lava).pack(anchor='w',pady=5)
        self._section_label(paste,"STRUCTURES")
        Pill(paste,"Import structure…",self.import_dialog,width=218).pack(fill="x",pady=5)
        Pill(paste,"Export selection…",self.export_dialog,width=218).pack(fill="x",pady=5)
        Pill(paste,"Repeat / clone…",self.clone_dialog,width=218).pack(fill="x",pady=5)
        world,_ = self._scroll_tab("World")
        self._section_label(world,"DIMENSION")
        self.dimension_var = tk.StringVar(value=self.document.dimension)
        self.dimension_box = ttk.Combobox(world,textvariable=self.dimension_var,values=self.document.world.dimensions,state="readonly",width=16)
        self.dimension_box.pack(fill="x",pady=(0,9))
        self.dimension_box.bind("<<ComboboxSelected>>",self.change_dimension)
        Pill(world,'Manage chunks…',self.chunks_dialog,width=218,height=36).pack(fill='x',pady=4)
        Pill(world,'Layered fill…',self.layer_dialog,width=218,height=36).pack(fill='x',pady=4)
        Pill(world,'Custom operations…',self.operations_dialog,width=218,height=36).pack(fill='x',pady=4)
        for text,fn in (("Go to coordinates…",self.goto_dialog),("Set selection biome…",self.biome_dialog),("Inspect block NBT…",self.nbt_dialog),("Waterlog selection",lambda:self.waterlog(True)),("Remove waterlogging",lambda:self.waterlog(False))):
            Pill(world,text,fn,width=218,height=36).pack(fill="x",pady=4)
        self._section_label(world,"WORLD ARCHIVES")
        Pill(world,"Import .mcworld…",self.import_world_archive,width=218).pack(fill="x",pady=5)
        Pill(world,"Export .mcworld…",self.export_world_archive,width=218).pack(fill="x",pady=5)
        history,_ = self._scroll_tab("History")
        self._section_label(history,"YOUR CREATIVE TRAIL")
        self.history_label = label(history,"A fresh start.",9,color=MUTED,wraplength=210,justify="left")
        self.history_label.pack(anchor="w",pady=(0,12))
        self.history_list = tk.Listbox(history,bg="#0c1728",fg=INK,selectbackground=PALE,selectforeground=BLUE,borderwidth=0,highlightthickness=0,activestyle="none",font=(FONT,9),height=13)
        self.history_list.pack(fill="x")
        self.history_list.bind("<Double-Button-1>",lambda _:self.history_restore())
        Pill(history,"Return to selected step",self.history_restore,width=218,height=36).pack(fill="x",pady=12)
        label(history,"Double-click a step to undo back to it.\nRedo remains available.",8,color=MUTED,justify="left").pack(anchor="w")
        Pill(history,'Recovery workspaces…',self.recovery_dialog,width=218,height=36).pack(fill='x',pady=12)

    def _build_action_dock(self):
        self.action_dock = GlassPanel(self.workspace,500,72)
        row = self.action_dock.body
        self.undo_button = Pill(row,"↶",self.undo,width=35,height=36)
        self.undo_button.pack(side="left",padx=(0,4))
        self.redo_button = Pill(row,"↷",self.redo,width=35,height=36)
        self.redo_button.pack(side="left",padx=(0,12))
        self.fill_button = Pill(row,"Fill selection",self.fill,True,width=130,height=36)
        self.fill_button.pack(side="left",padx=(0,8))
        Pill(row,"Replace",self.replace_dialog,width=100,height=36).pack(side="left",padx=(0,8))
        Pill(row,"Erase",self.delete,width=83,height=36).pack(side="left")

    def _build_status(self):
        status = tk.Frame(self,bg=BG,height=29)
        status.pack(fill="x")
        status.pack_propagate(False)
        label(status,"●",8,color="#71d7b7").pack(side="left",padx=(22,8))
        tk.Label(status,textvariable=self.status_var,bg=BG,fg=MUTED,font=(FONT,8),anchor="w").pack(side="left",fill="x",expand=True)
        label(status,"FACETEDIT  /  LOCAL BY DESIGN",7,color="#66809f").pack(side="right",padx=22)
