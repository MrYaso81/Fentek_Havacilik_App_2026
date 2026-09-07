"""School-branded, tabbed synthetic ground station."""
import math
import queue
import time
from pathlib import Path
import tkinter as tk
from tkinter import ttk
import demo

BLACK, SURFACE, LINE = '#0c0d0f', '#17191c', '#303238'
YELLOW, WHITE, GRAY = '#ffd42a', '#f5f3e8', '#afb0b4'
demo.BG, demo.PANEL, demo.ACCENT, demo.TEXT, demo.MUTED = BLACK, SURFACE, YELLOW, WHITE, GRAY


class SchoolStation(demo.Demo):
    def __init__(self, root):
        self.root, self.t, self.running, self.link = root, 0., True, True
        self.last_tick = self.last_received = time.monotonic()
        self.flight_center=demo.CENTER
        self.data = demo.sample(0,self.flight_center)
        self.track, self.records, self.image = [], [], None
        self.google_pending = False
        self.results = queue.Queue()
        root.title('Fentek Havacılık • İHA Yer İstasyonu')
        root.geometry('1280x820')
        root.minsize(1060, 720)
        root.configure(bg=BLACK)
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TButton', background=YELLOW, foreground=BLACK, borderwidth=0, padding=(18,12), font=('Segoe UI',11,'bold'))
        style.map('TButton', background=[('active','#ffe77b'),('pressed','#cba700')], foreground=[('disabled','#686868')])
        style.configure('Dark.TButton', background='#2a2c30', foreground=WHITE)
        style.map('Dark.TButton', background=[('active','#42454a')])
        header = tk.Frame(root,bg=SURFACE,padx=18,pady=10)
        header.pack(fill='x')
        source = tk.PhotoImage(file=str(Path(__file__).with_name('okul_logo.png')))
        self.logo = source.subsample(max(1,source.width()//62))
        tk.Label(header,image=self.logo,bg=SURFACE).pack(side='left',padx=(0,12))
        brand=tk.Frame(header,bg=SURFACE)
        brand.pack(side='left')
        self.label(brand,'FENTEK HAVACILIK',19,YELLOW,True).pack(anchor='w')
        self.label(brand,'İHA TAKİP VE TELEMETRİ MERKEZİ',9,GRAY).pack(anchor='w',pady=4)
        tk.Label(header,text='SENTETİK DEMO\nDonanım bağlı değil',bg='#352f14',fg=YELLOW,font=('Segoe UI',10,'bold'),padx=18,pady=10).pack(side='right')
        self.label(header,'CUBE ORANGE  +  HERE3',10,WHITE,True).pack(side='right',padx=24)
        footer=tk.Frame(root,bg=SURFACE,padx=18,pady=12)
        footer.pack(side='bottom',fill='x')
        self.status=tk.StringVar(value='Sentetik uçuş başlatılıyor')
        tk.Label(footer,textvariable=self.status,bg=SURFACE,fg=YELLOW,font=('Segoe UI',10)).pack(side='left')
        shell=tk.Frame(root,bg=BLACK)
        shell.pack(fill='both',expand=True)
        nav=tk.Frame(shell,bg='#111214',width=210,padx=14,pady=20)
        nav.pack(side='left',fill='y')
        nav.pack_propagate(False)
        self.label(nav,'ÇALIŞMA ALANLARI',9,GRAY,True).pack(anchor='w',pady=(0,16))
        self.deck=tk.Frame(shell,bg=BLACK,padx=16,pady=16)
        self.deck.pack(side='left',fill='both',expand=True)
        self.pages,self.nav_buttons={},{}
        for name in ['Uçuş ekranı','Telemetri','Harita ayarları','Demo kontrolleri']:
            page=tk.Frame(self.deck,bg=BLACK)
            self.pages[name]=page
            button=tk.Button(nav,text=name,anchor='w',command=lambda n=name:self.select(n),bg='#111214',fg=WHITE,activebackground=YELLOW,activeforeground=BLACK,relief='flat',bd=0,padx=12,pady=15,font=('Segoe UI',11,'bold'),cursor='hand2')
            button.pack(fill='x',pady=4)
            self.nav_buttons[name]=button
        self.label(nav,'01 / İHA-01\n\nÇevrimdışı demo\nGerçek uçuş komutu yok',10,GRAY).pack(side='bottom',anchor='w',pady=12)
        self.values={k:tk.StringVar() for k in ('İrtifa / yerden','Yer hızı','Batarya','GPS / uydu','Enlem','Boylam')}
        live=self.pages['Uçuş ekranı']
        self.heading(live,'UÇUŞ EKRANI','Sentetik rota üzerinde anlık durum')
        metrics=tk.Frame(live,bg=BLACK)
        metrics.pack(fill='x',pady=(0,12))
        for i,k in enumerate(('İrtifa / yerden','Yer hızı','Batarya','GPS / uydu')):
            metrics.columnconfigure(i,weight=1,uniform='metric')
            self.metric(metrics,k).grid(row=0,column=i,sticky='ew',padx=(0,8))
        content=tk.Frame(live,bg=BLACK)
        content.pack(fill='both',expand=True)
        mapbox=tk.Frame(content,bg=SURFACE,padx=10,pady=10)
        mapbox.pack(side='left',fill='both',expand=True)
        self.layer=tk.StringVar(value='ŞEMATİK DEMO • UYDU GÖRÜNTÜSÜ DEĞİL')
        tk.Label(mapbox,textvariable=self.layer,bg=SURFACE,fg=YELLOW,font=('Segoe UI',8,'bold')).pack(anchor='w',pady=(0,8))
        self.canvas=tk.Canvas(mapbox,bg='#161917',highlightthickness=0,width=560,height=340)
        self.canvas.pack(fill='both',expand=True)
        self.canvas.bind('<Configure>',lambda e:self.draw_map())
        self.canvas.bind('<Double-Button-1>',self.google_link)
        side=tk.Frame(content,bg=BLACK,width=210)
        side.pack(side='right',fill='y',padx=(12,0))
        side.pack_propagate(False)
        self.horizon=tk.Canvas(side,height=160,bg=SURFACE,highlightthickness=0)
        self.horizon.pack(fill='x',pady=(0,10))
        for k in ('Enlem','Boylam'): self.metric(side,k).pack(fill='x',pady=4)
        ttk.Button(side,text='Kontroller →',command=lambda:self.select('Demo kontrolleri')).pack(fill='x',pady=12)
        telemetry=self.pages['Telemetri']
        self.heading(telemetry,'TELEMETRİ','Tüm değerler sentetiktir; bir cihazdan alınmaz.')
        grid=tk.Frame(telemetry,bg=BLACK)
        grid.pack(fill='x')
        for i,k in enumerate(self.values):
            grid.columnconfigure(i%2,weight=1)
            self.metric(grid,k,26).grid(row=i//2,column=i%2,sticky='ew',padx=6,pady=8)
        maps=self.pages['Harita ayarları']
        self.heading(maps,'HARİTA KATMANI','Demo zeminini veya Google uydu görüntüsünü seçin.')
        self.info(maps,'ÇEVRİMDIŞI DEMO','Anahtar ve internet gerektirmeden çalışır. Harita çizimi temsili, uçuş verileri sentetiktir.')
        ttk.Button(maps,text='Demo haritayı kullan',command=self.offline_map).pack(anchor='w',pady=14)
        self.info(maps,'GOOGLE UYDU GÖRÜNTÜSÜ','Google Maps Static API anahtarı ve etkin faturalandırma gerekir. Görüntü canlı uydu yayını değildir. Anahtar olmadan Google görüntüsü gösterilmez.')
        ttk.Button(maps,text='Google uydu görüntüsünü bağla',command=self.google_dialog).pack(anchor='w',pady=14)
        self.map_status=tk.StringVar(value='Çevrimdışı demo harita etkin.')
        tk.Label(maps,textvariable=self.map_status,bg=BLACK,fg=YELLOW,wraplength=740,justify='left',font=('Segoe UI',11)).pack(anchor='w',pady=10)
        control=self.pages['Demo kontrolleri']
        self.heading(control,'DEMO KONTROLLERİ','Gerçek uçuş komutları gönderilmez.')
        self.info(control,'UÇUŞ OYNATIMI','Simülasyonu duraklatın veya başlangıç konumuna dönün.')
        buttons=tk.Frame(control,bg=BLACK)
        buttons.pack(fill='x',pady=14)
        self.pause_button=ttk.Button(buttons,text='Duraklat',command=self.pause)
        self.pause_button.pack(side='left',padx=(0,12))
        ttk.Button(buttons,text='Baştan başlat',command=self.reset,style='Dark.TButton').pack(side='left')
        self.info(control,'BAĞLANTI SENARYOSU','Bağlantı kaybında son konum sabit kalır. Alt çubukta verinin yaşı artar.')
        self.link_button=ttk.Button(control,text='Bağlantı kaybını dene',command=self.toggle_link)
        self.link_button.pack(anchor='w',pady=14)
        ttk.Button(control,text='Sentetik uçuş verisini kaydet (CSV)',command=self.export,style='Dark.TButton').pack(anchor='w',pady=12)
        self.select('Uçuş ekranı')
        self.update_display()
        self.job=root.after(100,self.tick)
        root.protocol('WM_DELETE_WINDOW',self.close)

    def heading(self,parent,title,subtitle):
        self.label(parent,title,20,WHITE,True).pack(anchor='w')
        self.label(parent,subtitle,10,GRAY).pack(anchor='w',pady=(5,18))

    def metric(self,parent,key,size=19):
        panel=tk.Frame(parent,bg=SURFACE,padx=14,pady=10,highlightthickness=1,highlightbackground=LINE)
        self.label(panel,key.upper(),9,GRAY).pack(anchor='w')
        tk.Label(panel,textvariable=self.values[key],bg=SURFACE,fg=YELLOW,font=('Segoe UI',size,'bold')).pack(anchor='w',pady=(5,0))
        return panel

    def info(self,parent,title,body):
        box=tk.Frame(parent,bg=SURFACE,padx=18,pady=16)
        box.pack(fill='x',pady=5)
        self.label(box,title,11,YELLOW,True).pack(anchor='w')
        tk.Label(box,text=body,bg=SURFACE,fg=GRAY,wraplength=700,justify='left',font=('Segoe UI',11)).pack(anchor='w',pady=(8,0))

    def select(self,name):
        for key,page in self.pages.items():
            page.pack_forget()
            self.nav_buttons[key].configure(bg=YELLOW if key==name else '#111214',fg=BLACK if key==name else WHITE)
        self.pages[name].pack(fill='both',expand=True)

    def update_display(self):
        super().update_display()
        # Compact horizon in the sidebar, consistent with the black/yellow palette.
        c=self.horizon
        c.delete('all')
        w=max(190,c.winfo_width())
        tilt=math.tan(math.radians(self.data['roll']))*w/2
        c.create_rectangle(0,0,w,160,fill='#24282a',outline='')
        c.create_polygon(0,80-tilt,w,80+tilt,w,160,0,160,fill='#3b331d',outline='')
        c.create_line(0,80-tilt,w,80+tilt,fill=YELLOW,width=2)
        c.create_line(w/2-32,80,w/2-8,80,w/2,88,w/2+8,80,w/2+32,80,fill=WHITE,width=3)
        c.create_text(w/2,22,text=f"YÖN {self.data['heading']:03.0f}°",fill=YELLOW,font=('Segoe UI',13,'bold'))
        c.create_text(w/2,140,text='SENTETİK YÖNELİM',fill=GRAY,font=('Segoe UI',8))


if __name__=='__main__':
    root=tk.Tk()
    SchoolStation(root)
    root.mainloop()
