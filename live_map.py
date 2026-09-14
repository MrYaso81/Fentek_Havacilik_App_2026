import math
import queue
import threading
import sys
import time
from pathlib import Path
import tkinter as tk
from tkinter import ttk,messagebox
from connection import Session,endpoint
from live_position import PositionState
from safety_gate import SafetyGate


class LiveMap:
    def __init__(self,app):
        self.app=app;self.state=PositionState();self.safety=SafetyGate(self.state);self.enabled=False
        self.events=queue.Queue();self.stop=threading.Event();self.thread=None
        self.centered=False;self.last_map=0;self.connection='Bağlantı yok'
        self.follow=tk.BooleanVar(value=True)
        self.text=tk.StringVar(value='Gerçek konum bekleniyor…')
        self.panel=tk.Label(app.canvas,textvariable=self.text,bg='#111315',fg='#ffd42a',
                            justify='left',padx=10,pady=8,font=('Consolas',9))
        self.arm_button=None
        self.mission_button=None;self.session=None
        self.failsafe_values={}
        self.started_at=0;self.connected_once=False;self.lost_since=None
        self.auto_watch=tk.BooleanVar(value=True);self.auto_scanning=False;self.auto_next_scan=0
        self.auto_results=queue.Queue();self.auto_cancel=threading.Event();self.auto_job=app.root.after(700,self.auto_tick)
        self.auto_status=tk.StringVar(value='Bağlantı penceresi açılınca USB telemetri taranır.')
        self.setup_mode=tk.BooleanVar(value=False)

    def arm_toggle(self):
        if not self.enabled or not self.app.link or not self.session or not self.session.link:
            messagebox.showinfo('ARM','Önce canlı ve güncel Cube bağlantısı kurun.',parent=self.app.root);return
        target=not bool(self.state.armed)
        if target and not self.safety.allow('arm'):
            messagebox.showwarning('ARM engellendi',self.safety.summary(),parent=self.app.root);return
        if target and not messagebox.askyesno('ARM güvenlik onayı','Pervaneler takılı değil ve çevre güvenli mi?\nARM komutu karta gönderilecek.',parent=self.app.root):return
        if not target and not messagebox.askyesno('DISARM onayı','Kart DISARM komutu alacak. Devam edilsin mi?',parent=self.app.root):return
        self.session.commands.put(('arm',target))
        if self.arm_button:self.arm_button.configure(state='disabled')
        self.text.set(('ARM' if target else 'DISARM')+' komutu bekleniyor…')

    def request_stabilize(self):
        """Request the real vehicle's STABILIZE mode from the main cockpit button."""
        app=self.app
        if not self.enabled or not app.link or not self.session or not self.session.link:
            messagebox.showinfo('Denge modu','Canlı ve güncel Cube bağlantısı bekleniyor.',parent=app.root);return
        if str(self.state.mode).upper()=='STABILIZE':
            messagebox.showinfo('Denge modu','Cube Orange zaten STABILIZE denge modunda.',parent=app.root);return
        modes=getattr(getattr(app,'operations',None),'mode_names',())
        if modes and 'STABILIZE' not in modes:
            messagebox.showwarning('Denge modu','Bağlı araç STABILIZE modunu desteklediğini bildirmedi.',parent=app.root);return
        if not messagebox.askyesno('Gerçek Cube denge modu',
                'STABILIZE modu gerçek Cube Orange karta gönderilecek. Araç davranışı değişebilir. Devam edilsin mi?',parent=app.root):return
        self.session.commands.put(('mode','STABILIZE'))
        self.connection='STABILIZE modu gönderildi; kart doğrulaması bekleniyor.'
        self.text.set(self.connection)

    def dialog(self):
        if getattr(self,'window',None) and self.window.winfo_exists():self.window.lift();return
        w=tk.Toplevel(self.app.root);self.window=w;w.title('Cube Orange • Canlı bağlantı');w.geometry('900x390');w.minsize(820,360);w.configure(bg='#17191c');w.resizable(True,True)
        style=ttk.Style(w)
        style.configure('Live.TEntry',fieldbackground='#24272b',foreground='#f1f2f4',insertcolor='#ffd42a')
        style.configure('Live.TCombobox',fieldbackground='#24272b',foreground='#f1f2f4')
        style.configure('Live.TButton',background='#2a2c30',foreground='#f1f2f4',padding=(12,8),font=('Segoe UI',10,'bold'))
        style.map('Live.TButton',background=[('active','#45484e')])
        box=tk.Frame(w,bg='#17191c',padx=24,pady=20);box.pack(fill='both',expand=True)
        tk.Label(box,text='CUBE ORANGE • CANLI TELEMETRİ',bg='#17191c',fg='#ffd42a',font=('Segoe UI',16,'bold')).pack(anchor='w')
        tk.Label(box,text='WGS84 koordinatları doğrudan Cube GPS’inden okunur.',bg='#17191c',fg='#b8bcc4',font=('Segoe UI',10)).pack(anchor='w',pady=(4,18))
        auto=tk.Frame(box,bg='#111315',padx=12,pady=10);auto.pack(fill='x',pady=(0,10))
        ttk.Checkbutton(auto,text='USB telemetri takılınca otomatik bağlan',variable=self.auto_watch).pack(side='left')
        ttk.Button(auto,text='Şimdi otomatik tara',command=lambda:self.scan_ports(True),style='Live.TButton').pack(side='left',padx=10)
        tk.Label(auto,textvariable=self.auto_status,bg='#111315',fg='#ffd42a',font=('Segoe UI',9),anchor='w').pack(side='left',fill='x',expand=True)
        row=tk.Frame(box,bg='#17191c');row.pack(fill='x',pady=12)
        tk.Label(row,text='Bağlantı',bg='#17191c',fg='#e7e9ee').pack(side='left');kind=ttk.Combobox(row,values=['Seri / USB','UDP dinle','UDP gönder','TCP'],width=13,state='readonly');kind.set('Seri / USB');kind.pack(side='left',padx=6)
        tk.Label(row,text='COM / adres',bg='#17191c',fg='#e7e9ee').pack(side='left')
        port_values=[]
        try:
            sys.path.insert(0,str(Path(__file__).parent/'vendor'))
            from serial.tools import list_ports
            port_values=[p.device for p in list_ports.comports()]
        except Exception: pass
        address=ttk.Combobox(row,values=port_values,width=18,style='Live.TCombobox');address.pack(side='left',padx=6)
        if port_values: address.set(port_values[0])
        self.address_widget=address
        ttk.Button(row,text='↻ COM tara',command=lambda: self.refresh_ports(address),style='Live.TButton').pack(side='left')
        tk.Label(row,text='Baud',bg='#17191c',fg='#e7e9ee').pack(side='left');baud=ttk.Combobox(row,width=8,values=('57600','115200','230400','460800','921600'),state='readonly',style='Live.TCombobox');baud.set('57600');baud.pack(side='left',padx=6)
        self.baud_widget=baud
        tk.Label(row,text='Araç ID',bg='#17191c',fg='#e7e9ee').pack(side='left');target=ttk.Entry(row,width=4,style='Live.TEntry');target.insert(0,'1');target.pack(side='left',padx=6)
        def connect():
            try:
                speed=int(baud.get());sid=int(target.get())
                if not 1<=sid<=254:raise ValueError('Araç ID 1–254 olmalı.')
                dest=endpoint(kind.get(),address.get(),speed)
                self.start(dest,speed,sid,self.setup_mode.get())
            except (ValueError,RuntimeError) as exc:messagebox.showerror('Bağlantı',str(exc),parent=w)
        tk.Button(box,text='  BAĞLAN VE CANLI KONUMU GÖSTER  ',command=connect,bg='#ffd42a',fg='#0c0d0f',relief='flat',font=('Segoe UI',11,'bold'),padx=12,pady=9,cursor='hand2').pack(anchor='w',pady=(2,8))
        tk.Button(box,text='Bağlantıyı kes',command=self.disconnect,bg='#2a2c30',fg='#f1f2f4',relief='flat',font=('Segoe UI',10),padx=12,pady=7).pack(anchor='w',pady=(0,10))
        ttk.Checkbutton(box,text='USB yer kurulumu • Kalibrasyon ve pervanesiz çıkış testlerine izin ver',variable=self.setup_mode).pack(anchor='w',pady=(0,6))
        ttk.Checkbutton(box,text='Harita İHA’yı takip etsin',variable=self.follow).pack(anchor='w')
        tk.Label(box,text='Uçuş modu, görev ve failsafe işlemleri kendi çalışma alanlarından yönetilir. Bağlantı kesilince son gerçek veri tutulur.',bg='#17191c',fg='#8f959f',font=('Segoe UI',9)).pack(anchor='w',pady=(12,0))
        self.auto_next_scan=0

    def serial_ports(self):
        try:
            sys.path.insert(0,str(Path(__file__).parent/'vendor'))
            from serial.tools import list_ports
            ports=list(list_ports.comports())
        except Exception:return []
        keywords=('sik','telemetry','ftdi','cp210','silicon labs','usb serial','ch340','uart')
        return sorted(ports,key=lambda p:(not any(k in f'{p.description} {p.manufacturer}'.lower() for k in keywords),p.device))

    def scan_ports(self,force=False):
        if self.auto_scanning or self.enabled or (self.thread and self.thread.is_alive()):return
        ports=self.serial_ports()
        if not ports:
            self.auto_status.set('USB seri cihaz bulunamadı. Telemetri alıcısını takın.')
            self.auto_next_scan=time.monotonic()+3;return
        self.auto_scanning=True;self.auto_cancel=threading.Event()
        self.auto_status.set(f'{len(ports)} portta ArduPilot sinyali aranıyor…')
        cancel=self.auto_cancel
        def worker():
            try:
                sys.path.insert(0,str(Path(__file__).parent/'vendor'))
                from pymavlink import mavutil
                for port in ports:
                    for speed in (57600,115200,230400,460800,921600):
                        if cancel.is_set():return
                        link=None
                        try:
                            link=mavutil.mavlink_connection(port.device,baud=speed,source_system=255,source_component=190,dialect='ardupilotmega')
                            deadline=time.monotonic()+1.6
                            while not cancel.is_set() and time.monotonic()<deadline:
                                hb=link.recv_match(type='HEARTBEAT',blocking=True,timeout=.35)
                                if hb and hb.autopilot==mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA:
                                    self.auto_results.put(('found',(port.device,speed,hb.get_srcSystem(),hb.get_srcComponent())))
                                    return
                        except Exception:pass
                        finally:
                            if link:
                                try:link.close()
                                except Exception:pass
                self.auto_results.put(('none','ArduPilot yaşam sinyali bulunamadı. Port ve radyo eşleşmesini kontrol edin.'))
            except ImportError:self.auto_results.put(('none','MAVLink bileşeni eksik. KUR.bat dosyasını çalıştırın.'))
        threading.Thread(target=worker,daemon=True).start()

    def auto_tick(self):
        try:
            kind,value=self.auto_results.get_nowait();self.auto_scanning=False;self.auto_next_scan=time.monotonic()+3
            if kind=='found':
                port,speed,system,component=value
                self.auto_status.set(f'Doğrulandı: {port} • {speed} baud • Araç {system}/{component}')
                if hasattr(self,'address_widget') and self.address_widget.winfo_exists():self.address_widget.set(port)
                if hasattr(self,'baud_widget') and self.baud_widget.winfo_exists():self.baud_widget.set(str(speed))
                if self.auto_watch.get() and not self.enabled:
                    try:self.start(port,speed,system,self.setup_mode.get())
                    except RuntimeError as exc:self.auto_status.set(str(exc))
            else:self.auto_status.set(value)
        except queue.Empty:pass
        window=getattr(self,'window',None)
        window_open=bool(window and window.winfo_exists())
        if window_open and self.auto_watch.get() and not self.enabled and not self.auto_scanning and not (self.thread and self.thread.is_alive()) and time.monotonic()>=self.auto_next_scan:
            self.scan_ports()
        self.auto_job=self.app.root.after(700,self.auto_tick)

    def refresh_ports(self, widget):
        try:
            sys.path.insert(0,str(Path(__file__).parent/'vendor'))
            from serial.tools import list_ports
            values=[p.device for p in list_ports.comports()]
        except Exception: values=[]
        widget.configure(values=values)
        if values: widget.set(values[0])
        else: widget.set('COM portu bulunamadı')

    def set_mode(self):
        mode=self.mode_var.get().upper()
        if not self.enabled or not self.app.link or not self.session or not self.session.link:
            messagebox.showinfo('Uçuş modu','Önce canlı ve güncel Cube bağlantısı kurun.',parent=self.window);return
        action=self.safety.action_for_mode(mode)
        if action!='basic_mode' and not self.safety.allow(action):
            messagebox.showwarning('Uçuş modu engellendi',self.safety.summary(action=action),parent=self.window);return
        if mode in ('AUTO','GUIDED','RTL','LAND','LOITER','POSHOLD') and not messagebox.askyesno('Uçuş modu onayı',f'{mode} modu karta gönderilecek. Araç davranışı değişebilir. Devam edilsin mi?',parent=self.window):return
        self.session.commands.put(('mode',mode))
        self.text.set(f'{mode} modu bekleniyor…')

    def toggle_mission(self):
        if not self.app.link or not self.session:return
        start=self.mission_button.cget('text')=='Görevi başlat'
        if start and not self.safety.allow('mission'):
            messagebox.showwarning('Görev engellendi',self.safety.summary(action='mission'),parent=self.window);return
        if not messagebox.askyesno('Görev kontrolü',('AUTO görev başlatılacak; araç hareket edebilir.' if start else 'Görev durdurulup LOITER istenecek.')+' Devam edilsin mi?',parent=self.window):return
        self.session.commands.put(('mission','start' if start else 'stop'))

    def failsafe_dialog(self):
        if not self.enabled or not self.session or not self.app.link:
            messagebox.showinfo('Failsafe','Önce canlı ve güncel Cube bağlantısı kurun.',parent=self.window);return
        w=tk.Toplevel(self.window);w.title('ArduPilot • Failsafe ayarları');w.geometry('560x390');self.failsafe_window=w
        box=ttk.Frame(w,padding=14);box.pack(fill='both',expand=True)
        ttk.Label(box,text='Karttan oku, değeri değiştir ve “Kartta doğrula” ile yaz.').pack(anchor='w')
        names=('FS_GCS_ENABLE','FS_GCS_TIMEOUT','FS_THR_ENABLE','FS_EKF_ACTION','FS_BATT_ENABLE');fields={}
        for name in names:
            row=ttk.Frame(box);row.pack(fill='x',pady=3);ttk.Label(row,text=name,width=20).pack(side='left')
            var=tk.StringVar(value='—');fields[name]=var;ttk.Entry(row,textvariable=var,width=12).pack(side='left')
            ttk.Button(row,text='Yaz',command=lambda n=name:self.set_param(n,fields[n].get(),w)).pack(side='left',padx=5)
        status=tk.StringVar(value='Karttan okunması bekleniyor…');ttk.Label(box,textvariable=status,wraplength=510).pack(anchor='w',pady=10)
        ttk.Button(box,text='Karttan oku',command=lambda:self.session.commands.put(('param_read',names))).pack(anchor='w')
        self._failsafe_fields=fields;self._failsafe_status=status

    def set_param(self,name,value,window):
        try:value=float(str(value).replace(',','.'))
        except ValueError:messagebox.showerror('Failsafe','Sayısal değer girin.',parent=window);return
        if not messagebox.askyesno('Failsafe parametresi',f'{name} = {value:g} karta yazılacak. Devam edilsin mi?',parent=window):return
        self.session.commands.put(('param_set',name,value));self._failsafe_status.set(f'{name} yazılıyor…')

    def start(self,dest,baud,sid,calibration=False):
        if self.thread and self.thread.is_alive():raise RuntimeError('Önce mevcut bağlantıyı kesin; kapanmasını bekleyin.')
        if getattr(self.app,'mission_busy',False):raise RuntimeError('Görev yüklemesi tamamlanana kadar bekleyin.')
        sys.path.insert(0,str(Path(__file__).parent/'vendor'))
        self.enabled=True;self.started_at=time.monotonic();self.connected_once=False;self.lost_since=None
        self.state=PositionState();self.safety=SafetyGate(self.state);self.centered=False
        self.stop=threading.Event();self.events=queue.Queue()
        self.app.track=[];self.app.records=[];self.app.link=False
        self.app.data={k:0 for k in self.app.data}
        for value in self.app.values.values():value.set('—')
        self.app.horizon.delete('all')
        def labels(widget):
            if isinstance(widget,tk.Label) and 'SENTETİK DEMO' in str(widget.cget('text')):
                widget.configure(text='CANLI KART VERİSİ\nKonum bekleniyor')
            for child in widget.winfo_children():labels(child)
        labels(self.app.root)
        self.app.xyz_panel.place_forget()
        self.panel.place(relx=1,x=-14,y=14,anchor='ne')
        self.app.location_button.configure(state='disabled')
        for name in ('quick_pause','quick_link'):
            button=getattr(self.app,name,None)
            if button and button.winfo_exists():button.configure(state='disabled')
        if getattr(self.app,'balance_button',None):self.app.balance_button.configure(text='DENGE • BAĞLANTI BEKLENİYOR',state='disabled')
        if getattr(self.app,'demo_controls_button',None):self.app.demo_controls_button.configure(state='disabled')
        self.app.balance_badge.configure(text='CANLI TELEMETRİ',bg='#193c32')
        self.app.balance_note.set('Canlı bağlantı kurulunca bu düğme gerçek Cube Orange kartına STABILIZE modu gönderir ve karttan doğrulama bekler.')
        self.app.map_mode_var.set('Dünya Haritası');self.app.change_map_mode()
        session=Session(self.events,self.stop,dest,baud,reconnect=True,calibration=bool(calibration))
        session.identity=(sid,1)
        self.session=session
        self.thread=threading.Thread(target=session.run,daemon=True);self.thread.start()

    def disconnect(self):
        self.auto_watch.set(False);self.auto_cancel.set()
        self.stop.set();self.connection='Bağlantı kesildi';self.state.heartbeat_time=0

    def tick(self):
        app=self.app;now=time.monotonic()
        try:
            for _ in range(200):
                kind,value=self.events.get_nowait()
                if getattr(app,'operations',None):app.operations.event(kind,value)
                if getattr(app,'ground_tools',None):app.ground_tools.event(kind,value)
                if kind=='message':
                    self.state.ingest(value,now)
                    if value.get_type()=='HEARTBEAT':self.update_vehicle_modes(value)
                elif kind in ('online','status','lost','error'):
                    self.connection=str(value)
                    if kind=='online':self.connected_once=True;self.lost_since=None;self.auto_status.set(str(value))
                    elif kind in ('lost','error') and self.connected_once and self.lost_since is None:self.lost_since=now
                elif kind=='control':self.connection=str(value)
                elif kind=='param_result':
                    name,ok,note=value;self.connection=f'{name}: {note}'
                    if hasattr(self,'_failsafe_status'):self._failsafe_status.set(self.connection)
                elif kind=='param':
                    name,val=value;self.failsafe_values[name]=val
                    if hasattr(self,'_failsafe_fields') and name in self._failsafe_fields:self._failsafe_fields[name].set(str(val))
                elif kind=='param_error' and hasattr(self,'_failsafe_status'):self._failsafe_status.set(value)
                elif kind=='done':self.connection='Bağlantı kapalı'
                if kind in ('lost','error','done'):self.state.heartbeat_time=0
        except queue.Empty:pass
        # The Session retries the verified port first. If Windows assigns a new
        # COM number after a long outage, release it and return to USB discovery.
        if self.auto_watch.get() and self.lost_since and now-self.lost_since>25:
            self.stop.set();self.enabled=False;self.auto_next_scan=0
            self.connection='Bağlantı uzun süre yok • USB portları yeniden taranıyor'
            self.lost_since=None
        st=self.state;app.link=st.fresh(now) and not self.stop.is_set()
        if st.position:
            app.data.update({k:v for k,v in st.position.items() if k!='heading'})
            app.data['heading']=st.position['heading'] if st.position['heading'] is not None else (st.attitude[2]%360 if st.attitude else 0)
            app.last_received=st.position_time
            app.data['battery']=st.battery if st.battery is not None else 0
            app.data['satellites']=st.satellites if st.satellites is not None else 0
            if st.attitude:app.data['roll'],app.data['pitch']=st.attitude[:2]
            if not self.centered:
                app.flight_center=st.home[:2] if st.home else (app.data['lat'],app.data['lon'])
                app.world_center[:]=app.flight_center;app.world_features=[];self.centered=True
            point=(app.data['lat'],app.data['lon'])
            if app.link and (not app.track or point!=app.track[-1]):app.track.append(point);app.track=app.track[-600:]
            if app.link and self.follow.get():
                app.view_center[:]=point
                # Static Google imagery is a full billable image request. Thirty
                # seconds plus FlightPro's position signature avoids duplicate
                # downloads while the vehicle remains in the same small area.
                interval=30 if app.map_mode=='Google Uydu' else 1.5
                if now-self.last_map>interval and app.map_mode!='Simülasyon Haritası (3D)':app.load_map();self.last_map=now
            app.update_display()
        app.draw_map()
        self.render_status(now)
        app.job=app.root.after(100,app.tick)

    def update_vehicle_modes(self,msg):
        """Show and decode only the modes advertised for this ArduPilot vehicle type."""
        try:
            from pymavlink import mavutil
            mapping=mavutil.mode_mapping_byname(msg.type) or {}
            name=mavutil.mode_string_v10(msg)
        except Exception:return
        self.state.mode=name
        if getattr(self.app,'operations',None):self.app.operations.modes(tuple(sorted(mapping,key=mapping.get)))
        if getattr(self,'mode_box',None) and self.mode_box.winfo_exists():
            names=tuple(sorted(mapping,key=mapping.get))
            if names and tuple(self.mode_box.cget('values'))!=names:
                self.mode_box.configure(values=names)
                if self.mode_var.get() not in mapping:self.mode_var.set(name if name in mapping else names[0])

    def render_status(self,now):
        app=self.app;st=self.state
        title='CANLI • WGS84' if app.link else 'SON KONUM • GÜNCEL DEĞİL' if st.position else 'KART KONUMU BEKLENİYOR'
        app.status.set(title+' | '+self.connection)
        app.layer.set(title)
        rows=app.cockpit_rows
        for key in rows:rows[key].set('—')
        if st.position:
            p=st.position
            for key,value in {'lat':f"{p['lat']:.7f}",'lon':f"{p['lon']:.7f}",'altitude':f"{p['altitude']:.2f} m HOME",'speed':f"{p['speed']:.2f} m/s",'heading':'—' if p['heading'] is None else f"{p['heading']:.2f}°"}.items():rows[key].set(value)
            text=f"{title}\nEnlem  {p['lat']:.7f}°\nBoylam {p['lon']:.7f}°\nHOME üstü {p['altitude']:.2f} m\nDeniz sev. {p['amsl']:.2f} m\nVeri yaşı {now-st.position_time:.1f} sn"
        else:text=title
        text+='\nNED • Kartın yerel başlangıcına göre'
        text+='\nGüvenlik: '+self.safety.summary(now)
        if st.ned is not None and now-st.ned_time<3 and app.link:
            for key,value in zip(('pos_x','pos_y','pos_z'),st.ned):rows[key].set(f'{value:+.2f}')
            text+=f'\nX Kuzey {st.ned[0]:.2f} m\nY Doğu  {st.ned[1]:.2f} m\nZ Aşağı {st.ned[2]:.2f} m'
        else:text+='\nX / Y / Z: Güncel veri yok'
        self.text.set(text)
        rows['link'].set('CANLI' if app.link else 'GÜNCEL DEĞİL')
        rows['arm'].set('—' if now-st.heartbeat_time>3 else 'ARMED' if st.armed else 'DISARMED')
        if self.arm_button:
            self.arm_button.configure(text='DISARM' if st.armed else 'ARM',state='normal' if app.link else 'disabled')
        if self.mission_button:self.mission_button.configure(state='normal' if app.link else 'disabled',text='Görevi durdur' if st.mode.endswith('AUTO') else 'Görevi başlat')
        if getattr(app,'balance_button',None):
            modes=getattr(getattr(app,'operations',None),'mode_names',())
            supported=not modes or 'STABILIZE' in modes
            active=app.link and str(st.mode).upper()=='STABILIZE'
            app.balance_button.configure(
                text='✓ STABILIZE AKTİF' if active else "STABILIZE'A GEÇ" if app.link and supported else 'DENGE • BAĞLANTI BEKLENİYOR' if not app.link else 'STABILIZE DESTEKLENMİYOR',
                state='disabled' if active or not app.link or not supported else 'normal')
            app.balance_badge.configure(text=('CANLI • '+str(st.mode).upper()) if app.link else 'CANLI TELEMETRİ • BEKLENİYOR',
                                        bg='#193c32' if app.link else '#3b3519')
        rows['mode'].set(st.mode if now-st.heartbeat_time<3 else '—')
        rows['gps'].set(f'Fix {st.fix} • {st.satellites if st.satellites is not None else "—"} uydu')
        battery=[]
        if st.battery is not None:battery.append(f'%{st.battery}')
        if st.battery_voltage is not None:battery.append(f'{st.battery_voltage:.2f} V')
        rows['battery'].set(' • '.join(battery) if battery else '—')
        current=[]
        if st.battery_current is not None:current.append(f'{st.battery_current:.2f} A')
        if st.battery_consumed is not None:current.append(f'{st.battery_consumed:.0f} mAh')
        rows['battery_current'].set(' • '.join(current) if current else '—')
        app.update_battery_gauge(st.battery,st.battery_voltage,st.battery_current,st.battery_consumed,
                                 live=True,fresh=app.link)
        if getattr(app,'battery_panel_label',None):
            color='#ff756a' if st.battery is not None and st.battery<=20 else '#ffd42a' if st.battery is not None and st.battery<=50 else '#7cdbac' if st.battery is not None else '#eceef1'
            app.battery_panel_label.configure(fg=color)
        rows['data_age'].set(f'{now-st.position_time:.1f} sn' if st.position else '—')
        if st.position:
            # Other telemetry pages also distinguish altitude relative to HOME.
            for key in app.values:
                if 'İrtifa' in key:app.values[key].set(f"{st.position['altitude']:.2f} m HOME")
