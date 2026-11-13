"""Explicit operation selection and execution; discovery never executes Python."""
from importlib import resources
import threading
import tkinter as tk
from tkinter import ttk,filedialog
from .chrome import SURFACE,INK,MUTED,BLUE,PALE,FONT,Pill,label
from .operations import OperationSpec,run_operation,Cancelled


class OperationsUI:
    def operations_dialog(self):
        dialog,content=self._dialog('Make it your operation',660,610)
        label(content,'Choose a bundled operation or load your own Python script.',10,color=MUTED).pack(anchor='w',pady=(0,10))
        listing=tk.Listbox(content,bg='#0c1728',fg=INK,selectbackground=PALE,selectforeground=BLUE,highlightthickness=0,borderwidth=0,font=(FONT,10),height=4,exportselection=False)
        listing.pack(fill='x')
        description=label(content,'',9,color=MUTED,wraplength=600,justify='left');description.pack(anchor='w',pady=12)
        form=tk.Frame(content,bg=SURFACE);form.pack(fill='both',expand=True)
        specs=[];variables={};cancel=threading.Event()
        def choose(_=None):
            for child in form.winfo_children():child.destroy()
            variables.clear()
            if not listing.curselection():return
            spec=specs[listing.curselection()[0]];description.configure(text=spec.description)
            for item in spec.options:
                row=tk.Frame(form,bg=SURFACE);row.pack(fill='x',pady=5)
                label(row,item['name'].replace('_',' ').capitalize(),10,width=20,anchor='w').pack(side='left')
                kind=item.get('type','text');value=item.get('default','')
                var=tk.BooleanVar(value=value) if kind=='bool' else tk.StringVar(value=value)
                variables[item['name']]=var
                if kind=='bool':widget=ttk.Checkbutton(row,variable=var)
                elif kind=='choice':widget=ttk.Combobox(row,textvariable=var,values=item['choices'],state='readonly')
                else:widget=ttk.Entry(row,textvariable=var)
                widget.pack(side='left',fill='x',expand=True)
        def append(spec):
            specs.append(spec);listing.insert('end',spec.name);listing.selection_clear(0,'end');listing.selection_set(len(specs)-1);choose()
        def load():
            if self.busy:return
            path=filedialog.askopenfilename(parent=dialog,title='Load a trusted FacetEdit operation',filetypes=[('Python operation','*.py')])
            if path:
                try:append(OperationSpec.read(path))
                except Exception as exc:self.show_error(exc)
        def run():
            if self.busy or not listing.curselection():return
            spec=specs[listing.curselection()[0]];values={name:var.get() for name,var in variables.items()};doc=self.document
            cancel.clear()
            def work():
                try:return run_operation(spec,doc,values,cancel,lambda value:self.messages.put(('progress',f'{spec.name} · {value:.0%}')))
                except Cancelled:return None
            def complete(result):
                if result is None or cancel.is_set():self.status_var.set('Operation cancelled · No edits applied')
                else:self.run_action(lambda:result.commit(self.document),lambda n:f'{spec.name} · {n:,} edits · Undo is available')
            self.worker(work,complete,'Preparing operation…')
        label(content,'Custom Python runs with your account. Load scripts you trust.\nCancellation is cooperative; edits are staged until the script finishes.',8,color=MUTED,justify='left').pack(anchor='w',pady=12)
        row=tk.Frame(content,bg=SURFACE);row.pack(fill='x')
        Pill(row,'Load script…',load,width=135).pack(side='left')
        Pill(row,'Cancel run',cancel.set,width=125).pack(side='left',padx=10)
        Pill(row,'Run operation',run,True,165).pack(side='right')
        listing.bind('<<ListboxSelect>>',choose)
        for name in ('checkerboard.py','shell.py'):
            source=resources.files('facetedit').joinpath('operation_examples',name).read_text('utf-8')
            append(OperationSpec.parse(source,name))
        listing.selection_clear(0,'end');listing.selection_set(0);choose()
        self.operation_list,self.operation_vars=listing,variables
        def close():cancel.set();dialog.destroy()
        dialog.protocol('WM_DELETE_WINDOW',close);dialog.bind('<Escape>',lambda _:close())
        self._manager_views.append((dialog,lambda:None))
