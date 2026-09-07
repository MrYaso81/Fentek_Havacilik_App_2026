"""Short, non-blocking color transitions for native and themed buttons."""
import tkinter as tk
from tkinter import ttk


def install_button_motion(root):
    style=ttk.Style(root)
    def attach(event):
        widget=event.widget
        if not isinstance(widget,(tk.Button,ttk.Button)) or hasattr(widget,'_motion'):return
        themed=isinstance(widget,ttk.Button)
        original=widget.cget('style') or 'TButton' if themed else None
        base=style.lookup(original,'background') if themed else widget.cget('background')
        if not base:return
        name=f'Motion{id(widget)}.{original}' if themed else None
        if themed:
            style.configure(name,background=base)
            style.map(name,background=[('disabled','#303238')])
            widget.configure(style=name)
        state={'job':None,'base':base,'current':base}
        widget._motion=state
        def disabled():
            return widget.instate(['disabled']) if themed else widget.cget('state')=='disabled'
        def animate(target):
            if state['job']:
                root.after_cancel(state['job']);state['job']=None
            if not widget.winfo_exists() or disabled():return
            start=widget.winfo_rgb(state['current'])
            end=widget.winfo_rgb(target)
            def frame(step=1):
                state['job']=None
                if not widget.winfo_exists() or disabled():return
                t=1-(1-step/8)**3
                color='#'+''.join(f'{round((a+(b-a)*t)/257):02x}' for a,b in zip(start,end))
                state['current']=color
                if themed:style.configure(name,background=color)
                else:widget.configure(background=color,activebackground=color)
                if step<8:state['job']=root.after(16,lambda:frame(step+1))
            frame()
        def enter(_):
            if not themed and widget.cget('background')!=state['current']:
                state['base']=state['current']=widget.cget('background')
            rgb=widget.winfo_rgb(state['base'])
            hover='#'+''.join(f'{min(255,round(v/257*.82+46)):02x}' for v in rgb)
            animate(hover)
        def leave(_):animate(state['base'])
        def press(_):animate('#b49a35')
        def release(_):
            # Let existing command handlers finish before restoring their selected color.
            root.after_idle(lambda:enter(None) if widget.winfo_exists() else None)
        def destroy(_):
            if state['job']:root.after_cancel(state['job']);state['job']=None
        for event_name,handler in [('<Enter>',enter),('<Leave>',leave),('<ButtonPress-1>',press),
                                   ('<ButtonRelease-1>',release),('<FocusIn>',enter),('<FocusOut>',leave),('<Destroy>',destroy)]:
            widget.bind(event_name,handler,add='+')
    root.bind_all('<Map>',attach,add='+')
    def visit(widget):
        attach(type('Mapped',(),{'widget':widget})())
        for child in widget.winfo_children():visit(child)
    visit(root)
