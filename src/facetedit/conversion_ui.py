"""Desktop preflight/report flows for clipboard and template-world conversion."""
from pathlib import Path
import threading
import tkinter as tk
from tkinter import ttk, filedialog

from .chrome import SURFACE, INK, MUTED, FONT, Pill, label
from .converter import prepare_conversion, publish_conversion
from .registry import PROFILE_FILES, profile, for_world
from .translation import translate_clipboard
from .world import open_world
from .dialog_state import DialogState


def report_box(content):
    frame = tk.Frame(content,bg=SURFACE)
    frame.pack(fill='both',expand=True,pady=12)
    text = tk.Text(frame,bg='#0b1627',fg=INK,insertbackground=INK,borderwidth=0,highlightthickness=0,
                   font=(FONT,10),wrap='word',padx=14,pady=12,state='disabled',height=10)
    scrollbar=ttk.Scrollbar(frame,command=text.yview)
    text.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side='right',fill='y');text.pack(fill='both',expand=True)
    def display(value):
        text.configure(state='normal');text.delete('1.0','end');text.insert('1.0',value);text.configure(state='disabled')
    return text,display


class ConversionUI:
    def translate_clipboard_dialog(self):
        if self.busy:
            return
        clip=self.document.clipboard
        if clip is None:
            self.status_var.set('Copy a selection or import a structure first')
            return
        dialog,content=self._dialog('Translate your clipboard',760,550)
        lifetime=DialogState(dialog)
        label(content,'Review version and state compatibility before replacing the clipboard.',10,color=MUTED).pack(anchor='w')
        source=lifetime.string('Read from structure')
        try:
            target_label=for_world(self.document.world).label
        except ValueError:
            target_label='Java 1.21.4'
        target=lifetime.string(target_label)
        for title,variable,choices in (('Source edition / version',source,['Read from structure',*PROFILE_FILES]),('Target edition / version',target,list(PROFILE_FILES))):
            label(content,title,9,color=MUTED).pack(anchor='w',pady=(12,4))
            ttk.Combobox(content,textvariable=variable,values=choices,state='readonly').pack(fill='x')
        text,display=report_box(content)
        display('Select a source version explicitly only when the imported format has no version metadata. Unsupported blocks or payloads are listed with coordinates.')
        prepared=[None];cancel=threading.Event()
        lifetime.cleanups.append(cancel.set)
        def invalidate(*_):
            prepared[0]=None
            apply_button.state(False)
        source.trace_add('write',invalidate);target.trace_add('write',invalidate)
        def preview():
            if self.busy:
                return
            invalidate()
            cancelled=cancel.is_set;cancel.clear()
            source_profile=None if source.get()=='Read from structure' else profile(source.get())
            target_profile=profile(target.get())
            parameters=(source.get(),target.get())
            if source_profile is not None and source_profile.edition!=clip.edition:
                display('Source edition does not match the imported structure.');return
            if source_profile is not None and clip.edition=='Java' and source_profile.data_version!=clip.data_version:
                display('Source DataVersion disagrees with the structure.');return
            if source_profile is not None and clip.game_version and source_profile.version!=clip.game_version:
                display('Source release disagrees with the structure.');return
            def work():
                try:
                    return translate_clipboard(clip,target_profile,source_profile,cancelled=cancelled)
                except InterruptedError:
                    return None
            def complete(result):
                if not dialog.winfo_exists():
                    return
                if result is None:
                    display('Translation cancelled.');return
                if parameters!=(source.get(),target.get()):
                    display('Options changed during translation. Run preview again.');return
                prepared[0]=result[0];display(result[1].summary())
                apply_button.state(prepared[0] is not None)
            self.worker(work,complete,'Checking clipboard translation…')
        def use():
            if self.busy or prepared[0] is None:
                return
            if self.document.clipboard is not clip:
                display('The clipboard changed. Close this window and review the new clipboard.');return
            self.document.clipboard=prepared[0]
            self.status_var.set('Translated clipboard ready · Select a destination and paste')
            self.refresh();close()
        row=tk.Frame(content,bg=SURFACE);row.pack(fill='x')
        Pill(row,'Preview translation',preview,True,185).pack(side='left')
        apply_button=Pill(row,'Use translated clipboard',use,width=230);apply_button.pack(side='right');apply_button.state(False)
        def close():
            cancel.set();dialog.destroy()
        dialog.protocol('WM_DELETE_WINDOW',close);dialog.bind('<Escape>',lambda _:close())
        dialog.conversion_controls={'source':source,'target':target,'preview':preview,'use':use,'report':text,'prepared':prepared}

    def convert_world_dialog(self):
        if self.busy:
            return
        dialog,content=self._dialog('World conversion studio',850,650)
        lifetime=DialogState(dialog)
        label(content,'Convert the open world into a new copy of a target template world.',11,color=MUTED).pack(anchor='w')
        label(content,'The template supplies the target edition, version, seed, settings and players.\nSource blocks replace matching chunks; template chunks outside that footprint remain.',9,color=MUTED,justify='left').pack(anchor='w',pady=(8,12))
        template_path=lifetime.string()
        row=tk.Frame(content,bg=SURFACE);row.pack(fill='x')
        ttk.Entry(row,textvariable=template_path).pack(side='left',fill='x',expand=True)
        def browse():
            value=filedialog.askdirectory(parent=dialog,title='Choose a saved target template world')
            if value:
                template_path.set(value)
        Pill(row,'Choose template…',browse,width=170).pack(side='right',padx=(10,0))
        policies={'Preserve biome cells exactly':'preserve','Sample biomes into target cells':'sample','Use dimension default biomes':'dimension_default'}
        policy=lifetime.string(next(iter(policies)))
        ttk.Combobox(content,textvariable=policy,values=list(policies),state='readonly').pack(fill='x',pady=(12,0))
        text,display=report_box(content)
        display('Preflight writes temporary converted chunks for inspection. The source and target template stay unchanged. No output world is published while the report contains blockers.')
        plan=[None];revision=[None];cancel=threading.Event()
        def cleanup():
            cancel.set()
            if plan[0] is not None:
                plan[0].close();plan[0]=None
        lifetime.cleanups.append(cleanup)
        doc=self.document
        def discard(*_):
            if plan[0] is not None:
                plan[0].close();plan[0]=None
            publish_button.state(False)
        template_path.trace_add('write',discard);policy.trace_add('write',discard)
        def progress(message):
            self.messages.put(('progress',message))
        def preview():
            if self.busy:
                return
            discard();cancel.clear();revision[0]=doc.revision
            path=template_path.get();mode=policies[policy.get()]
            def work():
                try:
                    return prepare_conversion(doc,open_world(Path(path)),mode,cancel.is_set,progress)
                except InterruptedError:
                    return None
            def complete(result):
                if not dialog.winfo_exists():
                    if result is not None:result.close()
                    return
                if cancel.is_set() or result is None:
                    if result is not None:result.close()
                    display('Conversion cancelled · No output published');self.status_var.set('Conversion cancelled');return
                if (path,mode)!=(template_path.get(),policies[policy.get()]):
                    result.close();display('Options changed during preflight. Run preflight again.');return
                plan[0]=result
                display(result.report.summary()+f'\n\n{len(result.entries):,} prepared chunks.' if result is not None else 'Conversion cancelled.')
                publish_button.state(result.report.ok)
            self.worker(work,complete,'Preparing conversion preflight…')
        def publish():
            if self.busy or plan[0] is None or not plan[0].report.ok:
                return
            if self.document is not doc or doc.revision!=revision[0]:
                display('The workspace changed after preflight. Run preflight again.');return
            path=filedialog.asksaveasfilename(parent=dialog,title='Name a new converted-world folder',initialfile=doc.world.name+' converted')
            if not path:
                return
            prepared=plan[0];plan[0]=None;cancel.clear();publish_button.state(False)
            def work():
                try:
                    return publish_conversion(prepared,path,cancel.is_set,progress)
                except InterruptedError:
                    return None
                finally:
                    prepared.close()
            def complete(result):
                message='Conversion cancelled · No output published' if result is None else 'Converted world saved · '+str(result)
                self.status_var.set(message)
                if dialog.winfo_exists():display(message)
            self.worker(work,complete,'Writing the converted world copy…')
        row=tk.Frame(content,bg=SURFACE);row.pack(fill='x')
        Pill(row,'Run preflight',preview,True,150).pack(side='left')
        Pill(row,'Cancel run',cancel.set,width=130).pack(side='left',padx=10)
        publish_button=Pill(row,'Save converted copy…',publish,width=210);publish_button.pack(side='right');publish_button.state(False)
        def close():
            cancel.set();discard();dialog.destroy()
        dialog.protocol('WM_DELETE_WINDOW',close);dialog.bind('<Escape>',lambda _:close())
        dialog.conversion_controls={'template':template_path,'policy':policy,'preview':preview,'publish':publish,'report':text,'plan':plan,'cancel':cancel}
