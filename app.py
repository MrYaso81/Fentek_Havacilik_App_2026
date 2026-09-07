"""Cube Station: USB MAVLink telemetry desktop prototype."""
import math
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser


def gps_values(msg):
    lat, lon = msg.lat / 1e7, msg.lon / 1e7
    valid = msg.fix_type in (3, 4, 5, 6, 7, 8) and -90 <= lat <= 90 and -180 <= lon <= 180
    return valid, lat, lon, {
        'GPS': f'Fix {msg.fix_type}' if valid else 'Konum bekleniyor',
        'Uydu': 'Bilinmiyor' if msg.satellites_visible == 255 else str(msg.satellites_visible),
        'Enlem': f'{lat:.7f}' if valid else '—',
        'Boylam': f'{lon:.7f}' if valid else '—',
        'GPS irtifası': f'{msg.alt / 1000:.1f} m' if valid else '—',
        'Hız': f'{msg.vel * .036:.1f} km/sa' if valid and msg.vel != 65535 else '—',
    }


class Station:
    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.worker = None
        self.position = None
        self.gps_time = 0
        self.seen = {}
        root.title('Fentek Havacılık • Yer İstasyonu')
        root.geometry('980x640')
        root.configure(bg='#101b2b')
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background='#101b2b')
        style.configure('TLabel', background='#101b2b', foreground='#e5edf6', font=('Segoe UI', 11))
        style.configure('TButton', font=('Segoe UI', 10), padding=9)
        shell = ttk.Frame(root, padding=24)
        shell.pack(fill='both', expand=True)
        ttk.Label(shell, text='CUBE STATION', font=('Segoe UI', 24, 'bold')).pack(anchor='w')
        ttk.Label(shell, text='Cube Orange + Here3  /  USB telemetri').pack(anchor='w', pady=(0, 18))
        bar = ttk.Frame(shell)
        bar.pack(fill='x')
        self.port = ttk.Combobox(bar, width=19, state='readonly')
        self.port.pack(side='left', padx=(0, 8))
        ttk.Button(bar, text='Portları yenile', command=self.refresh).pack(side='left')
        self.connect_button = ttk.Button(bar, text='Bağlan', command=self.connect)
        self.connect_button.pack(side='left', padx=8)
        ttk.Button(bar, text='Bağlantıyı kes', command=self.disconnect).pack(side='left')
        self.status = tk.StringVar(value='Bağlı değil')
        ttk.Label(shell, textvariable=self.status).pack(anchor='w', pady=18)
        grid = ttk.Frame(shell)
        grid.pack(fill='both', expand=True)
        self.values = {}
        for i, name in enumerate(['GPS', 'Uydu', 'Enlem', 'Boylam', 'GPS irtifası', 'Hız', 'Uçuş modu', 'Batarya', 'Yatış', 'Yunuslama', 'Yön', 'Motor durumu']):
            cell = tk.Frame(grid, bg='#1b2c42', padx=16, pady=12)
            cell.grid(row=i // 4, column=i % 4, sticky='nsew', padx=4, pady=4)
            tk.Label(cell, text=name, bg='#1b2c42', fg='#9caec3', font=('Segoe UI', 10)).pack(anchor='w')
            var = tk.StringVar(value='—')
            tk.Label(cell, textvariable=var, bg='#1b2c42', fg='#65ded0', font=('Segoe UI', 16, 'bold')).pack(anchor='w', pady=8)
            self.values[name] = var
        for i in range(4):
            grid.columnconfigure(i, weight=1)
        self.map_button = ttk.Button(shell, text='Güncel konumu Google Haritalar’da aç', command=self.open_map, state='disabled')
        self.map_button.pack(anchor='w', pady=16)
        ttk.Label(shell, text='Harita tarayıcıda açılır. Bu sürüm konum ve telemetri izleme içindir.').pack(anchor='w')
        self.refresh()
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(100, self.tick)

    def refresh(self):
        try:
            from serial.tools import list_ports
            ports = [p.device for p in list_ports.comports()]
            self.port['values'] = ports
            if ports and self.port.get() not in ports:
                self.port.set(ports[0])
        except ImportError:
            self.status.set('Kurulum gerekli: requirements.txt bağımlılıklarını yükleyin.')

    def clear(self):
        self.position = None
        self.seen.clear()
        self.map_button['state'] = 'disabled'
        for value in self.values.values():
            value.set('—')

    def connect(self):
        if self.worker and self.worker.is_alive():
            return
        if not self.port.get():
            messagebox.showinfo('USB bağlantısı', 'Cube Orange’ı USB veri kablosuyla bağlayıp portları yenileyin.')
            return
        self.clear()
        self.stop = threading.Event()
        self.connect_button['state'] = 'disabled'
        self.status.set('Cube Orange yanıtı bekleniyor…')
        self.worker = threading.Thread(target=self.receive, args=(self.port.get(), self.stop), daemon=True)
        self.worker.start()

    def receive(self, port, stop):
        link = None
        try:
            from pymavlink import mavutil
            link = mavutil.mavlink_connection(port, baud=115200, source_system=255)
            deadline = time.monotonic() + 12
            hb = None
            while not stop.is_set() and time.monotonic() < deadline:
                msg = link.recv_match(type='HEARTBEAT', blocking=True, timeout=.3)
                if msg and msg.autopilot != mavutil.mavlink.MAV_AUTOPILOT_INVALID:
                    hb = msg
                    break
            if stop.is_set():
                return
            if hb is None:
                raise TimeoutError('MAVLink yanıtı yok. Doğru COM portunu ve kart yazılımını kontrol edin.')
            system, component = hb.get_srcSystem(), hb.get_srcComponent()
            link.mav.request_data_stream_send(system, component, mavutil.mavlink.MAV_DATA_STREAM_ALL, 2, 1)
            self.events.put(('status', 'Bağlandı • GPS verisi bekleniyor'))
            last_hb = time.monotonic()
            while not stop.is_set():
                msg = link.recv_match(blocking=True, timeout=.3)
                now = time.monotonic()
                if now - last_hb > 6:
                    raise TimeoutError('Bağlantı kesildi: kartın yaşam sinyali alınamıyor.')
                if msg is None or msg.get_srcSystem() != system or msg.get_srcComponent() != component:
                    continue
                kind = msg.get_type()
                if kind == 'HEARTBEAT':
                    last_hb = now
                    self.events.put(('values', {'Uçuş modu': mavutil.mode_string_v10(msg), 'Motor durumu': 'ARMED' if msg.base_mode & 128 else 'DISARMED'}))
                elif kind == 'GPS_RAW_INT':
                    self.events.put(('gps', gps_values(msg)))
                elif kind == 'ATTITUDE':
                    self.events.put(('values', {key: f'{value:.1f}°' for key, value in zip(('Yatış', 'Yunuslama', 'Yön'), (math.degrees(msg.roll), math.degrees(msg.pitch), math.degrees(msg.yaw) % 360))}))
                elif kind == 'SYS_STATUS':
                    self.events.put(('values', {'Batarya': 'Bilinmiyor' if msg.voltage_battery == 65535 else f'{msg.voltage_battery / 1000:.2f} V'}))
        except Exception as exc:
            self.events.put(('error', str(exc)))
        finally:
            if link:
                link.close()
            self.events.put(('done', None))

    def disconnect(self):
        self.stop.set()
        self.clear()
        self.status.set('Bağlantı kapatılıyor…' if self.worker and self.worker.is_alive() else 'Bağlı değil')

    def tick(self):
        while not self.events.empty():
            kind, data = self.events.get()
            if kind == 'done':
                self.clear()
                self.connect_button['state'] = 'normal'
                if self.stop.is_set():
                    self.status.set('Bağlı değil')
            elif kind == 'error':
                self.status.set('Hata: ' + data)
            elif not self.stop.is_set():
                if kind == 'status':
                    self.status.set(data)
                elif kind in ('gps', 'values'):
                    if kind == 'gps':
                        valid, lat, lon, data = data
                        self.position = (lat, lon) if valid else None
                        self.gps_time = time.monotonic()
                        self.map_button['state'] = 'normal' if valid else 'disabled'
                        self.status.set('Bağlandı • GPS konumu alınıyor' if valid else 'Bağlandı • GPS sabitlenmesi bekleniyor')
                    for key, value in data.items():
                        self.values[key].set(value)
                        self.seen[key] = time.monotonic()
        now = time.monotonic()
        for key in list(self.seen):
            if now - self.seen[key] > 5:
                self.values[key].set('Veri güncel değil')
                del self.seen[key]
        if self.position and now - self.gps_time > 5:
            self.position = None
            self.map_button['state'] = 'disabled'
            self.status.set('GPS verisi güncel değil')
        self.root.after(100, self.tick)

    def open_map(self):
        if self.position and time.monotonic() - self.gps_time <= 5:
            lat, lon = self.position
            webbrowser.open(f'https://www.google.com/maps/search/?api=1&query={lat:.7f}%2C{lon:.7f}')

    def close(self):
        self.stop.set()
        self.root.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    Station(root)
    root.mainloop()
