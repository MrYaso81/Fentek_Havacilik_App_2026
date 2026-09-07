"""Light/dark application chrome; imagery and flight instruments keep their colors."""
import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk


class ThemeControl:
    COLORS={'#0c0d0f':'#eef2f7','#17191c':'#ffffff','#303238':'#ccd5e1',
            '#111214':'#e3eaf3','#121315':'#e3eaf3','#111315':'#e3eaf3',
            '#292b2f':'#dce5f0','#2a2c30':'#dce5f0','#292b2e':'#dce5f0',
            '#3b3519':'#fff0b3','#352f14':'#fff0b3',
            '#f5f3e8':'#182638','#afb0b4':'#526176','#d8d8d8':'#526176'}

    def __init__(self,root):
        self.root=root
        self.style=ttk.Style(root)
        self.saved={}
        self.style_saved={}
        self.light=False
        self.path=Path(__file__).with_name('appearance.json')
        header=root.winfo_children()[0]
        self.button=ttk.Button(header,text='☀ Aydınlık',command=self.toggle)
        self.button.pack(side='right',padx=10)
        try:preferred=json.loads(self.path.read_text(encoding='utf-8')).get('theme')=='light'
        except (OSError,ValueError):preferred=False
        if preferred:self.toggle(save=False)
        self.job=root.after(250,self.poll)

    def color(self,value,option):
        value=str(value).lower()
        if value=='#0c0d0f' and option in ('foreground','activeforeground','insertbackground'):return value
        if value=='#ffd42a' and option in ('foreground','activeforeground'):return '#806000'
        return self.COLORS.get(value,value)

    def apply(self):
        def visit(widget):
            # Do not recolor maps, the horizon or their drawing items.
            if not isinstance(widget,ttk.Widget) and not isinstance(widget,tk.Canvas):
                for option in ('background','foreground','activebackground','activeforeground','highlightbackground','insertbackground','selectbackground'):
                    if option not in widget.keys():continue
                    value=widget.cget(option)
                    replacement=self.color(value,option)
                    if str(value).lower()!=replacement:
                        self.saved.setdefault((widget,option),value)
                        widget.configure(**{option:replacement})
            if isinstance(widget,ttk.Widget) and 'style' in widget.keys():
                name=widget.cget('style') or widget.winfo_class()
                for option in ('background','foreground','fieldbackground'):
                    value=self.style.lookup(name,option)
                    if not value:continue
                    replacement=self.color(value,option)
                    if str(value).lower()!=replacement:
                        self.style_saved.setdefault((name,option),value)
                        self.style.configure(name,**{option:replacement})
            motion=getattr(widget,'_motion',None)
            if motion:
                themed=isinstance(widget,ttk.Button)
                base=self.style.lookup(widget.cget('style'),'background') if themed else widget.cget('background')
                replacement=self.color(motion['base'],'background')
                if replacement!=motion['base']:
                    if motion['job']:self.root.after_cancel(motion['job']);motion['job']=None
                    motion['base']=motion['current']=replacement
            for child in widget.winfo_children():visit(child)
        visit(self.root)

    def toggle(self,save=True):
        self.light=not self.light
        if self.light:self.apply()
        else:
            for (widget,option),value in self.saved.items():
                if widget.winfo_exists():widget.configure(**{option:value})
            for (name,option),value in self.style_saved.items():self.style.configure(name,**{option:value})
            self.saved.clear();self.style_saved.clear()
            def reset(widget):
                motion=getattr(widget,'_motion',None)
                if motion:
                    if motion['job']:self.root.after_cancel(motion['job']);motion['job']=None
                    base=self.style.lookup(widget.cget('style'),'background') if isinstance(widget,ttk.Button) else widget.cget('background')
                    motion['base']=motion['current']=base
                for child in widget.winfo_children():reset(child)
            reset(self.root)
        self.button.configure(text='☾ Karanlık' if self.light else '☀ Aydınlık')
        if save:
            try:self.path.write_text(json.dumps({'theme':'light' if self.light else 'dark'}),encoding='utf-8')
            except OSError:pass

    def poll(self):
        if self.light:self.apply()
        self.job=self.root.after(250,self.poll)

    def close(self):
        self.root.after_cancel(self.job)
