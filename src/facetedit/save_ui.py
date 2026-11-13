"""Original-world save and retained-backup recovery controls."""
from pathlib import Path
import tkinter as tk
from tkinter import filedialog,messagebox
from .chrome import SURFACE,INK,MUTED,BLUE,PALE,FONT,Pill,label
from .worldsave import save_original,list_saves,recover
from .model import Document


class WorldSaveUI:
    def save_original(self):
        if self.busy:return
        doc=self.document
        if doc.world.path is None:return self.save_project_dialog()
        if doc.revision==self._saved_revision and not doc.pending_count:
            self.status_var.set('No changes to save');return
        if not messagebox.askyesno('Save to the original world?',f'Update {doc.world.name} at its original location?\n\nClose Minecraft first. A complete backup is retained beside the world. Save copy is also available.',parent=self):return
        edits=dict(doc.edits);metadata=doc.export_metadata()
        def work():
            histories=doc.history_for_saved_world()
            result=save_original(doc.world,edits,lambda msg:self.messages.put(('progress',msg)),**metadata)
            return result,histories
        def complete(value):
            result,histories=value
            doc.rebase_saved_world(result.world,histories)
            self._saved_revision=doc.revision;self._forget_recovery()
            self.status_var.set('Original world saved · Undo retained · Backup: '+str(result.backup))
            self.viewport._geometry_key=None;self.refresh()
        self.worker(work,complete,'Preparing a recoverable world save…')

    def world_recovery_dialog(self,parent=None):
        if self.busy:return
        if parent is None:
            parent=self.document.world.path.parent if self.document.world.path else filedialog.askdirectory(parent=self,title='Choose the folder containing your Minecraft worlds and save backups')
        if not parent:return
        entries=[entry for entry in list_saves(parent,include_finished=True) if entry[1].get('state') not in ('rolled_back','cancelled')]
        dialog,content=self._dialog('World save checkpoints',800,490)
        label(content,'Recover an interrupted save or restore a retained original backup.',10,color=MUTED).pack(anchor='w',pady=(0,12))
        listing=tk.Listbox(content,bg='#0c1728',fg=INK,selectbackground=PALE,selectforeground=BLUE,highlightthickness=0,borderwidth=0,font=(FONT,10),exportselection=False)
        listing.pack(fill='both',expand=True)
        for folder,data,target in entries:listing.insert('end',f'{target.name}   ·   {data["state"]}   ·   {folder.name[-8:]}')
        details=label(content,'Current worlds that have changed since a checkpoint are preserved.',9,color=MUTED,wraplength=740,justify='left');details.pack(anchor='w',pady=12)
        def choose(_=None):
            if listing.curselection():details.configure(text=str(entries[listing.curselection()[0]][0]))
        def apply(action):
            if self.busy or not listing.curselection():return
            folder,data,target=entries[listing.curselection()[0]]
            if not self._confirm_discard():return
            if not messagebox.askyesno('Recover world save?',('Restore the original backup for ' if action=='rollback' else 'Finish the prepared save for ')+target.name+'?\n\nClose Minecraft before continuing.',parent=dialog):return
            def complete(world):
                self._attach(Document(world));self.status_var.set('World save recovered · '+str(target))
                if dialog.winfo_exists():dialog.destroy()
            self.worker(lambda:recover(folder,action),complete,'Recovering world save…')
        row=tk.Frame(content,bg=SURFACE);row.pack(fill='x')
        Pill(row,'Restore original backup',lambda:apply('rollback'),width=225).pack(side='left')
        Pill(row,'Finish interrupted save',lambda:apply('finish'),True,225).pack(side='right')
        listing.bind('<<ListboxSelect>>',choose)
        self.world_save_list=listing
        self._manager_views.append((dialog,lambda:None))
