"""Synthetic calibration/motor workbench. No transport or hardware commands."""
import json
import math
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from premium import PremiumStation
from branded import BLACK, SURFACE, YELLOW, WHITE, GRAY


class Workbench(PremiumStation):
    def __init__(self,root):
        self.motor_job=None
        self.cal_job=None
        self.motor_active=False
        self.cal_step=None
        self.settings={'DEMO_TEST_PERCENT':20.,'DEMO_TEST_SECONDS':3.,'DEMO_LOW_BATTERY_PERCENT':25.}
        super().__init__(root)
        nav=next(iter(self.nav_buttons.values())).master
        name='Kurulum ve test'
        page=tk.Frame(self.deck,bg=BLACK)
        self.pages[name]=page
        button=tk.Button(nav,text='07   Kurulum ve test',anchor='w',command=lambda:self.select(name),bg='#101113',fg=GRAY,activebackground='#25231a',activeforeground=YELLOW,relief='flat',bd=0,padx=15,pady=10,font=('Segoe UI',10,'bold'),cursor='hand2')
        button.pack(fill='x',pady=4)
        button.bind('<Enter>',lambda e:self.hover(name,True))
        button.bind('<Leave>',lambda e:self.hover(name,False))
        self.nav_buttons[name]=button
        for b in self.nav_buttons.values(): b.configure(pady=10)
        self.heading(page,'KURULUM VE TEST','Yalnızca simülasyon • Motora veya karta komut gönderilmez')
        style=ttk.Style()
        style.configure('TNotebook',background=BLACK,borderwidth=0)
        style.configure('TNotebook.Tab',background=SURFACE,foreground=WHITE,padding=(18,12),font=('Segoe UI',10,'bold'))
        style.map('TNotebook.Tab',background=[('selected',YELLOW)],foreground=[('selected',BLACK)])
        tabs=ttk.Notebook(page)
        tabs.pack(fill='both',expand=True)
        self.test_tabs=tabs
        calibration,motors,parameters=[tk.Frame(tabs,bg=BLACK,padx=14,pady=14) for _ in range(3)]
        for frame,title in [(calibration,'Kalibrasyon'),(motors,'Motor testi'),(parameters,'Parametreler')]: tabs.add(frame,text=title)
        self.build_calibration(calibration)
        self.build_motors(motors)
        self.build_parameters(parameters)
        self.event('Kurulum laboratuvarı hazır: kalibrasyon ve motor testleri yalnız sentetik.')

    def build_calibration(self,parent):
        self.info(parent,'İVMEÖLÇER / 6 YÖN','Mission Planner’daki adım akışını örnekleyen demo. Gerçek sensör ölçülmez veya kalibrasyon kaydedilmez.')
        self.cal_status=tk.StringVar(value='Hazır • Bir demo kalibrasyonu seçin.')
        tk.Label(parent,textvariable=self.cal_status,bg=BLACK,fg=YELLOW,wraplength=690,font=('Segoe UI',14,'bold'),justify='left').pack(anchor='w',pady=18)
        self.cal_progress=ttk.Progressbar(parent,maximum=6)
        self.cal_progress.pack(fill='x',pady=12)
        row=tk.Frame(parent,bg=BLACK)
        row.pack(fill='x',pady=8)
        ttk.Button(row,text='6 yön demosunu başlat',command=self.begin_cal).pack(side='left')
        self.cal_next=ttk.Button(row,text='Yönü onayla →',command=self.next_cal,state='disabled')
        self.cal_next.pack(side='left',padx=10)
        ttk.Button(row,text='İptal',command=self.cancel_cal,style='Dark.TButton').pack(side='left')
        ttk.Button(parent,text='Jiroskop demo kontrolü',command=self.gyro_demo,style='Dark.TButton').pack(anchor='w',pady=18)
        self.label(parent,'Demo sonucu gerçek uçuşa uygunluk veya sensör doğruluğu göstermez.',10,GRAY).pack(anchor='w')

    def begin_cal(self):
        self.cancel_cal(log=False)
        self.cal_step=0
        self.cal_progress['value']=0
        self.cal_next['state']='normal'
        self.cal_status.set('1 / 6 — Düz konum • Demo yönünü onaylayın.')
        self.event('İvmeölçer demo adımları başlatıldı.')

    def next_cal(self):
        if self.cal_step is None:return
        self.cal_step+=1
        self.cal_progress['value']=self.cal_step
        directions=['Düz','Sol yan','Sağ yan','Burun aşağı','Burun yukarı','Sırt üstü']
        if self.cal_step==6:
            self.cal_status.set('Demo adımları tamamlandı • Gerçek kalibrasyon yapılmadı.')
            self.cal_next['state']='disabled'
            self.cal_step=None
            self.event('6 yön kalibrasyon demosu tamamlandı; karta yazılmadı.')
        else:self.cal_status.set(f'{self.cal_step+1} / 6 — {directions[self.cal_step]} • Demo yönünü onaylayın.')

    def cancel_cal(self,log=True):
        if self.cal_job:self.root.after_cancel(self.cal_job)
        self.cal_job=None
        self.cal_step=None
        self.cal_next['state']='disabled'
        self.cal_progress['value']=0
        self.cal_status.set('Demo kalibrasyonu durduruldu.')
        if log:self.event('Demo kalibrasyonu iptal edildi.')

    def gyro_demo(self):
        self.cancel_cal(log=False)
        self.cal_status.set('Sentetik jiroskop örnekleri inceleniyor…')
        def finish():
            self.cal_job=None
            self.cal_progress['value']=6
            self.cal_status.set('Jiroskop demosu tamamlandı • Gerçek sensör ölçülmedi.')
            self.event('Jiroskop demo kontrolü tamamlandı.')
        self.cal_job=self.root.after(1800,finish)

    def build_motors(self,parent):
        self.info(parent,'ÇİFT MOTORLU DEMO DÜZENİ','Sol/sağ etiketleri temsili. Gerçek motor numarası ve çıkış eşlemesi tanımlı değil. Yüzde, test gaz komutudur; ölçülmüş güç değildir.')
        self.motor_canvas=tk.Canvas(parent,bg=SURFACE,height=155,highlightthickness=0)
        self.motor_canvas.pack(fill='x',pady=10)
        row=tk.Frame(parent,bg=BLACK)
        row.pack(fill='x',pady=8)
        self.motor_choice=ttk.Combobox(row,values=['Sol motor','Sağ motor'],state='readonly',width=14)
        self.motor_choice.set('Sol motor')
        self.motor_choice.pack(side='left',padx=(0,10))
        self.label(row,'Gaz %',10,WHITE).pack(side='left')
        self.percent=tk.StringVar(value='20')
        ttk.Spinbox(row,from_=0,to=100,textvariable=self.percent,width=6).pack(side='left',padx=8)
        self.label(row,'Süre (sn)',10,WHITE).pack(side='left')
        self.seconds=tk.StringVar(value='3')
        ttk.Spinbox(row,from_=1,to=10,textvariable=self.seconds,width=6).pack(side='left',padx=8)
        buttons=tk.Frame(parent,bg=BLACK)
        buttons.pack(fill='x',pady=10)
        self.motor_start=ttk.Button(buttons,text='Demo testini başlat',command=self.start_motor)
        self.motor_start.pack(side='left')
        ttk.Button(buttons,text='TESTİ DURDUR',command=self.stop_motor,style='Dark.TButton').pack(side='left',padx=12)
        self.motor_status=tk.StringVar(value='Hazır • Gerçek motor bağlı değil.')
        tk.Label(parent,textvariable=self.motor_status,bg=BLACK,fg=YELLOW,font=('Segoe UI',11,'bold')).pack(anchor='w',pady=8)
        self.motor_canvas.bind('<Configure>',lambda e:self.draw_motors(0))

    @staticmethod
    def valid_test(percent,seconds):
        p,s=float(percent),float(seconds)
        if not(math.isfinite(p) and math.isfinite(s) and 0<=p<=100 and 1<=s<=10):
            raise ValueError('Gaz %0–100, süre 1–10 saniye olmalı.')
        return p,s

    def start_motor(self):
        if self.motor_active:return
        try:p,s=self.valid_test(self.percent.get(),self.seconds.get())
        except ValueError:
            messagebox.showerror('Test değerleri','Gaz %0–100, süre 1–10 saniye olmalı.');return
        if not self.link:
            self.motor_status.set('Önce demo bağlantısını geri getirin.');return
        self.motor_active=True
        self.motor_start['state']='disabled'
        self.motor_target=self.motor_choice.get()
        self.motor_percent=p
        start=time.monotonic()
        self.event(f'{self.motor_target} demo testi: %{p:g} gaz, {s:g} sn.')
        def frame():
            elapsed=time.monotonic()-start
            if not self.link or elapsed>=s:
                self.stop_motor('Süre doldu' if self.link else 'Demo bağlantısı kesildi');return
            self.motor_status.set(f'{self.motor_target} • %{p:g} gaz (sentetik) • {s-elapsed:.1f} sn kaldı')
            self.draw_motors(elapsed*p*25)
            self.motor_job=self.root.after(50,frame)
        frame()

    def draw_motors(self,angle):
        c=self.motor_canvas
        c.delete('all')
        w=max(400,c.winfo_width())
        c.create_line(w*.22,70,w*.78,70,fill='#46484d',width=12)
        c.create_polygon(w/2,20,w/2-20,120,w/2+20,120,fill='#636367')
        for index,label in enumerate(['Sol motor','Sağ motor']):
            x=w*(.25 if index==0 else .75)
            active=self.motor_active and self.motor_target==label
            color=YELLOW if active else GRAY
            c.create_oval(x-32,38,x+32,102,outline=color,width=2)
            a=math.radians(angle if active else 0)
            dx,dy=28*math.cos(a),28*math.sin(a)
            c.create_line(x-dx,70-dy,x+dx,70+dy,fill=color,width=7)
            c.create_text(x,130,text=label+(' • TEST' if active else ' • DURUYOR'),fill=color,font=('Segoe UI',10,'bold'))

    def stop_motor(self,reason='Kullanıcı durdurdu'):
        if self.motor_job:self.root.after_cancel(self.motor_job)
        self.motor_job=None
        was_active=self.motor_active
        self.motor_active=False
        self.motor_start['state']='normal'
        self.motor_status.set(f'{reason} • Demo motor çıkışı %0.')
        self.draw_motors(0)
        if was_active:self.event('Motor demosu sonlandı: '+reason)

    def build_parameters(self,parent):
        self.info(parent,'DEMO PARAMETRELERİ','Bu liste uygulamaya aittir; ArduPilot parametre dökümü değildir. Karttan değer okunmaz veya karta yazılmaz.')
        self.param_vars={}
        labels={'DEMO_TEST_PERCENT':'Varsayılan test gazı (%)','DEMO_TEST_SECONDS':'Varsayılan test süresi (sn)','DEMO_LOW_BATTERY_PERCENT':'Demo düşük batarya eşiği (%)'}
        for key,value in self.settings.items():
            row=tk.Frame(parent,bg=SURFACE,padx=14,pady=12)
            row.pack(fill='x',pady=5)
            self.label(row,labels[key],11,WHITE).pack(side='left')
            var=tk.StringVar(value=str(value))
            self.param_vars[key]=var
            ttk.Entry(row,textvariable=var,width=10).pack(side='right')
        row=tk.Frame(parent,bg=BLACK)
        row.pack(fill='x',pady=16)
        ttk.Button(row,text='Demoya uygula',command=self.apply_params).pack(side='left')
        ttk.Button(row,text='JSON olarak kaydet',command=self.save_params,style='Dark.TButton').pack(side='left',padx=10)
        self.param_status=tk.StringVar(value='Değişiklikler yalnız bu demo oturumuna uygulanır.')
        tk.Label(parent,textvariable=self.param_status,bg=BLACK,fg=YELLOW,wraplength=680,font=('Segoe UI',10)).pack(anchor='w')

    def apply_params(self):
        try:
            values={k:float(v.get()) for k,v in self.param_vars.items()}
            self.valid_test(values['DEMO_TEST_PERCENT'],values['DEMO_TEST_SECONDS'])
            b=values['DEMO_LOW_BATTERY_PERCENT']
            if not math.isfinite(b) or not 0<=b<=100:raise ValueError()
        except ValueError:
            self.param_status.set('Değerler geçersiz. Gaz/eşik %0–100; süre 1–10 sn olmalı.');return False
        self.settings=values
        self.percent.set(f"{values['DEMO_TEST_PERCENT']:g}")
        self.seconds.set(f"{values['DEMO_TEST_SECONDS']:g}")
        low=self.data['battery']<=values['DEMO_LOW_BATTERY_PERCENT']
        self.param_status.set('Demoya uygulandı • Batarya: '+('eşik altında' if low else 'eşik üstünde'))
        self.event('Demo test parametreleri güncellendi; karta yazılmadı.')
        return True

    def save_params(self):
        if not self.apply_params():return
        path=filedialog.asksaveasfilename(defaultextension='.json',initialfile='demo_parametreleri.json')
        if path:
            try:
                with open(path,'w',encoding='utf-8') as f:json.dump({'mode':'SYNTHETIC_DEMO','parameters':self.settings},f,indent=2)
                self.param_status.set('Demo parametre dosyası kaydedildi.')
            except OSError:self.param_status.set('Dosya kaydedilemedi.')

    def close(self):
        for job in (self.motor_job,self.cal_job):
            if job:self.root.after_cancel(job)
        super().close()


if __name__=='__main__':
    root=tk.Tk()
    Workbench(root)
    root.mainloop()
