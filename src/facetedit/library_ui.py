"""World library with background metadata scanning and manual folder access."""
import threading
import tkinter as tk
from tkinter import ttk,filedialog

from .chrome import SURFACE,INK,MUTED,FONT,Pill,label
from .discovery import standard_paths,discover_worlds
from .dialog_state import DialogState


class LibraryUI:
    def world_library(self):
        if self.busy:return
        dialog,content=self._dialog('Your worlds, within reach',820,590)
        lifetime=DialogState(dialog)
        label(content,'Java and Bedrock saves · choose a world or browse any folder.',10,color=MUTED).pack(anchor='w',pady=(0,12))
        search=lifetime.string();entry=ttk.Entry(content,textvariable=search);entry.pack(fill='x',pady=(0,12))
        table=tk.Frame(content,bg=SURFACE);table.pack(fill='both',expand=True)
        listing=ttk.Treeview(table,columns=('edition','version'),show='tree headings',selectmode='browse',height=6)
        listing.heading('#0',text='World');listing.heading('edition',text='Edition');listing.heading('version',text='Version')
        listing.column('#0',width=350);listing.column('edition',width=100);listing.column('version',width=155)
        scroll=ttk.Scrollbar(table,command=listing.yview);listing.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y');listing.pack(fill='both',expand=True)
        detail=lifetime.string('Scanning known Minecraft installations…')
        label(content,'',9,color=MUTED,textvariable=detail,wraplength=750,justify='left').pack(fill='x',pady=12)
        worlds=[];issues=[];cancel=threading.Event()
        lifetime.cleanups.append(cancel.set)
        def filter_worlds(*_):
            listing.delete(*listing.get_children())
            query=search.get().casefold()
            for index,world in enumerate(worlds):
                if query in (world.name+' '+world.edition+' '+str(world.path)).casefold():
                    listing.insert('','end',iid=str(index),text=world.name,values=(world.edition,world.version))
        def select(_=None):
            choice=listing.selection()
            if choice:detail.set(str(worlds[int(choice[0])].path))
        def open_selected(_=None):
            choice=listing.selection()
            if choice and not self.busy:
                path=worlds[int(choice[0])].path;close();self.open_path(path)
        def browse():
            if self.busy:return
            path=filedialog.askdirectory(parent=dialog,title='Open a Minecraft world folder',mustexist=True)
            if path:close();self.open_path(path)
        def scan():
            if self.busy:return
            cancel.clear()
            roots=(*standard_paths(),*self.settings.data['world_roots']);recent=list(self.settings.data['recent'])
            def work():
                try:return discover_worlds(roots,recent,cancel.is_set)
                except InterruptedError:return None
            def complete(result):
                if result is None or not dialog.winfo_exists():return
                worlds[:],issues[:]=result;filter_worlds()
                detail.set(f'{len(worlds)} worlds found.'+(' '+str(len(issues))+' folders could not be read; browse to open another world.' if issues else ''))
            self.worker(work,complete,'Scanning Minecraft save metadata…')
        def add_root():
            if self.busy:return
            path=filedialog.askdirectory(parent=dialog,title='Add a folder containing worlds',mustexist=True)
            if path:
                self.settings.data['world_roots']=list(dict.fromkeys([*self.settings.data['world_roots'],path]))[-32:]
                try:self.settings.save()
                except OSError as exc:self.show_error(exc);return
                scan()
        row=tk.Frame(content,bg=SURFACE);row.pack(fill='x')
        Pill(row,'Browse folder…',browse,width=150).pack(side='left')
        Pill(row,'Add saves folder…',add_root,width=165).pack(side='left',padx=8)
        Pill(row,'Refresh',scan,width=105).pack(side='left')
        Pill(row,'Open world',open_selected,True,140).pack(side='right')
        search.trace_add('write',filter_worlds);listing.bind('<<TreeviewSelect>>',select);listing.bind('<Double-Button-1>',open_selected)
        dialog.bind('<Return>',open_selected)
        def close():cancel.set();dialog.destroy()
        dialog.protocol('WM_DELETE_WINDOW',close);dialog.bind('<Escape>',lambda _:close())
        dialog.library_controls={'search':search,'listing':listing,'worlds':worlds,'open':open_selected,'scan':scan,'issues':issues}
        scan();entry.focus_set()
