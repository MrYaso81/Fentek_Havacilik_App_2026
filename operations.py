"""Scrollable operational pages. Unknown hardware values are never simulated."""
import json
import math
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from atlas import parse_parameters
from mission_transfer import validate_points
from parameter_store import checked_value,validate_safety_parameter
from guide_catalog import TOPICS,parameter_help
from flight_tools import haversine_m,route_metrics,polygon_area_m2,radio_assessment,failsafe_preview
from rally_transfer import validate_rally_points
from hardware_acceptance import evaluate_acceptance,acceptance_result,PARAMETERS as ACCEPTANCE_PARAMETERS
from parameter_metadata import metadata_for,validate_metadata
from sitl_acceptance import run_sitl,format_report

BG='#0c0d0f';PANEL='#191c20';GOLD='#ffd42a';WHITE='#eceef1'

class Operations:
    def __init__(self,app):
        self.app=app;self.params={};self.pending={};self.indices=set();self.count=0;self.mode_names=()
        self.last_result='Donanım bağlı değil • Değerler bekleniyor';self.telemetry_vars={};self.job=None
        self.guide_return_page='Uçuş ekranı';self.rally_points=[];self.direct_enabled=False;self.direct_job=None
        self.acceptance_active=False;self.acceptance_stable_since=None;self.acceptance_last=[];self.acceptance_final='BAŞLATILMADI'
        self.param_history=[];self.param_write_context=None
        self.pages={}
        for name in ('Uçuş modu özellikleri','Doğrudan kontrol','Görev planlama','Ölçüm araçları','Rally / Güvenli iniş','Parametreler','Güvenlik','ArduPilot SITL Testi','Kablosuz Telemetri','Yardımcı donanım','Bilgi ve Kılavuz'):
            self.pages[name]=self.page(name)
        self.sitl_results=queue.Queue();self.sitl_running=False;self.sitl_last=''
        self.build_modes();self.build_direct_control();self.build_route();self.build_measurements();self.build_rally();self.build_params();self.build_safety();self.build_sitl();self.build_radio();self.build_hardware()
        self.build_telemetry();self.build_guide()
        self.make_navigation_scrollable()
        self.app.root.bind_all('<MouseWheel>',self.wheel,add='+')
        self.refresh()

    def page(self,name):
        if name in self.app.pages:
            outer=self.app.pages[name]
            for child in outer.winfo_children():child.destroy()
        else:
            outer=tk.Frame(self.app.deck,bg=BG);self.app.pages[name]=outer
            nav=next(iter(self.app.nav_buttons.values())).master
            b=tk.Button(nav,text=f'{len(self.app.nav_buttons)+1:02}   {name}',anchor='w',bg=BG,fg=WHITE,
                        activebackground=PANEL,activeforeground=GOLD,relief='flat',font=('Segoe UI',10,'bold'),
                        padx=12,pady=9,command=lambda n=name:self.app.select(n))
            b.pack(fill='x',pady=3);self.app.nav_buttons[name]=b
        canvas=tk.Canvas(outer,bg=BG,highlightthickness=0)
        scrollbar=ttk.Scrollbar(outer,command=canvas.yview);scrollbar.pack(side='right',fill='y')
        canvas.pack(side='left',fill='both',expand=True);canvas.configure(yscrollcommand=scrollbar.set)
        body=tk.Frame(canvas,bg=BG,padx=18,pady=16);item=canvas.create_window(0,0,anchor='nw',window=body)
        body.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(item,width=e.width))
        outer._scroll_canvas=canvas
        self.label(body,name.upper(),17,GOLD)
        return body

    def make_navigation_scrollable(self):
        old_nav=next(iter(self.app.nav_buttons.values())).master
        host=old_nav.master;info=old_nav.pack_info();old_nav.pack_forget()
        canvas=tk.Canvas(host,bg='#101113',width=235,highlightthickness=0)
        canvas.pack(side=info.get('side','left'),fill='y',before=self.app.deck)
        scroll=ttk.Scrollbar(host,command=canvas.yview)
        scroll.pack(side='left',fill='y',before=self.app.deck)
        canvas.configure(yscrollcommand=scroll.set)
        nav=tk.Frame(canvas,bg='#101113',padx=12,pady=15)
        item=canvas.create_window(0,0,window=nav,anchor='nw',width=235)
        tk.Label(nav,text='ÇALIŞMA ALANLARI',bg='#101113',fg='#8f939a',font=('Segoe UI',9,'bold'),anchor='w').pack(fill='x',pady=(0,9))
        tk.Frame(nav,bg=GOLD,height=2).pack(fill='x',pady=(0,8))
        buttons={}
        for index,name in enumerate(self.app.pages,1):
            button=tk.Button(nav,text=f'{index:02}   {name}',anchor='w',command=lambda n=name:self.app.select(n),
                             bg='#101113',fg='#a7a8ac',activebackground='#25231a',activeforeground=GOLD,
                             relief='flat',bd=0,padx=12,pady=9,font=('Segoe UI',9,'bold'),cursor='hand2')
            button.pack(fill='x',pady=2)
            button.bind('<Enter>',lambda e,n=name:self.app.hover(n,True),add='+')
            button.bind('<Leave>',lambda e,n=name:self.app.hover(n,False),add='+')
            buttons[name]=button
        tk.Label(nav,text='İHA-01\nDemo / canlı Cube çalışma alanı',bg='#101113',fg='#8f939a',
                 font=('Segoe UI',9),anchor='w',justify='left').pack(fill='x',pady=(14,4))
        self.app.nav_buttons=buttons
        self.app.indicator=tk.Frame(nav,bg=GOLD,width=3,height=24)
        nav.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')),add='+')
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(item,width=e.width),add='+')
        nav._scroll_canvas=canvas
        self.nav_canvas=canvas
        self.app.root.update_idletasks()
        self.app.select(getattr(self.app,'active_page','Uçuş ekranı'))

    def wheel(self,event):
        widget=event.widget
        if isinstance(widget,(ttk.Treeview,tk.Text,ttk.Combobox)):return
        while widget:
            if hasattr(widget,'_scroll_canvas'):
                widget._scroll_canvas.yview_scroll(-int(event.delta/120) or (-1 if event.delta>0 else 1),'units');return
            widget=getattr(widget,'master',None)

    def label(self,parent,text,size=10,color=WHITE):
        label=tk.Label(parent,text=text,bg=parent.cget('bg'),fg=color,font=('Segoe UI',size),anchor='w',justify='left',wraplength=850)
        label.pack(fill='x',pady=5);return label

    def row(self,parent):
        row=tk.Frame(parent,bg=parent.cget('bg'));row.pack(fill='x',pady=6);return row

    def button(self,parent,text,command):
        b=tk.Button(parent,text=text,command=command,bg='#30343a',fg=WHITE,activebackground=GOLD,activeforeground=BG,
                    font=('Segoe UI',9,'bold'),relief='flat',padx=12,pady=8,cursor='hand2');b.pack(side='left',padx=(0,7));return b

    def entry(self,parent,value='',width=18):
        var=tk.StringVar(value=value);ttk.Entry(parent,textvariable=var,width=width).pack(side='left',padx=5);return var

    def live(self):
        live=self.app.live_map
        return live.enabled and not live.stop.is_set() and time.monotonic()-live.state.heartbeat_time<3 and getattr(live,'session',None) and live.session.link

    def send(self,action):
        if not self.live():messagebox.showinfo('Bağlantı','Önce güncel Cube bağlantısı kurun.',parent=self.app.root);return False
        self.app.live_map.session.commands.put(action);return True

    def build_modes(self):
        p=self.pages['Uçuş modu özellikleri']
        self.label(p,'Bağlantı yokken seçilen İHA türünün temel modları gösterilir. Cube bağlanınca liste kartın gerçekten desteklediği modlarla değiştirilir.')
        row=self.row(p);self.mode=tk.StringVar();self.mode_box=ttk.Combobox(row,textvariable=self.mode,state='readonly',width=22);self.mode_box.pack(side='left',padx=5)
        self.button(row,'Modu uygula',self.apply_mode)
        self.mode_status=self.label(p,'Kart modu: bekleniyor',13,GOLD)
        for title,detail in [('STABILIZE','Pilot kumandasıyla denge desteği.'),('ALT_HOLD / LOITER','İrtifa veya konum tutma; araç türü ve sensör desteğine bağlı.'),('AUTO / GUIDED','Yüklü görev veya haricî hedef denetimi.'),('RTL / LAND','Eve dönüş veya iniş; kart ayarlarına göre uygulanır.'),('MANUAL / FBWA','Sabit kanada özgü pilot kontrol seçenekleri.')]:self.label(p,title+' — '+detail)
        self.label(p,'Kumanda anahtarı atamaları: Parametreler bölümünde FLTMODE araması. Araç türü seçimi gerçek kartı yeniden yapılandırmaz.')
        row=self.row(p);self.button(row,'Kumanda mod parametreleri',lambda:self.filter_group('FLTMODE'))
        self.offline_modes(getattr(self.app,'aircraft_type','Döner kanat'))

    def offline_modes(self,aircraft_type):
        choices={
            'Döner kanat':('STABILIZE','ALT_HOLD','LOITER','POSHOLD','BRAKE','GUIDED','AUTO','RTL','LAND'),
            'Sabit kanat':('MANUAL','STABILIZE','FBWA','FBWB','CRUISE','LOITER','GUIDED','AUTO','RTL','TAKEOFF'),
            'FPV':('ACRO','STABILIZE','ALT_HOLD','LOITER','POSHOLD','RTL','LAND'),
        }
        self.modes(choices.get(aircraft_type,choices['Döner kanat']))

    def apply_mode(self):
        if not self.live():self.send(('mode',self.mode.get()));return
        mode=self.mode.get()
        if mode not in self.mode_names:return
        safety=self.app.live_map.safety;action=safety.action_for_mode(mode)
        if action!='basic_mode' and not safety.allow(action):
            messagebox.showwarning('Mod engellendi',safety.summary(action=action));return
        if messagebox.askyesno('Uçuş modu',f'{mode} modu karta gönderilsin mi? Araç davranışı değişebilir.',parent=self.app.root):self.send(('mode',mode))

    def build_direct_control(self):
        p=self.pages['Doğrudan kontrol']
        self.label(p,'TEK İHA • BASILI TUTARAK MAVLINK MANUAL_CONTROL',13,GOLD)
        self.label(p,'Bu ekran yalnız bağlı ve ARMED ArduPilot araca yön komutu gönderir. Gaz ekseni gönderilmez; fiziksel RC kumanda ana kontrol ve geri alma yolu olarak hazır tutulmalıdır.')
        self.direct_status=self.label(p,'KİLİTLİ • Canlı bağlantı ve ARMED durumu bekleniyor.',12,GOLD)
        row=self.row(p);self.button(row,'Uyumluluk parametrelerini oku',self.read_direct_params);self.button(row,'Kontrol kilidini aç',self.enable_direct);self.button(row,'ACİL BIRAK / KİLİTLE',self.disable_direct)
        row=self.row(p);self.label(row,'Komut şiddeti');self.direct_strength=tk.StringVar(value='250');box=ttk.Combobox(row,textvariable=self.direct_strength,values=('150','250','400'),state='readonly',width=8);box.pack(side='left',padx=8)
        self.label(p,'Düğmeye basılı tutulduğu sürece yaklaşık 7 Hz komut gönderilir. Fare bırakılınca bütün eksenler geçersiz/serbest durumuna alınır.')
        grid=tk.Frame(p,bg=BG);grid.pack(anchor='w',pady=12)
        specs=[('İLERİ',0,1,(1,0,0)),('SOLA',1,0,(0,-1,0)),('SAĞA',1,2,(0,1,0)),('GERİ',2,1,(-1,0,0)),('SOLA DÖN',3,0,(0,0,-1)),('SAĞA DÖN',3,2,(0,0,1))]
        self.direct_buttons=[]
        for title,row,column,axes in specs:
            b=tk.Button(grid,text=title,width=15,bg='#30343a',fg=WHITE,activebackground=GOLD,activeforeground=BG,font=('Segoe UI',10,'bold'),relief='flat',padx=8,pady=14,cursor='hand2')
            b.grid(row=row,column=column,padx=5,pady=5)
            b.bind('<ButtonPress-1>',lambda e,a=axes:self.start_direct(a));b.bind('<ButtonRelease-1>',lambda e:self.stop_direct())
            self.direct_buttons.append(b)
        self.label(p,'Destek ve eksen yorumu bağlı araç/firmware moduna göre değişebilir. Kontrol kilidi bağlantı kaybında veya DISARM durumunda otomatik kapanır.',9,'#aeb2b9')

    def enable_direct(self):
        st=self.app.live_map.state
        if not self.live() or st.armed is not True:
            messagebox.showwarning('Doğrudan kontrol','Önce güncel Cube bağlantısı kurulmalı ve kart ARMED durumunu bildirmelidir.',parent=self.app.root);return
        options=self.params.get('MAV_OPTIONS')
        gcs=self.params.get('MAV_GCS_SYSID') or self.params.get('SYSID_MYGCS')
        if not options or int(options[0])&1!=1 or not gcs or int(gcs[0])!=255:
            messagebox.showwarning('Doğrudan kontrol','Önce uyumluluk parametrelerini okuyun. MAV_OPTIONS bit 0 açık ve GCS sistem kimliği 255 olmalıdır.',parent=self.app.root);return
        if not messagebox.askyesno('Doğrudan kontrol kilidi','Tek İHA’ya MANUAL_CONTROL yön komutları gönderilecek. Fiziksel RC kumanda hazır mı ve alan güvenli mi?',parent=self.app.root):return
        self.direct_enabled=True;self.direct_status.configure(text='HAZIR • Bir yön düğmesine basılı tutun.',fg='#7cdbac')

    def read_direct_params(self):
        if self.send(('param_read',('MAV_OPTIONS','MAV_GCS_SYSID','SYSID_MYGCS'))):self.direct_status.configure(text='Uyumluluk parametreleri karttan isteniyor…',fg=GOLD)

    def start_direct(self,axes):
        if not self.direct_enabled:return
        if not self.live() or self.app.live_map.state.armed is not True:self.stop_direct();return
        strength=int(self.direct_strength.get());self.direct_axes=tuple(v*strength for v in axes)
        self.send_direct_frame()

    def send_direct_frame(self):
        if not self.direct_enabled or not getattr(self,'direct_axes',None):return
        x,y,r=self.direct_axes
        if not self.live() or self.app.live_map.state.armed is not True:self.stop_direct();return
        self.app.live_map.session.commands.put(('manual_control',x,y,32767,r))
        self.direct_status.configure(text=f'CANLI KOMUT • X {x:+d}  Y {y:+d}  R {r:+d}',fg='#ffcc4d')
        self.direct_job=self.app.root.after(140,self.send_direct_frame)

    def stop_direct(self):
        if self.direct_job:
            try:self.app.root.after_cancel(self.direct_job)
            except tk.TclError:pass
        self.direct_job=None;self.direct_axes=None
        if self.live() and self.app.live_map.state.armed is True:
            self.app.live_map.session.commands.put(('manual_control',32767,32767,32767,32767))
        if hasattr(self,'direct_status'):
            self.direct_status.configure(text='HAZIR • Komut kesildi.' if self.direct_enabled else 'KİLİTLİ • Canlı bağlantı ve ARMED durumu bekleniyor.',fg=GOLD)

    def disable_direct(self):
        self.direct_enabled=False;self.stop_direct()

    def build_route(self):
        p=self.pages['Görev planlama'];self.label(p,'Haritadaki rota ile ortak liste • İrtifa HOME üstü metre • Son komut RTL')
        route_box=ttk.Frame(p);route_box.pack(fill='x',pady=10)
        self.route=ttk.Treeview(route_box,columns=('lat','lon','alt'),show='headings',height=8)
        for name,title in [('lat','Enlem'),('lon','Boylam'),('alt','İrtifa (m)')]:self.route.heading(name,text=title);self.route.column(name,width=170,stretch=True)
        route_scroll=ttk.Scrollbar(route_box,orient='vertical',command=self.route.yview)
        self.route.configure(yscrollcommand=route_scroll.set)
        self.route.pack(side='left',fill='x',expand=True);route_scroll.pack(side='right',fill='y')
        row=self.row(p);self.lat=self.entry(row,'41.0');self.lon=self.entry(row,'29.0');self.alt=self.entry(row,'50')
        self.route.bind('<<TreeviewSelect>>',self.select_point)
        row=self.row(p)
        self.button(row,'Nokta ekle',lambda:self.edit_point(False));self.button(row,'Seçiliyi güncelle',lambda:self.edit_point(True));self.button(row,'Seçiliyi sil',self.delete_point)
        self.button(row,'↑',lambda:self.move_point(-1));self.button(row,'↓',lambda:self.move_point(1))
        row=self.row(p);self.button(row,'Rotayı kaydet',lambda:self.route_file(False));self.button(row,'Rota aç',lambda:self.route_file(True));self.button(row,'Haritada göster',lambda:self.app.select('Uçuş ekranı'))
        row=self.row(p)
        from mission_dialog import open_mission
        self.button(row,'Gözden geçir ve karta yükle',lambda:open_mission(self.app))
        row=self.row(p);self.button(row,'Karttaki görevi başlat',self.start_mission);self.button(row,'Duraklat',lambda:self.mission_pause(True));self.button(row,'Devam et',lambda:self.mission_pause(False));self.button(row,'LOITER / görevi bırak',lambda:self.request_loiter())
        row=self.row(p);self.mission_step=self.entry(row,'0',8);self.button(row,'Belirli görev adımına geç',self.mission_jump)
        self.route_status=self.label(p,'Henüz nokta yok.',11,GOLD)
        self.label(p,'Yükleme penceresinde servo adımları eklenebilir. Yükleme mevcut kart görevini değiştirir; uçuşu başlatmaz.')

    def start_mission(self):
        if not self.live():self.send(('mission','start'));return
        safety=self.app.live_map.safety
        if not safety.allow('mission'):messagebox.showwarning('Görev engellendi',safety.summary(action='mission'));return
        if messagebox.askyesno('Görevi başlat','Kartta yüklü görev başlatılacak. Bu ekrandaki taslak yüklenmediyse karttaki eski görev çalışabilir. Devam?'):
            self.send(('mission','start'))

    def request_loiter(self):
        if 'LOITER' not in self.mode_names:messagebox.showinfo('Mod','Bağlı araç türünde LOITER doğrulanmadı.');return
        if messagebox.askyesno('LOITER isteği','Kart LOITER moduna geçirilsin mi?'):
            self.send(('mode','LOITER'))

    def mission_pause(self,pause):
        action='pause' if pause else 'resume'
        text='Görev duraklatılsın mı?' if pause else 'Göreve kaldığı yerden devam edilsin mi?'
        if messagebox.askyesno('Görev kontrolü',text,parent=self.app.root):self.send(('mission',action))

    def mission_jump(self):
        try:seq=int(self.mission_step.get())
        except ValueError:messagebox.showerror('Görev adımı','0 veya daha büyük bir görev sıra numarası girin.');return
        if not 0<=seq<=65535:messagebox.showerror('Görev adımı','Görev adımı 0–65535 arasında olmalı.');return
        if messagebox.askyesno('Görev adımını değiştir',f'Cube görev adımı {seq} olarak değiştirilsin mi?',parent=self.app.root):self.send(('mission','jump',seq))

    def select_point(self,event=None):
        selection=self.route.selection()
        if selection:
            for var,value in zip((self.lat,self.lon,self.alt),self.route.item(selection[0],'values')):var.set(value)

    def edit_point(self,replace):
        try:
            point=tuple(float(v.get().replace(',','.')) for v in (self.lat,self.lon,self.alt));validate_points([point])
            if replace:
                selection=self.route.selection()
                if not selection:raise ValueError('Önce bir nokta seçin.')
                self.app.markers[int(selection[0])]=point
            else:self.app.markers.append(point)
            self.route_changed()
        except ValueError as exc:messagebox.showerror('Rota',str(exc))

    def delete_point(self):
        for item in sorted(map(int,self.route.selection()),reverse=True):self.app.markers.pop(item)
        self.route_changed()

    def move_point(self,delta):
        selected=self.route.selection()
        if not selected:return
        i=int(selected[0]);j=i+delta
        if 0<=j<len(self.app.markers):
            self.app.markers[i],self.app.markers[j]=self.app.markers[j],self.app.markers[i];self.route_changed();self.route.selection_set(str(j))

    def route_changed(self):
        self.app.update_marker_buttons();self.app.draw_map();self.route_snapshot=None;self.refresh_route()

    def route_file(self,opening):
        path=(filedialog.askopenfilename(filetypes=[('Fentek rota','*.json')]) if opening else filedialog.asksaveasfilename(defaultextension='.json',initialfile='fentek_rota.json'))
        if not path:return
        try:
            if opening:
                if Path(path).stat().st_size>50000000:raise ValueError('Rota dosyası 50 MB sınırını aşıyor.')
                data=json.loads(Path(path).read_text(encoding='utf-8'));points=data['points']
                if data.get('frame')!='HOME_RELATIVE':raise ValueError('İrtifa referansı desteklenmiyor.')
                validate_points(points)
                self.app.markers=[tuple(p) for p in points];self.route_changed()
            else:
                validate_points(self.app.markers)
                Path(path).write_text(json.dumps({'frame':'HOME_RELATIVE','points':self.app.markers,'end':'RTL'},indent=2),encoding='utf-8')
        except (ValueError,OSError,KeyError,TypeError) as exc:messagebox.showerror('Rota dosyası',str(exc))

    def refresh_route(self):
        points=tuple(tuple(p) for p in self.app.markers)
        if points==getattr(self,'route_snapshot',None):return
        self.route_snapshot=points;self.route.delete(*self.route.get_children())
        for i,point in enumerate(points):self.route.insert('','end',iid=str(i),values=point)
        self.route_status.configure(text=f'{len(points)} nokta • HOME üstü irtifa • Son işlem RTL')
        if hasattr(self,'measure_a'):self.refresh_measurements()

    def build_measurements(self):
        p=self.pages['Ölçüm araçları'];self.label(p,'HARİTA VE ROTA ÖLÇÜMLERİ',13,GOLD)
        self.label(p,'Rota noktalarından iki nokta arası mesafe, toplam rota, kapalı alan ve seçilen hıza göre yaklaşık süre hesaplanır.')
        row=self.row(p);self.label(row,'Nokta A');self.measure_a=tk.StringVar();self.measure_a_box=ttk.Combobox(row,textvariable=self.measure_a,state='readonly',width=12);self.measure_a_box.pack(side='left',padx=6)
        self.label(row,'Nokta B');self.measure_b=tk.StringVar();self.measure_b_box=ttk.Combobox(row,textvariable=self.measure_b,state='readonly',width=12);self.measure_b_box.pack(side='left',padx=6)
        self.button(row,'Hesapla',self.refresh_measurements)
        row=self.row(p);self.label(row,'Tahmini yatay hız (m/s)');self.measure_speed=self.entry(row,'10',10);self.button(row,'Süreyi yenile',self.refresh_measurements)
        self.measure_result=self.label(p,'Rota noktası bekleniyor.',13,GOLD)
        self.measure_legs=ttk.Treeview(p,columns=('leg','distance'),show='headings',height=9)
        self.measure_legs.heading('leg',text='Rota ayağı');self.measure_legs.heading('distance',text='Mesafe')
        self.measure_legs.column('leg',width=260);self.measure_legs.column('distance',width=180);self.measure_legs.pack(fill='x',pady=8)
        self.label(p,'Süre hesabı tırmanış, rüzgâr, dönüş yarıçapı, bekleme ve iniş süresini içermez; yalnız yatay rota/hız tahminidir.',9,'#aeb2b9')
        self.refresh_measurements()

    def refresh_measurements(self):
        if not hasattr(self,'measure_result'):return
        points=list(self.app.markers);values=tuple(str(i+1) for i in range(len(points)))
        self.measure_a_box.configure(values=values);self.measure_b_box.configure(values=values)
        if values and self.measure_a.get() not in values:self.measure_a.set(values[0])
        if values and self.measure_b.get() not in values:self.measure_b.set(values[-1])
        self.measure_legs.delete(*self.measure_legs.get_children())
        try:speed=float(self.measure_speed.get().replace(',','.'))
        except ValueError:speed=0
        if not points or speed<=0:
            self.measure_result.configure(text='Rota noktası ve sıfırdan büyük tahmini hız girin.');return
        try:metrics=route_metrics(points,speed)
        except ValueError as exc:self.measure_result.configure(text=str(exc));return
        for i,distance in enumerate(metrics['legs'],1):self.measure_legs.insert('','end',values=(f'{i} → {i+1}',f'{distance:.1f} m'))
        pair=0
        if self.measure_a.get() and self.measure_b.get():pair=haversine_m(points[int(self.measure_a.get())-1],points[int(self.measure_b.get())-1])
        area=polygon_area_m2(points)
        minutes=int(metrics['seconds']//60);seconds=int(round(metrics['seconds']%60))
        self.measure_result.configure(text=f'A–B: {pair:.1f} m\nToplam rota: {metrics["total_m"]:.1f} m\nKapalı alan: {area:.1f} m²\nTahmini süre: {minutes:02d}:{seconds:02d}')

    def build_rally(self):
        p=self.pages['Rally / Güvenli iniş'];self.label(p,'ALTERNATİF DÖNÜŞ VE GÜVENLİ İNİŞ NOKTALARI',13,GOLD)
        self.label(p,'Rally noktaları ana görevden bağımsızdır. ArduPilot uygun ayarlarda RTL sırasında HOME yerine yakındaki geçerli rally noktasını seçebilir.')
        self.rally_table=ttk.Treeview(p,columns=('lat','lon','alt'),show='headings',height=8)
        for key,title in [('lat','Enlem'),('lon','Boylam'),('alt','HOME üstü irtifa')]:self.rally_table.heading(key,text=title);self.rally_table.column(key,width=210)
        self.rally_table.pack(fill='x',pady=8);self.rally_table.bind('<<TreeviewSelect>>',self.select_rally)
        row=self.row(p);self.rally_lat=self.entry(row,'41.0');self.rally_lon=self.entry(row,'29.0');self.rally_alt=self.entry(row,'60')
        row=self.row(p);self.button(row,'Rally ekle',lambda:self.edit_rally(False));self.button(row,'Seçiliyi güncelle',lambda:self.edit_rally(True));self.button(row,'Seçiliyi sil',self.delete_rally);self.button(row,'Son rota noktasını al',self.rally_from_route)
        row=self.row(p);self.button(row,'Rally planını kaydet',lambda:self.rally_file(False));self.button(row,'Rally planı aç',lambda:self.rally_file(True));self.button(row,'Cube’a yükle ve doğrula',self.upload_rally)
        self.rally_status=self.label(p,'Henüz rally noktası yok.',11,GOLD)
        self.label(p,'Aktarım MAVLink 2, DISARMED ArduPilot ve geri okuma doğrulaması ister. RALLY_INCL_HOME ve RALLY_LIMIT_KM gibi kart parametreleri ayrıca kontrol edilmelidir.',9,'#aeb2b9')

    def refresh_rally(self):
        self.rally_table.delete(*self.rally_table.get_children())
        for i,p in enumerate(self.rally_points):self.rally_table.insert('','end',iid=str(i),values=(f'{p[0]:.7f}',f'{p[1]:.7f}',f'{p[2]:.1f}'))
        self.rally_status.configure(text=f'{len(self.rally_points)} rally noktası • Ana görevden bağımsız')
        self.app.draw_map()

    def select_rally(self,event=None):
        selected=self.rally_table.selection()
        if selected:
            for var,value in zip((self.rally_lat,self.rally_lon,self.rally_alt),self.rally_points[int(selected[0])]):var.set(str(value))

    def edit_rally(self,replace):
        try:point=validate_rally_points([(self.rally_lat.get().replace(',','.'),self.rally_lon.get().replace(',','.'),self.rally_alt.get().replace(',','.'))])[0]
        except ValueError as exc:messagebox.showerror('Rally noktası',str(exc));return
        if replace:
            selected=self.rally_table.selection()
            if not selected:messagebox.showinfo('Rally noktası','Önce bir rally noktası seçin.');return
            self.rally_points[int(selected[0])]=point
        else:self.rally_points.append(point)
        self.refresh_rally()

    def delete_rally(self):
        for item in sorted(map(int,self.rally_table.selection()),reverse=True):self.rally_points.pop(item)
        self.refresh_rally()

    def rally_from_route(self):
        if not self.app.markers:messagebox.showinfo('Rally noktası','Önce görev planına bir nokta ekleyin.');return
        p=self.app.markers[-1];self.rally_lat.set(str(p[0]));self.rally_lon.set(str(p[1]));self.rally_alt.set(str(p[2] if len(p)>2 and p[2]>0 else 60));self.edit_rally(False)

    def rally_file(self,opening):
        path=filedialog.askopenfilename(filetypes=[('Fentek rally','*.json')]) if opening else filedialog.asksaveasfilename(defaultextension='.json',initialfile='fentek_rally.json')
        if not path:return
        try:
            if opening:
                data=json.loads(Path(path).read_text(encoding='utf-8'));self.rally_points=validate_rally_points(data['points']);self.refresh_rally()
            else:Path(path).write_text(json.dumps({'type':'RALLY','frame':'GLOBAL_RELATIVE_ALT','points':self.rally_points},indent=2),encoding='utf-8')
        except (ValueError,OSError,KeyError,TypeError) as exc:messagebox.showerror('Rally dosyası',str(exc))

    def upload_rally(self):
        from rally_dialog import open_rally_upload
        open_rally_upload(self.app,self.rally_points)

    def build_params(self):
        p=self.pages['Parametreler'];self.label(p,'Karttan okunan değerler • Dosya karşılaştırma • Tek tek onaylı yazma')
        row=self.row(p);self.button(row,'Tümünü karttan oku',self.read_params);self.button(row,'Yedek kaydet',self.save_params);self.button(row,'Dosyayla karşılaştır',self.compare_params)
        row=self.row(p);self.query=self.entry(row,'',30);self.query.trace_add('write',lambda *a:self.render_params())
        self.label(p,'Arama: BATT, GPS, CAN, SERIAL, SERVO, RC, FLTMODE, FENCE, RTL veya parametre adı.')
        self.param_table=ttk.Treeview(p,columns=('name','value','draft'),show='headings',height=13)
        for key,title in [('name','Parametre'),('value','Kart değeri'),('draft','Taslak / dosya')]:self.param_table.heading(key,text=title);self.param_table.column(key,width=220)
        self.param_table.pack(fill='x');self.param_table.bind('<<TreeviewSelect>>',self.select_param)
        row=self.row(p);self.value=self.entry(row,'',20);self.button(row,'Taslağa al',self.stage_param);self.button(row,'Seçiliyi karta yaz',self.write_param);self.button(row,'Bu parametreyi açıkla',self.explain_selected_param);self.button(row,'Taslakları temizle',self.clear_drafts)
        self.param_meta=self.label(p,'Firmware/araç metadata’sı: Bir parametre seçin.',10,'#aeb2b9')
        self.param_status=self.label(p,'Karttan henüz liste alınmadı.',11,GOLD)
        self.label(p,'Yazma yalnız DISARMED ve güncel bağlantıda yapılır. Bilinen kritik alanlar araç profiline göre denetlenir; bilinmeyen firmware parametresine aralık uydurulmaz.')
        self.label(p,'DOĞRULANMIŞ DEĞİŞİKLİK GEÇMİŞİ VE GERİ ALMA',13,GOLD)
        self.param_history_table=ttk.Treeview(p,columns=('time','name','before','after'),show='headings',height=7)
        for key,title,width in [('time','Saat',90),('name','Parametre',230),('before','Önceki',130),('after','Yeni',130)]:self.param_history_table.heading(key,text=title);self.param_history_table.column(key,width=width)
        self.param_history_table.pack(fill='x',pady=5)
        row=self.row(p);self.button(row,'Seçili değişikliği geri al',self.rollback_param);self.button(row,'Geçmişi JSON kaydet',self.export_param_history)

    def read_params(self):
        if self.send(('param_list',)):
            self.params.clear();self.indices.clear();self.count=0;self.last_result='Liste isteniyor…';self.render_params()

    def render_params(self):
        selected=self.param_table.selection()
        self.param_table.delete(*self.param_table.get_children());query=self.query.get().upper()
        for name,(value,kind) in sorted(self.params.items()):
            if query in name:self.param_table.insert('','end',iid=name,values=(name,f'{value:g}',self.pending.get(name,'')))
        for name in selected:
            if self.param_table.exists(name):self.param_table.selection_add(name);self.param_table.see(name)

    def select_param(self,event=None):
        selected=self.param_table.selection()
        if selected:
            name=selected[0];self.value.set(self.pending.get(name,self.params[name][0]))
            meta=metadata_for(name,getattr(self.app.live_map.state,'vehicle_type',None))
            self.param_meta.configure(text=(f'{name}: {meta[3]} • {meta[0]:g}–{meta[1]:g} {meta[2]} • bağlı araç profili' if meta else f'{name}: Bu firmware parametresi için yerel doğrulanmış aralık yok; kart dokümanından kontrol edin.'),fg=GOLD if meta else '#ffb36a')

    def stage_param(self):
        selected=self.param_table.selection()
        if not selected:return
        name=selected[0]
        try:
            value=checked_value(self.value.get().replace(',','.'),self.params[name][1]);validate_metadata(name,value,getattr(self.app.live_map.state,'vehicle_type',None));self.pending[name]=value
        except ValueError as exc:messagebox.showerror('Parametre',str(exc));return
        self.render_params();self.param_table.selection_set(name)

    def write_param(self):
        selected=self.param_table.selection()
        if not selected:return
        name=selected[0]
        if name not in self.pending:messagebox.showinfo('Parametre','Önce yeni değeri taslağa alın.');return
        try:validate_safety_parameter(name,self.pending[name])
        except ValueError as exc:messagebox.showerror('Güvenlik kilidi',str(exc));return
        if not self.live():self.send(('param_set',name,self.pending[name]));return
        if self.app.live_map.state.armed is not False:messagebox.showwarning('Yazma kilitli','Kart DISARMED olmalı.');return
        if messagebox.askyesno('Parametreyi değiştir',f'{name}\nKart: {self.params[name][0]:g}\nYeni: {self.pending[name]:g}\nBu değeri karta yaz?'):
            self.param_write_context=(name,self.params[name][0],self.pending[name]);self.send(('param_set',name,self.pending[name]));self.last_result=f'{name}: kart doğrulaması bekleniyor'

    def render_param_history(self):
        self.param_history_table.delete(*self.param_history_table.get_children())
        for index,item in enumerate(self.param_history):self.param_history_table.insert('','end',iid=str(index),values=(item['time'],item['name'],f"{item['before']:g}",f"{item['after']:g}"))

    def rollback_param(self):
        selected=self.param_history_table.selection()
        if not selected:messagebox.showinfo('Parametre geri alma','Önce geçmişten bir değişiklik seçin.',parent=self.app.root);return
        item=self.param_history[int(selected[0])];name=item['name']
        if name not in self.params:messagebox.showwarning('Parametre geri alma','Parametre bu canlı bağlantıda okunmadı.',parent=self.app.root);return
        current=self.params[name][0]
        if not math.isclose(current,item['after'],rel_tol=1e-6,abs_tol=1e-7):messagebox.showwarning('Parametre geri alma',f'Kartın güncel {name} değeri geçmişteki yeni değerle aynı değil. Önce yeniden okuyun.',parent=self.app.root);return
        self.pending[name]=item['before'];self.render_params();self.param_table.selection_set(name);self.param_table.see(name)
        if messagebox.askyesno('Parametre geri alma',f'{name}: {current:g} değerinden {item["before"]:g} değerine geri dönülsün mü?',parent=self.app.root):
            self.param_write_context=(name,current,item['before']);self.send(('param_set',name,item['before']));self.last_result=f'{name}: geri alma doğrulaması bekleniyor'

    def export_param_history(self):
        if not self.param_history:messagebox.showinfo('Parametre geçmişi','Henüz doğrulanmış değişiklik yok.',parent=self.app.root);return
        path=filedialog.asksaveasfilename(parent=self.app.root,defaultextension='.json',initialfile='Fentek_Parametre_Gecmisi.json',filetypes=[('JSON','*.json')])
        if path:
            try:Path(path).write_text(json.dumps({'changes':self.param_history},ensure_ascii=False,indent=2),encoding='utf-8')
            except OSError as exc:messagebox.showerror('Parametre geçmişi',str(exc),parent=self.app.root)

    def clear_drafts(self):self.pending.clear();self.render_params()

    def save_params(self):
        if not self.params:return
        path=filedialog.asksaveasfilename(defaultextension='.param',initialfile='fentek_yedek.param')
        if path:
            try:Path(path).write_text(f'# Karttan okunan {len(self.indices)}/{self.count} parametre\n'+''.join(f'{n},{v[0]:.9g}\n' for n,v in sorted(self.params.items())),encoding='utf-8')
            except OSError as exc:messagebox.showerror('Yedek',str(exc))

    def compare_params(self):
        path=filedialog.askopenfilename(filetypes=[('Parametre','*.param *.params *.txt')])
        if not path:return
        try:
            if Path(path).stat().st_size>2000000:raise ValueError('Dosya 2 MB sınırını aşıyor.')
            values=parse_parameters(Path(path).read_text(encoding='utf-8-sig'));draft={}
            for name,value in values.items():
                if name in self.params:
                    value=checked_value(value,self.params[name][1])
                    if value!=self.params[name][0]:draft[name]=value
            self.pending=draft;self.render_params();self.last_result=f'{len(draft)} fark taslağa alındı; karta yazılmadı.'
        except (ValueError,OSError) as exc:messagebox.showerror('Parametre dosyası',str(exc))

    def filter_group(self,query):self.query.set(query);self.app.select('Parametreler')

    def build_safety(self):
        p=self.pages['Güvenlik'];self.label(p,'UÇUŞ ÖNCESİ DENETİM',13,GOLD)
        self.safety_label=self.label(p,'Donanım bağlı değil. Uçuşa hazır olduğu doğrulanamaz.',12)
        self.label(p,'Eksik/eski ölçüm uygun sayılmaz. ARM ve AUTO isteği gönderim anında yeniden denetlenir. Kartın kendi arming kontrolleri devrede kalır.')
        self.label(p,'GERÇEK DONANIM KABUL TESTİ',13,GOLD)
        self.label(p,'Salt okunur testtir; motora, servoya, ARM veya uçuş moduna komut göndermez. Sonucun uygun olması için kritik veriler en az 5 saniye kesintisiz doğrulanır.')
        row=self.row(p);self.acceptance_phase=tk.StringVar(value='USB yer testi')
        ttk.Combobox(row,textvariable=self.acceptance_phase,values=('USB yer testi','Kablosuz telemetri / uçuş öncesi'),state='readonly',width=38).pack(side='left',padx=5)
        self.button(row,'Kabul testini başlat',self.start_acceptance);self.button(row,'Testi durdur',self.stop_acceptance);self.button(row,'Raporu kaydet',self.save_acceptance)
        self.acceptance_status=self.label(p,'BAŞLATILMADI • Canlı Cube bağlantısı bekleniyor.',12,GOLD)
        self.acceptance_rows={}
        for name in ('MAVLink bağlantısı','Kart kimliği','Yerde güvenlik','Kart çalışma durumu','Sensör sağlığı','Here3 / GPS','Canlı konum','EKF yönelim','EKF navigasyon','Batarya monitörü','HOME konumu','ARMING_CHECK','BATT_MONITOR','Telemetri failsafe','Temel uçuş modları','SiK RADIO_STATUS'):
            line=tk.Frame(p,bg=PANEL,padx=12,pady=6);line.pack(fill='x',pady=1)
            status=tk.Label(line,text='BEKLE',width=10,bg='#493315',fg='#ffd86a',font=('Segoe UI',9,'bold'));status.pack(side='left',padx=(0,12))
            tk.Label(line,text=name,width=23,anchor='w',bg=PANEL,fg=WHITE,font=('Segoe UI',9,'bold')).pack(side='left')
            info=tk.Label(line,text='Test başlatılmadı',anchor='w',bg=PANEL,fg='#aeb2b9',font=('Segoe UI',9));info.pack(side='left',fill='x',expand=True)
            self.acceptance_rows[name]=(status,info)
        self.label(p,'CANLI GÜVENLİK KONTROL LİSTESİ',13,GOLD)
        self.safety_rows={}
        for name,ok,detail in self.app.live_map.safety.checklist():
            line=tk.Frame(p,bg=PANEL,padx=12,pady=7);line.pack(fill='x',pady=2)
            status=tk.Label(line,text='BEKLE',width=10,bg='#493315',fg='#ffd86a',font=('Segoe UI',9,'bold'))
            status.pack(side='left',padx=(0,12))
            tk.Label(line,text=name,width=20,anchor='w',bg=PANEL,fg=WHITE,font=('Segoe UI',10,'bold')).pack(side='left')
            info=tk.Label(line,text=detail,anchor='w',bg=PANEL,fg='#aeb2b9',font=('Segoe UI',9))
            info.pack(side='left',fill='x',expand=True)
            self.safety_rows[name]=(status,info)
        self.label(p,'KARTTAKİ KORUMA AYARLARI',13,GOLD)
        for title,prefix in [('Bağlantı ve kumanda kaybı','FS_'),('Batarya koruması','BATT_'),('Eve dönüş','RTL'),('Sanal çit / yükseklik / yarıçap','FENCE_'),('ARM kontrolleri','ARMING_')]:
            row=self.row(p);self.button(row,title,lambda q=prefix:self.filter_group(q))
        self.label(p,'Sanal çit parametreleri kartta bulunuyorsa düzenlenebilir. Haritada çokgen çit aktarımı bu ekranda yok; çitin etkinliği yalnız kart verisiyle değerlendirilir.')
        self.label(p,'KART UYARILARI / PRE-ARM',13,GOLD)
        self.warning_text=tk.Text(p,height=9,bg=PANEL,fg=WHITE,wrap='word',font=('Consolas',10));self.warning_text.pack(fill='x');self.warning_text.configure(state='disabled')
        self.label(p,'YERDE GÜVENLİK SENARYOSU',13,GOLD)
        self.label(p,'Bu test gerçek bağlantıyı kesmez ve araca hareket komutu göndermez. Karttan okunan ayarlara göre hangi failsafe parametresinin devreye gireceğini gösterir.')
        row=self.row(p);self.scenario=tk.StringVar(value='Yer istasyonu bağlantısı kesilirse')
        scenarios=('Yer istasyonu bağlantısı kesilirse','RC kumanda sinyali kesilirse','Batarya düşük seviyeye inerse','Batarya kritik seviyeye inerse','EKF veya konum çözümü bozulursa')
        box=ttk.Combobox(row,textvariable=self.scenario,values=scenarios,state='readonly',width=42);box.pack(side='left',padx=5)
        self.button(row,'Senaryoyu yerde değerlendir',self.run_safety_scenario);self.button(row,'Gerekli parametreleri karttan oku',self.read_safety_params)
        self.scenario_result=self.label(p,'Senaryo seçildi; kart parametreleri bekleniyor.',11,GOLD)

    def start_acceptance(self):
        if not self.live():
            self.acceptance_status.configure(text='BEKLE • Önce Cube’a canlı bağlantı kurun.',fg=GOLD)
            messagebox.showinfo('Donanım kabul testi','Önce Uçuş ekranından Cube’a bağlanın. Test, sentetik demo verisini kabul etmez.',parent=self.app.root);return
        if self.app.live_map.state.armed is not False:
            messagebox.showwarning('Donanım kabul testi','Araç DISARMED olarak doğrulanmadan yer testi başlatılamaz.',parent=self.app.root);return
        self.acceptance_active=True;self.acceptance_stable_since=None;self.acceptance_final='BEKLİYOR'
        self.send(('param_read',ACCEPTANCE_PARAMETERS))
        self.acceptance_status.configure(text='BEKLİYOR • Canlı veriler ve koruma parametreleri okunuyor…',fg=GOLD)
        self.app.event('Gerçek donanım kabul testi başlatıldı: '+self.acceptance_phase.get())

    def stop_acceptance(self):
        was_active=self.acceptance_active;self.acceptance_active=False;self.acceptance_stable_since=None
        if was_active:self.app.event('Gerçek donanım kabul testi kullanıcı tarafından durduruldu.')
        self.acceptance_status.configure(text='DURDURULDU • Sonuç uçuşa hazır kanıtı değildir.',fg=GOLD)

    def save_acceptance(self):
        if not self.acceptance_last:
            messagebox.showinfo('Kabul testi','Önce kabul testini başlatın.',parent=self.app.root);return
        target=filedialog.asksaveasfilename(parent=self.app.root,title='Donanım kabul raporunu kaydet',defaultextension='.txt',initialfile='Fentek_Donanim_Kabul_Raporu.txt',filetypes=[('Metin raporu','*.txt')])
        if not target:return
        lines=['FENTEK HAVACILIK • GERÇEK DONANIM KABUL RAPORU',time.strftime('%Y-%m-%d %H:%M:%S'),f'Aşama: {self.acceptance_phase.get()}',f'Sonuç: {self.acceptance_final}','']
        for item in self.acceptance_last:
            status='UYGUN' if item.ok is True else 'UYGUN DEĞİL' if item.ok is False else 'BEKLE'
            lines.append(f'[{status}] {item.name}: {item.detail}'+('' if item.critical else ' (bu aşamada bilgi)'))
        lines+=['','Bu rapor yalnız kayıt anında uygulamaya ulaşan verileri gösterir; uçuş sertifikası veya güvenlik garantisi değildir.']
        try:Path(target).write_text('\n'.join(lines),encoding='utf-8');messagebox.showinfo('Kabul testi','Rapor kaydedildi.',parent=self.app.root)
        except OSError as exc:messagebox.showerror('Kabul testi',f'Rapor kaydedilemedi:\n{exc}',parent=self.app.root)

    def read_safety_params(self):
        names=('FS_GCS_ENABLE','FS_THR_ENABLE','BATT_FS_LOW_ACT','BATT_FS_CRT_ACT','FS_EKF_ACTION')
        if self.send(('param_read',names)):self.scenario_result.configure(text='Güvenlik parametreleri karttan isteniyor…')

    def run_safety_scenario(self):
        status,text=failsafe_preview(self.params,self.scenario.get())
        color='#7cdbac' if status=='YAPILANDIRILMIŞ' else GOLD
        self.scenario_result.configure(text=f'{status}\n{text}\nBu bir yapılandırma önizlemesidir; gerçek failsafe tetiklenmedi.',fg=color)

    def safety_mode(self,mode):
        if not self.live():self.send(('mode',mode));return
        action=self.app.live_map.safety.action_for_mode(mode)
        if action!='basic_mode' and not self.app.live_map.safety.allow(action):
            messagebox.showwarning('Komut engellendi',self.app.live_map.safety.summary(action=action),parent=self.app.root);return
        if messagebox.askyesno('Acil uçuş davranışı',f'{mode} modu karta gönderilsin mi?',parent=self.app.root):
            self.send(('mode',mode))

    def build_hardware(self):
        p=self.pages['Yardımcı donanım'];self.label(p,'Uçuş için sık kullanılan donanım ayarları. Yalnız kartın bildirdiği parametreler gösterilir.')
        for title,detail,prefix in [('GPS / Here3','GPS türü, alıcı seçimi ve ilgili ayarlar.','GPS'),('DroneCAN','CAN sürücü/port ayarları. Düğüm firmware yükleyicisi içermez.','CAN_'),('Batarya monitörü','Sensör türü, kapasite, voltaj/akım ölçekleri.','BATT'),('Telemetri portları','Port protokolü ve seri hız. Aktif portu değiştirmek bağlantıyı kesebilir.','SERIAL'),('Servo çıkışları','Fonksiyon, alt/üst limit ve ters yön. Canlı servo testi değildir.','SERVO'),('Kumanda','RC kanal sınırları ve yardımcı fonksiyonlar.','RC'),('Hava hızı','Sabit kanatta kullanılan airspeed sensörü.','ARSPD')]:
            self.label(p,title,13,GOLD);self.label(p,detail);self.button(self.row(p),title+' parametreleri',lambda q=prefix:self.filter_group(q))

    def build_sitl(self):
        p=self.pages['ArduPilot SITL Testi'];self.label(p,'ARDUPILOT SITL • GERÇEK FIRMWARE SİMÜLASYON TESTİ',13,GOLD)
        self.label(p,'Bu ekran yalnız aynı bilgisayardaki 127.0.0.1 ArduPilot SITL sunucusuna bağlanır. COM portu veya ağdaki gerçek araca bağlanamaz. SIM_SPEEDUP parametresi okunmadan hedef SITL kabul edilmez.')
        row=self.row(p);self.sitl_endpoint=tk.StringVar(value='tcp:127.0.0.1:5760')
        ttk.Combobox(row,textvariable=self.sitl_endpoint,values=('tcp:127.0.0.1:5760','tcp:127.0.0.1:5762'),state='readonly',width=27).pack(side='left',padx=5)
        self.button(row,'Bağlı SITL’yi test et',self.start_sitl);self.button(row,'Raporu kaydet',self.save_sitl)
        self.sitl_status=self.label(p,'BEKLE • ArduPilot SITL ayrıca başlatılmalıdır.',12,GOLD)
        self.sitl_text=tk.Text(p,height=22,bg=PANEL,fg=WHITE,wrap='word',font=('Consolas',10),padx=12,pady=10);self.sitl_text.pack(fill='both',expand=True)
        self.sitl_text.insert('1.0','Test; gerçek SITL heartbeat ve telemetri mesajlarını okur. Ardından GPS, batarya, sensör, EKF, HOME ve sanal çit kaybı için uygulamanın fail-closed engellerini sınar.\n\nSITL kurulumu bu uygulamayla birlikte gelmez.')
        self.sitl_text.configure(state='disabled')

    def start_sitl(self):
        if self.sitl_running:return
        self.sitl_running=True;self.sitl_status.configure(text='SITL BAĞLANIYOR • Yerel simülatör bekleniyor…',fg=GOLD);endpoint=self.sitl_endpoint.get()
        def worker():
            try:self.sitl_results.put(('ok',format_report(run_sitl(endpoint))))
            except Exception as exc:self.sitl_results.put(('error',str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def poll_sitl(self):
        try:kind,value=self.sitl_results.get_nowait()
        except queue.Empty:return
        self.sitl_running=False;self.sitl_last=value
        self.sitl_text.configure(state='normal');self.sitl_text.delete('1.0','end');self.sitl_text.insert('1.0',value);self.sitl_text.configure(state='disabled')
        self.sitl_status.configure(text=('GEÇTİ • Gerçek ArduPilot SITL ve hata matrisi doğrulandı.' if kind=='ok' and 'SONUÇ: GEÇTİ' in value else 'GEÇMEDİ • '+value),fg='#7cdbac' if kind=='ok' and 'SONUÇ: GEÇTİ' in value else '#ff756a')

    def save_sitl(self):
        if not self.sitl_last:messagebox.showinfo('SITL raporu','Önce SITL testini çalıştırın.',parent=self.app.root);return
        path=filedialog.asksaveasfilename(parent=self.app.root,defaultextension='.txt',initialfile='Fentek_SITL_Test_Raporu.txt',filetypes=[('Metin','*.txt')])
        if path:
            try:Path(path).write_text(self.sitl_last,encoding='utf-8')
            except OSError as exc:messagebox.showerror('SITL raporu',str(exc),parent=self.app.root)

    def build_radio(self):
        p=self.pages['Kablosuz Telemetri'];self.label(p,'KABLOSUZ TELEMETRİ BAĞLANTI KALİTESİ',13,GOLD)
        self.label(p,'SiK yer ve hava radyosu RADIO_STATUS mesajlarını MAVLink akışına eklerse değerler canlı görünür. RSSI ölçeği cihaz modeline bağlıdır; sinyal/gürültü farkı birlikte değerlendirilir.')
        self.radio_status=self.label(p,'BEKLE • Radyo verisi bekleniyor.',13,GOLD)
        self.radio_vars={}
        labels=(('rssi','Yerel RSSI'),('noise','Yerel gürültü'),('remrssi','Uzak RSSI'),('remnoise','Uzak gürültü'),('txbuf','Gönderim tamponu'),('rxerrors','Alım hata sayacı'),('fixed','Düzeltilen paket sayacı'))
        for key,title in labels:
            row=tk.Frame(p,bg=PANEL,padx=12,pady=8);row.pack(fill='x',pady=2)
            tk.Label(row,text=title,bg=PANEL,fg=WHITE,font=('Segoe UI',10,'bold')).pack(side='left')
            var=tk.StringVar(value='—');self.radio_vars[key]=var;tk.Label(row,textvariable=var,bg=PANEL,fg=GOLD,font=('Consolas',11)).pack(side='right')
        self.radio_loss=tk.StringVar(value='—')
        row=tk.Frame(p,bg=PANEL,padx=12,pady=8);row.pack(fill='x',pady=2);tk.Label(row,text='MAVLink tahmini paket kaybı',bg=PANEL,fg=WHITE,font=('Segoe UI',10,'bold')).pack(side='left');tk.Label(row,textvariable=self.radio_loss,bg=PANEL,fg=GOLD,font=('Consolas',11)).pack(side='right')
        row=self.row(p);self.button(row,'Telemetri port parametreleri',lambda:self.filter_group('SERIAL'))
        self.label(p,'EŞLEŞME VE SAHA KONTROLÜ',13,GOLD)
        for text in ('Yer ve hava modülünün Net ID / kanal / hava hızı ayarları aynı olmalı.','Antenler takılmadan radyo modüllerine güç verilmemeli.','Cube TELEM portu protokolü MAVLink 2 ve seri hızı radyo ayarıyla uyumlu olmalı.','Bağlantı kalitesi uçuş alanında, araç yerde ve motorlar kapalıyken menzil boyunca izlenmeli.'):
            self.label(p,'• '+text)
        self.label(p,'Paket kaybı, gelen MAVLink sıra numaralarındaki boşluklardan yaklaşık hesaplanır. RF menzil garantisi değildir. Uçuş öncesinde yerde menzil testi ve anten yönü kontrolü yapılmalıdır.',9,'#aeb2b9')

    def build_telemetry(self):
        p=self.page('Telemetri');self.telemetry_body=p
        self.label(p,'GERÇEK KART GÖSTERGELERİ • Veri gelmeyen alanlar — olarak kalır. Fare tekerleğiyle aşağı kaydırın.')
        names=['Enlem','Boylam','HOME üstü irtifa','Deniz seviyesi irtifa','ARM durumu','Yatış','Yunuslama','Yönelim','GPS fix','Uydu sayısı','Batarya seviyesi','Batarya voltajı','Batarya akımı','Batarya 0 tüketim','Batarya 0 sıcaklık','GPS HDOP','GPS VDOP','Hava hızı','Yer hızı','Dikey hız','Gaz','CPU yükü','EKF bayrakları','velocity_variance','pos_horiz_variance','pos_vert_variance','compass_variance','vibration_x','vibration_y','vibration_z','clipping_0','clipping_1','clipping_2','Aktif görev adımı','Sanal çit ihlali']+[f'RC {i}' for i in range(1,19)]+[f'Çıkış 0:{i}' for i in range(1,17)]
        for name in names:
            row=tk.Frame(p,bg=PANEL,padx=12,pady=7);row.pack(fill='x',pady=2)
            tk.Label(row,text=name,bg=PANEL,fg=WHITE,font=('Segoe UI',10)).pack(side='left')
            var=tk.StringVar(value='—');tk.Label(row,textvariable=var,bg=PANEL,fg=GOLD,font=('Consolas',11)).pack(side='right');self.telemetry_vars[name]=var

    def build_guide(self):
        p=self.pages['Bilgi ve Kılavuz']
        back=self.row(p);self.button(back,'←  Önceki sayfaya dön',self.guide_back)
        download=self.button(back,'↓  Bilgi Kılavuzunu İndir (PDF)',self.download_guide_pdf)
        download.configure(bg=GOLD,fg=BG,activebackground='#ffe36a')
        self.label(p,'Uygulamadaki bir düğmeyi, uçuş modunu veya parametreyi arayın. Açıklamalar işlem yapmaz ve karta komut göndermez.')
        quick=self.row(p)
        for title in ('Hızlı başlangıç','ARM / DISARM','Nokta ekle / güncelle / sil','BEKLE ve UYGUN ne demek?'):
            self.button(quick,title,lambda t=title:self.show_guide_title(t))
        search=self.row(p);self.guide_query=self.entry(search,'',34)
        self.guide_query.trace_add('write',lambda *a:self.render_guide())
        self.button(search,'Aramayı temizle',lambda:self.guide_query.set(''))
        host=tk.Frame(p,bg=BG);host.pack(fill='both',expand=True,pady=8)
        self.guide_tree=ttk.Treeview(host,columns=('category','title'),show='headings',height=15)
        self.guide_tree.heading('category',text='Bölüm');self.guide_tree.heading('title',text='Konu')
        self.guide_tree.column('category',width=130,stretch=False);self.guide_tree.column('title',width=300)
        self.guide_tree.pack(side='left',fill='both',expand=True);self.guide_tree.bind('<<TreeviewSelect>>',self.guide_selected)
        right=tk.Frame(host,bg=PANEL,padx=12,pady=10);right.pack(side='left',fill='both',expand=True,padx=(10,0))
        self.guide_title=tk.Label(right,text='Bir konu seçin',bg=PANEL,fg=GOLD,font=('Segoe UI',13,'bold'),anchor='w',wraplength=560,justify='left')
        self.guide_title.pack(fill='x',pady=(0,8))
        self.guide_text=tk.Text(right,height=15,bg='#111315',fg=WHITE,wrap='word',relief='flat',padx=12,pady=10,font=('Segoe UI',10))
        self.guide_text.pack(fill='both',expand=True);self.guide_text.configure(state='disabled')
        self.label(p,'PARAMETRE SÖZLÜĞÜ',13,GOLD)
        row=self.row(p);self.guide_param=self.entry(row,'ARMING_CHECK',28);self.button(row,'Parametreyi açıkla',self.explain_parameter)
        self.guide_param_result=self.label(p,'Parametre adını tam olarak yazın veya Parametreler sayfasından seçin.',10,'#aeb2b9')
        self.render_guide()
        self.guide_tree.selection_set('0');self.guide_selected()

    def render_guide(self):
        query=self.guide_query.get().strip().casefold() if hasattr(self,'guide_query') else ''
        self.guide_tree.delete(*self.guide_tree.get_children())
        for index,(category,title,body) in enumerate(TOPICS):
            if query and query not in (category+' '+title+' '+body).casefold():continue
            self.guide_tree.insert('','end',iid=str(index),values=(category,title))

    def guide_selected(self,event=None):
        selected=self.guide_tree.selection()
        if not selected:return
        category,title,body=TOPICS[int(selected[0])]
        self.guide_title.configure(text=f'{category} • {title}')
        self.guide_text.configure(state='normal');self.guide_text.delete('1.0','end');self.guide_text.insert('1.0',body);self.guide_text.configure(state='disabled')

    def show_guide_title(self,title):
        current=getattr(self.app,'active_page','Uçuş ekranı')
        if current!='Bilgi ve Kılavuz':self.guide_return_page=current
        self.app.select('Bilgi ve Kılavuz')
        if self.guide_query.get():self.guide_query.set('')
        for index,item in enumerate(TOPICS):
            if item[1]==title:
                self.guide_tree.selection_set(str(index));self.guide_tree.see(str(index));self.guide_selected();return

    def guide_back(self):
        target=self.guide_return_page
        if target not in self.app.pages or target=='Bilgi ve Kılavuz':target='Uçuş ekranı'
        self.app.select(target)

    def download_guide_pdf(self):
        source=Path(__file__).resolve().parent/'assets'/'Fentek_Havacilik_Bilgi_Kilavuzu.pdf'
        if not source.exists():
            messagebox.showerror('Bilgi Kılavuzu','Uygulama içindeki PDF kılavuz dosyası bulunamadı.',parent=self.app.root);return
        target=filedialog.asksaveasfilename(parent=self.app.root,title='Bilgi Kılavuzunu Kaydet',
                    defaultextension='.pdf',initialfile='Fentek_Havacilik_Bilgi_Kilavuzu.pdf',
                    filetypes=[('PDF belgesi','*.pdf')])
        if not target:return
        try:
            Path(target).write_bytes(source.read_bytes())
            messagebox.showinfo('Bilgi Kılavuzu',f'PDF kılavuz kaydedildi:\n{target}',parent=self.app.root)
        except OSError as exc:messagebox.showerror('Bilgi Kılavuzu',f'PDF kaydedilemedi:\n{exc}',parent=self.app.root)

    def explain_parameter(self,name=None):
        name=(name or self.guide_param.get()).strip().upper()
        if not name:messagebox.showinfo('Parametre sözlüğü','Bir parametre adı yazın.',parent=self.app.root);return
        self.guide_param.set(name);category,description=parameter_help(name)
        current=self.params.get(name)
        value=f'\n\nBu bağlantıda kart değeri: {current[0]:g}' if current else '\n\nBu bağlantıda karttan okunmuş bir değer yok.'
        self.guide_param_result.configure(text=f'{name} • {category}\n{description}{value}',fg=GOLD if category!='Firmware özel' else '#ffb36a')

    def explain_selected_param(self):
        selected=self.param_table.selection()
        if not selected:messagebox.showinfo('Parametre sözlüğü','Önce listeden bir parametre seçin.',parent=self.app.root);return
        self.guide_return_page='Parametreler'
        self.app.select('Bilgi ve Kılavuz');self.explain_parameter(selected[0])

    def event(self,kind,value):
        if kind=='online':self.params.clear();self.indices.clear();self.pending.clear();self.render_params()
        if kind=='parameter':
            name,val,typ,index,count=value;self.params[name]=(val,typ);self.count=count
            if 0<=index<count:self.indices.add(index)
            self.param_dirty=True
        elif kind=='param_result':
            name,ok,note=value;self.last_result=f'{name}: {note}'
            if ok:
                self.pending.pop(name,None)
                if self.param_write_context and self.param_write_context[0]==name:
                    _,before,after=self.param_write_context;self.param_history.append({'time':time.strftime('%H:%M:%S'),'name':name,'before':before,'after':after});self.render_param_history()
            if self.param_write_context and self.param_write_context[0]==name:self.param_write_context=None
            self.param_dirty=True
        elif kind in ('control','cal','param_error'):self.last_result=str(value)

    def refresh(self):
        now=time.monotonic();live=self.app.live_map;state=live.state
        self.poll_sitl()
        if self.direct_enabled and (not self.live() or state.armed is not True):
            self.direct_enabled=False;self.stop_direct()
        self.refresh_route()
        if getattr(self,'param_dirty',False):self.render_params();self.param_dirty=False
        self.param_status.configure(text=f'{len(self.indices)}/{self.count} alındı • {self.last_result}')
        self.mode_status.configure(text='Kart modu: '+(state.mode if self.live() else 'Bağlantı yok / eski veri'))
        errors=live.safety.checks(now,'auto' if state.armed else 'arm')
        self.safety_label.configure(text=('BEKLE\n'+'\n'.join('• '+e for e in errors)) if errors else 'Kontroller uygun • Son karar kartın',fg=GOLD if errors else '#7cdbac')
        for name,ok,detail in live.safety.checklist(now):
            if name not in self.safety_rows:continue
            status,info=self.safety_rows[name]
            status.configure(text='UYGUN' if ok else 'BEKLE',bg='#173d31' if ok else '#493315',fg='#8ce3bd' if ok else '#ffd86a')
            info.configure(text=detail)
        if self.acceptance_active:
            rows=evaluate_acceptance(state,now,self.acceptance_phase.get(),self.params,self.mode_names)
            self.acceptance_last=rows;result=acceptance_result(rows)
            if result=='UYGUN':
                if self.acceptance_stable_since is None:self.acceptance_stable_since=now
                stable=now-self.acceptance_stable_since
                if stable>=5:
                    self.acceptance_final='UYGUN';message='UYGUN • Kritik veriler 5 saniye kesintisiz doğrulandı.';color='#7cdbac'
                else:
                    self.acceptance_final='BEKLİYOR';message=f'DOĞRULANIYOR • Kesintisiz veri {stable:.1f}/5.0 sn';color=GOLD
            else:
                self.acceptance_stable_since=None;self.acceptance_final=result
                message=('BAŞARISIZ • Açıkça hatalı kritik madde var.' if result=='BAŞARISIZ' else 'BEKLİYOR • Eksik veya eski kritik veri var.')
                color='#ff756a' if result=='BAŞARISIZ' else GOLD
            self.acceptance_status.configure(text=message,fg=color)
            for item in rows:
                status,info=self.acceptance_rows[item.name]
                if item.ok is True:label,bg,fg='UYGUN','#173d31','#8ce3bd'
                elif item.ok is False:label,bg,fg=('HATA' if item.critical else 'UYARI'),'#54221f','#ff8c84'
                else:label,bg,fg=('BEKLE' if item.critical else 'BİLGİ'),'#493315','#ffd86a'
                status.configure(text=label,bg=bg,fg=fg);info.configure(text=item.detail)
            if not self.live():
                self.acceptance_active=False;self.acceptance_stable_since=None;self.acceptance_final='BEKLİYOR'
                self.acceptance_status.configure(text='KESİLDİ • Canlı bağlantı kayboldu; test tamamlanmadı.',fg='#ff756a')
        for name,var in self.telemetry_vars.items():
            item=state.metrics.get(name)
            if not item:var.set('— • veri yok');continue
            value,unit,stamp=item
            number=f'{value:.7f}' if name in ('Enlem','Boylam') else f'{value:.2f}'
            var.set(f'{number} {unit}'+(' • ESKİ' if now-stamp>3 or not self.live() else ''))
        warnings='\n'.join(f'{now-stamp:.0f} sn önce • seviye {severity} • {text}' for stamp,severity,text in state.messages[-30:]) or 'Karttan durum mesajı gelmedi.'
        self.warning_text.configure(state='normal');self.warning_text.delete('1.0','end');self.warning_text.insert('1.0',warnings);self.warning_text.configure(state='disabled')
        if hasattr(self,'radio_vars'):
            age=now-state.radio_time if state.radio_time else None
            for key,var in self.radio_vars.items():
                value=state.radio.get(key)
                var.set('—' if value is None or value==255 else (f'{value}%' if key=='txbuf' else str(value)))
            status,detail=radio_assessment(state.radio.get('rssi'),state.radio.get('noise'),state.radio.get('remrssi'),state.radio.get('remnoise'),age)
            colors={'İYİ':'#7cdbac','ORTA':'#ffd42a','ZAYIF':'#ff756a'}
            self.radio_status.configure(text=f'{status} • {detail}',fg=colors.get(status,GOLD))
            total=state.packet_received+state.packet_lost
            self.radio_loss.set('—' if not total else f'%{100*state.packet_lost/total:.2f} ({state.packet_lost}/{total})')
        self.job=self.app.root.after(700,self.refresh)

    def modes(self,names):
        self.mode_names=tuple(names);self.mode_box.configure(values=self.mode_names)
        if self.mode.get() not in names:self.mode.set('STABILIZE' if 'STABILIZE' in names else next(iter(names),''))

    def close(self):
        self.stop_direct()
        if self.job:self.app.root.after_cancel(self.job)
