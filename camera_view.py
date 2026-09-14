"""Non-blocking USB and network camera viewer for the ground station."""
import base64
import json
import queue
import re
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox, filedialog

from branded import BLACK, SURFACE, YELLOW, WHITE, GRAY


CAMERA_SOURCES=('USB Kamera 0','USB Kamera 1','Ağ kamerası (RTSP / HTTP)')


def source_value(choice,url=''):
    if choice=='USB Kamera 0':return 0
    if choice=='USB Kamera 1':return 1
    url=str(url).strip()
    if not re.match(r'^https?://|^rtsp://',url,re.I):
        raise ValueError('Ağ kamerası adresi http://, https:// veya rtsp:// ile başlamalıdır.')
    return url


class CameraView:
    def __init__(self,app):
        self.app=app;self.running=False;self.stop_event=threading.Event()
        self.frames=queue.Queue(maxsize=2);self.photo=None;self.worker=None
        self.latest_png=None;self.recording=False;self.record_path=None
        self.poll_job=None;self.display_size=(960,540)
        self._build()
        self.poll_job=self.app.root.after(40,self.poll)

    def _build(self):
        name='Kamera görüntüsü'
        page=tk.Frame(self.app.deck,bg=BLACK);self.app.pages[name]=page
        nav=next(iter(self.app.nav_buttons.values())).master
        button=tk.Button(nav,text='10   Kamera görüntüsü',anchor='w',command=lambda:self.app.select(name),
                         bg='#101113',fg=GRAY,activebackground='#25231a',activeforeground=YELLOW,
                         relief='flat',bd=0,padx=15,pady=10,font=('Segoe UI',10,'bold'),cursor='hand2')
        button.pack(fill='x',pady=4);self.app.nav_buttons[name]=button
        self.app.heading(page,'KAMERA GÖRÜNTÜSÜ','USB veya RTSP/HTTP yayın • Görüntüleme uçuş kontrolünden bağımsızdır')

        controls=tk.Frame(page,bg=SURFACE,padx=12,pady=10,highlightthickness=1,highlightbackground='#303238')
        controls.pack(fill='x',pady=(0,10))
        tk.Label(controls,text='KAYNAK',bg=SURFACE,fg=GRAY,font=('Segoe UI',8,'bold')).pack(side='left',padx=(0,7))
        self.source=tk.StringVar(value=CAMERA_SOURCES[0])
        self.source_box=ttk.Combobox(controls,textvariable=self.source,values=CAMERA_SOURCES,state='readonly',width=28)
        self.source_box.pack(side='left',padx=(0,8));self.source_box.bind('<<ComboboxSelected>>',lambda _e:self.update_source_ui())
        self.url=tk.StringVar()
        self.url_entry=tk.Entry(controls,textvariable=self.url,bg='#25282d',fg=WHITE,insertbackground=YELLOW,
                                relief='flat',font=('Segoe UI',9),width=38)
        self.start_button=tk.Button(controls,text='▶  Kamerayı başlat',command=self.start,bg=YELLOW,fg=BLACK,
                                    activebackground='#ffe36a',activeforeground=BLACK,relief='flat',bd=0,
                                    padx=13,pady=8,font=('Segoe UI',9,'bold'),cursor='hand2')
        self.start_button.pack(side='left',padx=(0,7))
        self.stop_button=tk.Button(controls,text='■  Durdur',command=self.stop,bg='#30343a',fg=WHITE,
                                   activebackground='#454950',activeforeground=WHITE,relief='flat',bd=0,
                                   padx=12,pady=8,font=('Segoe UI',9,'bold'),cursor='hand2',state='disabled')
        self.stop_button.pack(side='left',padx=(0,7))
        tk.Button(controls,text='Test görüntüsü',command=self.test_pattern,bg='#30343a',fg=WHITE,
                  activebackground='#454950',activeforeground=WHITE,relief='flat',bd=0,
                  padx=12,pady=8,font=('Segoe UI',9,'bold'),cursor='hand2').pack(side='left')

        tools=tk.Frame(page,bg=SURFACE,padx=12,pady=8,highlightthickness=1,highlightbackground='#303238')
        tools.pack(fill='x',pady=(0,8))
        tk.Button(tools,text='📷  Fotoğraf kaydet',command=self.snapshot,bg='#30343a',fg=WHITE,activebackground='#454950',activeforeground=WHITE,relief='flat',bd=0,padx=12,pady=7,font=('Segoe UI',9,'bold'),cursor='hand2').pack(side='left',padx=(0,7))
        self.record_button=tk.Button(tools,text='●  Kaydı başlat',command=self.toggle_record,bg='#30343a',fg=WHITE,activebackground='#454950',activeforeground=WHITE,relief='flat',bd=0,padx=12,pady=7,font=('Segoe UI',9,'bold'),cursor='hand2')
        self.record_button.pack(side='left',padx=(0,14))
        tk.Label(tools,text='GÖREV ADIMI',bg=SURFACE,fg=GRAY,font=('Segoe UI',8,'bold')).pack(side='left')
        self.waypoint=tk.StringVar(value='Otomatik');ttk.Combobox(tools,textvariable=self.waypoint,values=('Otomatik',)+tuple(map(str,range(0,100))),width=9,state='readonly').pack(side='left',padx=(5,14))
        tk.Label(tools,text='GİMBAL PITCH',bg=SURFACE,fg=GRAY,font=('Segoe UI',8,'bold')).pack(side='left')
        self.gimbal_pitch=tk.StringVar(value='-30');ttk.Spinbox(tools,from_=-90,to=30,textvariable=self.gimbal_pitch,width=6).pack(side='left',padx=5)
        tk.Label(tools,text='YAW',bg=SURFACE,fg=GRAY,font=('Segoe UI',8,'bold')).pack(side='left')
        self.gimbal_yaw=tk.StringVar(value='0');ttk.Spinbox(tools,from_=-180,to=180,textvariable=self.gimbal_yaw,width=6).pack(side='left',padx=5)
        tk.Button(tools,text='Gimbal hedefini gönder',command=self.send_gimbal,bg=YELLOW,fg=BLACK,activebackground='#ffe36a',activeforeground=BLACK,relief='flat',bd=0,padx=12,pady=7,font=('Segoe UI',9,'bold'),cursor='hand2').pack(side='left',padx=7)
        tk.Button(tools,text='MAVLink fotoğraf tetikle',command=self.trigger_camera,bg='#30343a',fg=WHITE,activebackground='#454950',activeforeground=WHITE,relief='flat',bd=0,padx=10,pady=7,font=('Segoe UI',9,'bold'),cursor='hand2').pack(side='left',padx=(0,4))

        self.status=tk.StringVar(value='KAMERA KAPALI • Bir kaynak seçip başlatın')
        tk.Label(page,textvariable=self.status,bg='#302a12',fg=YELLOW,anchor='w',padx=12,pady=7,
                 font=('Segoe UI',9,'bold')).pack(fill='x',pady=(0,8))
        self.canvas=tk.Canvas(page,bg='#101316',highlightthickness=1,highlightbackground='#303238')
        self.canvas.pack(fill='both',expand=True)
        self.canvas.bind('<Configure>',self.resize)
        self.draw_placeholder('KAMERA GÖRÜNTÜSÜ BEKLENİYOR','USB kamera veya ağ kamerası otomatik olarak açılmaz.')
        tk.Label(page,text='Ağ kamerası adresi yalnız bu oturumda kullanılır. Fotoğraf/video bilgisayara kaydedilir. Gimbal komutu yalnız canlı Cube bağlantısında ve kullanıcı onayıyla gönderilir.',
                 bg=BLACK,fg=GRAY,anchor='w',font=('Segoe UI',8)).pack(fill='x',pady=(7,0))

    def update_source_ui(self):
        self.url_entry.pack_forget()
        if self.source.get()==CAMERA_SOURCES[2]:
            self.url_entry.pack(side='left',fill='x',expand=True,padx=(0,8),before=self.start_button)
            if not self.url.get():self.url.set('rtsp://')

    def resize(self,event):
        self.display_size=(max(320,event.width-8),max(180,event.height-8))

    def draw_placeholder(self,title,detail=''):
        c=self.canvas;c.delete('all');w=max(500,c.winfo_width());h=max(300,c.winfo_height())
        c.create_rectangle(0,0,w,h,fill='#101316',outline='')
        c.create_oval(w/2-34,h/2-42,w/2+34,h/2+26,outline=YELLOW,width=3)
        c.create_oval(w/2-11,h/2-19,w/2+11,h/2+3,fill=YELLOW,outline='')
        c.create_polygon(w/2+34,h/2-25,w/2+62,h/2-39,w/2+62,h/2+23,w/2+34,h/2+9,outline=YELLOW,fill='')
        c.create_text(w/2,h/2+62,text=title,fill=WHITE,font=('Segoe UI',13,'bold'))
        c.create_text(w/2,h/2+88,text=detail,fill=GRAY,font=('Segoe UI',9))

    def test_pattern(self):
        self.stop();c=self.canvas;c.delete('all');w=max(600,c.winfo_width());h=max(360,c.winfo_height())
        colors=('#f4d328','#f3f3e9','#22b6bc','#68cc62','#bc46a9','#e7463e','#315bd1')
        band=w/len(colors)
        for index,color in enumerate(colors):c.create_rectangle(index*band,0,(index+1)*band,h*.72,fill=color,outline='')
        c.create_rectangle(0,h*.72,w,h,fill='#101316',outline='')
        c.create_text(w/2,h*.82,text='FENTEK HAVACILIK • KAMERA TESTİ',fill=YELLOW,font=('Segoe UI',16,'bold'))
        c.create_text(w/2,h*.90,text=time.strftime('%H:%M:%S'),fill=WHITE,font=('Consolas',12))
        self.status.set('TEST GÖRÜNTÜSÜ • Gerçek kamera kullanılmıyor')

    def start(self):
        if self.running:return
        try:source=source_value(self.source.get(),self.url.get())
        except ValueError as exc:
            messagebox.showwarning('Kamera adresi',str(exc),parent=self.app.root);return
        try:import cv2
        except ImportError:
            messagebox.showerror('Kamera desteği','Bu bilgisayarda kamera bileşeni bulunamadı. OpenCV kurulumu gerekir.',parent=self.app.root);return
        self.stop_event.clear();self.running=True
        self.start_button.configure(state='disabled');self.stop_button.configure(state='normal')
        self.status.set('KAMERA BAĞLANIYOR…')
        self.worker=threading.Thread(target=self._capture,args=(source,cv2),daemon=True);self.worker.start()

    def _capture(self,source,cv2):
        cap=None;writer=None;writer_path=None
        try:
            backend=cv2.CAP_DSHOW if isinstance(source,int) and hasattr(cv2,'CAP_DSHOW') else cv2.CAP_ANY
            cap=cv2.VideoCapture(source,backend)
            if not cap.isOpened():raise RuntimeError('Kamera açılamadı.')
            cap.set(cv2.CAP_PROP_BUFFERSIZE,1)
            self.frames.put(('opened',None))
            failures=0
            while not self.stop_event.is_set():
                ok,frame=cap.read()
                if not ok:
                    failures+=1
                    if failures>=15:raise RuntimeError('Kamera görüntüsü kesildi.')
                    time.sleep(.05);continue
                failures=0
                if self.recording:
                    if writer is None or writer_path!=self.record_path:
                        if writer is not None:writer.release()
                        height,width=frame.shape[:2];fps=cap.get(cv2.CAP_PROP_FPS)
                        if not isinstance(fps,(int,float)) or not 1<=fps<=120:fps=20
                        writer=cv2.VideoWriter(str(self.record_path),cv2.VideoWriter_fourcc(*'mp4v'),fps,(width,height));writer_path=self.record_path
                        if not writer.isOpened():
                            writer.release();writer=None;self.recording=False;self.frames.put(('record_error','Video dosyası açılamadı.'))
                    if writer is not None:writer.write(frame)
                elif writer is not None:
                    writer.release();writer=None;writer_path=None;self.frames.put(('record_stopped',None))
                target_w,target_h=self.display_size
                height,width=frame.shape[:2]
                scale=min(target_w/width,target_h/height,1.0)
                if scale<1:frame=cv2.resize(frame,(max(1,int(width*scale)),max(1,int(height*scale))),interpolation=cv2.INTER_AREA)
                ok,png=cv2.imencode('.png',frame)
                if not ok:continue
                item=('frame',png.tobytes())
                try:self.frames.put_nowait(item)
                except queue.Full:
                    try:self.frames.get_nowait()
                    except queue.Empty:pass
                    try:self.frames.put_nowait(item)
                    except queue.Full:pass
        except Exception as exc:
            try:self.frames.put_nowait(('error',str(exc) or 'Kamera bağlantısı kurulamadı.'))
            except queue.Full:pass
        finally:
            if writer is not None:writer.release()
            if cap is not None:cap.release()
            try:self.frames.put_nowait(('stopped',None))
            except queue.Full:pass

    def poll(self):
        latest=None
        try:
            while True:
                kind,value=self.frames.get_nowait()
                if kind=='frame':latest=value
                elif kind=='opened':self.status.set('CANLI KAMERA • Görüntü alınıyor')
                elif kind=='error':
                    self.status.set('KAMERA HATASI • '+value);self.draw_placeholder('KAMERA AÇILAMADI',value)
                elif kind=='record_error':
                    self.recording=False;self.record_button.configure(text='●  Kaydı başlat');messagebox.showerror('Video kaydı',value,parent=self.app.root)
                elif kind=='record_stopped':self.status.set('CANLI KAMERA • Video kaydı tamamlandı')
                elif kind=='stopped':
                    self.running=False;self.recording=False;self.record_button.configure(text='●  Kaydı başlat');self.start_button.configure(state='normal');self.stop_button.configure(state='disabled')
        except queue.Empty:pass
        if latest:
            self.latest_png=latest
            try:
                self.photo=tk.PhotoImage(data=base64.b64encode(latest).decode('ascii'),format='png')
                c=self.canvas;c.delete('all');c.create_image(c.winfo_width()/2,c.winfo_height()/2,image=self.photo,anchor='center')
            except tk.TclError:self.status.set('KAMERA HATASI • Görüntü çözümlenemedi')
        try:self.poll_job=self.app.root.after(40,self.poll)
        except tk.TclError:self.poll_job=None

    def stop(self):
        self.recording=False;self.stop_event.set()
        if self.running:
            self.start_button.configure(state='disabled');self.stop_button.configure(state='disabled')
            self.status.set('KAMERA DURDURULUYOR…')
        else:
            self.start_button.configure(state='normal');self.stop_button.configure(state='disabled')
            self.status.set('KAMERA DURDURULDU')

    def current_metadata(self):
        waypoint=self.waypoint.get()
        state=getattr(getattr(self.app,'live_map',None),'state',None);position=getattr(state,'position',None) if state else None
        if waypoint=='Otomatik' and state:
            metric=getattr(state,'metrics',{}).get('Aktif görev adımı');waypoint=str(int(metric[0])) if metric else '—'
        return {'created':time.strftime('%Y-%m-%d %H:%M:%S'),'source':self.source.get(),'mission_step':waypoint,
                'position':position if position and time.monotonic()-getattr(state,'position_time',0)<=3 else None}

    def snapshot(self):
        if not self.latest_png:messagebox.showinfo('Fotoğraf','Önce gerçek kamera görüntüsü başlatın.',parent=self.app.root);return
        path=filedialog.asksaveasfilename(parent=self.app.root,defaultextension='.png',initialfile='Fentek_Kamera_'+time.strftime('%Y%m%d_%H%M%S')+'.png',filetypes=[('PNG görüntü','*.png')])
        if not path:return
        try:
            target=Path(path);target.write_bytes(self.latest_png);target.with_suffix('.json').write_text(json.dumps(self.current_metadata(),ensure_ascii=False,indent=2),encoding='utf-8')
            self.status.set('FOTOĞRAF KAYDEDİLDİ • Konum/görev etiketi JSON dosyasına yazıldı')
        except OSError as exc:messagebox.showerror('Fotoğraf',str(exc),parent=self.app.root)

    def toggle_record(self):
        if self.recording:
            self.recording=False;self.record_button.configure(text='●  Kaydı başlat');self.status.set('VİDEO KAYDI DURDURULUYOR…');return
        if not self.running:messagebox.showinfo('Video kaydı','Önce kamerayı başlatın.',parent=self.app.root);return
        path=filedialog.asksaveasfilename(parent=self.app.root,defaultextension='.mp4',initialfile='Fentek_Ucus_'+time.strftime('%Y%m%d_%H%M%S')+'.mp4',filetypes=[('MP4 video','*.mp4')])
        if not path:return
        try:Path(path).parent.mkdir(parents=True,exist_ok=True)
        except OSError as exc:messagebox.showerror('Video kaydı',str(exc),parent=self.app.root);return
        self.record_path=path;self.recording=True;self.record_button.configure(text='■  Kaydı durdur');self.status.set('CANLI KAMERA • VİDEO KAYDI AÇIK')

    def send_gimbal(self):
        live=getattr(self.app,'live_map',None)
        try:pitch=float(self.gimbal_pitch.get().replace(',','.'));yaw=float(self.gimbal_yaw.get().replace(',','.'))
        except ValueError:messagebox.showerror('Gimbal','Pitch ve yaw sayı olmalı.',parent=self.app.root);return
        if not (-90<=pitch<=30 and -180<=yaw<=180):messagebox.showerror('Gimbal','Pitch -90…30°, yaw -180…180° olmalı.',parent=self.app.root);return
        if not live or not live.enabled or not live.session or not live.session.link or time.monotonic()-live.state.heartbeat_time>2:
            messagebox.showinfo('Gimbal','Önce canlı Cube bağlantısı kurun.',parent=self.app.root);return
        if messagebox.askyesno('Gimbal komutu',f'Gerçek gimbala pitch {pitch:g}°, yaw {yaw:g}° hedefi gönderilsin mi?',parent=self.app.root):live.session.commands.put(('gimbal',pitch,yaw));self.status.set('GİMBAL KOMUTU • Kart onayı bekleniyor')

    def trigger_camera(self):
        live=getattr(self.app,'live_map',None)
        if not live or not live.enabled or not live.session or not live.session.link or time.monotonic()-live.state.heartbeat_time>2:
            messagebox.showinfo('Kamera tetikleme','Önce canlı Cube bağlantısı kurun.',parent=self.app.root);return
        if messagebox.askyesno('MAVLink kamera','Bağlı kamera bileşenine tek fotoğraf tetikleme komutu gönderilsin mi?',parent=self.app.root):
            live.session.commands.put(('camera_trigger',));self.status.set('MAVLINK FOTOĞRAF • Kamera onayı bekleniyor')

    def close(self):
        self.stop_event.set()
        if self.poll_job:
            try:self.app.root.after_cancel(self.poll_job)
            except tk.TclError:pass
