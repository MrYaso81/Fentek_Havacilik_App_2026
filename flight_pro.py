"""Street map, satellite imagery, 3D simulation and PC geolocation."""
import math
import queue
import json
import os
import base64
import subprocess
import threading
import time
import webbrowser
import tkinter as tk
from tkinter import ttk,messagebox
from pathlib import Path
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request,urlopen
from cockpit import Cockpit
from atlas import Atlas
from branded import BLACK,SURFACE,YELLOW,WHITE,GRAY
from demo import CENTER,world,sample
from button_motion import install_button_motion
from startup_intro import StartupIntro
from live_map import LiveMap
from flight_tools import google_static_url
from alert_system import AlertManager
from pilot_ari import PilotAri
from camera_view import CameraView


def parse_windows_location(text):
    parts=text.strip().split(';')
    if len(parts)!=3:raise ValueError('Konum yanıtı okunamadı.')
    lat,lon,accuracy=map(float,parts)
    if not (-90<=lat<=90 and -180<=lon<=180 and accuracy>=0):raise ValueError('Geçersiz konum yanıtı.')
    return lat,lon,accuracy


class FlightPro(Cockpit):
    def __init__(self,root,autoload=True):
        self.aircraft_type='Döner kanat'
        self.map_mode='Dünya Haritası'
        self.camera_distance=520.0
        self.camera_yaw=-25.0
        self.camera_tilt=48.0
        self.zoom_target=self.camera_distance
        self.zoom_job=None
        self.location_result=queue.Queue()
        self.location_job=None
        self.location_pending=False
        self.pc_location=None
        self.place_city='Aranıyor…'
        self.place_country='—'
        self.drag_3d=None
        self.world_features=[]
        self.world_center=list(CENTER)
        self.feature_queue=queue.Queue()
        self.feature_loading=False
        self.feature_job=None
        self.google_maps_key=os.environ.get('GOOGLE_MAPS_API_KEY','').strip()
        self.google_queue=queue.Queue();self.google_loading=False;self.google_reload_pending=False;self.google_image=None
        self.google_request_signature=None
        self.google_loaded_signature=None
        self.google_job=None
        super().__init__(root,autoload=False)
        root.title('Fentek Havacılık • İHA Uçuş Merkezi')
        self.live_map=LiveMap(self)
        self.alert_manager=AlertManager(self)
        self.pilot_ari=PilotAri(self)
        self.camera_view=CameraView(self)
        self.add_flight_controls()
        self.build_map_settings()
        # Give the safety-critical calibration workflow a clear, dedicated name.
        if 'Kurulum ve test' in self.pages:
            self.pages['Kalibrasyon merkezi']=self.pages.pop('Kurulum ve test')
        from operations import Operations
        self.operations=Operations(self)
        from ground_tools import GroundTools
        self.ground_tools=GroundTools(self)
        install_button_motion(root)
        self.startup_intro=StartupIntro(root) if autoload else None
        self.location_job=root.after(120,self.poll_location)
        self.feature_job=root.after(120,self.poll_features)
        self.google_job=root.after(120,self.poll_google)
        if autoload:
            root.after(300,self.load_map)
            root.after(900,self.request_pc_location)

    def add_flight_controls(self):
        live=self.pages['Uçuş ekranı']
        title=live.winfo_children()[0]
        self.aircraft_var=tk.StringVar(value=self.aircraft_type)
        aircraft=ttk.Combobox(title,textvariable=self.aircraft_var,values=['Sabit kanat','Döner kanat','FPV'],state='readonly',width=14)
        aircraft.pack(side='right',padx=12)
        aircraft.bind('<<ComboboxSelected>>',self.change_aircraft)
        self.label(title,'İHA TÜRÜ',8,GRAY,True).pack(side='right')
        live=self.pages['Uçuş ekranı']
        quick=tk.Frame(live,bg='#121315',padx=10,pady=8)
        quick.pack(fill='x',before=live.winfo_children()[1],pady=(0,10))
        self.connect_button=ttk.Button(quick,text='⌁  CUBE’A BAĞLAN • CANLI KONUM',command=self.live_map.dialog)
        self.connect_button.pack(side='left',padx=(0,7))
        ttk.Button(quick,text='⚙  Kalibrasyon merkezi',command=lambda:self.select('Kalibrasyon merkezi'),style='Dark.TButton').pack(side='left',padx=7)
        self.live_map.arm_button=ttk.Button(quick,text='ARM',command=self.live_map.arm_toggle,style='Dark.TButton',state='disabled')
        self.live_map.arm_button.pack(side='left',padx=7)
        ttk.Button(quick,text='Görev planlama',command=lambda:self.select('Görev planlama'),style='Dark.TButton').pack(side='left',padx=7)
        ttk.Button(quick,text='Güvenlik durumu',command=lambda:self.select('Güvenlik'),style='Dark.TButton').pack(side='left',padx=7)
        center=self.canvas.master
        top=self.canvas.pack_info()['in'] if False else center.winfo_children()[0]
        self.map_mode_var=tk.StringVar(value=self.map_mode)
        mode=ttk.Combobox(top,textvariable=self.map_mode_var,values=['Dünya Haritası','Uydu Görüntüsü','Google Uydu','Simülasyon Haritası (3D)'],state='readonly',width=24)
        self.map_mode_control=mode
        mode.pack(side='right',padx=10)
        mode.bind('<<ComboboxSelected>>',self.change_map_mode)
        ttk.Button(top,text='Haritayı yenile',command=self.refresh_maps,style='Dark.TButton').pack(side='right',padx=5)
        mapbar=self.mapbar_location_host
        self.location_button=tk.Button(mapbar,text='◎  Konumumu bul',command=self.request_pc_location,bg='#292b2f',fg=WHITE,
                                       activebackground='#3b3e43',activeforeground=WHITE,relief='flat',bd=0,padx=10,pady=6,
                                       font=('Segoe UI',9,'bold'),cursor='hand2')
        self.location_button.pack(side='right',padx=(5,0))
        self.coordinate_button=tk.Button(mapbar,text='⌖  Koordinat gir',command=self.add_coordinate_marker,
                                         bg='#292b2f',fg=WHITE,activebackground='#3b3e43',activeforeground=WHITE,
                                         relief='flat',bd=0,padx=10,pady=6,font=('Segoe UI',9,'bold'),cursor='hand2')
        self.coordinate_button.pack(side='right',padx=5)
        self.canvas.bind('<ButtonPress-1>',self.map_press)
        self.canvas.bind('<B1-Motion>',self.map_drag)
        self.canvas.bind('<ButtonRelease-1>',self.map_release)
        self.canvas.bind('<MouseWheel>',self.map_wheel)
        self.canvas.bind('<Double-Button-1>',self.center_vehicle)
        self.build_xyz_overlay()
        self.build_map_credit()
        self.draw_map()

    def add_coordinate_marker(self):
        window=tk.Toplevel(self.root);window.title('Koordinatla nokta ekle');window.geometry('560x315');window.resizable(False,False);window.configure(bg=BLACK);window.transient(self.root)
        box=tk.Frame(window,bg=BLACK,padx=24,pady=20);box.pack(fill='both',expand=True)
        tk.Label(box,text='KOORDİNATLA NOKTA EKLE',bg=BLACK,fg=YELLOW,font=('Segoe UI',15,'bold')).pack(anchor='w')
        tk.Label(box,text='WGS84 koordinatı • Nokta görev planına eklenir',bg=BLACK,fg=GRAY,font=('Segoe UI',9)).pack(anchor='w',pady=(3,16))
        fields=tk.Frame(box,bg=BLACK);fields.pack(fill='x',pady=(0,10))
        vars={key:tk.StringVar() for key in ('Enlem','Boylam','İrtifa (HOME üstü m)')}
        for col,key in enumerate(vars):
            tk.Label(fields,text=key,bg=BLACK,fg=WHITE,font=('Segoe UI',9,'bold')).grid(row=0,column=col,padx=(0,10),sticky='w')
            entry=tk.Entry(fields,textvariable=vars[key],width=19,bg='#24272b',fg=WHITE,insertbackground=YELLOW,selectbackground='#6b5b1d',relief='flat',font=('Consolas',10))
            entry.grid(row=1,column=col,padx=(0,10),pady=(6,0),ipady=6)
        tk.Label(box,text='Enlem  -90…90   •   Boylam  -180…180   •   İrtifa HOME üstü, 0’dan büyük',bg=BLACK,fg=GRAY,font=('Segoe UI',9)).pack(anchor='w',pady=(0,16))
        def add():
            try:
                lat=float(vars['Enlem'].get().replace(',','.'));lon=float(vars['Boylam'].get().replace(',','.'));alt=float(vars['İrtifa (HOME üstü m)'].get().replace(',','.'))
                from mission_transfer import validate_points
                validate_points([(lat,lon,alt)])
            except (ValueError,KeyError) as exc:
                messagebox.showerror('Koordinat',str(exc) or 'Koordinatları kontrol edin.',parent=window);return
            self.markers.append((lat,lon,alt));self.update_marker_buttons();self.view_center[:]=[lat,lon];self.draw_map();self.event(f'WGS84 koordinatı eklendi: {lat:.7f}, {lon:.7f}, HOME +{alt:.1f} m');window.destroy()
        actions=tk.Frame(box,bg=BLACK);actions.pack(fill='x')
        tk.Button(actions,text='✓  Noktayı ekle',command=add,bg=YELLOW,fg=BLACK,activebackground='#ffe36a',relief='flat',bd=0,padx=18,pady=9,font=('Segoe UI',10,'bold'),cursor='hand2').pack(side='left')
        tk.Button(actions,text='İptal',command=window.destroy,bg='#292b2f',fg=WHITE,activebackground='#3b3e43',relief='flat',bd=0,padx=22,pady=9,font=('Segoe UI',10,'bold'),cursor='hand2').pack(side='left',padx=10)

    def build_map_credit(self):
        self.map_credit_button=tk.Button(self.canvas,text='© OpenStreetMap contributors',command=self.show_map_licenses,
                                         bg='#111315',fg='#d8d8d8',activebackground='#292c30',activeforeground=WHITE,
                                         relief='flat',bd=0,padx=6,pady=2,font=('Segoe UI',7),cursor='hand2')
        self.map_credit_button.place(relx=0.0,rely=1.0,x=8,y=-8,anchor='sw')

    def update_map_credit(self):
        if not hasattr(self,'map_credit_button'):return
        if self.map_mode=='Dünya Haritası':
            text='© OpenStreetMap contributors'
        elif self.map_mode=='Uydu Görüntüsü':
            text='© Esri • Maxar • Earthstar • GIS Community'
        elif self.map_mode=='Google Uydu':
            text='Google Maps Platform • Static satellite'
        else:text='ⓘ Fentek Havacılık • Harita kaynakları'
        self.map_credit_button.configure(text=text)
        if self.map_mode=='Google Uydu':self.map_credit_button.place(relx=0.0,rely=0.0,x=8,y=8,anchor='nw')
        else:self.map_credit_button.place(relx=0.0,rely=1.0,x=8,y=-8,anchor='sw')

    def show_map_licenses(self):
        existing=getattr(self,'license_window',None)
        if existing and existing.winfo_exists():
            existing.lift();existing.focus_force();return
        window=tk.Toplevel(self.root)
        self.license_window=window
        window.title('Fentek Havacılık • Harita Kaynakları ve Lisanslar')
        screen_w,screen_h=window.winfo_screenwidth(),window.winfo_screenheight()
        width=min(860,max(680,screen_w-180))
        height=min(690,max(540,screen_h-180))
        window.geometry(f'{width}x{height}')
        window.minsize(640,520)
        window.configure(bg=BLACK)
        header=tk.Frame(window,bg=SURFACE,padx=18,pady=14)
        header.pack(fill='x')
        tk.Label(header,text='HARİTA KAYNAKLARI VE LİSANSLAR',bg=SURFACE,fg=YELLOW,font=('Segoe UI',15,'bold')).pack(anchor='w')
        tk.Label(header,text='Fentek Havacılık • veri kaynakları, telifler ve kullanım notları',bg=SURFACE,fg=GRAY,font=('Segoe UI',9)).pack(anchor='w',pady=(4,0))
        # Pack the footer first so the expanding text area can never cover its buttons.
        links=tk.Frame(window,bg=BLACK,padx=16,pady=12)
        links.pack(side='bottom',fill='x')
        link_specs=(
            ('OpenStreetMap lisansı','https://www.openstreetmap.org/copyright',True),
            ('OSM döşeme kuralları','https://operations.osmfoundation.org/policies/tiles/',False),
            ('Esri atıf bilgisi','https://developers.arcgis.com/documentation/glossary/data-attribution/',False),
            ('Google Maps koşulları','https://cloud.google.com/maps-platform/terms',False))
        for label,url,primary in link_specs:
            tk.Button(links,text=label,command=lambda u=url:webbrowser.open(u),bg=YELLOW if primary else '#292c30',
                      fg=BLACK if primary else WHITE,activebackground='#ffe46b' if primary else '#41454a',
                      activeforeground=BLACK if primary else WHITE,relief='flat',bd=0,padx=12,pady=8,
                      font=('Segoe UI',9,'bold'),cursor='hand2').pack(side='left',padx=(0,8))
        tk.Button(links,text='Kapat',command=window.destroy,bg=YELLOW,fg=BLACK,activebackground='#ffe46b',
                  activeforeground=BLACK,relief='flat',bd=0,padx=22,pady=8,font=('Segoe UI',9,'bold'),
                  cursor='hand2').pack(side='right')
        body_host=tk.Frame(window,bg=BLACK)
        body_host.pack(fill='both',expand=True,padx=16,pady=14)
        scroll=ttk.Scrollbar(body_host,orient='vertical')
        scroll.pack(side='right',fill='y')
        body=tk.Text(body_host,bg='#111315',fg=WHITE,insertbackground=YELLOW,relief='flat',wrap='word',padx=18,pady=16,
                     font=('Segoe UI',10),cursor='arrow',yscrollcommand=scroll.set)
        body.pack(side='left',fill='both',expand=True)
        scroll.configure(command=body.yview)
        content=(
            '1. DÜNYA HARİTASI — OPENSTREETMAP\n\n'
            'Harita verisi © OpenStreetMap contributors. Veriler Open Database License (ODbL) 1.0 kapsamında kullanılır. '
            'Standart harita döşemeleri OpenStreetMap Foundation altyapısından alınır.\n\n'
            '2. UYDU GÖRÜNTÜSÜ — ESRI WORLD IMAGERY\n\n'
            'Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community. '
            'Uydu katmanı canlı kamera yayını değildir; sağlayıcı tarafından hazırlanmış harita görüntüleridir.\n\n'
            '3. GOOGLE UYDU — MAPS STATIC API\n\n'
            'Google uydu seçeneği kullanıcının API anahtarıyla Maps Static API üzerinden alınır. Google logosu ve atfı görüntü içinde korunur. '
            'Anahtar dosyaya yazılmaz. API etkinliği, kota, faturalandırma ve kullanım koşulları Google hesabına bağlıdır.\n\n'
            '4. ŞEHİR VE ÜLKE ÇÖZÜMLEMESİ\n\n'
            'Yer adı sonuçları OpenStreetMap verisini kullanan Nominatim hizmetinden alınır. Sonuçlar yaklaşık olabilir.\n\n'
            '5. FENTEK HAVACILIK UYGULAMA NOTLARI\n\n'
            'Fentek Havacılık, üçüncü taraf harita verilerinin sahibi olduğunu iddia etmez. Harita görüntüleri yedi gün yerel '
            'önbellekte tutulabilir. Sentetik demo konumu, gerçek uçuş veya canlı uydu takibi anlamına gelmez. İnternet erişimi '
            've harita servislerinin kullanılabilirliği ilgili sağlayıcılara bağlıdır.\n')
        body.insert('1.0',content)
        body.configure(state='disabled')

    def build_xyz_overlay(self):
        panel=tk.Frame(self.canvas,bg='#111315',highlightthickness=1,highlightbackground='#65571e',padx=10,pady=8)
        panel.place(relx=1.0,x=-14,y=14,anchor='ne')
        self.xyz_panel=panel
        top=tk.Frame(panel,bg='#111315')
        top.pack(fill='x',pady=(0,5))
        tk.Label(top,text='YEREL KOORDİNAT',bg='#111315',fg=YELLOW,font=('Segoe UI',9,'bold')).pack(side='left')
        tk.Label(top,text='metre',bg='#111315',fg=GRAY,font=('Segoe UI',8)).pack(side='right')
        self.xyz_vars={axis:tk.StringVar(value='0.0') for axis in ('X','Y','Z')}
        self.xyz_entries=[]
        fields=tk.Frame(panel,bg='#111315')
        fields.pack(fill='x')
        for axis in ('X','Y','Z'):
            cell=tk.Frame(fields,bg='#111315')
            cell.pack(side='left',padx=3)
            tk.Label(cell,text=axis,bg='#111315',fg=YELLOW,font=('Segoe UI',8,'bold')).pack(anchor='w')
            entry=tk.Entry(cell,textvariable=self.xyz_vars[axis],width=8,bg='#24272b',fg=WHITE,insertbackground=YELLOW,
                           selectbackground='#6b5b1d',relief='flat',font=('Consolas',9),justify='right')
            entry.pack(ipady=4)
            self.xyz_entries.append(entry)
        actions=tk.Frame(panel,bg='#111315')
        actions.pack(fill='x',pady=(7,0))
        self.xyz_button(actions,'İHA’dan al',self.load_vehicle_xyz).pack(side='left')
        self.xyz_button(actions,'Nokta koy',self.add_xyz_marker,True).pack(side='left',padx=5)
        self.xyz_button(actions,'Kopyala',self.copy_xyz).pack(side='left')
        self.load_vehicle_xyz()

    def xyz_button(self,parent,text,command,primary=False):
        return tk.Button(parent,text=text,command=command,bg=YELLOW if primary else '#2a2d31',fg=BLACK if primary else WHITE,
                         activebackground='#ffe36a' if primary else '#41454a',activeforeground=BLACK if primary else WHITE,
                         relief='flat',bd=0,padx=7,pady=4,font=('Segoe UI',8,'bold'),cursor='hand2')

    def vehicle_xyz(self):
        home=self.flight_center
        north=(self.data['lat']-home[0])*111320
        east=(self.data['lon']-home[1])*111320*math.cos(math.radians(home[0]))
        return east,north,self.data['altitude']

    def load_vehicle_xyz(self):
        if getattr(self,'live_map',None) and self.live_map.enabled:return
        for axis,value in zip(('X','Y','Z'),self.vehicle_xyz()):self.xyz_vars[axis].set(f'{value:.1f}')

    def read_xyz(self):
        try:
            values=tuple(float(self.xyz_vars[axis].get().replace(',','.')) for axis in ('X','Y','Z'))
            if not all(math.isfinite(value) and abs(value)<=1_000_000 for value in values):raise ValueError
            return values
        except ValueError:
            messagebox.showerror('X / Y / Z','X, Y ve Z alanlarına geçerli metre değerleri girin.')
            return None

    def copy_xyz(self):
        values=self.read_xyz()
        if values is None:return
        text='X: {:.1f} m   Y: {:.1f} m   Z: {:.1f} m'.format(*values)
        self.root.clipboard_clear();self.root.clipboard_append(text)
        self.event('X / Y / Z koordinatları panoya kopyalandı.')

    def add_xyz_marker(self):
        if getattr(self,'live_map',None) and self.live_map.enabled:
            messagebox.showinfo('Koordinat','Canlı NED değerleri kartın yerel başlangıcına göredir. Görev noktalarını enlem/boylam haritasından ekleyin.');return
        values=self.read_xyz()
        if values is None:return
        east,north,altitude=values
        home=self.flight_center
        lat=home[0]+north/111320
        lon=home[1]+east/(111320*math.cos(math.radians(home[0])))
        self.markers.append((lat,lon,altitude))
        self.update_marker_buttons();self.draw_map()
        self.event(f'X {east:.1f}, Y {north:.1f}, Z {altitude:.1f} m koordinatına nokta eklendi.')

    def build_map_settings(self):
        page=self.pages['Harita ayarları']
        for child in page.winfo_children():child.destroy()
        self.heading(page,'HARİTA SEÇİMİ','Sokak haritası, uydu görüntüsü ve 3D simülasyon ayrı sistemlerdir.')
        for title,description,mode in [
            ('DÜNYA HARİTASI','Gönderdiğiniz app.py ile aynı OpenStreetMap haritası. Sokaklar, yapılar ve yer adları gerçek harita katmanında görünür. İnternet ilk yüklemede gerekir.','Dünya Haritası'),
            ('UYDU GÖRÜNTÜSÜ','Gönderdiğiniz index.html ile aynı Esri World Imagery katmanı. API anahtarı gerekmez; internet bağlantısı gerekir.','Uydu Görüntüsü'),
            ('GOOGLE UYDU','Google Maps Static API uydu görüntüsü. API anahtarı, etkin Maps Static API ve Google Cloud faturalandırması gerekir. Kaydırma/yakınlaştırma sonrası yeni merkez görüntüsü istenir.','Google Uydu'),
            ('SİMÜLASYON HARİTASI (3D)','OpenStreetMap yol ve bina verisinden 3D çevre. Bina yüksekliği bilinmiyorsa tahmin edilir. Veri yoksa örnek sahne gösterilir.','Simülasyon Haritası (3D)')]:
            box=tk.Frame(page,bg=SURFACE,padx=18,pady=16)
            box.pack(fill='x',pady=7)
            self.label(box,title,12,YELLOW,True).pack(anchor='w')
            tk.Label(box,text=description,bg=SURFACE,fg=GRAY,wraplength=760,justify='left',font=('Segoe UI',10)).pack(anchor='w',pady=8)
            ttk.Button(box,text=f'{mode} seç',command=lambda m=mode:self.set_map_mode(m)).pack(anchor='w')
        keybox=tk.Frame(page,bg=SURFACE,padx=18,pady=14);keybox.pack(fill='x',pady=7)
        self.label(keybox,'GOOGLE MAPS API ANAHTARI',12,YELLOW,True).pack(anchor='w')
        row=tk.Frame(keybox,bg=SURFACE);row.pack(fill='x',pady=8)
        self.google_key_var=tk.StringVar(value=self.google_maps_key)
        tk.Entry(row,textvariable=self.google_key_var,show='•',width=52,bg='#24272b',fg=WHITE,insertbackground=YELLOW,relief='flat').pack(side='left',ipady=7)
        ttk.Button(row,text='Bu oturumda kullan',command=self.apply_google_key).pack(side='left',padx=8)
        self.label(keybox,'Anahtar dosyaya kaydedilmez. Kalıcı kullanmak isterseniz Windows’ta GOOGLE_MAPS_API_KEY ortam değişkenini tanımlayın.',9,GRAY).pack(anchor='w')
        self.map_settings_status=tk.StringVar(value='Etkin görünüm: '+self.map_mode)
        tk.Label(page,textvariable=self.map_settings_status,bg=BLACK,fg=WHITE,font=('Segoe UI',11,'bold')).pack(anchor='w',pady=14)
        self.label(page,'Uydu görüntüsünün çekim tarihi bölgeye göre değişir. Yenileme, sağlayıcının sunduğu veriyi kullanır.',9,GRAY).pack(anchor='w')

    def apply_google_key(self):
        self.google_maps_key=self.google_key_var.get().strip()
        if not self.google_maps_key:messagebox.showinfo('Google Maps','Anahtar boş bırakıldı. Google uydu görünümü yüklenmez.');return
        self.google_loaded_signature=None
        self.map_status.set('Google Maps anahtarı bu oturum için alındı; dosyaya kaydedilmedi.')
        if self.map_mode=='Google Uydu':self.load_map()

    def load_map(self):
        if getattr(self,'map_tile_source','osm')!='google':return Atlas.load_map(self)
        if self.google_loading:
            self.google_reload_pending=True;return
        key=self.google_maps_key.strip()
        if not key:
            # Google Static Maps cannot return imagery without a billable API key.
            # Fall back immediately instead of leaving a blank map that appears to hang.
            self.map_mode='Uydu Görüntüsü';self.map_mode_var.set(self.map_mode)
            self.map_tile_source='esri';self.osm_enabled=True;self.image=None
            self.update_map_credit()
            if hasattr(self,'map_settings_status'):self.map_settings_status.set('Etkin görünüm: '+self.map_mode)
            self.layer.set('ESRI WORLD IMAGERY • UYDU GÖRÜNTÜSÜ')
            self.map_status.set('Google anahtarı yok • ücretsiz Esri uydu görünümüne geçildi.')
            Atlas.load_map(self);return
        self.root.update_idletasks();lat,lon=self.view_center;zoom=self.view_zoom
        signature=(round(float(lat),4),round(float(lon),4),int(zoom))
        if signature==self.google_loaded_signature and self.google_image is not None:
            self.image=self.google_image
            self.map_status.set('Google uydu hazır • mevcut görüntü yeniden kullanıldı.')
            self.draw_map();return
        self.google_loading=True;self.google_reload_pending=False;self.image=None
        self.google_request_signature=signature
        self.map_status.set('Google uydu görüntüsü yükleniyor… API kullanımı kotaya/ücretlendirmeye tabi olabilir.')
        url=google_static_url(lat,lon,zoom,key)
        def worker():
            try:
                req=Request(url,headers={'User-Agent':'Fentek-Havacilik/1.0'})
                with urlopen(req,timeout=8) as response:data=response.read(5_000_000)
                if not data.startswith(b'\x89PNG'):raise ValueError('Google geçerli PNG görüntüsü döndürmedi; API, kota ve faturalandırmayı kontrol edin.')
                self.google_queue.put(('ok',(lat,lon,zoom,signature,data)))
            except HTTPError as exc:
                notes={400:'istek geçersiz',403:'anahtar, Maps Static API veya faturalandırma etkin değil',429:'Google kotası aşıldı'}
                self.google_queue.put(('error',f'Google HTTP {exc.code}: {notes.get(exc.code,"sunucu isteği reddetti")}'))
            except (URLError,TimeoutError):
                self.google_queue.put(('error','Google sunucusuna zamanında ulaşılamadı. İnternet bağlantısını kontrol edin.'))
            except Exception as exc:self.google_queue.put(('error',str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def poll_google(self):
        try:
            kind,value=self.google_queue.get_nowait();self.google_loading=False
            if kind=='ok':
                lat,lon,zoom,signature,data=value
                try:self.google_image=tk.PhotoImage(data=base64.b64encode(data));self.image=self.google_image
                except tk.TclError:self.image=None;self.map_status.set('Google görüntüsü açılamadı.')
                else:
                    self.google_loaded_signature=signature
                    self.map_status.set(f'Google uydu hazır • merkez {lat:.5f}, {lon:.5f} • yakınlaştırma {zoom}')
                    self.draw_map()
            else:
                # Keep the map usable when Google rejects the key or the request
                # times out. The error remains in the event log for diagnosis.
                self.event('Google uydu alınamadı: '+value)
                self.map_mode='Uydu Görüntüsü';self.map_mode_var.set(self.map_mode)
                self.map_tile_source='esri';self.osm_enabled=True;self.image=None
                self.update_map_credit()
                if hasattr(self,'map_settings_status'):self.map_settings_status.set('Etkin görünüm: '+self.map_mode)
                self.layer.set('ESRI WORLD IMAGERY • UYDU GÖRÜNTÜSÜ')
                self.map_status.set('Google açılamadı • ücretsiz Esri uydu görünümüne geçiliyor…')
                Atlas.load_map(self)
            if self.google_reload_pending:
                self.google_reload_pending=False;self.root.after_idle(self.load_map)
        except queue.Empty:pass
        self.google_job=self.root.after(120,self.poll_google)

    def refresh_maps(self):
        if self.tile_loading or self.feature_loading or self.google_loading:
            self.map_status.set('Yükleme sürüyor; tamamlanınca yeniden deneyin.')
            return
        self.tiles.clear()
        self.tile_times.clear()
        self.world_center[:]=self.flight_center
        self.world_features=[]
        if self.map_mode=='Simülasyon Haritası (3D)':self.load_world_features()
        else:self.load_map()
        self.draw_map()

    def set_map_mode(self,mode):
        self.map_mode_var.set(mode)
        self.change_map_mode()

    def change_aircraft(self,event=None):
        self.aircraft_type=self.aircraft_var.get()
        if getattr(self,'operations',None) and not self.live_map.enabled:
            self.operations.offline_modes(self.aircraft_type)
        self.event('İHA profili seçildi: '+self.aircraft_type+' (sentetik).')
        self.draw_map()

    def pause(self):
        super().pause()
        if hasattr(self,'quick_pause'):self.quick_pause['text']='▶  Devam et' if not self.running else '⏸  Duraklat'

    def reset(self):
        if getattr(self,'live_map',None) and self.live_map.enabled:return
        super().reset()
        if hasattr(self,'quick_pause'):self.quick_pause['text']='⏸  Duraklat'
        if hasattr(self,'quick_link'):self.quick_link['text']='⌁  Bağlantı kaybını dene'

    def toggle_link(self):
        super().toggle_link()
        if hasattr(self,'quick_link'):self.quick_link['text']='⌁  Bağlantıyı geri getir' if not self.link else '⌁  Bağlantı kaybını dene'

    def change_map_mode(self,event=None):
        if getattr(self,'live_map',None) and self.live_map.enabled and self.map_mode_var.get()=='Simülasyon Haritası (3D)':
            self.map_mode_var.set('Dünya Haritası')
        self.map_mode=self.map_mode_var.get()
        self.update_map_credit()
        if hasattr(self,'map_settings_status'):self.map_settings_status.set('Etkin görünüm: '+self.map_mode)
        if self.map_mode=='Dünya Haritası':
            self.map_tile_source='osm'
            self.layer.set('OPENSTREETMAP • GERÇEK DÜNYA HARİTASI')
            self.map_status.set('OpenStreetMap görüntüleri yükleniyor…')
            self.osm_enabled=True
            self.load_map()
        elif self.map_mode=='Uydu Görüntüsü':
            self.map_tile_source='esri'
            self.layer.set('ESRI WORLD IMAGERY • UYDU GÖRÜNTÜSÜ')
            self.map_status.set('Esri uydu görüntüleri yükleniyor…')
            self.osm_enabled=True
            self.load_map()
        elif self.map_mode=='Google Uydu':
            self.map_tile_source='google';self.osm_enabled=True
            self.layer.set('GOOGLE MAPS STATIC API • UYDU GÖRÜNTÜSÜ')
            self.map_status.set('Google uydu görüntüsü hazırlanıyor…')
            self.load_map()
        else:
            self.layer.set('SİMÜLASYON HARİTASI 3D • SENTETİK SAHNE')
            self.map_status.set('Simülasyon haritası • Fareyle döndür, tekerlekle akıcı yaklaş/uzaklaş.')
            self.world_center[:]=self.flight_center
            self.load_world_features()
            self.draw_map()

    def request_pc_location(self):
        if getattr(self,'live_map',None) and self.live_map.enabled:return
        if self.location_pending:return
        self.location_pending=True
        self.location_button['state']='disabled'
        self.map_status.set('Windows konum izni ve konum servisi bekleniyor…')
        script=("Add-Type -AssemblyName System.Device;"
                "$w=New-Object System.Device.Location.GeoCoordinateWatcher([System.Device.Location.GeoPositionAccuracy]::High);"
                "$w.Start();$d=(Get-Date).AddSeconds(12);"
                "while($w.Position.Location.IsUnknown -and (Get-Date) -lt $d){Start-Sleep -Milliseconds 200};"
                "$c=$w.Position.Location;$w.Stop();"
                "if($c.IsUnknown){exit 2};"
                "[Console]::WriteLine(('{0};{1};{2}' -f $c.Latitude,$c.Longitude,$c.HorizontalAccuracy))")
        def worker():
            try:
                flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
                result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],capture_output=True,text=True,timeout=16,creationflags=flags)
                if result.returncode:raise RuntimeError()
                self.location_result.put(('ok',parse_windows_location(result.stdout)))
            except Exception:
                self.location_result.put(('error','Bilgisayar konumu alınamadı. Windows Ayarlar > Gizlilik ve güvenlik > Konum bölümünü kontrol edin.'))
        threading.Thread(target=worker,daemon=True).start()

    def poll_location(self):
        try:
            kind,value=self.location_result.get_nowait()
            if kind=='ok':
                if getattr(self,'live_map',None) and self.live_map.enabled:
                    self.location_pending=False
                    self.location_job=self.root.after(120,self.poll_location)
                    return
                self.location_pending=False
                self.location_button['state']='normal'
                self.pc_location=value
                self.flight_center=tuple(value[:2])
                self.data=sample(self.t,self.flight_center)
                self.track=[]
                self.view_center[:]=value[:2]
                self.world_center[:]=value[:2]
                self.world_features=[]
                self.map_status.set(f'Bilgisayar konumu bulundu • yaklaşık doğruluk: {value[2]:.0f} m')
                self.event(f'Bilgisayar konumu kullanıcı isteğiyle alındı; doğruluk yaklaşık {value[2]:.0f} m.')
                self.request_place(*value[:2])
                if self.map_mode in ('Dünya Haritası','Uydu Görüntüsü'):self.load_map()
                else:self.load_world_features()
                self.draw_map()
            elif kind=='error':
                self.location_pending=False
                self.location_button['state']='normal'
                self.map_status.set(value)
                self.request_place(*self.flight_center)
            elif kind=='place':
                self.place_city,self.place_country=value
                self.event(f'Konum bilgisi: {self.place_city}, {self.place_country}.')
                self.update_cockpit_rows()
            elif kind=='place_error':
                self.place_city,self.place_country='Bilinmiyor','Bilinmiyor'
                self.update_cockpit_rows()
        except queue.Empty:pass
        self.location_job=self.root.after(120,self.poll_location)

    def request_place(self,lat,lon):
        def worker():
            try:
                query=urlencode({'lat':f'{lat:.7f}','lon':f'{lon:.7f}','format':'jsonv2','zoom':'10','addressdetails':'1','accept-language':'tr'})
                req=Request('https://nominatim.openstreetmap.org/reverse?'+query,headers={'User-Agent':'Fentek-Havacilik/1.0 (desktop ground station)'})
                with urlopen(req,timeout=12) as response:data=json.loads(response.read(500000).decode('utf-8'))
                address=data.get('address',{})
                city=next((address.get(k) for k in ('city','town','village','municipality','county','state') if address.get(k)),None)
                country=address.get('country')
                if not city or not country:raise ValueError('Yer adı bulunamadı')
                self.location_result.put(('place',(city,country)))
            except Exception:self.location_result.put(('place_error',None))
        threading.Thread(target=worker,daemon=True).start()

    def map_wheel(self,event):
        if self.map_mode!='Simülasyon Haritası (3D)':return Atlas.map_wheel(self,event)
        factor=.82 if event.delta>0 else 1.22
        self.zoom_target=max(180,min(1400,self.zoom_target*factor))
        if not self.zoom_job:self.animate_zoom()

    def animate_zoom(self):
        difference=self.zoom_target-self.camera_distance
        if abs(difference)<.6:
            self.camera_distance=self.zoom_target
            self.zoom_job=None
            self.draw_map()
            return
        self.camera_distance+=difference*.18
        self.draw_map()
        self.zoom_job=self.root.after(16,self.animate_zoom)

    def map_press(self,event):
        if self.map_mode!='Simülasyon Haritası (3D)':return Atlas.map_press(self,event)
        if self.marking:return
        self.drag_3d=(event.x,event.y,self.camera_yaw,self.camera_tilt)
        self.canvas.configure(cursor='hand2')

    def map_drag(self,event):
        if self.map_mode!='Simülasyon Haritası (3D)':return Atlas.map_drag(self,event)
        if not self.drag_3d:return
        self.camera_yaw=self.drag_3d[2]+(event.x-self.drag_3d[0])*.25
        self.camera_tilt=max(20,min(75,self.drag_3d[3]-(event.y-self.drag_3d[1])*.18))
        self.draw_map()

    def map_release(self,event):
        if self.map_mode!='Simülasyon Haritası (3D)':return Atlas.map_release(self,event)
        self.drag_3d=None
        self.canvas.configure(cursor='fleur')

    def center_vehicle(self,event=None):
        if self.map_mode!='Simülasyon Haritası (3D)':return Atlas.center_vehicle(self,event)
        self.camera_yaw=-25
        self.camera_tilt=48
        self.zoom_target=520
        if not self.zoom_job:self.animate_zoom()

    def project(self,east,north,altitude=0):
        w,h=self.canvas.winfo_width(),self.canvas.winfo_height()
        yaw=math.radians(self.camera_yaw)
        rx=east*math.cos(yaw)-north*math.sin(yaw)
        depth=east*math.sin(yaw)+north*math.cos(yaw)
        scale=520/self.camera_distance
        tilt=math.radians(self.camera_tilt)
        return w/2+rx*scale,h*.53+depth*scale*math.sin(tilt)-altitude*scale*math.cos(tilt)

    def draw_aircraft(self,c,x,y,heading,size=1):
        angle=math.radians(heading)
        scene=self.map_mode=='Simülasyon Haritası (3D)'
        def p(a,b):
            if not scene:
                return x+(a*math.cos(angle)-b*math.sin(angle))*size,y+(a*math.sin(angle)+b*math.cos(angle))*size
            roll=math.radians(self.data.get('roll',0))
            pitch=math.radians(self.data.get('pitch',0))
            forward=-b
            right=a*math.cos(roll)
            up=-a*math.sin(roll)
            forward,up=forward*math.cos(pitch)-up*math.sin(pitch),forward*math.sin(pitch)+up*math.cos(pitch)
            east=right*math.cos(angle)+forward*math.sin(angle)
            north=-right*math.sin(angle)+forward*math.cos(angle)
            yaw=math.radians(self.camera_yaw)
            tilt=math.radians(self.camera_tilt)
            return (x+(east*math.cos(yaw)-north*math.sin(yaw))*size,
                    y+((east*math.sin(yaw)+north*math.cos(yaw))*math.sin(tilt)-up*math.cos(tilt))*size)
        def disc(a,b,r,fill,outline,width=1):
            points=[p(a+r*math.cos(i*math.tau/24),b+r*math.sin(i*math.tau/24)) for i in range(24)]
            c.create_polygon(*[v for q in points for v in q],fill=fill,outline=outline,width=width,smooth=True)
        if self.aircraft_type=='Sabit kanat':
            shape=[p(0,-22),p(-5,-3),p(-25,7),p(-5,9),p(-4,19),p(4,19),p(5,9),p(25,7),p(5,-3)]
            shadow=[(px+3,py+4) for px,py in shape]
            c.create_polygon(*[v for q in shadow for v in q],fill='#050606',outline='')
            c.create_polygon(*[v for q in shape for v in q],fill=YELLOW,outline='#fff0a0',width=2)
            c.create_line(*p(0,-18),*p(0,15),fill='#6f5710',width=max(1,int(2*size)))
            disc(0,-2,3,'#111315',WHITE)
        elif self.aircraft_type=='FPV':
            c.create_line(*p(-13,-13),*p(13,13),fill=BLACK,width=max(6,int(8*size)))
            c.create_line(*p(13,-13),*p(-13,13),fill=BLACK,width=max(6,int(8*size)))
            for a,b in [(-11,-11),(11,-11),(-11,11),(11,11)]:
                disc(a,b,7,'#222629','#fff5bd',2)
                c.create_line(*p(a-5,b),*p(a+5,b),fill=YELLOW,width=2)
            frame=[p(0,-13),p(-8,1),p(-5,11),p(5,11),p(8,1)]
            c.create_polygon(*[v for q in frame for v in q],fill='#f0ad24',outline=WHITE,width=2)
            disc(0,-4,4,'#162d39','#79d8ff')
        else:
            c.create_line(*p(-15,-15),*p(15,15),fill=BLACK,width=max(7,int(9*size)))
            c.create_line(*p(15,-15),*p(-15,15),fill=BLACK,width=max(7,int(9*size)))
            for a,b in [(-14,-14),(14,-14),(-14,14),(14,14)]:
                disc(a,b,8,'#202427',WHITE,2)
                disc(a,b,2.8,YELLOW,BLACK)
            body=[p(0,-14),p(-8,-3),p(-7,9),p(0,13),p(7,9),p(8,-3)]
            c.create_polygon(*[v for q in body for v in q],fill='#f3bd24',outline='#fff1a8',width=2)
            c.create_polygon(*[v for q in [p(0,-13),p(-4,-5),p(4,-5)] for v in q],fill='#ff6f32',outline='')

    def draw_vehicle_marker(self,c,x,y,heading):
        if getattr(self,'live_map',None) and self.live_map.enabled and self.live_map.state.position is None:return
        pulse=30+(time.monotonic()%1.4)*7
        color=YELLOW if self.link else '#ff8c67'
        c.create_oval(x-pulse,y-pulse,x+pulse,y+pulse,outline='#8e7923',width=1)
        c.create_oval(x-25,y-25,x+25,y+25,outline=color,width=2)
        # Atlas map is north-up; compensate for the 3D camera yaw used by draw_aircraft.
        saved_yaw=self.camera_yaw
        self.camera_yaw=0
        try:self.draw_aircraft(c,x,y,heading,1.0)
        finally:self.camera_yaw=saved_yaw
        label=self.aircraft_type.upper() if self.link else 'SON KONUM'
        c.create_rectangle(x+31,y-25,x+148,y+3,fill='#111315',outline='#514719',width=1)
        c.create_text(x+39,y-11,text=label,fill=WHITE,anchor='w',font=('Segoe UI',9,'bold'))

    def marker_xy(self,marker):
        if self.map_mode!='Simülasyon Haritası (3D)':return self.map_xy(*marker[:2])
        north=(marker[0]-self.flight_center[0])*111320
        east=(marker[1]-self.flight_center[1])*111320*math.cos(math.radians(self.flight_center[0]))
        return self.project(east,north,marker[2] if len(marker)>2 else 0)

    def draw_map(self):
        if getattr(self,'map_mode','Dünya Haritası') in ('Dünya Haritası','Uydu Görüntüsü','Google Uydu'):
            return Atlas.draw_map(self)
        c=self.canvas;c.delete('all')
        w,h=c.winfo_width(),c.winfo_height()
        if w<10:return
        c.create_rectangle(0,0,w,h,fill='#11161b',outline='')
        c.create_rectangle(0,0,w,h*.28,fill='#17232b',outline='')
        # Perspective ground grid is the base of the offline 3D simulation.
        for n in range(-400,401,50):
            p1=self.project(-400,n);p2=self.project(400,n)
            c.create_line(*p1,*p2,fill='#34372f')
            p1=self.project(n,-400);p2=self.project(n,400)
            c.create_line(*p1,*p2,fill='#34372f')
        if self.world_features:self.draw_world_features(c)
        for east,north,height in ([] if self.world_features else [(-210,-80,38),(-145,110,55),(190,-120,70),(245,95,42),(-25,210,62)]):
            self.draw_building(c,[(east-25,north-20),(east+25,north-20),(east+25,north+20),(east-25,north+20)],height)
        route=[]
        for t in ([] if getattr(self,'live_map',None) and self.live_map.enabled else range(64)):
            d=sample(t,self.flight_center)
            north=(d['lat']-self.flight_center[0])*111320;east=(d['lon']-self.flight_center[1])*111320*math.cos(math.radians(self.flight_center[0]))
            route.extend(self.project(east,north,d['altitude']))
        if len(route)>=4:c.create_line(*route,fill='#8f813a',width=2,dash=(5,5),smooth=True)
        d=self.data
        north=(d['lat']-self.flight_center[0])*111320;east=(d['lon']-self.flight_center[1])*111320*math.cos(math.radians(self.flight_center[0]))
        x,y=self.project(east,north,d['altitude'])
        pulse=28+(time.monotonic()%1.5)*10
        c.create_oval(x-pulse,y-pulse/2,x+pulse,y+pulse/2,outline='#9e8c32')
        self.draw_aircraft(c,x,y,d['heading'],1.1)
        c.create_text(x+25,y-22,text=self.aircraft_type.upper(),anchor='w',fill=WHITE,font=('Segoe UI',9,'bold'))
        if self.pc_location:
            # PC marker is shown only if it lies close enough to this synthetic scene.
            pn=(self.pc_location[0]-self.flight_center[0])*111320;pe=(self.pc_location[1]-self.flight_center[1])*111320*math.cos(math.radians(self.flight_center[0]))
            if abs(pn)<1000 and abs(pe)<1000:
                px,py=self.project(pe,pn,0);c.create_rectangle(px-6,py-6,px+6,py+6,fill='#5bbcff',outline=WHITE);c.create_text(px+10,py,text='BİLGİSAYAR',anchor='w',fill='#8dccff',font=('Segoe UI',8,'bold'))
        source='OSM YOL VE BİNALAR • YÜKSEKLİKLER KISMEN TAHMİNİ' if self.world_features else 'ÖRNEK SAHNE • HARİTA VERİSİ YOK'
        c.create_text(16,18,text=f'{source}  •  KAMERA {self.camera_distance:.0f} m  •  EĞİM {self.camera_tilt:.0f}°',anchor='w',fill=YELLOW,font=('Segoe UI',9,'bold'))
        c.create_text(w-12,h-12,text='3D çizim • Uydu fotoğrafı değildir',anchor='e',fill=GRAY,font=('Segoe UI',8))
        self.layer.set(self.map_mode.upper()+' • '+self.aircraft_type.upper())
        self.draw_map_markers()

    def draw_building(self,c,points,height):
        if len(points)<3:return
        base=[self.project(e,n) for e,n in points]
        top=[self.project(e,n,height) for e,n in points]
        for i in range(len(points)):
            j=(i+1)%len(points)
            c.create_polygon(*base[i],*base[j],*top[j],*top[i],fill='#30312d',outline='#55523d')
        c.create_polygon(*[v for point in top for v in point],fill='#5a5431',outline=YELLOW)

    def draw_world_features(self,c):
        buildings=[f for f in self.world_features if f['kind']=='building']
        roads=[f for f in self.world_features if f['kind']=='road']
        areas=[f for f in self.world_features if f['kind']=='area']
        for area in areas:
            coords=[]
            for east,north in area['points']:coords.extend(self.project(east,north,.05))
            if len(coords)>=6:c.create_polygon(*coords,fill='#26372a',outline='#425444')
        for road in roads:
            coords=[]
            for east,north in road['points']:coords.extend(self.project(east,north,.3))
            if len(coords)>=4:
                c.create_line(*coords,fill='#343436',width=road.get('width',7)+3,smooth=True)
                c.create_line(*coords,fill='#b0aa91',width=road.get('width',4),smooth=True)
                if road.get('name'):
                    middle=road['points'][len(road['points'])//2]
                    x,y=self.project(*middle,.5)
                    c.create_text(x,y-7,text=road['name'],fill='#d5d0bc',font=('Segoe UI',7))
        # Draw farther buildings first so nearby roofs remain visible.
        yaw=math.radians(self.camera_yaw)
        buildings.sort(key=lambda f:sum(e*math.sin(yaw)+n*math.cos(yaw) for e,n in f['points'])/len(f['points']))
        for building in buildings:self.draw_building(c,building['points'],building['height'])

    def load_world_features(self):
        if self.feature_loading:return
        lat,lon=self.world_center
        self.feature_loading=True
        self.map_status.set('Dünya haritası için OSM bina ve yolları yükleniyor…')
        cache=Path(__file__).parent/'map_cache'/f'features_v2_{lat:.4f}_{lon:.4f}.json'
        query=f'[out:json][timeout:20];(way["building"](around:450,{lat},{lon});way["highway"](around:450,{lat},{lon});way["leisure"="park"](around:450,{lat},{lon});way["landuse"~"grass|recreation_ground"](around:450,{lat},{lon}););out geom 600;'
        def worker():
            try:
                cache.parent.mkdir(exist_ok=True)
                if cache.exists() and time.time()-cache.stat().st_mtime<86400:data=json.loads(cache.read_text(encoding='utf-8'))
                else:
                    request=Request('https://overpass-api.de/api/interpreter?'+urlencode({'data':query}),headers={'User-Agent':'Fentek-Havacilik/1.0 (3D map viewer)'})
                    with urlopen(request,timeout=25) as response:
                        raw=response.read(5_000_001)
                        if len(raw)>5_000_000:raise ValueError('Yanıt çok büyük')
                    data=json.loads(raw)
                    cache.write_text(json.dumps(data),encoding='utf-8')
                features=[]
                for item in data.get('elements',[]):
                    geometry=item.get('geometry',[])
                    if len(geometry)<2:continue
                    points=[]
                    for point in geometry:
                        north=(point['lat']-lat)*111320
                        east=(point['lon']-lon)*111320*math.cos(math.radians(lat))
                        if abs(north)<=650 and abs(east)<=650:points.append((east,north))
                    if len(points)<2:continue
                    tags=item.get('tags',{})
                    if 'building' in tags and len(points)>=3:
                        try:height=float(str(tags.get('height','')).replace(' m',''))
                        except ValueError:
                            try:height=float(tags.get('building:levels',2))*3.2
                            except ValueError:height=7
                        features.append({'kind':'building','points':points[:80],'height':max(3,min(80,height))})
                    elif 'highway' in tags:
                        widths={'motorway':8,'trunk':8,'primary':7,'secondary':6,'tertiary':5,'residential':4,'service':3,'footway':2,'path':2}
                        features.append({'kind':'road','points':points[:100],'height':0,'width':widths.get(tags.get('highway'),3),'name':tags.get('name','')[:40]})
                    elif tags.get('leisure')=='park' or tags.get('landuse') in ('grass','recreation_ground'):
                        features.append({'kind':'area','points':points[:100],'height':0})
                def distance(feature):
                    point=feature['points'][len(feature['points'])//2]
                    return point[0]*point[0]+point[1]*point[1]
                buildings=sorted((f for f in features if f['kind']=='building'),key=distance)[:90]
                roads=sorted((f for f in features if f['kind']=='road'),key=distance)[:40]
                areas=sorted((f for f in features if f['kind']=='area'),key=distance)[:15]
                features=areas+roads+buildings
                self.feature_queue.put(('ok',((lat,lon),features)))
            except Exception:self.feature_queue.put(('error','Dünya haritası verisi alınamadı. Simülasyon haritasını kullanabilir veya tekrar deneyebilirsiniz.'))
        threading.Thread(target=worker,daemon=True).start()

    def poll_features(self):
        try:
            kind,value=self.feature_queue.get_nowait()
            self.feature_loading=False
            if kind=='ok':
                center,value=value
                if tuple(self.world_center)!=center:
                    self.load_world_features()
                    self.feature_job=self.root.after(120,self.poll_features)
                    return
                self.world_features=value
                buildings=sum(f['kind']=='building' for f in value);roads=sum(f['kind']=='road' for f in value);areas=sum(f['kind']=='area' for f in value)
                self.map_status.set(f'Dünya haritası hazır • {buildings} gerçek bina, {roads} yol, {areas} yeşil alan • İHA sentetik')
                self.event(f'OSM 3D sahnesi: {buildings} bina, {roads} yol ve {areas} alan yüklendi.')
                self.draw_map()
            else:self.map_status.set(value)
        except queue.Empty:pass
        self.feature_job=self.root.after(120,self.poll_features)

    def tick(self):
        if getattr(self,'live_map',None) and self.live_map.enabled:return self.live_map.tick()
        super().tick()

    def close(self):
        if getattr(self,'alert_manager',None):self.alert_manager.close()
        if getattr(self,'pilot_ari',None):self.pilot_ari.close()
        if getattr(self,'camera_view',None):self.camera_view.close()
        if getattr(self,'operations',None):self.operations.close()
        if getattr(self,'ground_tools',None):self.ground_tools.close()
        if getattr(self,'live_map',None):self.live_map.disconnect()
        if self.startup_intro:self.startup_intro.close()
        for job in (self.zoom_job,self.location_job,self.feature_job,self.google_job):
            if job:
                try:self.root.after_cancel(job)
                except tk.TclError:pass
        super().close()


if __name__=='__main__':
    root=tk.Tk()
    root.withdraw()
    root.attributes('-alpha',0.0)
    FlightPro(root)
    root.deiconify()
    root.mainloop()
