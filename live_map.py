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
        self.failsafe_values={}

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

    def dialog(self):
        if getattr(self,'window',None) and self.window.winfo_exists():self.window.lift();return
        w=tk.Toplevel(self.app.root);self.window=w;w.title('Cube • Canlı harita');w.geometry('650x230')
        box=ttk.Frame(w,padding=16);box.pack(fill='both',expand=True)
        ttk.Label(box,text='WGS84 enlem/boylam • Kartın konumu kullanılır; bilgisayar konumu kullanılmaz.').pack(anchor='w')
        row=ttk.Frame(box);row.pack(fill='x',pady=12)
        kind=ttk.Combobox(row,values=['Seri / USB','UDP dinle','UDP gönder','TCP'],width=13,state='readonly');kind.set('Seri / USB');kind.pack(side='left')
        address=ttk.Entry(row,width=22);address.pack(side='left',padx=4)
        baud=ttk.Entry(row,width=8);baud.insert(0,'115200');baud.pack(side='left')
        ttk.Label(row,text='Araç ID').pack(side='left')
        target=ttk.Entry(row,width=4);target.insert(0,'1');target.pack(side='left')
        def connect():
            try:
                speed=int(baud.get());sid=int(target.get())
                if not 1<=sid<=254:raise ValueError('Araç ID 1–254 olmalı.')
                dest=endpoint(kind.get(),address.get(),speed)
                self.start(dest,speed,sid)
            except (ValueError,RuntimeError) as exc:messagebox.showerror('Bağlantı',str(exc),parent=w)
        ttk.Button(box,text='Canlı konuma bağlan',command=connect).pack(anchor='w')
        ttk.Button(box,text='Bağlantıyı kes',command=self.disconnect).pack(anchor='w',pady=5)
        ttk.Checkbutton(box,text='Harita İHA’yı takip etsin',variable=self.follow).pack(anchor='w')
        mode_row=ttk.Frame(box);mode_row.pack(fill='x',pady=6)
        ttk.Label(mode_row,text='Uçuş modu:').pack(side='left')
        self.mode_var=tk.StringVar(value='STABILIZE')
        mode_box=ttk.Combobox(mode_row,textvariable=self.mode_var,values=['STABILIZE','ALT_HOLD','LOITER','GUIDED','AUTO','RTL','LAND','MANUAL'],state='readonly',width=14)
        mode_box.pack(side='left',padx=6)
        ttk.Button(mode_row,text='Modu uygula',command=self.set_mode).pack(side='left')
        ttk.Button(mode_row,text='Failsafe ayarları',command=self.failsafe_dialog).pack(side='left',padx=6)
        self.mission_button=ttk.Button(mode_row,text='Görevi başlat',command=self.toggle_mission,state='disabled');self.mission_button.pack(side='left',padx=6)
        ttk.Label(box,text='Bağlantı kesilince son veri tutulur; sentetik harekete geçilmez.').pack(anchor='w')

    def set_mode(self):
        mode=self.mode_var.get().upper()
        if not self.enabled or not self.app.link or not self.session or not self.session.link:
            messagebox.showinfo('Uçuş modu','Önce canlı ve güncel Cube bağlantısı kurun.',parent=self.window);return
        if mode in ('AUTO','GUIDED','RTL','LAND') and not messagebox.askyesno('Uçuş modu onayı',f'{mode} modu karta gönderilecek. Araç hareket edebilir. Devam edilsin mi?',parent=self.window):return
        if mode=='AUTO' and not self.safety.allow('auto'):
            messagebox.showwarning('AUTO engellendi',self.safety.summary(),parent=self.window);return
        self.session.commands.put(('mode',mode))
        self.text.set(f'{mode} modu bekleniyor…')

    def toggle_mission(self):
        if not self.app.link or not self.session:return
        start=self.mission_button.cget('text')=='Görevi başlat'
        if start and not self.safety.allow('mission'):
            messagebox.showwarning('Görev engellendi',self.safety.summary(),parent=self.window);return
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

    def start(self,dest,baud,sid):
        if self.thread and self.thread.is_alive():raise RuntimeError('Önce mevcut bağlantıyı kesin; kapanmasını bekleyin.')
        if getattr(self.app,'mission_busy',False):raise RuntimeError('Görev yüklemesi tamamlanana kadar bekleyin.')
        sys.path.insert(0,str(Path(__file__).parent/'vendor'))
        self.enabled=True;self.state=PositionState();self.safety=SafetyGate(self.state);self.centered=False
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
        for button in (self.app.quick_pause,self.app.quick_link,self.app.balance_button):button.configure(state='disabled')
        self.app.balance_badge.configure(text='CANLI TELEMETRİ',bg='#193c32')
        self.app.balance_note.set('Karttan okunan gerçek veriler. Bu ekrandan uçuş komutu gönderilmez.')
        self.app.map_mode_var.set('Dünya Haritası');self.app.change_map_mode()
        session=Session(self.events,self.stop,dest,baud,reconnect=True)
        session.identity=(sid,1)
        self.session=session
        self.thread=threading.Thread(target=session.run,daemon=True);self.thread.start()

    def disconnect(self):
        self.stop.set();self.connection='Bağlantı kesildi';self.state.heartbeat_time=0

    def tick(self):
        app=self.app;now=time.monotonic()
        try:
            for _ in range(200):
                kind,value=self.events.get_nowait()
                if kind=='message':self.state.ingest(value,now)
                elif kind in ('online','status','lost','error'):self.connection=str(value)
                elif kind=='control':self.connection=str(value)
                elif kind=='param':
                    name,val=value;self.failsafe_values[name]=val
                    if hasattr(self,'_failsafe_fields') and name in self._failsafe_fields:self._failsafe_fields[name].set(str(val))
                elif kind=='param_error' and hasattr(self,'_failsafe_status'):self._failsafe_status.set(value)
                elif kind=='done':self.connection='Bağlantı kapalı'
                if kind in ('lost','error','done'):self.state.heartbeat_time=0
        except queue.Empty:pass
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
                if now-self.last_map>1.5 and app.map_mode!='Simülasyon Haritası (3D)':app.load_map();self.last_map=now
            app.update_display()
        app.draw_map()
        self.render_status(now)
        app.job=app.root.after(100,app.tick)

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
        rows['mode'].set(st.mode if now-st.heartbeat_time<3 else '—')
        rows['gps'].set(f'Fix {st.fix} • {st.satellites if st.satellites is not None else "—"} uydu')
        rows['battery'].set('—' if st.battery is None else f'%{st.battery}')
        rows['data_age'].set(f'{now-st.position_time:.1f} sn' if st.position else '—')
        if st.position:
            # Other telemetry pages also distinguish altitude relative to HOME.
            for key in app.values:
                if 'İrtifa' in key:app.values[key].set(f"{st.position['altitude']:.2f} m HOME")
