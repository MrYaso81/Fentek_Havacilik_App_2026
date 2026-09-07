"""Radar intro followed by a cross dissolve."""
import math
import time
import tkinter as tk



class StartupIntro:
    def __init__(self,root,duration=3.4):
        self.root=root
        self.root.attributes('-alpha',0.0)
        self.duration=duration
        self.started=time.monotonic()
        self.job=None
        self.fading=False
        self.closed=False
        self.overlay=tk.Toplevel(root)
        self.overlay.withdraw()
        self.overlay.overrideredirect(True)
        self.overlay.transient(root)
        self.overlay.configure(bg='#080c12')
        self.overlay.attributes('-alpha',0.0)
        self.canvas=tk.Canvas(self.overlay,bg='#080c12',highlightthickness=0,cursor='hand2')
        self.canvas.pack(fill='both',expand=True)
        self.sync_geometry()
        self.configure_binding=root.bind('<Configure>',self.sync_geometry,add='+')
        self.overlay.deiconify()
        self.overlay.lift(root)
        self.canvas.bind('<Button-1>',lambda _:self.dissolve())
        self.canvas.bind('<Escape>',lambda _:self.dissolve())
        self.canvas.focus_set()
        self.frame()

    def frame(self):
        self.job=None
        elapsed=time.monotonic()-self.started
        entrance=min(1,elapsed/1.2)
        self.overlay.attributes('-alpha',entrance*entrance*(3-2*entrance))
        if elapsed>=self.duration:
            self.dissolve();return
        c=self.canvas
        w,h=max(600,c.winfo_width()),max(400,c.winfo_height())
        c.delete('all')
        x,y=w/2,h*.40
        radius=min(110,h*.17)
        for offset in range(-6,7):
            c.create_line(x+offset*45,0,x+offset*45,h,fill='#101b26')
            c.create_line(0,y+offset*45,w,y+offset*45,fill='#101b26')
        for fraction in (.35,.68,1):
            r=radius*fraction
            c.create_oval(x-r,y-r,x+r,y+r,outline='#35505b',width=1)
        angle=elapsed*2.8
        for i in range(14):
            a=angle-i*.025
            c.create_line(x,y,x+radius*math.cos(a),y-radius*math.sin(a),
                          fill='#'+f'{65+i*10:02x}{60+i*9:02x}20',width=2)
        c.create_polygon(x,y-28,x+25,y+23,x,y+12,x-25,y+23,fill='#ffd42a',outline='#fff1a0',width=2)
        c.create_text(x,y+radius+48,text='FENTEK HAVACILIK',fill='#ffd42a',font=('Segoe UI',26,'bold'))
        c.create_text(x,y+radius+85,text='İHA UÇUŞ MERKEZİ',fill='#dce6ef',font=('Segoe UI',12))
        c.create_text(x,h-68,text='SENTETİK DEMO  •  Donanım bağlı değil',fill='#899aa9',font=('Segoe UI',10))
        c.create_text(x,h-35,text='Geçmek için tıkla veya Esc',fill='#627583',font=('Segoe UI',9))
        self.job=self.root.after(25,self.frame)

    def sync_geometry(self,event=None):
        if self.closed or (event is not None and event.widget!=self.root):return
        self.overlay.geometry(f'{max(1,self.root.winfo_width())}x{max(1,self.root.winfo_height())}+{self.root.winfo_rootx()}+{self.root.winfo_rooty()}')

    def dissolve(self):
        if self.closed or self.fading:return
        self.fading=True
        if self.job:self.root.after_cancel(self.job)
        self.fade_started=time.monotonic()
        self.fade_alpha=float(self.overlay.attributes('-alpha'))
        # Reveal the prepared workspace only once the intro begins dissolving.
        self.root.attributes('-alpha',1.0)
        self.fade_frame()

    def fade_frame(self):
        self.job=None
        progress=min(1,(time.monotonic()-self.fade_started)/2.0)
        eased=progress*progress*(3-2*progress)
        self.overlay.attributes('-alpha',self.fade_alpha*(1-eased))
        if progress>=1:self.close()
        else:self.job=self.root.after(16,self.fade_frame)

    def close(self):
        if self.closed:return
        self.closed=True
        self.root.attributes('-alpha',1.0)
        if self.job:
            self.root.after_cancel(self.job)
            self.job=None
        self.root.unbind('<Configure>',self.configure_binding)
        if self.overlay.winfo_exists():self.overlay.destroy()

