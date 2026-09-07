"""Refined animated navigation for the synthetic desktop station."""
import time
import tkinter as tk
from tkinter import ttk
from enhanced import EnhancedStation
from branded import BLACK, SURFACE, YELLOW, WHITE, GRAY


class PremiumStation(EnhancedStation):
    def __init__(self,root):
        self.effects_ready=False
        self.active_page='Uçuş ekranı'
        self.motion=True
        self.slide_job=None
        self.pulse_job=None
        self.hover_jobs={}
        super().__init__(root)
        root.title('Fentek Havacılık • Yer İstasyonu')
        style=ttk.Style()
        style.configure('TButton',padding=(18,11),font=('Segoe UI',10,'bold'),borderwidth=0)
        style.configure('Dark.TButton',background='#25272b',foreground='#deddd7')
        style.map('Dark.TButton',background=[('active','#383a3e')],foreground=[('active','#ffffff')])
        nav=next(iter(self.nav_buttons.values())).master
        nav.configure(bg='#101113',width=224,padx=14)
        for widget in nav.winfo_children():
            if isinstance(widget,tk.Label): widget.configure(bg='#101113')
        # A restrained animated highlight lives above the navigation tabs.
        self.motion_strip=tk.Canvas(nav,height=22,bg='#101113',highlightthickness=0)
        self.motion_strip.pack(fill='x',before=next(iter(self.nav_buttons.values())),pady=(0,8))
        self.motion_strip.create_text(1,9,text='UÇUŞ ÇALIŞMA ALANI',anchor='w',fill='#888a90',font=('Segoe UI',8,'bold'))
        self.motion_strip.create_line(0,21,194,21,fill='#323027')
        self.shimmer=self.motion_strip.create_line(0,21,35,21,fill=YELLOW,width=2)
        symbols=['01','02','03','04','05','06']
        for index,(name,button) in enumerate(self.nav_buttons.items()):
            button.configure(text=f'{symbols[index]}   {name}',bg='#101113',fg='#a7a8ac',font=('Segoe UI',10,'bold'),padx=15,pady=16,activebackground='#25231a',activeforeground=YELLOW)
            button.bind('<Enter>',lambda e,n=name:self.hover(n,True))
            button.bind('<Leave>',lambda e,n=name:self.hover(n,False))
        self.indicator=tk.Frame(nav,bg=YELLOW,width=3,height=30)
        self.indicator.place(x=1,y=65)
        self.motion_var=tk.BooleanVar(value=True)
        style.configure('Motion.TCheckbutton',background='#101113',foreground='#a7a8ac',font=('Segoe UI',9))
        style.map('Motion.TCheckbutton',background=[('active','#101113')],foreground=[('active',WHITE)])
        ttk.Checkbutton(nav,text='Animasyonlar',variable=self.motion_var,command=self.set_motion,style='Motion.TCheckbutton').pack(fill='x',pady=(15,0))
        # Give all sections a quiet, consistent surface instead of heavy borders.
        self.refine(self.deck)
        self.effects_ready=True
        self.root.update_idletasks()
        self.select(self.active_page)
        self.pulse_start=time.monotonic()
        self.animate_strip()

    def refine(self,widget):
        for child in widget.winfo_children():
            if isinstance(child,tk.Frame) and child.cget('bg')==SURFACE:
                child.configure(bg='#181a1e')
                if int(child.cget('highlightthickness')):
                    child.configure(highlightbackground='#2b2d31')
                for label in child.winfo_children():
                    if isinstance(label,tk.Label): label.configure(bg='#181a1e')
            self.refine(child)

    def select(self,name):
        if not self.effects_ready:
            self.active_page=name
            return super().select(name)
        self.active_page=name
        if self.slide_job:
            self.root.after_cancel(self.slide_job)
            self.slide_job=None
        for job in self.hover_jobs.values(): self.root.after_cancel(job)
        self.hover_jobs.clear()
        for key,page in self.pages.items():
            page.pack_forget()
            self.nav_buttons[key].configure(bg='#292618' if key==name else '#101113',fg=YELLOW if key==name else '#a7a8ac')
        page=self.pages[name]
        page.pack(fill='both',expand=True,padx=(12,0) if self.motion else 0)
        self.root.update_idletasks()
        button=self.nav_buttons[name]
        target=button.winfo_y()+10
        current=self.indicator.winfo_y()
        start=time.monotonic()
        def frame():
            p=min(1,(time.monotonic()-start)/.20) if self.motion else 1
            eased=1-(1-p)**3
            self.indicator.place_configure(y=int(current+(target-current)*eased),height=max(24,button.winfo_height()-20))
            page.pack_configure(padx=(round(12*(1-eased)),0))
            if p<1:
                self.slide_job=self.root.after(16,frame)
            else: self.slide_job=None
        frame()

    def hover(self,name,entering):
        if name==self.active_page: return
        old=self.hover_jobs.pop(name,None)
        if old: self.root.after_cancel(old)
        button=self.nav_buttons[name]
        color=button.cget('bg')
        initial=tuple(int(color[i:i+2],16) for i in (1,3,5))
        final=(34,35,39) if entering else (16,17,19)
        start=time.monotonic()
        def frame():
            if name==self.active_page: return
            p=min(1,(time.monotonic()-start)/.12) if self.motion else 1
            rgb=tuple(round(a+(b-a)*p) for a,b in zip(initial,final))
            button.configure(bg='#%02x%02x%02x'%rgb,fg=WHITE if entering else '#a7a8ac')
            if p<1: self.hover_jobs[name]=self.root.after(20,frame)
            else: self.hover_jobs.pop(name,None)
        frame()

    def animate_strip(self):
        if self.motion:
            phase=((time.monotonic()-self.pulse_start)%5)/5
            width=max(100,self.motion_strip.winfo_width())
            x=phase*(width+35)-35
            self.motion_strip.coords(self.shimmer,max(0,x),21,min(width,x+35),21)
        self.pulse_job=self.root.after(100,self.animate_strip)

    def set_motion(self):
        self.motion=self.motion_var.get()
        self.motion_strip.itemconfigure(self.shimmer,state='normal' if self.motion else 'hidden')
        self.select(self.active_page)

    def close(self):
        for job in [self.slide_job,self.pulse_job,*self.hover_jobs.values()]:
            if job:
                try: self.root.after_cancel(job)
                except tk.TclError: pass
        super().close()


if __name__=='__main__':
    root=tk.Tk()
    PremiumStation(root)
    root.mainloop()
