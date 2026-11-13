"""Selection, chunk-map and recovery workflows for the native studio."""

from datetime import datetime
import threading
import tkinter as tk
from tkinter import ttk,filedialog,messagebox

from .chrome import BG,SURFACE,INK,MUTED,BLUE,PALE,FONT,Pill,label
from .model import Selection,SelectionGroup
from .recovery import RecoveryStore
from .structures import project_data
from .world import open_world


class EditorManagers:
    def _initialize_managers(self):
        self._manager_views = []
        self.recovery = RecoveryStore(self.settings.path.parent/'Recovery')
        self._restored_recovery = None
        self._recovery_inflight = False
        self._autosaved_revision = None
        self._recovery_id = self.after(self.settings.data['autosave_seconds']*1000,self._autosave_tick)

    def _refresh_managers(self):
        live = []
        for dialog,callback in self._manager_views:
            if dialog.winfo_exists():
                callback();live.append((dialog,callback))
        self._manager_views = live

    def _close_managers(self):
        for dialog,_ in self._manager_views:
            if dialog.winfo_exists():dialog.destroy()
        self._manager_views = []

    def _forget_recovery(self,preserve_current=False):
        self.recovery.clear(preserve=preserve_current)
        if self._restored_recovery is not None:
            self.recovery.discard(self._restored_recovery)
            self._restored_recovery = None
        self._autosaved_revision = None

    def _autosave_tick(self,reschedule=True):
        if self._recovery_id is not None:self.after_cancel(self._recovery_id)
        self._recovery_id = None
        if reschedule:
            self._recovery_id = self.after(self.settings.data['autosave_seconds']*1000,self._autosave_tick)
        doc = self.document
        identity = (id(doc),doc.revision)
        if not self.settings.data['autosave'] or self.busy or self._recovery_inflight or doc.revision==self._saved_revision or identity==self._autosaved_revision:
            return
        snapshot = doc.snapshot()
        generation = self.recovery.generation
        self._recovery_inflight = True
        def checkpoint():
            try:
                written = self.recovery.write(project_data(snapshot),snapshot.world.name,snapshot.pending_count,generation)
                self.messages.put(('recovery_saved',identity,generation,written))
            except Exception as exc:self.messages.put(('recovery_error',identity,str(exc)))
        threading.Thread(target=checkpoint,daemon=True,name='FacetEdit-recovery').start()

    def _handle_recovery_message(self,message):
        self._recovery_inflight = False
        if message[1][0]!=id(self.document):return
        if message[0]=='recovery_saved':
            if message[2]==self.recovery.generation and message[3]:
                self._autosaved_revision = message[1]
        else:self.status_var.set('Recovery copy could not be saved · '+message[2])

    def recovery_dialog(self):
        dialog,content = self._dialog('Pick up where you left off',690,470)
        label(content,'Recovery copies are separate from your source worlds.',10,color=MUTED).pack(anchor='w',pady=(0,12))
        listing = tk.Listbox(content,bg='#0c1728',fg=INK,selectbackground=PALE,selectforeground=BLUE,borderwidth=0,highlightthickness=0,font=(FONT,10),activestyle='none')
        listing.pack(fill='both',expand=True)
        details = label(content,'',9,color=MUTED)
        details.pack(anchor='w',pady=12)
        entries = []
        def refresh():
            entries[:] = self.recovery.entries(include_current=True)
            listing.delete(0,'end')
            for entry in entries:
                timestamp = datetime.fromtimestamp(entry.saved_at).strftime('%b %d  %H:%M')
                listing.insert('end',f'{timestamp}   {entry.name}   ·   {entry.changes:,} changes')
            details.configure(text=f'{len(entries)} recovery copies' if entries else 'No recovery copies. Unsaved edits are checkpointed every 30 seconds by default.')
        def selected():
            return entries[listing.curselection()[0]] if listing.curselection() else None
        def restore():
            entry = selected()
            if entry is None or self.busy:return
            # Loading before clearing the current session also supports restoring
            # an earlier checkpoint from this same open window.
            def complete(doc):
                if not self._confirm_discard():return
                self._attach(doc,preserve_recovery=entry.path==self.recovery.path)
                self._restored_recovery = entry.path if entry.path!=self.recovery.path else None
                self.document.revision = 1;self._saved_revision = 0
                if entry.path==self.recovery.path and self.recovery.path.exists():
                    self._autosaved_revision=(id(self.document),1)
                else:self._autosave_tick()
                self.status_var.set('Recovered '+entry.name+' · Save a project or edited world copy')
                self.refresh();dialog.destroy()
            self.worker(lambda:self.recovery.restore(entry.path),complete,'Restoring the recovery copy…')
        def discard():
            entry = selected()
            if entry and messagebox.askyesno('Discard recovery copy?','Remove this recovery checkpoint?\n'+entry.name,parent=dialog):
                self.recovery.discard(entry.path);refresh()
        row = tk.Frame(content,bg=SURFACE);row.pack(fill='x',pady=(5,0))
        Pill(row,'Discard selected',discard,width=165).pack(side='left')
        Pill(row,'Restore workspace',restore,True,190).pack(side='right')
        listing.bind('<Double-Button-1>',lambda _:restore())
        self.recovery_list = listing
        refresh()

    def regions_dialog(self):
        dialog,content = self._dialog('Build a selection, piece by piece',700,570)
        label(content,'Add boxes or subtract holes. Overlapping blocks are edited only once.',10,color=MUTED).pack(anchor='w',pady=(0,12))
        listing = tk.Listbox(content,bg='#0c1728',fg=INK,selectbackground=PALE,selectforeground=BLUE,borderwidth=0,highlightthickness=0,font=(FONT,10),height=8,exportselection=False,activestyle='none')
        listing.pack(fill='both',expand=True)
        summary = label(content,'',9,color=BLUE);summary.pack(anchor='w',pady=10)
        current = self.document.selection
        values = (*current.minimum,*current.maximum) if current else (0,0,0,15,15,15)
        variables = [tk.StringVar(value=str(v)) for v in values]
        for row_index,title in enumerate(('MINIMUM','MAXIMUM')):
            row = tk.Frame(content,bg=SURFACE);row.pack(fill='x',pady=4)
            label(row,title,8,True,MUTED,width=10,anchor='w').pack(side='left')
            for column,axis in enumerate('XYZ'):
                label(row,axis,9,color=MUTED).pack(side='left',padx=(12,6))
                ttk.Entry(row,textvariable=variables[row_index*3+column],width=10).pack(side='left')
        def box():
            values = tuple(int(v.get()) for v in variables)
            return Selection(values[:3],values[3:])
        def apply(mode):
            def action():
                if mode=='replace':self.document.selection = box()
                else:self.document.combine_selection(box(),mode)
            self.run_action(action)
            self._sync_selection()
        def remove():
            if self.busy or not listing.curselection() or not self.document.selection:return
            index = listing.curselection()[0]
            boxes = list(self.document.selection.boxes);boxes.pop(index)
            self.document.selection = SelectionGroup(boxes) if boxes else None
            self._sync_selection()
        def selected(_):
            if self.document.selection and listing.curselection():
                index=listing.curselection()[0]
                if index<len(self.document.selection.boxes):
                    item=self.document.selection.boxes[index]
                    for variable,value in zip(variables,(*item.minimum,*item.maximum)):variable.set(value)
        def refresh():
            listing.delete(0,'end')
            selection=self.document.selection
            for i,item in enumerate(selection.boxes if selection else (),1):
                listing.insert('end',f'{i:02}   {item.minimum}  →  {item.maximum}   ·   {item.volume:,} blocks')
            summary.configure(text=f'{len(selection.boxes)} regions · {selection.volume:,} unique blocks' if selection else 'No regions selected')
        row=tk.Frame(content,bg=SURFACE);row.pack(fill='x',pady=(17,0))
        for title,command,width in (('Add box',lambda:apply('add'),130),('Subtract box',lambda:apply('subtract'),145),('Use only this box',lambda:apply('replace'),170),('Remove',remove,105)):
            Pill(row,title,command,title=='Add box',width).pack(side='left',padx=(0,7))
        listing.bind('<<ListboxSelect>>',selected)
        self.region_vars,self.region_list=variables,listing
        self._manager_views.append((dialog,refresh));refresh()

    def chunks_dialog(self):
        if self.document.world.path is None:
            self.show_error(ValueError('Open a Java or Bedrock world to manage its stored chunks'))
            return
        doc = self.document
        dialog,content = self._dialog('The bigger picture',920,690)
        label(content,'Chunk edits are staged with undo. Save copy writes a separate world.',10,color=MUTED).pack(anchor='w',pady=(0,14))
        row=tk.Frame(content,bg=SURFACE);row.pack(fill='both',expand=True)
        left=tk.Frame(row,bg=SURFACE);left.pack(side='left',fill='both',expand=True,padx=(0,20))
        right=tk.Frame(row,bg=SURFACE,width=290);right.pack(side='right',fill='y');right.pack_propagate(False)
        map_view=tk.Canvas(left,bg='#0a1425',highlightthickness=1,highlightbackground='#30445f',width=510,height=440)
        map_view.pack(fill='both',expand=True)
        hover=label(left,'Click a chunk · Shift-click to add · Right-click to subtract',8,color=MUTED)
        hover.pack(anchor='w',pady=9)
        summary=label(right,'Reading chunk inventory…',10,True,BLUE,wraplength=280,justify='left');summary.pack(anchor='w',pady=(0,8))
        coords = [tk.StringVar() for _ in range(4)]
        center=[self.viewport.center_x//16,self.viewport.center_z//16]
        state={'loaded':False,'inventory':set(),'cell':27,'origin':(0,0),'start':(0,0)}
        selection=doc.selection
        default=(selection.minimum[0]//16,selection.minimum[2]//16,selection.maximum[0]//16,selection.maximum[2]//16) if selection else (*center,*center)
        for var,value in zip(coords,default):var.set(value)
        for offset,title in ((0,'FROM CHUNK X / Z'),(2,'TO CHUNK X / Z')):
            label(right,title,8,True,MUTED).pack(anchor='w',pady=(8,5))
            inputs=tk.Frame(right,bg=SURFACE);inputs.pack(fill='x')
            for var in coords[offset:offset+2]:ttk.Entry(inputs,textvariable=var,width=12).pack(side='left',padx=(0,8))
        def make_selection():
            x1,z1,x2,z2 = (int(v.get()) for v in coords)
            minimum,maximum=doc.world.bounds(doc.dimension)
            box=Selection((x1*16,minimum,z1*16),(x2*16+15,maximum,z2*16+15))
            box.chunks()  # Check the chunk budget without enumerating its blocks.
            return box
        def set_bounds():
            def action():
                doc.selection=make_selection()
                center[:]=[doc.selection.minimum[0]//16,doc.selection.minimum[2]//16]
            self.run_action(action);self._sync_selection()
        Pill(right,'Select these chunks',set_bounds,width=274).pack(fill='x',pady=(10,10))
        label(right,'CHUNK ACTIONS',8,True,MUTED).pack(anchor='w',pady=(0,8))
        def job(label_text,planner):
            if self.busy:return
            def complete(requested):
                if self.document is doc:
                    self.run_action(lambda:doc._chunk_transaction(label_text,requested),lambda n:f'{label_text} · {n:,} chunks · Undo is available')
            self.worker(planner,complete,'Preparing chunk changes…')
        def prune():
            if self.busy:return
            try:
                count=len(doc.chunk_positions()-doc.require_selection().chunks())
            except Exception as exc:self.show_error(exc);return
            if count and messagebox.askyesno('Prune outside the selection?',f'Stage deletion of {count:,} chunks outside the selected area?\n\nUndo remains available. The source world is preserved.',parent=dialog):
                job('Prune outside selection',lambda:doc.prepare_delete_chunks(True))
        def import_chunks():
            if self.busy:return
            path=filedialog.askdirectory(title='Choose a matching source world; chunks retain their coordinates',parent=dialog,mustexist=True)
            if path:job('Import chunks',lambda:doc.prepare_import_chunks(open_world(path)))
        for title,command in (('Create empty chunks',lambda:job('Create empty chunks',doc.prepare_create_chunks)),('Delete selected chunks',lambda:job('Delete selected chunks',doc.prepare_delete_chunks)),('Prune outside selection…',prune),('Import chunks from world…',import_chunks)):
            Pill(right,title,command,width=274,height=36).pack(fill='x',pady=4)
        label(right,'Empty means no generated terrain.\nImported chunks keep their coordinates.\nEdition and game versions must match.',8,color=MUTED,justify='left').pack(anchor='w',pady=10)
        def center_selection():
            if doc.selection:center[:]=[doc.selection.minimum[0]//16,doc.selection.minimum[2]//16]
            draw()
        Pill(right,'Center map on selection',center_selection,width=274,height=34).pack(fill='x',pady=4)
        def draw():
            if not state['loaded'] or self.document is not doc:return
            state['inventory']=doc.chunk_positions()
            try:selected_chunks=doc.selection.chunks() if doc.selection else set()
            except ValueError:selected_chunks=set()
            w,h=map_view.winfo_width(),map_view.winfo_height();cell=state['cell']
            columns,rows=max(1,w//cell),max(1,h//cell)
            start=(center[0]-columns//2,center[1]-rows//2)
            origin=((w-columns*cell)//2,(h-rows*cell)//2)
            state['start'],state['origin']=start,origin
            map_view.delete('all')
            for dz in range(rows):
                for dx in range(columns):
                    pos=(start[0]+dx,start[1]+dz);x,y=origin[0]+dx*cell,origin[1]+dz*cell
                    pending=doc.chunk_edits.get((doc.dimension,*pos))
                    fill='#24465a' if pos in state['inventory'] else '#0e1b2d'
                    if pending:fill='#523248' if pending.kind=='deleted' else '#215b54'
                    if pos in selected_chunks:fill='#579aa5'
                    map_view.create_rectangle(x+2,y+2,x+cell-2,y+cell-2,fill=fill,outline=BLUE if pos in selected_chunks else '#2c4057',width=1)
                    if pending and pending.kind=='deleted':map_view.create_line(x+7,y+7,x+cell-7,y+cell-7,fill='#df99bb')
                    if cell>=36:map_view.create_text(x+cell/2,y+cell/2,text=f'{pos[0]}\n{pos[1]}',fill=INK,font=(FONT,7))
            summary.configure(text=f'{len(state["inventory"]):,} stored chunks\n{len(selected_chunks):,} selected · {sum(key[0]==doc.dimension for key in doc.chunk_edits)} staged')
        def position(event):
            return (state['start'][0]+(event.x-state['origin'][0])//state['cell'],state['start'][1]+(event.y-state['origin'][1])//state['cell'])
        def pick(event,subtract=False):
            if self.busy or not state['loaded']:return
            cx,cz=position(event);minimum,maximum=doc.world.bounds(doc.dimension)
            box=Selection((cx*16,minimum,cz*16),(cx*16+15,maximum,cz*16+15))
            def apply():
                if subtract:doc.combine_selection(box,'subtract')
                elif event.state&1:doc.combine_selection(box,'add')
                else:doc.selection=box
            self.run_action(apply);self._sync_selection()
            for var,value in zip(coords,(cx,cz,cx,cz)):var.set(value)
        def motion(event):
            if state['loaded']:
                cx,cz=position(event);hover.configure(text=f'Chunk {cx}, {cz} · Blocks X {cx*16}…{cx*16+15}, Z {cz*16}…{cz*16+15}')
        def zoom(event):
            state['cell']=max(15,min(60,state['cell']+(3 if getattr(event,'delta',0)>0 or getattr(event,'num',0)==4 else -3)));draw()
        map_view.bind('<Button-1>',pick);map_view.bind('<Button-3>',lambda e:pick(e,True))
        map_view.bind('<Motion>',motion);map_view.bind('<Configure>',lambda _:draw())
        for event in ('<MouseWheel>','<Button-4>','<Button-5>'):map_view.bind(event,zoom)
        self.chunk_map,self.chunk_vars=map_view,coords
        self._manager_views.append((dialog,draw))
        def ready(_):
            if dialog.winfo_exists():state['loaded']=True;draw()
        self.worker(doc.chunk_positions,ready,'Reading the chunk inventory…')
