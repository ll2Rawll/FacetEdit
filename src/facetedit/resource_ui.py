"""Local resource stacks and renderer preferences, with no asset downloads."""
from pathlib import Path
import os,sys
import tkinter as tk
from tkinter import ttk,filedialog
from .chrome import SURFACE,INK,MUTED,BLUE,PALE,Pill,label
from .resources import ResourceStack


def installed_clients():
    base=Path(os.environ.get('APPDATA',Path.home()/'AppData/Roaming'))/'.minecraft' if sys.platform=='win32' else Path.home()/'Library/Application Support/minecraft' if sys.platform=='darwin' else Path.home()/'.minecraft'
    return tuple(sorted((p for p in (base/'versions').glob('*/*.jar') if p.stem==p.parent.name),key=lambda p:p.parent.name,reverse=True))[:256]


class ResourceUI:
    def _restore_resources(self):
        data=self.settings.data
        if data['resource_packs'] and data['resources_enabled']:
            self.load_resources(data['resource_packs'],True,data['renderer'],data['animate_textures'],persist=False)

    def load_resources(self,paths,enabled=True,backend='auto',animate=False,completed=None,persist=True):
        if self.busy:return
        paths=tuple(dict.fromkeys(str(Path(path).expanduser().resolve()) for path in paths))
        if len(paths)>16:raise ValueError('Use at most 16 resource packs in a stack')
        if backend not in ('auto','software'):raise ValueError('Unknown renderer')
        def loaded(stack):
            self.viewport.set_resources(stack,backend,animate)
            warning=''
            if persist:
                self.settings.data.update(resource_packs=list(paths),resources_enabled=bool(enabled),renderer=backend,animate_textures=bool(animate))
                try:self.settings.save()
                except OSError as exc:warning=' · Preferences were not saved: '+str(exc)
            self.status_var.set((f'{len(paths)} resource pack(s) loaded · Textured rendering enabled' if stack is not None else 'Solid-color rendering enabled')+warning)
            if completed is not None:completed()
        self.worker(lambda:ResourceStack(paths) if enabled and paths else None,loaded,'Reading local resource packs…')

    def resources_dialog(self):
        dialog,content=self._dialog('The material studio',720,650)
        label(content,'Bring your world into focus',19,True).pack(anchor='w')
        label(content,'Add Java resource folders, ZIPs, or an installed Minecraft client JAR.\nPacks near the bottom override the ones above them.',10,color=MUTED,justify='left').pack(anchor='w',pady=(6,14))
        paths=list(self.settings.data['resource_packs'])
        listing=tk.Listbox(content,bg=SURFACE,fg=INK,selectbackground=PALE,selectforeground=BLUE,highlightthickness=1,highlightbackground='#284059',borderwidth=0,activestyle='none',height=7,exportselection=False)
        listing.pack(fill='x')
        def refresh(index=None):
            listing.delete(0,'end')
            for i,path in enumerate(paths):listing.insert('end',f'  {i+1:02d}   {Path(path).name}   ·   {path}')
            if paths:listing.selection_set(min(len(paths)-1,index if index is not None else len(paths)-1))
        def add(path):
            if path and str(Path(path).resolve()) not in paths:
                if len(paths)>=16:self.show_error(ValueError('Use at most 16 resource packs'));return
                paths.append(str(Path(path).resolve()));refresh()
        def remove():
            if listing.curselection():paths.pop(listing.curselection()[0]);refresh()
        def move(step):
            if listing.curselection():
                index=listing.curselection()[0];target=index+step
                if 0<=target<len(paths):paths[index],paths[target]=paths[target],paths[index];refresh(target)
        row=tk.Frame(content,bg=SURFACE);row.pack(fill='x',pady=10)
        Pill(row,'Add ZIP / JAR',lambda:add(filedialog.askopenfilename(parent=dialog,title='Choose local resource assets',filetypes=[('Resource pack / client','*.zip *.jar'),('All files','*')])),width=133,height=32).pack(side='left',padx=(0,7))
        Pill(row,'Add folder',lambda:add(filedialog.askdirectory(parent=dialog,title='Choose a folder containing assets')),width=115,height=32).pack(side='left',padx=(0,7))
        for title,action,width in (('Remove',remove,89),('↑',lambda:move(-1),44),('↓',lambda:move(1),44)):
            Pill(row,title,action,width=width,height=32).pack(side='left',padx=(0,7))
        clients=installed_clients()
        if clients:
            row=tk.Frame(content,bg=SURFACE);row.pack(fill='x',pady=5);choice=tk.StringVar(value=str(clients[0]))
            ttk.Combobox(row,textvariable=choice,values=tuple(map(str,clients)),state='readonly',width=48).pack(side='left',fill='x',expand=True)
            Pill(row,'Add installed',lambda:add(choice.get()),width=120,height=30).pack(side='right',padx=(10,0))
        enabled=tk.BooleanVar(value=self.settings.data['resources_enabled']);animate=tk.BooleanVar(value=self.settings.data['animate_textures']);backend=tk.StringVar(value=self.settings.data['renderer'])
        ttk.Checkbutton(content,text='Render models and textures from this stack',variable=enabled).pack(anchor='w',pady=(8,3))
        ttk.Checkbutton(content,text='Animate textures (uses CPU / graphics while the view is idle)',variable=animate).pack(anchor='w',pady=3)
        row=tk.Frame(content,bg=SURFACE);row.pack(fill='x',pady=9)
        label(row,'Graphics',10,color=MUTED).pack(side='left')
        ttk.Combobox(row,textvariable=backend,values=('auto','software'),state='readonly',width=14).pack(side='left',padx=12)
        label(row,'Auto uses system OpenGL with a portable fallback.',9,color=MUTED).pack(side='left')
        summary=label(content,'',9,color=MUTED,wraplength=640,justify='left');summary.pack(anchor='w',pady=(8,6))
        def diagnostics():
            stack=self.viewport.resources;warnings=list(stack.warnings.items()) if stack is not None else []
            summary.configure(text=self.viewport.render_status+f'\n{len(warnings)} resource diagnostic(s). Missing or unsupported models use colored cubes.')
        def details():
            window,body=self._dialog('Resource diagnostics',650,430)
            text=tk.Text(body,bg=SURFACE,fg=MUTED,relief='flat',wrap='word',height=18);text.pack(fill='both',expand=True)
            stack=self.viewport.resources;warnings=list(stack.warnings.items()) if stack is not None else []
            fallback=self.viewport._display_frame.fallback_reason if self.viewport._display_frame is not None else ''
            text.insert('1.0',self.viewport.render_status+'\n'+(fallback+'\n' if fallback else '')+'\n'+('\n\n'.join(name+'\n'+reason for name,reason in warnings) or 'No resource errors recorded.'))
            text.configure(state='disabled');Pill(body,'Close',window.destroy,width=90).pack(anchor='e',pady=10)
        label(content,'Game assets stay on your computer. Some procedural block/entity models,\nBedrock model definitions and game lighting are not fully supported yet.',9,color=MUTED,justify='left').pack(anchor='w',pady=(5,10))
        row=tk.Frame(content,bg=SURFACE);row.pack(fill='x',pady=7)
        Pill(row,'Diagnostics',details,width=120).pack(side='left')
        def apply():
            try:self.load_resources(paths,enabled.get(),backend.get(),animate.get(),lambda:dialog.destroy() if dialog.winfo_exists() else None)
            except Exception as exc:self.show_error(exc)
        Pill(row,'Apply / reload',apply,True,155).pack(side='right')
        self.resource_paths=paths;self.resource_list=listing;self.resource_controls={'enabled':enabled,'animate':animate,'backend':backend,'apply':apply,'add':add,'remove':remove,'move':move,'diagnostics':details}
        refresh();diagnostics();self._manager_views.append((dialog,diagnostics))
