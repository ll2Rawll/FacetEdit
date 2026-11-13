"""Movable paste preview and independent XYZ transform controls."""
import tkinter as tk
from tkinter import ttk
from .chrome import SURFACE,MUTED,Pill,label


class TransformUI:
    def transform_dialog(self):
        if self.busy:return
        if self.document.clipboard is None:
            self.show_error(ValueError('Copy a selection or import a structure first'));return
        dialog,content=self._dialog('Place your next idea',610,620)
        doc=self.document;clipboard=doc.clipboard
        origin=doc.selection.minimum if doc.selection else (0,0,0)
        values={name:[tk.StringVar(value=str(v)) for v in initial] for name,initial in (('origin',origin),('rotation',(0,0,0)),('scale',(1,1,1)))}
        label(content,'Rotate freely, stretch, or reflect your clipboard before placing it.',10,color=MUTED,wraplength=540,justify='left').pack(anchor='w',pady=(0,14))
        for name,title in (('origin','Destination · X / Y / Z'),('rotation','Rotation in degrees · X / Y / Z'),('scale','Scale · X / Y / Z (negative values reflect)')):
            label(content,title,10,True).pack(anchor='w',pady=(10,5))
            row=tk.Frame(content,bg=SURFACE);row.pack(fill='x')
            for var in values[name]:ttk.Entry(row,textvariable=var,width=14).pack(side='left',expand=True,fill='x',padx=(0,9))
        rotate=tk.BooleanVar(value=True)
        ttk.Checkbutton(content,text='Rotate block states with the structure',variable=rotate).pack(anchor='w',pady=(16,6))
        label(content,'The rotated bounding box starts at the destination. Arbitrary angles\nresample blocks. Some blocks cannot represent tilted orientations.',9,color=MUTED,justify='left').pack(anchor='w',pady=6)
        summary=label(content,'',10,color=MUTED,wraplength=540,justify='left');summary.pack(anchor='w',pady=8)
        def read():
            position=tuple(int(v.get()) for v in values['origin'])
            if any(abs(v)>30_000_000 for v in position):raise ValueError('Destination must be inside world coordinate bounds')
            return position,tuple(float(v.get()) for v in values['rotation']),tuple(float(v.get()) for v in values['scale'])
        def preview():
            try:
                position,rotation,scale=read();clip=clipboard.affine(rotation,scale,rotate.get())
                anchor=tuple(position[i]+clip.offset[i] for i in range(3))
                self.viewport.preview=(clip,anchor)
                summary.configure(text=f'{len(clip.blocks):,} sampled blocks · '+' × '.join(map(str,clip.size))+' bounds\nPlacement preview shows bounds and representative blocks.')
                self.viewport.schedule()
            except Exception as exc:self.viewport.preview=None;self.viewport.schedule();summary.configure(text=str(exc))
        def close():self.viewport.preview=None;self.viewport.schedule();dialog.destroy()
        def paste():
            def apply():
                if self.document is not doc or doc.clipboard is not clipboard:raise ValueError('Clipboard changed; reopen the transform panel')
                position,rotation,scale=read()
                return doc.paste(position,include_air=self.include_air.get(),include_water=self.include_water.get(),include_lava=self.include_lava.get(),rotation=rotation,scale=scale,rotate_states=rotate.get())
            if self.run_action(apply,lambda n:f'Pasted {n:,} transformed blocks · Undo is available') is not None:close()
        nudge=tk.Frame(content,bg=SURFACE);nudge.pack(fill='x',pady=9)
        def move(axis,amount):
            try:values['origin'][axis].set(str(int(values['origin'][axis].get())+amount));preview()
            except ValueError:summary.configure(text='Destination needs integer coordinates')
        for axis,key in enumerate('XYZ'):
            for amount in (-1,1):Pill(nudge,key+(' −' if amount<0 else ' +'),lambda a=axis,n=amount:move(a,n),width=78,height=29).pack(side='left',padx=(0,8))
        row=tk.Frame(content,bg=SURFACE);row.pack(fill='x',pady=10)
        Pill(row,'Preview',preview,width=120).pack(side='left')
        Pill(row,'Cancel',close,width=100).pack(side='left',padx=10)
        Pill(row,'Paste transform',paste,True,175).pack(side='right')
        self.transform_vars,self.transform_rotate=values,rotate
        dialog.protocol('WM_DELETE_WINDOW',close);dialog.bind('<Escape>',lambda _:close())
        def destroyed(event):
            if event.widget is dialog:self.viewport.preview=None;self.viewport.schedule()
        dialog.bind('<Destroy>',destroyed);self._manager_views.append((dialog,lambda:None));preview()
