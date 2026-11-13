"""Searchable, edition-aware block and typed-state browser."""
import tkinter as tk
from tkinter import ttk

from .blocks import Block
from .chrome import INK, MUTED, SURFACE, PALE, BLUE, FONT, Pill, label
from .registry import PROFILE_FILES, for_world, profile
from .dialog_state import DialogState


class MaterialsUI:
    def material_block(self):
        block = Block.parse(self.block_var.get())
        try:
            schema = for_world(self.document.world)
        except ValueError:
            return block
        return schema.validate(block, defaults=True) if block.name in schema.blocks else block

    def material_dialog(self):
        dialog, content = self._dialog('Material studio', 780, 610)
        lifetime = DialogState(dialog)
        dialog.resizable(True, True)
        dialog.minsize(680, 520)
        try:
            active = for_world(self.document.world).label
            caution = ''
        except ValueError:
            active = 'Bedrock 1.21.50' if self.document.world.edition.startswith('Bedrock') else 'Java 1.21.4'
            caution = 'This world has no matching bundled schema. Choose a reference version; compatibility is not assumed.'
        selected_profile = lifetime.string(active)
        version = ttk.Combobox(content, textvariable=selected_profile, values=list(PROFILE_FILES), state='readonly')
        version.pack(fill='x', pady=(0,8))
        search = lifetime.string()
        entry = ttk.Entry(content, textvariable=search)
        entry.pack(fill='x', pady=(0,12))
        body = tk.Frame(content, bg=SURFACE)
        body.pack(fill='both', expand=True)
        listing = tk.Frame(body, bg=SURFACE)
        listing.pack(side='left', fill='both', expand=True)
        choices = tk.Listbox(listing, bg='#0b1627', fg=INK, selectbackground=PALE, selectforeground=BLUE,
                             borderwidth=0, highlightthickness=0, font=(FONT,10), activestyle='none', exportselection=False)
        scroll = ttk.Scrollbar(listing, orient='vertical', command=choices.yview)
        choices.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        choices.pack(fill='both', expand=True)
        state_panel = tk.Frame(body, bg=SURFACE, width=290)
        state_panel.pack(side='right', fill='both', padx=(20,0))
        state_panel.pack_propagate(False)
        state_canvas = tk.Canvas(state_panel, bg=SURFACE, highlightthickness=0)
        state_scroll = ttk.Scrollbar(state_panel, command=state_canvas.yview)
        state_canvas.configure(yscrollcommand=state_scroll.set)
        state_scroll.pack(side='right', fill='y');state_canvas.pack(fill='both', expand=True)
        states = tk.Frame(state_canvas, bg=SURFACE)
        state_window = state_canvas.create_window(0,0,window=states,anchor='nw')
        states.bind('<Configure>',lambda _:state_canvas.configure(scrollregion=state_canvas.bbox('all')))
        state_canvas.bind('<Configure>',lambda e:state_canvas.itemconfigure(state_window,width=e.width))
        state_canvas.inspector_page = True
        for event in ('<MouseWheel>','<Button-4>','<Button-5>'):
            dialog.bind(event,self._inspector_wheel,add='+')
        def reveal(event):
            top=event.widget.winfo_rooty()-states.winfo_rooty()
            bottom=top+event.widget.winfo_height()
            visible=state_canvas.canvasy(0);height=state_canvas.winfo_height()
            destination=top if top<visible else bottom-height if bottom>visible+height else None
            if destination is not None:
                state_canvas.yview_moveto(max(0,destination)/max(1,states.winfo_height()))
        preview, note = lifetime.string(), lifetime.string(caution)
        preview_label=label(content, '', 9, color=MUTED, textvariable=preview, wraplength=710)
        preview_label.pack(fill='x', pady=(12,4))
        note_label=label(content, '', 9, color=MUTED, textvariable=note, wraplength=710)
        note_label.pack(fill='x')
        content.bind('<Configure>',lambda e:[widget.configure(wraplength=max(300,e.width-8)) for widget in (preview_label,note_label)])
        matches, variables = [], {}
        current = [None]
        try:
            original = Block.parse(self.block_var.get())
        except ValueError:
            original = None
        def value():
            return profile(selected_profile.get()).block(current[0], {k:v.get() for k,v in variables.items()})
        def preview_state(*_):
            if current[0]:
                preview.set(str(value()))
        def select(_=None):
            if not choices.curselection():
                return
            name = matches[choices.curselection()[0]]
            current[0] = name
            for child in states.winfo_children():
                child.destroy()
            for variable in list(variables.values()):
                lifetime.release(variable)
            variables.clear()
            schema = profile(selected_profile.get())
            initial = schema.initial(name)
            if original is not None and original.name == name:
                try:
                    initial = schema.validate(original, defaults=True)
                except ValueError:
                    pass
            label(states, Block(name).label, 12, True, wraplength=270).pack(anchor='w', pady=(0,12))
            defaults = dict(initial.properties)
            for key, (kind, domain) in schema.blocks[name]['properties'].items():
                row = tk.Frame(states, bg=SURFACE)
                row.pack(fill='x', pady=3)
                label(row, key.replace('minecraft:', ''), 9, color=MUTED).pack(anchor='w')
                variable = lifetime.string(defaults[key])
                variables[key] = variable
                combo = ttk.Combobox(row, textvariable=variable, values=domain, state='readonly')
                combo.pack(fill='x')
                combo.bind('<FocusIn>',reveal)
                variable.trace_add('write', preview_state)
            if not variables:
                label(states, 'This block has no states.', 10, color=MUTED).pack(anchor='w')
            detail = 'Java game defaults are preselected.' if schema.edition == 'Java' else 'Bedrock state domains are from Mojang. Initial choices are not verified game defaults.'
            note.set(caution or detail)
            preview_state()
            state_canvas.yview_moveto(0)
        def update(*_):
            words = search.get().lower().split()
            matches[:] = [name for name in profile(selected_profile.get()).blocks if all(w in name.replace('_',' ') or w in name for w in words)]
            choices.delete(0, 'end')
            for name in matches:
                choices.insert('end', '  '+name.removeprefix('minecraft:'))
            if matches:
                index = matches.index(original.name) if original and original.name in matches else 0
                choices.selection_set(index)
                choices.see(index)
                select()
            else:
                current[0] = None
                preview.set('No matching blocks')
        def choose(_=None):
            if current[0]:
                self.block_var.set(str(value()))
                self.inspector_tabs.select(0)
                dialog.destroy()
        search.trace_add('write', update)
        version.bind('<<ComboboxSelected>>', update)
        choices.bind('<<ListboxSelect>>', select)
        choices.bind('<Double-Button-1>', choose)
        dialog.bind('<Return>', choose)
        Pill(content, 'Use this material', choose, True, 180).pack(anchor='e', pady=(12,0))
        # Handles support real desktop automation without reaching into closures.
        dialog.material_controls = {'search':search, 'profile':selected_profile, 'choices':choices, 'states':variables, 'preview':preview, 'choose':choose, 'state_canvas':state_canvas, 'state_panel':states}
        update()
        entry.focus_set()
