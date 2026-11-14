"""FacetEdit's dark native desktop editor; standard-library Python/Tk only."""
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog,messagebox,ttk,font as tkfont
from . import __version__,nbt,chrome,studio
from .blocks import Block,PALETTE,color
from .model import Document,Selection
from .settings import Settings
from .structures import export_structure,import_structure,import_mcstructure,load_project,save_project
from .world import SampleWorld,open_world
from .chrome import BG,SURFACE,INK,MUTED,LINE,BLUE,PALE,FONT,GlassPanel,Pill,label,rounded
from .studio import StudioLayout
from .managers import EditorManagers
from .operation_ui import OperationsUI
from .save_ui import WorldSaveUI
from .transform_ui import TransformUI
from .resource_ui import ResourceUI
from .material_ui import MaterialsUI
from .conversion_ui import ConversionUI
from .library_ui import LibraryUI
from .navigation_ui import NavigationUI

class FacetEditApp(NavigationUI,LibraryUI,ConversionUI,MaterialsUI,ResourceUI,TransformUI,WorldSaveUI,OperationsUI,EditorManagers,StudioLayout,tk.Tk):
    def __init__(self,settings_path=None):
        super().__init__()
        global FONT
        if FONT.lower() not in {name.lower() for name in tkfont.families(self)}:
            FONT = 'Helvetica'
            chrome.FONT = studio.FONT = FONT
        self.title('FacetEdit — shape what is next')
        self.geometry('1440x900')
        self.minsize(1040,700)
        self.configure(bg=BG)
        self.option_add('*Font',(FONT,10))
        self.option_add('*Background',SURFACE)
        self.option_add('*Foreground',INK)
        self.settings = Settings(settings_path)
        self.document = Document(SampleWorld())
        self._saved_revision = 0
        self.busy = False
        self.messages = queue.Queue()
        self.block_var = tk.StringVar(value='minecraft:stone')
        self.search_var = tk.StringVar()
        self.status_var = tk.StringVar(value='Willow Bay · Editable sample · Your next idea starts here')
        self.selection_vars = [tk.StringVar(value=str(v)) for v in (-5,12,-4,-2,14,-1)]
        self.turns = tk.IntVar(value=0)
        self.mirror = tk.BooleanVar(value=False)
        self.include_air = tk.BooleanVar(value=False)
        self.include_water=tk.BooleanVar(value=True)
        self.include_lava=tk.BooleanVar(value=True)
        self._poll_id = None
        self._initialize_managers()
        self.app_logo = chrome.logo(self,64)
        self.iconphoto(True,self.app_logo)
        self._build_style()
        self._build_menus()
        self._build_header()
        self._build_workspace()
        self._build_status()
        self._bindings()
        self.protocol('WM_DELETE_WINDOW',self.close_app)
        self._poll_id = self.after(80,self._poll)
        self.refresh()
        recovered = len(self.recovery.entries())
        if recovered:self.status_var.set(f'{recovered} recovery copies available · File → Recovery workspaces')
        self.after_idle(self._restore_resources)

    def _build_menus(self):
        menu = tk.Menu(self)
        file = tk.Menu(menu, tearoff=False)
        file.add_command(label="Open world…", accelerator="Ctrl+O", command=self.open_dialog)
        file.add_command(label="Open FacetEdit project…", command=self.open_project_dialog)
        file.add_command(label="Open sample world", command=self.open_sample)
        self.recent_menu = tk.Menu(file, tearoff=False)
        file.add_cascade(label="Recent worlds", menu=self.recent_menu)
        file.add_separator()
        file.add_command(label='Save original world…',accelerator='Ctrl+S',command=self.save_original)
        file.add_command(label="Save edited copy…", command=self.save_copy)
        file.add_command(label="Convert world…",command=self.convert_world_dialog)
        file.add_command(label="Save FacetEdit project…", accelerator="Ctrl+Shift+S", command=self.save_project_dialog)
        file.add_command(label="Import structure…", command=self.import_dialog)
        file.add_command(label="Export selection as structure…", command=self.export_dialog)
        file.add_command(label="Import .mcworld archive…", command=self.import_world_archive)
        file.add_command(label="Export .mcworld archive…", command=self.export_world_archive)
        file.add_command(label="Recovery workspaces…",command=self.recovery_dialog)
        file.add_command(label='World save checkpoints…',command=self.world_recovery_dialog)
        file.add_separator()
        file.add_command(label="Quit", command=self.close_app)
        menu.add_cascade(label="File", menu=file)
        edit = tk.Menu(menu, tearoff=False)
        for text, shortcut, fn in (("Undo", "Ctrl+Z", self.undo), ("Redo", "Ctrl+Y", self.redo), ("Copy", "Ctrl+C", self.copy), ("Cut", "Ctrl+X", self.cut), ("Paste", "Ctrl+V", self.paste), ("Delete selection", "Delete", self.delete)):
            edit.add_command(label=text, accelerator=shortcut, command=fn)
        edit.add_separator()
        edit.add_command(label='Manage selection regions…',command=self.regions_dialog)
        edit.add_command(label='Manage chunks…',command=self.chunks_dialog)
        edit.add_command(label='Layered fill…',command=self.layer_dialog)
        edit.add_command(label='Custom operations…',command=self.operations_dialog)
        edit.add_command(label='Transform and preview paste…',command=self.transform_dialog)
        edit.add_command(label='Translate clipboard…',command=self.translate_clipboard_dialog)
        for text,fn in (("Clone / repeat…",self.clone_dialog),("Nudge selection…",self.nudge_dialog),("Set biome…",self.biome_dialog),("Inspect block NBT…",self.nbt_dialog)):
            edit.add_command(label=text,command=fn)
        menu.add_cascade(label="Edit", menu=edit)
        view = tk.Menu(menu, tearoff=False)
        view.add_command(label='Switch orbit / flight',accelerator='F5',command=self.toggle_camera)
        view.add_command(label="Reset camera", command=lambda: self.viewport.reset())
        view.add_command(label="Go to coordinates…", command=self.goto_dialog)
        view.add_command(label='Resource packs and graphics…',command=self.resources_dialog)
        view.add_command(label='Navigation and controls…',command=self.navigation_dialog)
        view.add_command(label="Preferences…", command=self.preferences)
        menu.add_cascade(label="View", menu=view)
        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="Controls & compatibility", command=self.help_dialog)
        help_menu.add_command(label="Command palette", accelerator="Ctrl+K", command=self.command_palette)
        menu.add_cascade(label="Help", menu=help_menu)
        self.config(menu=menu)
        self._refresh_recent()

    def _refresh_recent(self):
        self.recent_menu.delete(0, "end")
        for path in self.settings.data["recent"]:
            self.recent_menu.add_command(label=Path(path).name + "  ·  " + path, command=lambda p=path: self.open_path(p))
        if not self.settings.data["recent"]:
            self.recent_menu.add_command(label="No recent worlds", state="disabled")

    def _bindings(self):
        commands = {"o": self.open_dialog, "s": self.save_original, "z": self.undo, "y": self.redo, "c": self.copy, "x": self.cut, "v": self.paste, "k": self.command_palette}
        modifier = "Command" if sys.platform == "darwin" else "Control"
        for key, fn in commands.items():
            self.bind(f"<{modifier}-{key}>", lambda event, f=fn, k=key: self._shortcut(event, f, k))
        self.bind(f"<{modifier}-Shift-S>", lambda e: self._shortcut(e, self.save_project_dialog, "s"))
        self.bind(f"<{modifier}-Shift-Z>", lambda e: self._shortcut(e, self.redo, "z"))
        self.bind("<Delete>", lambda e: self._shortcut(e, self.delete, "delete"))
        self.bind("<Escape>", lambda e: self.clear_selection() if not isinstance(e.widget, (tk.Entry, ttk.Entry)) else None)
        self.bind('<F5>',lambda e:self._shortcut(e,self.toggle_camera,'f5'))

    def _shortcut(self, event, fn, key):
        if key in ("c", "x", "v", "z", "y", "delete") and isinstance(event.widget, (tk.Entry, ttk.Entry, tk.Text, ttk.Combobox)):
            return None
        fn()
        return "break"

    def run_action(self, function, message=None):
        if self.busy:
            self.status_var.set("Please wait for the current file operation to finish")
            return None
        try:
            result = function()
            if message:
                self.status_var.set(message(result))
            self.refresh()
            return result
        except Exception as exc:
            self.show_error(exc)
            return None

    def show_error(self, error):
        self.status_var.set(str(error))
        messagebox.showerror("FacetEdit couldn't complete that", str(error), parent=self)

    def _render_error(self, text):
        self.status_var.set("View unavailable · " + text)

    def _refresh_blocks(self):
        query = self.search_var.get().lower()
        self.filtered_blocks = [b for b in PALETTE if query in b.label.lower() or query in b.name]
        self.block_list.delete(0, "end")
        for index, block in enumerate(self.filtered_blocks):
            self.block_list.insert("end", "  ▪   " + block.label)
            self.block_list.itemconfig(index, background=SURFACE)

    def _choose_block(self, _):
        if self.block_list.curselection():
            self.block_var.set(str(self.filtered_blocks[self.block_list.curselection()[0]]))

    def _refresh_material(self):
        try:
            block = Block.parse(self.block_var.get())
        except ValueError:
            self.material_label.configure(text="Custom block…")
            return
        self.material_label.configure(text=block.label)
        self.swatch.delete("all")
        rounded(self.swatch, 1, 1, 31, 30, 7, fill=color(block), outline="")

    def refresh(self):
        doc = self.document
        self.world_title.configure(text=doc.world.name)
        self.edition_label.configure(text=doc.world.edition + (" · Staged edits" if doc.world.path else " · Editable sample"))
        self.title(f"{'• ' if doc.revision != self._saved_revision else ''}{doc.world.name} — FacetEdit")
        self.undo_button.state(bool(doc.undo_stack) and not self.busy)
        self.redo_button.state(bool(doc.redo_stack) and not self.busy)
        self.fill_button.state(doc.selection is not None and not self.busy)
        self.save_button.state(not self.busy)
        self.dimension_box.configure(values=doc.world.dimensions)
        self.dimension_var.set(doc.dimension)
        self.view_label.configure(text=doc.dimension.upper().replace("_", " ") + '  /  '+('PERSPECTIVE' if self.viewport.mode=='fly' else 'ORBIT'))
        self.camera_button.text='Return to orbit  ·  F5' if self.viewport.mode=='fly' else 'Enter flight  ·  F5'
        self.camera_button.draw()
        if doc.selection:
            self.selection_label.configure(text=f'{len(doc.selection.boxes)} regions · {doc.selection.volume:,} blocks' if len(doc.selection.boxes)>1 else f"{doc.selection.volume:,} blocks  ·  " + " × ".join(map(str, doc.selection.size)))
        else:
            self.selection_label.configure(text="No blocks selected")
        self.history_label.configure(text=(doc.undo_stack[-1].label + f"\n{doc.pending_count:,} pending changes") if doc.undo_stack else f"{doc.pending_count:,} pending changes" if doc.pending_count else "A fresh start.")
        self.history_list.delete(0,"end")
        self.history_list.insert("end","○  Start of available history")
        for index,transaction in enumerate(doc.undo_stack,1):
            self.history_list.insert("end",f"{index:02}  {transaction.label}  ·  {transaction.count}")
        if doc.undo_stack:
            self.history_list.see("end")
        self.clip_label.configure(text=(" × ".join(map(str,doc.clipboard.size))+" blocks copied"+(f"\n{len(doc.clipboard.entities)} block entities preserved" if doc.clipboard.entities else "")) if doc.clipboard else "Nothing copied yet")
        self._refresh_material()
        self.viewport.schedule()
        self._refresh_managers()

    def _pick(self, position, extend):
        if self.busy:
            return
        previous = self.document.selection
        self.document.selection = Selection(previous.a if extend and previous else position, position)
        for var, value in zip(self.selection_vars, (*self.document.selection.a, *self.document.selection.b)):
            var.set(str(value))
        block = self.document.get(*position)
        self.status_var.set(f"X {position[0]}   Y {position[1]}   Z {position[2]}  ·  {block}")
        self.refresh()

    def set_selection(self):
        def set_it():
            coordinates = tuple(int(v.get()) for v in self.selection_vars)
            if any(abs(n) > 30_000_000 for n in coordinates):
                raise ValueError("Coordinates must be within ±30,000,000")
            self.document.selection = Selection(coordinates[:3], coordinates[3:])
        self.run_action(set_it)

    def clear_selection(self):
        if not self.busy:
            self.document.selection = None
            self.refresh()

    def fill(self):
        self.run_action(lambda: self.document.fill(self.material_block()), lambda n: f"Filled {n:,} blocks · Undo is available")

    def delete(self):
        self.run_action(self.document.delete, lambda n: f"Deleted {n:,} blocks · Undo is available")

    def copy(self):
        self.run_action(self.document.copy, lambda n: f"Copied {n:,} blocks")

    def cut(self):
        self.run_action(self.document.cut, lambda n: f"Cut {n:,} blocks · Undo is available")

    def paste(self):
        self.run_action(lambda: self.document.paste(turns=self.rotation_box.current(), mirror=self.mirror.get(), include_air=self.include_air.get(),include_water=self.include_water.get(),include_lava=self.include_lava.get()), lambda n: f"Pasted {n:,} blocks · Undo is available")

    def undo(self):
        self.run_action(self.document.undo, lambda name: "Undid " + name if name else "Nothing to undo")

    def redo(self):
        self.run_action(self.document.redo, lambda name: "Redid " + name if name else "Nothing to redo")

    def _dialog(self, title, width=440, height=240):
        dialog = tk.Toplevel(self)
        dialog.withdraw()
        dialog.title(title)
        dialog.configure(bg=SURFACE)
        dialog.transient(self)
        dialog.resizable(False, False)
        dialog.bind("<Escape>", lambda _: dialog.destroy())
        content = tk.Frame(dialog, bg=SURFACE)
        content.pack(fill="both", expand=True, padx=24, pady=22)
        label(content, title, 16, True).pack(anchor="w", pady=(0, 14))
        def center():
            if dialog.winfo_exists():
                dialog.update_idletasks()
                w,h = width,height
                x = max(0,min(self.winfo_screenwidth()-w,self.winfo_rootx()+(self.winfo_width()-w)//2))
                y = max(0,min(self.winfo_screenheight()-h-35,self.winfo_rooty()+(self.winfo_height()-h)//2))
                dialog.geometry(f"{w}x{h}+{x}+{y}")
                dialog.deiconify()
        dialog.after_idle(center)
        return dialog, content

    def replace_dialog(self):
        dialog, content = self._dialog("Replace blocks",480,315)
        label(content, "Match blocks inside the selection:", 10, color=MUTED).pack(anchor="w")
        value = tk.StringVar(value="minecraft:stone")
        entry = ttk.Entry(content, textvariable=value)
        entry.pack(fill="x", pady=10)
        entry.focus_set()
        modes={'Exact block and states':'exact','Block name, any states':'name','Name and specified states':'subset','Name pattern (* / ?) and specified states':'pattern'}
        mode=tk.StringVar(value=next(iter(modes)))
        ttk.Combobox(content,textvariable=mode,values=list(modes),state='readonly').pack(fill='x',pady=(0,10))
        def replace():
            from .matching import BlockMatcher
            result = self.run_action(lambda: self.document.fill(self.material_block(), replace=BlockMatcher.parse(value.get(),modes[mode.get()])), lambda n: f"Replaced {n:,} blocks")
            if result is not None:
                dialog.destroy()
        Pill(content, "Replace selection", replace, True, 176).pack(anchor="e", pady=8)

    def change_dimension(self, _=None):
        if self.busy:
            self.dimension_var.set(self.document.dimension)
            return
        dimension=self.dimension_var.get()
        try:minimum,maximum=self.document.world.bounds(dimension)
        except ValueError as exc:self.dimension_var.set(self.document.dimension);self.show_error(exc);return
        self._close_managers()
        self.document.dimension = dimension
        self.document.selection = None
        self.viewport.preview=None
        self.viewport.ceiling=maximum
        self.viewport.camera.position[1]=max(minimum,min(maximum,self.viewport.camera.position[1]))
        self.viewport._geometry_key = None
        self.refresh()

    def _confirm_discard(self):
        if self.busy:
            self.status_var.set("Wait for the current file operation to finish")
            return False
        if self.document.revision == self._saved_revision:
            return True
        choice = messagebox.askyesnocancel("Keep your changes?", "Save a FacetEdit project before leaving this world?", parent=self)
        if choice is None:
            return False
        return self.save_project_dialog() if choice else True

    def _attach(self, document,preserve_recovery=False):
        self._forget_recovery(preserve_current=preserve_recovery)
        self._close_managers()
        self.document = document
        self._saved_revision = document.revision
        self.viewport.attach(document)
        if document.selection:
            for variable,value in zip(self.selection_vars,(*document.selection.a,*document.selection.b)):variable.set(value)
        self.refresh()

    def open_sample(self):
        if self._confirm_discard():
            self._attach(Document(SampleWorld()))
            self.status_var.set("Willow Bay · Editable sample · No Minecraft world is open")

    def open_dialog(self):
        self.world_library()

    def open_path(self, path):
        if not Path(path).exists():
            from .worldsave import list_saves
            if list_saves(Path(path).parent,Path(path).name):
                self.world_recovery_dialog(Path(path).parent);return
        if not self._confirm_discard():
            return
        def finished(world):
            self._attach(Document(world))
            try:
                self.settings.remember(path)
                self._refresh_recent()
            except OSError as exc:
                self.status_var.set("World opened; preferences could not be saved: " + str(exc))
                return
            self.status_var.set(f"Opened {world.name} · {world.edition} · Close Minecraft before exporting")
        self.worker(lambda: open_world(path), finished, "Reading world metadata…")

    def open_project_dialog(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(title="Open FacetEdit project", filetypes=[("FacetEdit project", "*.facet"),("Legacy projects","*.luma *.facetedit")], parent=self)
        if path and self._confirm_discard():
            self.worker(lambda: load_project(path), self._attach, "Opening FacetEdit project…")

    def save_project_dialog(self):
        if self.busy:
            return False
        path = filedialog.asksaveasfilename(title="Save FacetEdit project", defaultextension=".facet", initialfile=self.document.world.name + ".facet", filetypes=[("FacetEdit project", "*.facet")], parent=self)
        if not path:
            return False
        try:
            save_project(self.document, path)
            self._saved_revision = self.document.revision
            self._forget_recovery()
            self.status_var.set("Project saved · " + path)
            self.refresh()
            return True
        except Exception as exc:
            self.show_error(exc)
            return False

    def save_copy(self):
        if self.busy:
            return
        if self.document.world.path is None:
            self.save_project_dialog()
            return
        # asksaveasfilename chooses a new path without creating an existing folder.
        destination = filedialog.asksaveasfilename(title="Choose a NEW folder name for the edited world", initialfile=self.document.world.name + " - FacetEdit", parent=self)
        if not destination:
            return
        world, edits = self.document.world, dict(self.document.edits)
        metadata = self.document.export_metadata()
        def complete(_):
            self._saved_revision = self.document.revision
            self._forget_recovery()
            self.status_var.set("Saved edited world copy · " + destination)
            self.refresh()
        self.worker(lambda: world.export(destination, edits, lambda msg: self.messages.put(("progress", msg)),**metadata), complete, "Preparing a separate world copy…")

    def import_dialog(self):
        if self.busy:
            return
        bedrock = self.document.world.edition.startswith("Bedrock")
        path = filedialog.askopenfilename(title="Import structure", filetypes=[("Construction", "*.construction"),("Java structure", "*.nbt"),("Sponge schematic","*.schem"),("Legacy schematic","*.schematic"),("Bedrock structure", "*.mcstructure")], parent=self)
        if path:
            def imported():
                from .schematic import load_schematic
                from .legacy_schematic import load_legacy_schematic
                from .construction import load_construction
                version=getattr(self.document.world,'version',4189)
                suffix=Path(path).suffix.lower()
                self.document.clipboard = load_construction(path) if suffix=='.construction' else import_mcstructure(path) if suffix=='.mcstructure' else load_legacy_schematic(path,version if version<1451 else None) if suffix=='.schematic' else load_schematic(path) if suffix=='.schem' else import_structure(path)
                return len(self.document.clipboard.blocks)
            self.run_action(imported, lambda n: f"Imported {n:,} blocks · Select a destination and paste")

    def export_dialog(self):
        if self.busy:
            return
        bedrock = self.document.world.edition.startswith("Bedrock")
        try:
            self.document.copy()
        except Exception as exc:
            self.show_error(exc)
            return
        legacy=getattr(self.document.world,'version',4189)<1451
        formats=([("Bedrock structure", "*.mcstructure")] if bedrock else [("Legacy schematic","*.schematic")] if legacy else [("Java structure", "*.nbt"),("Sponge schematic","*.schem")])+[("Construction","*.construction")]
        path = filedialog.asksaveasfilename(title="Export selection as structure", defaultextension=".mcstructure" if bedrock else '.schematic' if legacy else ".nbt", filetypes=formats, parent=self)
        if path:
            from .schematic import save_schematic
            from .legacy_schematic import save_legacy_schematic
            from .construction import save_construction
            writer = save_construction if Path(path).suffix.lower()=='.construction' else save_legacy_schematic if Path(path).suffix.lower()=='.schematic' else save_schematic if Path(path).suffix.lower()==".schem" else export_structure
            self.run_action(lambda: writer(self.document.clipboard, path), lambda _: "Block structure saved · " + path)

    def worker(self, function, completed, message):
        if self.busy:
            return
        self.busy = True
        self.status_var.set(message)
        self.refresh()
        def job():
            try:
                result = function()
                self.messages.put(("complete", completed, result))
            except Exception as exc:
                self.messages.put(("error", exc))
        threading.Thread(target=job, daemon=True, name="FacetEdit-file-worker").start()

    def _poll(self):
        try:
            while True:
                message = self.messages.get_nowait()
                if message[0] == "progress":
                    self.status_var.set(message[1])
                elif message[0] in ('recovery_saved','recovery_error'):
                    self._handle_recovery_message(message)
                elif message[0] == "complete":
                    self.busy = False
                    message[1](message[2])
                    self.refresh()
                else:
                    self.busy = False
                    self.refresh()
                    self.show_error(message[1])
        except queue.Empty:
            pass
        self._poll_id = self.after(80, self._poll)

    def toggle_camera(self):
        try:
            self.viewport.set_mode('fly' if self.viewport.mode=='orbit' else 'orbit')
            self.viewport.focus_set()
            self.refresh()
        except Exception as exc:self.show_error(exc)

    def goto_dialog(self):
        dialog, content = self._dialog("Go to coordinates")
        label(content, 'Fly directly to X / Y / Z.' if self.viewport.mode=='fly' else "Center the view at X / Z. Y clips terrain above it.", 9, color=MUTED, wraplength=380, justify="left").pack(anchor="w")
        row = tk.Frame(content, bg=SURFACE)
        row.pack(fill="x", pady=12)
        location=self.viewport.camera.position if self.viewport.mode=='fly' else (self.viewport.center_x,self.viewport.ceiling,self.viewport.center_z)
        values = [tk.StringVar(value=str(round(v))) for v in location]
        for axis, var in zip("XYZ", values):
            label(row, axis, 9, color=MUTED).pack(side="left", padx=(0, 5))
            ttk.Entry(row, textvariable=var, width=7).pack(side="left", padx=(0, 10))
        def go():
            try:
                x, y, z = (int(v.get()) for v in values)
                minimum,maximum=self.document.world.bounds(self.document.dimension)
                if max(abs(x), abs(z)) > 30_000_000 or not minimum <= y <= maximum:
                    raise ValueError("Coordinates are outside world bounds")
                self.viewport.go_to(x,y,z)
                dialog.destroy()
            except ValueError as exc:
                self.show_error(exc)
        Pill(content, "Go to location", go, True, 150).pack(anchor="e")

    def preferences(self):
        dialog, content = self._dialog("Make yourself at home",450,550)
        label(content,"MIDNIGHT GLASS  ·  DEFAULT DARK",9,True,BLUE).pack(anchor="w",pady=(0,10))
        label(content, "Display radius · smaller uses less CPU", 10, color=MUTED).pack(anchor="w")
        radius = tk.IntVar(value=self.viewport.radius)
        tk.Scale(content, from_=6, to=18, orient="horizontal", variable=radius, bg=SURFACE, fg=INK, highlightthickness=0, troughcolor=PALE, activebackground=BLUE).pack(fill="x", pady=8)
        grid = tk.BooleanVar(value=self.viewport.grid)
        ttk.Checkbutton(content, text="Show subtle block outlines", variable=grid).pack(anchor="w")
        glass = tk.BooleanVar(value=self.viewport.glass)
        ttk.Checkbutton(content,text="Atmospheric glass lighting",variable=glass).pack(anchor="w",pady=7)
        autosave=tk.BooleanVar(value=self.settings.data['autosave'])
        ttk.Checkbutton(content,text='Save recovery copies automatically',variable=autosave).pack(anchor='w',pady=(12,6))
        interval=tk.StringVar(value=str(self.settings.data['autosave_seconds']))
        row=tk.Frame(content,bg=SURFACE);row.pack(fill='x',pady=5)
        label(row,'Checkpoint interval · seconds',9,color=MUTED).pack(side='left')
        ttk.Combobox(row,textvariable=interval,values=(15,30,60,120,300,600),state='readonly',width=8).pack(side='right')
        def apply():
            self.viewport.radius, self.viewport.grid = radius.get(), grid.get()
            self.settings.data.update(radius=radius.get(),grid=grid.get(),glass=glass.get(),autosave=autosave.get(),autosave_seconds=int(interval.get()))
            self.viewport.glass = glass.get()
            try:
                self.settings.save()
                self.viewport.schedule()
                if self._recovery_id is not None:self.after_cancel(self._recovery_id)
                self._recovery_id=self.after(self.settings.data['autosave_seconds']*1000,self._autosave_tick)
                dialog.destroy()
            except OSError as exc:
                self.show_error(exc)
        Pill(content, "Save preferences", apply, True, 170).pack(anchor="e", pady=14)
        Pill(content,'Resource packs and graphics',lambda:(dialog.destroy(),self.resources_dialog()),width=290,height=32).pack(anchor='w')
        Pill(content,'Navigation and controls',lambda:(dialog.destroy(),self.navigation_dialog()),width=290,height=32).pack(anchor='w',pady=(8,0))

    def command_palette(self):
        dialog, content = self._dialog("What would you like to do?",520,445)
        query = tk.StringVar()
        entry = ttk.Entry(content, textvariable=query)
        entry.pack(fill="x", pady=(0, 12))
        options = tk.Listbox(content, bg=SURFACE, fg=INK, selectbackground=PALE, selectforeground=BLUE, highlightthickness=0, borderwidth=0, activestyle="none", font=(FONT, 11), height=11)
        options.pack(fill="both", expand=True)
        commands = [("Open Minecraft world", self.open_dialog), ("Save edited world copy", self.save_copy), ("Save FacetEdit project", self.save_project_dialog), ("Open FacetEdit project", self.open_project_dialog), ("Fill selection", self.fill), ("Replace blocks", self.replace_dialog), ("Delete selection", self.delete), ("Copy selection", self.copy), ("Paste clipboard", self.paste), ("Undo last change", self.undo), ("Redo change", self.redo), ("Go to coordinates", self.goto_dialog), ("Import structure", self.import_dialog), ("Export structure", self.export_dialog), ("Reset camera", self.viewport.reset), ("Preferences", self.preferences), ("Help and compatibility", self.help_dialog)]
        commands += [("Clone / repeat selection",self.clone_dialog),("Set biome",self.biome_dialog),("Inspect / edit block NBT",self.nbt_dialog),("Import .mcworld",self.import_world_archive),("Export .mcworld",self.export_world_archive),("Nudge selection",self.nudge_dialog),("Waterlog selection",lambda:self.waterlog(True))]
        commands += [('Manage selection regions',self.regions_dialog),('Manage chunks',self.chunks_dialog),('Restore recovery workspace',self.recovery_dialog),('Switch orbit / flight camera',self.toggle_camera),('Layered fill',self.layer_dialog),('Custom operations',self.operations_dialog),('Save original world',self.save_original),('Recover world save',self.world_recovery_dialog)]
        commands.append(('Transform and preview paste',self.transform_dialog))
        commands.append(('Resource packs and graphics',self.resources_dialog))
        commands.extend([('Find material and block states',self.material_dialog),('Translate clipboard',self.translate_clipboard_dialog),('Convert world',self.convert_world_dialog)])
        commands.append(('Navigation and controls',self.navigation_dialog))
        matches = []
        def search(*_):
            matches[:] = [(name, fn) for name, fn in commands if query.get().lower() in name.lower()]
            options.delete(0, "end")
            for name, _ in matches:
                options.insert("end", "  " + name)
            if matches:
                options.selection_set(0)
        def invoke(_=None):
            indexes = options.curselection()
            if indexes:
                function = matches[indexes[0]][1]
                dialog.destroy()
                self.after_idle(function)
            return "break"
        query.trace_add("write", search)
        options.bind("<Double-Button-1>", invoke)
        dialog.bind("<Return>", invoke)
        entry.bind("<Down>", lambda _: options.focus_set())
        search()
        entry.focus_set()

    def _sync_selection(self):
        if self.document.selection:
            for variable,value in zip(self.selection_vars,(*self.document.selection.a,*self.document.selection.b)):
                variable.set(value)
        self.refresh()

    def resize_selection(self,amount):
        self.run_action(lambda:self.document.expand_selection(amount))
        self._sync_selection()

    def nudge_dialog(self):
        self.clone_dialog(nudge=True)

    def clone_dialog(self,nudge=False):
        dialog,content = self._dialog("Nudge the selection" if nudge else "Repeat your idea",460,320)
        label(content,"Offset in blocks · X, Y, Z",10,color=MUTED).pack(anchor="w")
        offsets = [tk.StringVar(value=v) for v in ("8","0","0")]
        row = tk.Frame(content,bg=SURFACE)
        row.pack(fill="x",pady=12)
        for axis,var in zip("XYZ",offsets):
            label(row,axis,9,color=MUTED).pack(side="left",padx=(0,6))
            ttk.Entry(row,textvariable=var,width=7).pack(side="left",padx=(0,10))
        repeats = tk.StringVar(value="1")
        if not nudge:
            label(content,"Number of copies",10,color=MUTED).pack(anchor="w")
            ttk.Entry(content,textvariable=repeats,width=10).pack(anchor="w",pady=9)
        def apply():
            def perform():
                offset = tuple(int(v.get()) for v in offsets)
                if nudge:
                    self.document.nudge_selection(offset)
                    return 0
                return self.document.clone(offset,int(repeats.get()),self.include_air.get())
            result = self.run_action(perform,lambda n:"Selection moved" if nudge else f"Cloned {n:,} blocks · One undo step")
            if result is not None:
                self._sync_selection()
                dialog.destroy()
        Pill(content,"Move bounds" if nudge else "Create copies",apply,True,155).pack(anchor="e",pady=10)

    def waterlog(self,enabled):
        self.run_action(lambda:self.document.waterlog(enabled),lambda n:f"Updated waterlogging at {n:,} blocks")

    def layer_dialog(self):
        dialog,content=self._dialog('Build with layers',520,400)
        label(content,'Bedrock stores extra blocks, including water, in separate layers.',10,color=MUTED,wraplength=460,justify='left').pack(anchor='w')
        block=tk.StringVar(value=self.block_var.get());mode=tk.StringVar(value='overlay')
        label(content,'MATERIAL',8,True,MUTED).pack(anchor='w',pady=(16,6))
        ttk.Entry(content,textvariable=block).pack(fill='x')
        label(content,'LAYER ACTION',8,True,MUTED).pack(anchor='w',pady=(16,6))
        ttk.Combobox(content,textvariable=mode,values=('normal','overlay','underlay','game','first','second'),state='readonly').pack(fill='x')
        label(content,'Overlay adds a second block when the first is occupied.\nUnderlay moves the first block into the second layer.\nGame fill keeps water when placing a new first block.\nFirst / second replaces only that layer. Normal clears extras.',9,color=MUTED,justify='left').pack(anchor='w',pady=14)
        def apply():
            result=self.run_action(lambda:self.document.fill_layers(Block.parse(block.get()),mode.get()),lambda n:f'Layered fill · {n:,} blocks')
            if result is not None:dialog.destroy()
        Pill(content,'Apply layered fill',apply,True,180).pack(anchor='e')

    def biome_dialog(self):
        try:
            selection = self.document.require_selection()
            current = self.document.get_biome(*selection.minimum)
        except Exception as exc:
            self.show_error(exc)
            return
        dialog,content = self._dialog("A different atmosphere",490,360)
        label(content,'Change the selected box or its full-height columns.\nCell size follows the world format. Unknown numeric IDs\ncan be entered as numeric:<ID>.',10,color=MUTED,justify='left').pack(anchor='w',pady=(0,12))
        value = tk.StringVar(value=current)
        mode=tk.StringVar(value='box')
        ttk.Combobox(content,textvariable=value,values=tuple("minecraft:"+name for name in ("plains","forest","desert","cherry_grove","lush_caves","snowy_plains","badlands","swamp","ocean"))).pack(fill="x",pady=8)
        ttk.Combobox(content,textvariable=mode,values=('box','column'),state='readonly').pack(fill='x',pady=8)
        def apply():
            result = self.run_action(lambda:self.document.set_biome(value.get(),mode.get()),lambda n:f"Updated {n:,} biome cells · Undo is available")
            if result is not None:
                dialog.destroy()
        Pill(content,"Apply biome",apply,True,150).pack(anchor="e",pady=15)

    def nbt_dialog(self):
        from .nbt_edit import to_json,from_json
        try:
            position = self.document.require_selection().minimum
            data = self.document.get_entity(*position)
            if data is None:
                raise ValueError("No block entity at this selection corner. Select a chest, sign or another block with NBT data")
            _,tag = nbt.loads(data)
        except Exception as exc:
            self.show_error(exc)
            return
        dialog,content = self._dialog("Inside the block",800,650)
        dialog.resizable(True,True)
        label(content,"Typed NBT  ·  "+str(position)+"  ·  Coordinates must stay unchanged",9,color=MUTED).pack(anchor="w",pady=(0,10))
        buttons = tk.Frame(content,bg=SURFACE)
        buttons.pack(side="bottom",fill="x",pady=(12,0))
        editor = tk.Text(content,bg="#081322",fg="#bfd7ee",insertbackground=BLUE,selectbackground=PALE,relief="flat",borderwidth=0,padx=14,pady=14,undo=True,font=("Menlo" if sys.platform=="darwin" else "Consolas" if sys.platform=="win32" else "DejaVu Sans Mono",10),wrap="none")
        scroll = ttk.Scrollbar(content,orient="vertical",command=editor.yview)
        scroll.pack(side="right",fill="y")
        editor.configure(yscrollcommand=scroll.set)
        editor.pack(fill="both",expand=True)
        editor.insert("1.0",to_json(tag))
        def apply():
            result = self.run_action(lambda:self.document.set_entity(position,from_json(editor.get("1.0","end-1c"))),lambda n:"Block NBT updated · Undo is available" if n else "NBT unchanged")
            if result is not None:
                dialog.destroy()
        def validate():
            try:
                from_json(editor.get("1.0","end-1c"))
                self.status_var.set("NBT syntax and numeric ranges are valid")
                messagebox.showinfo("Valid NBT","All tag types and numeric ranges are valid.",parent=dialog)
            except Exception as exc:
                self.show_error(exc)
        Pill(buttons,"Validate",validate,width=105).pack(side="left")
        Pill(buttons,"Apply NBT",apply,True,135).pack(side="right")
        self.nbt_editor = editor

    def history_restore(self):
        if self.busy or not self.history_list.curselection():
            return
        target = self.history_list.curselection()[0]
        def restore():
            count = 0
            while len(self.document.undo_stack)>target:
                self.document.undo()
                count += 1
            return count
        self.run_action(restore,lambda count:f"Rewound {count} changes · Redo remains available")

    def import_world_archive(self):
        if self.busy:
            return
        archive = filedialog.askopenfilename(title="Open a Bedrock world archive",filetypes=[("Bedrock world","*.mcworld")],parent=self)
        if not archive:
            return
        destination = filedialog.asksaveasfilename(title="Choose a NEW folder for the imported world",initialfile=Path(archive).stem+" - imported",parent=self)
        if not destination or not self._confirm_discard():
            return
        from .archives import extract_world
        def perform():
            return open_world(extract_world(archive,destination))
        def complete(world):
            self._attach(Document(world))
            try:
                self.settings.remember(destination)
                self._refresh_recent()
            except OSError:
                pass
            self.status_var.set("Imported Bedrock world · "+str(destination))
        self.worker(perform,complete,"Extracting and validating the world archive…")

    def export_world_archive(self):
        if self.busy:
            return
        if not self.document.world.edition.startswith("Bedrock"):
            self.show_error(ValueError(".mcworld export is available for Bedrock worlds. Cross-edition conversion is not implemented"))
            return
        destination = filedialog.asksaveasfilename(title="Export edited Bedrock archive",defaultextension=".mcworld",initialfile=self.document.world.name+" - FacetEdit.mcworld",filetypes=[("Bedrock world","*.mcworld")],parent=self)
        if not destination:
            return
        from .archives import export_mcworld
        world,edits = self.document.world,dict(self.document.edits)
        metadata = self.document.export_metadata()
        def complete(_):
            self._saved_revision = self.document.revision
            self._forget_recovery()
            self.status_var.set("Bedrock archive saved · "+destination)
            self.refresh()
        self.worker(lambda:export_mcworld(world,destination,edits,lambda msg:self.messages.put(("progress",msg)),**metadata),complete,"Preparing the edited world archive…")

    def help_dialog(self):
        dialog, content = self._dialog("A little guidance",590,600)
        text = (
            "LOOK AROUND\nOrbit: drag to orbit, scroll to zoom, right-drag to pan.\nF5 switches to flight: WASD moves, Q/E goes down/up, Shift moves faster.\nDrag to look; scroll changes speed. Click a block to select it.\nFlight stops when another control receives focus. Go to coordinates\nmoves the camera; in orbit, Y clips the terrain.\n\n"
            "SELECT & EDIT\nClick a block, then Shift-click a second corner. Or enter both corners.\nChoose a material; fill, replace, delete, copy or paste. Undo with Ctrl/Cmd+Z.\nPaste → Free transform previews X/Y/Z rotations, scaling and reflections.\nSome states cannot represent tilted orientations; state rotation is optional.\n\n"
            "SAVE YOUR WORK\nCtrl/Cmd+S saves the original world with a retained backup. Close Minecraft\nbefore saving. Save copy exports a separate folder. Projects reference their\nsource world; keep that folder unchanged while using the project.\nUnsaved edits get recovery copies every 30 seconds by default. File includes\nworkspace recovery and world-save checkpoints for interrupted saves.\n\n"
            "DEEPER EDITING\nThe World tab includes Java/Bedrock biomes, typed block NBT, waterlogging,\nlayered fill, trusted Python operations and Bedrock archives. Paste includes\nclone/repeat. Structures: .nbt, .mcstructure, .schem v2/v3, legacy .schematic.\nManage selection regions adds boxes or subtracts holes. The chunk map\ncreates empty chunks, deletes, prunes and imports matching versions.\nChunk actions are staged and undoable, including associated metadata.\n\n"
            "MODELS & TEXTURES\nView → Resource packs and graphics loads local Java resource folders,\nZIPs or client JARs. Order packs, apply/reload and inspect diagnostics.\nAuto graphics uses system OpenGL with a portable software fallback.\nTextures, models, cutouts, fluids and biome colors appear in both cameras.\nOptional animation is off by default. Game assets are not downloaded.\n\n"
            "TRANSLATION & DISCOVERY\nOpen world discovers saved worlds and lets you add saves folders.\nMaterial studio searches versioned names and edits individual states.\nEdit → Translate clipboard previews Java 1.21.4 / Bedrock 1.21.50 and 1.21.60 rules.\nFile → Convert world creates a copy of a target template after preflight.\nUnsupported blocks, payload fields, actors and ticks block output.\n.construction imports/exports sparse native-edition selections and block NBT.\nView → Navigation and controls sets flight keys, speed, FOV and sensitivity.\n\n"
            "CURRENT COMPATIBILITY\nJava numeric/paletted Anvil through DataVersion 4189; Bedrock subchunks\nv8/v9. Legacy Java retains numeric metadata, not modern translated states.\nBedrock export is experimental; database budget is 256 MiB. Full Amulet\nparity, all-version translation, moving entities, specialized models\nand game lighting remain unfinished. Independent reference readers reopen\nconverted fixtures; exports have not been reopened in Minecraft.\n\n"
            "INDEPENDENT BY DESIGN\nOriginal code and art. Python + Tk only. No Amulet code or runtime.\nNo accounts, network requests, analytics or third-party Python packages."
        )
        Pill(content, "Got it", dialog.destroy, True, 100).pack(side="bottom",anchor="e",pady=12)
        body = tk.Text(content,bg=SURFACE,fg=MUTED,wrap="word",relief="flat",borderwidth=0,highlightthickness=0,font=(FONT,10),padx=0,pady=0)
        body.pack(fill="both",expand=True)
        body.insert("1.0",text)
        body.configure(state="disabled")

    def close_app(self):
        if self._confirm_discard():
            self._forget_recovery()
            self.destroy()

    def destroy(self):
        if self._recovery_id is not None:
            self.after_cancel(self._recovery_id)
            self._recovery_id = None
        if self._poll_id is not None:
            self.after_cancel(self._poll_id)
            self._poll_id = None
        super().destroy()


def launch():
    app = FacetEditApp()
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        path = sys.argv[1]
        if Path(path).suffix.lower() in (".facet",".facetedit",".luma"):
            app.after(100, lambda: app.worker(lambda: load_project(path), app._attach, "Opening project…"))
        else:
            app.after(100, lambda: app.open_path(path))
    app.mainloop()
