import tkinter as tk
from tkinter import ttk
from .chrome import SURFACE,MUTED,Pill,label
from .navigation import KEYS,validate_navigation,apply_navigation
from .dialog_state import DialogState


class NavigationUI:
    def navigation_dialog(self):
        dialog,content=self._dialog('Move at your own pace',650,680)
        lifetime=DialogState(dialog)
        values=self.settings.data['navigation']
        variables={}
        for title,key,limits in (('Field of view · degrees','fov','30–110'),('Flight speed · blocks / second','speed','1–64'),('Mouse sensitivity','sensitivity','0.1–3'),('Boost multiplier','boost','1–16')):
            row=tk.Frame(content,bg=SURFACE);row.pack(fill='x',pady=7)
            label(row,title,10).pack(side='left')
            label(row,limits,9,color=MUTED).pack(side='right',padx=12)
            variable=lifetime.string(str(values[key]));variables[key]=variable
            ttk.Entry(row,textvariable=variable,width=9).pack(side='right')
        invert=lifetime.boolean(values['invert_y'])
        ttk.Checkbutton(content,text='Invert vertical mouse look',variable=invert).pack(anchor='w',pady=10)
        label(content,'FLIGHT CONTROLS',9,True,color=MUTED).pack(anchor='w',pady=(12,8))
        grid=tk.Frame(content,bg=SURFACE);grid.pack(fill='x')
        bindings={}
        for index,(action,key) in enumerate(values['bindings'].items()):
            row,column=divmod(index,2)
            label(grid,action.title(),10).grid(row=row,column=column*2,sticky='w',padx=(0,12),pady=7)
            variable=lifetime.string(key);bindings[action]=variable
            ttk.Combobox(grid,textvariable=variable,values=KEYS,state='readonly',width=13).grid(row=row,column=column*2+1,sticky='ew',padx=(0,24),pady=7)
        label(content,'Space also moves up when unassigned. Shift uses either side when available.\nControls apply while the viewport has focus; typing in fields keeps working.',9,color=MUTED,justify='left').pack(anchor='w',pady=12)
        def save():
            try:
                result=validate_navigation({**{k:float(v.get()) for k,v in variables.items()},'invert_y':invert.get(),'bindings':{k:v.get() for k,v in bindings.items()}})
                self.settings.data['navigation']=result;self.settings.save();apply_navigation(self.viewport,result);dialog.destroy()
            except (ValueError,OSError) as exc:self.show_error(exc)
        Pill(content,'Save controls',save,True,165).pack(anchor='e')
        dialog.navigation_controls={'values':variables,'bindings':bindings,'invert':invert,'save':save}
