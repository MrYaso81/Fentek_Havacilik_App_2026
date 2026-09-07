"""Offline-first synthetic flight display. Standard library only."""
import base64
import csv
import math
import os
import queue
import threading
import time
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import HTTPError
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import webbrowser

BG, PANEL, MUTED, TEXT, ACCENT = '#0b1320', '#142236', '#8d9eb5', '#edf3fa', '#56e0bd'
# Demo center from the user-provided map application.
CENTER = (40.8438, 31.1565)


def sample(t,center=CENTER):
    # 90-second demo cycle: ground, takeoff, cruise, landing and disarmed wait.
    phase=t%90
    if phase<5:
        altitude,speed,angle=0.,0.,0.
    elif phase<15:
        altitude,speed,angle=(phase-5)*10,6.,(phase-5)*.025
    elif phase<65:
        angle=.25+(phase-15)*.1
        altitude,speed=100+8*math.sin(t/12),18.
    elif phase<75:
        angle=5.25+(phase-65)*.025
        altitude,speed=(75-phase)*10,6.
    else:
        altitude,speed,angle=0.,0.,5.5
    north, east = 180 * math.cos(angle), 180 * math.sin(angle)
    return dict(lat=center[0] + north / 111320, lon=center[1] + east / (111320 * math.cos(math.radians(center[0]))),
                altitude=altitude, speed=speed, heading=(90 + math.degrees(angle)) % 360,
                roll=10 * math.sin(t / 8), pitch=3 * math.sin(t / 5), battery=max(15, 98 - t / 60), satellites=18)


def world(lat, lon, zoom=17):
    size = 256 * 2 ** zoom
    s = math.sin(math.radians(lat))
    return (lon + 180) / 360 * size, (.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * size


class Demo:
    def __init__(self, root):
        self.root, self.t, self.running, self.link = root, 0., True, True
        self.last_tick = time.monotonic()
        self.last_received = self.last_tick
        self.flight_center=CENTER
        self.data = sample(0,self.flight_center)
        self.track, self.records = [], []
        self.image = None
        self.google_pending = False
        self.results = queue.Queue()
        root.title('Fentek Havacılık — Sentetik Uçuş')
        root.geometry('1180x820')
        root.minsize(1040, 740)
        root.configure(bg=BG)
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TButton', font=('Segoe UI', 10), padding=8)
        header = tk.Frame(root, bg=BG, padx=24, pady=18)
        header.pack(fill='x')
        self.label(header, 'FENTEK HAVACILIK', 23, TEXT, True).pack(side='left')
        self.label(header, '  YER İSTASYONU', 10).pack(side='left', padx=10)
        tk.Label(header, text='  SENTETİK VERİ • DONANIM BAĞLI DEĞİL  ', bg='#4b3918', fg='#ffda8e', font=('Segoe UI', 10, 'bold'), padx=8, pady=8).pack(side='right')
        controls = tk.Frame(root, bg=PANEL, padx=20, pady=10)
        controls.pack(fill='x', padx=24)
        self.pause_button = ttk.Button(controls, text='Duraklat', command=self.pause)
        self.pause_button.pack(side='left', padx=4)
        ttk.Button(controls, text='Baştan başlat', command=self.reset).pack(side='left', padx=4)
        self.link_button = ttk.Button(controls, text='Bağlantı kaybını dene', command=self.toggle_link)
        self.link_button.pack(side='left', padx=4)
        ttk.Button(controls, text='Uçuş verisini kaydet', command=self.export).pack(side='right', padx=4)
        body = tk.Frame(root, bg=BG)
        body.pack(fill='both', expand=True, padx=24, pady=16)
        left = tk.Frame(body, bg=PANEL, padx=12, pady=10)
        left.pack(side='left', fill='both', expand=True)
        top = tk.Frame(left, bg=PANEL)
        top.pack(fill='x', pady=(0, 6))
        self.label(top, 'UÇUŞ ALANI', 11, TEXT, True).pack(side='left')
        self.layer = tk.StringVar(value='ŞEMATİK DEMO • UYDU GÖRÜNTÜSÜ DEĞİL')
        tk.Label(top, textvariable=self.layer, bg=PANEL, fg=MUTED, font=('Segoe UI', 8)).pack(side='right')
        self.canvas = tk.Canvas(left, bg='#13282d', highlightthickness=0, width=640, height=450)
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Configure>', lambda e: self.draw_map())
        # Google requires a link from its static image to Maps; only explicit clicking opens it.
        self.canvas.bind('<Double-Button-1>', self.google_link)
        map_controls = tk.Frame(left, bg=PANEL)
        map_controls.pack(fill='x', pady=8)
        ttk.Button(map_controls, text='Google uydu görüntüsü', command=self.google_dialog).pack(side='left')
        ttk.Button(map_controls, text='Demo harita', command=self.offline_map).pack(side='left', padx=8)
        self.map_status = tk.StringVar(value='Çevrimdışı çalışıyor • Haritada hareket eden işaret sentetik İHA’dır.')
        tk.Label(left, textvariable=self.map_status, bg=PANEL, fg=MUTED, wraplength=640, anchor='w', justify='left', font=('Segoe UI', 9)).pack(fill='x')
        right = tk.Frame(body, bg=BG, width=290)
        right.pack(side='right', fill='y', padx=(16, 0))
        right.pack_propagate(False)
        self.horizon = tk.Canvas(right, height=165, bg=PANEL, highlightthickness=0)
        self.horizon.pack(fill='x', pady=(0, 10))
        self.values = {}
        for key in ('İrtifa / yerden', 'Yer hızı', 'Batarya', 'GPS / uydu', 'Enlem', 'Boylam'):
            row = tk.Frame(right, bg=PANEL, padx=14, pady=7)
            row.pack(fill='x', pady=3)
            self.label(row, key.upper(), 8).pack(anchor='w')
            var = tk.StringVar()
            self.values[key] = var
            tk.Label(row, textvariable=var, bg=PANEL, fg=ACCENT, font=('Segoe UI', 16, 'bold')).pack(anchor='w')
        footer = tk.Frame(root, bg=PANEL, padx=18, pady=12)
        footer.pack(fill='x', padx=24, pady=(0, 18))
        self.status = tk.StringVar()
        tk.Label(footer, textvariable=self.status, bg=PANEL, fg=TEXT, font=('Segoe UI', 10)).pack(side='left')
        self.label(footer, 'DEMO MODU  /  CUBE ORANGE + HERE3', 9).pack(side='right')
        self.update_display()
        self.job = root.after(100, self.tick)
        root.protocol('WM_DELETE_WINDOW', self.close)

    def label(self, parent, text, size=10, color=MUTED, bold=False):
        return tk.Label(parent, text=text, bg=parent.cget('bg'), fg=color, font=('Segoe UI', size, 'bold' if bold else 'normal'))

    def pause(self):
        self.running = not self.running
        self.pause_button['text'] = 'Devam et' if not self.running else 'Duraklat'

    def reset(self):
        self.t, self.track, self.records = 0., [], []
        self.data = sample(0,self.flight_center)
        self.running = self.link = True
        self.last_received = time.monotonic()
        self.pause_button['text'], self.link_button['text'] = 'Duraklat', 'Bağlantı kaybını dene'
        self.update_display()

    def toggle_link(self):
        self.link = not self.link
        self.link_button['text'] = 'Bağlantıyı geri getir' if not self.link else 'Bağlantı kaybını dene'

    def map_xy(self, lat, lon):
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        cx, cy = world(*CENTER)
        x, y = world(lat, lon)
        return w / 2 + x - cx, h / 2 + y - cy

    def draw_map(self):
        c = self.canvas
        c.delete('all')
        w, h = c.winfo_width(), c.winfo_height()
        if w < 2: return
        if self.image:
            c.create_image(w / 2, h / 2, image=self.image)
        elif not (getattr(self, 'osm_enabled', False) and getattr(self, 'tiles', None)):
            for x in range(0, w, 48): c.create_line(x, 0, x, h, fill='#203d40')
            for y in range(0, h, 48): c.create_line(0, y, w, y, fill='#203d40')
            c.create_polygon(0,h*.75,w*.3,h*.5,w*.55,h*.6,w,h*.1,w,h*.2,w*.55,h*.7,w*.3,h*.6,0,h*.85,fill='#1b4350',outline='')
            c.create_line(0,h*.22,w,h*.8,fill='#42504b',width=15)
            c.create_line(0,h*.22,w,h*.8,fill='#8e977b',width=1,dash=(8,10))
            c.create_text(18, 20, text='DEMO ALANI / ANKARA', fill='#9cb1b0', anchor='w', font=('Segoe UI', 9))
        # Keep Google attribution strip free of overlays.
        route = [self.map_xy(sample(t,self.flight_center)['lat'], sample(t,self.flight_center)['lon']) for t in ([] if getattr(self,'live_map',None) and self.live_map.enabled else range(0,64,2))]
        if route:c.create_line(*[v for point in route for v in point], fill='#5b8b86', width=2, dash=(4,6), smooth=True)
        if len(self.track) > 1:
            c.create_line(*[v for p in self.track for v in self.map_xy(*p)], fill=ACCENT, width=3, smooth=True)
        x,y = self.map_xy(self.data['lat'], self.data['lon'])
        self.draw_vehicle_marker(c,x,y,self.data['heading'])
        c.create_text(w-20,25,text='N ↑',fill=TEXT,anchor='e',font=('Segoe UI',11,'bold'))

    def draw_vehicle_marker(self,c,x,y,heading):
        angle = math.radians(heading)
        def rotate(a,b):
            return x+a*math.cos(angle)-b*math.sin(angle),y+a*math.sin(angle)+b*math.cos(angle)
        c.create_oval(x-23,y-23,x+23,y+23,outline=ACCENT if self.link else '#ffad65',width=1)
        # Four-motor UAV marker: body, crossed arms and four rotors.
        arm1=(*rotate(-12,-12),*rotate(12,12))
        arm2=(*rotate(12,-12),*rotate(-12,12))
        c.create_line(*arm1,fill=TEXT,width=4)
        c.create_line(*arm2,fill=TEXT,width=4)
        for a,b in ((-12,-12),(12,-12),(-12,12),(12,12)):
            rx,ry=rotate(a,b)
            c.create_oval(rx-5,ry-5,rx+5,ry+5,outline=TEXT,width=2)
        body=[rotate(0,-10),rotate(-6,5),rotate(0,2),rotate(6,5)]
        c.create_polygon(*[v for p in body for v in p],fill=ACCENT if self.link else '#ffad65',outline=BG,width=1)
        c.create_text(x+30,y-20,text='İHA-01' if self.link else 'SON KONUM',fill=TEXT,anchor='w',font=('Segoe UI',10,'bold'))

    def update_display(self):
        d = self.data
        entries = {'İrtifa / yerden':f"{d['altitude']:.1f} m", 'Yer hızı':f"{d['speed']:.1f} m/s", 'Batarya':f"%{d['battery']:.0f}", 'GPS / uydu':f"3D FIX · {d['satellites']} uydu", 'Enlem':f"{d['lat']:.7f}", 'Boylam':f"{d['lon']:.7f}"}
        for k,v in entries.items(): self.values[k].set(v)
        c = self.horizon
        c.delete('all')
        w = max(290,c.winfo_width())
        offset = d['pitch'] * 2
        tilt = math.tan(math.radians(d['roll'])) * w / 2
        c.create_rectangle(0,0,w,165,fill='#23495c',outline='')
        c.create_polygon(0,83+offset-tilt,w,83+offset+tilt,w,165,0,165,fill='#604b38',outline='')
        c.create_line(0,83+offset-tilt,w,83+offset+tilt,fill='#d7e7e9',width=2)
        c.create_line(w/2-40,83,w/2-12,83,w/2,90,w/2+12,83,w/2+40,83,fill='#ffda8e',width=3)
        c.create_text(w/2,22,text=f"YÖN {d['heading']:03.0f}°",fill=TEXT,font=('Segoe UI',13,'bold'))
        c.create_text(w/2,145,text='SENTETİK YÖNELİM',fill=TEXT,font=('Segoe UI',8))
        self.draw_map()

    def tick(self):
        now = time.monotonic()
        elapsed, self.last_tick = min(.5,now-self.last_tick), now
        if self.running:
            self.t += elapsed
            if self.link:
                self.data = sample(self.t,self.flight_center)
                self.last_received = now
                self.track.append((self.data['lat'],self.data['lon']))
                self.track = self.track[-600:]
                if not self.records or self.t-self.records[-1]['demo_seconds'] >= 1:
                    self.records.append(dict(demo_seconds=round(self.t,2), **self.data))
                    self.records = self.records[-3600:]
                self.update_display()
        age = now-self.last_received
        state = 'DURAKLATILDI' if not self.running else 'DEMO BAĞLANTISI AÇIK' if self.link else 'BAĞLANTI KAYBI • SON VERİ GÖSTERİLİYOR'
        self.status.set(f'{state}   |   Veri yaşı: {age:.1f} sn   |   Süre: {int(self.t)//60:02}:{int(self.t)%60:02}')
        try:
            result, payload = self.results.get_nowait()
            self.google_pending = False
            if result == 'image':
                try:
                    self.image = tk.PhotoImage(data=base64.b64encode(payload))
                    self.layer.set('GOOGLE UYDU GÖRÜNTÜSÜ • İHA VERİSİ SENTETİK')
                    self.map_status.set('Google görüntüsü yüklendi. İHA hareketi sentetiktir. Çift tıklama Google Haritalar bağlantısını açar.')
                    self.draw_map()
                except tk.TclError:
                    self.map_status.set('Görüntü açılamadı; demo harita kullanılabilir.')
            else: self.map_status.set(payload)
        except queue.Empty: pass
        self.job = self.root.after(100,self.tick)

    def offline_map(self):
        if self.google_pending:
            self.map_status.set('Görüntü isteği sürüyor; tamamlandıktan sonra demo haritayı seçebilirsiniz.')
            return
        self.image = None
        self.layer.set('ŞEMATİK DEMO • UYDU GÖRÜNTÜSÜ DEĞİL')
        self.map_status.set('Çevrimdışı demo harita • Gerçek uydu bağlantısı yok.')
        self.draw_map()

    def google_dialog(self):
        if self.google_pending: return
        dialog = tk.Toplevel(self.root)
        dialog.title('Google uydu görüntüsü')
        dialog.geometry('580x260')
        dialog.configure(bg=PANEL)
        tk.Label(dialog,text='Google Maps Static API anahtarı',bg=PANEL,fg=TEXT,font=('Segoe UI',14,'bold')).pack(pady=16)
        entry = ttk.Entry(dialog,show='•',width=60)
        entry.pack(padx=20,pady=8)
        saved_key = os.environ.get('GOOGLE_MAPS_API_KEY', '').strip()
        if saved_key:
            entry.insert(0, saved_key)
        tk.Label(dialog,text='Google projesinde Maps Static API ve faturalandırma etkin olmalı.\nYükle düğmesi bir görüntü isteği gönderir; Google ücret uygulayabilir.\nAnahtar diske kaydedilmez. Görüntü canlı uydu yayını değildir.',bg=PANEL,fg=MUTED,justify='left').pack(pady=8)
        def fetch():
            key=entry.get().strip()
            if not key: return
            dialog.destroy()
            self.google_pending=True
            self.map_status.set('Google uydu görüntüsü yükleniyor…')
            # Fixed size keeps API limits and attribution intact; no recurring map requests.
            width=min(640,max(200,self.canvas.winfo_width()))
            height=min(450,max(200,self.canvas.winfo_height()))
            def work():
                params=dict(center=f'{CENTER[0]},{CENTER[1]}',zoom=17,size=f'{width}x{height}',scale=1,maptype='satellite',format='png',key=key)
                try:
                    with urlopen('https://maps.googleapis.com/maps/api/staticmap?'+urlencode(params),timeout=15) as response:
                        data=response.read(5_000_001)
                        if not data.startswith(b'\x89PNG') or len(data)>5_000_000: raise ValueError()
                    self.results.put(('image',data))
                except HTTPError as exc:
                    self.results.put(('error',f'Google görüntüyü vermedi (HTTP {exc.code}). API, anahtar kısıtlarını ve faturalandırmayı kontrol edin.'))
                except Exception:
                    self.results.put(('error','Görüntü alınamadı. İnternet bağlantısını ve Google API ayarlarını kontrol edin.'))
            threading.Thread(target=work,daemon=True).start()
        ttk.Button(dialog,text='Uydu görüntüsünü yükle',command=fetch).pack(pady=8)

    def google_link(self,event=None):
        if self.image:
            webbrowser.open(f'https://www.google.com/maps/@{CENTER[0]},{CENTER[1]},17z/data=!3m1!1e3')

    def export(self):
        path=filedialog.asksaveasfilename(defaultextension='.csv',initialfile='sentetik_ucus.csv',filetypes=[('CSV','*.csv')])
        if path:
            try:
                with open(path,'w',newline='',encoding='utf-8-sig') as f:
                    writer=csv.DictWriter(f,fieldnames=['source','demo_seconds',*sample(0)])
                    writer.writeheader()
                    writer.writerows(dict(source='SYNTHETIC_DEMO',**r) for r in self.records)
                messagebox.showinfo('Kaydedildi','Sentetik uçuş verisi CSV olarak kaydedildi.')
            except OSError:
                messagebox.showerror('Kayıt hatası','Dosya yazılamadı. Farklı bir konum seçin.')

    def close(self):
        self.root.after_cancel(self.job)
        self.root.destroy()


if __name__=='__main__':
    root=tk.Tk()
    Demo(root)
    root.mainloop()
