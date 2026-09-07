"""Multi-transport desktop station built on the telemetry display."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'vendor'))
import queue
import threading
import time
import math
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
from app import Station as TelemetryDisplay, gps_values
from connection import Session, endpoint


class Station(TelemetryDisplay):
    def __init__(self, root):
        self.online = False
        self.session = None
        self.last_position = None
        self.last_position_time = 0
        self.transition = False
        super().__init__(root)
        root.geometry('1140x830')
        root.minsize(1040, 780)
        bar = self.port.master
        for widget in bar.winfo_children():
            widget.destroy()
        self.kind = ttk.Combobox(bar, width=13, values=['Seri / USB', 'UDP dinle', 'UDP gönder', 'TCP'], state='readonly')
        self.kind.set('Seri / USB')
        self.kind.pack(side='left', padx=4)
        self.port = ttk.Combobox(bar, width=23)
        self.port.pack(side='left', padx=4)
        self.baud = ttk.Combobox(bar, width=8, values=[9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600], state='readonly')
        self.baud.set('115200')
        self.baud.pack(side='left', padx=4)
        ttk.Button(bar, text='Portları yenile', command=self.refresh).pack(side='left', padx=4)
        self.connect_button = ttk.Button(bar, text='Bağlan', command=self.connect)
        self.connect_button.pack(side='left', padx=4)
        ttk.Button(bar, text='Kes', command=self.disconnect).pack(side='left', padx=4)
        ttk.Button(bar, text='Seçili bağlantıya geç', command=self.switch).pack(side='left', padx=4)
        shell = bar.master
        opts = ttk.Frame(shell)
        opts.pack(fill='x', before=bar, pady=8)
        self.retry = tk.BooleanVar(value=True)
        self.setup = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text='Kesilince yeniden bağlan', variable=self.retry).pack(side='left', padx=8)
        ttk.Checkbutton(opts, text='USB ile yerde kurulum', variable=self.setup).pack(side='left', padx=8)
        ttk.Button(opts, text='Kalibrasyon', command=self.show_calibration).pack(side='left', padx=8)
        ttk.Button(opts, text='Bağlantı rehberi', command=self.guide).pack(side='left', padx=8)
        self.age = tk.StringVar(value='Henüz geçerli konum alınmadı.')
        ttk.Label(shell, textvariable=self.age).pack(anchor='w', pady=8)
        self.last_button = ttk.Button(shell, text='Son bilinen konumu haritada aç', command=lambda: self.open_map(True), state='disabled')
        self.last_button.pack(anchor='w')
        self.log = tk.Text(shell, height=5, bg='#0b1421', fg='#a9bed4', font=('Consolas', 9), state='disabled')
        self.log.pack(fill='x', pady=8)
        self.cal_window = None
        self.cal_text = tk.StringVar(value='USB ile yerde kurulum seçiliyken bağlanın. Araç DISARMED olmalı.\nKalibrasyonda pervaneler sökülmüş olmalı; aracı sabit tutun.')
        self.cal_buttons = []
        self.position_request = None
        self.kind.bind('<<ComboboxSelected>>', self.change_kind)
        self.refresh()

    def note(self, text):
        self.log.configure(state='normal')
        self.log.insert('end', time.strftime('%H:%M:%S') + '  ' + str(text) + '\n')
        if int(self.log.index('end-1c').split('.')[0]) > 300:
            self.log.delete('1.0', '2.0')
        self.log.see('end')
        self.log.configure(state='disabled')

    def refresh(self):
        # Parent construction calls this before extended controls exist.
        try:
            from serial.tools import list_ports
            ports = list(list_ports.comports())
            self.port['values'] = [p.device for p in ports]
            if ports and not self.port.get():
                self.port.set(ports[0].device)
            if hasattr(self, 'log'):
                for p in ports:
                    self.note(f'{p.device}: {p.description}')
        except ImportError:
            self.status.set('Kurulum gerekli: KUR.bat dosyasını çalıştırın.')

    def change_kind(self, event=None):
        self.port.set('' if self.kind.get() == 'Seri / USB' else '0.0.0.0:14550' if self.kind.get() == 'UDP dinle' else '127.0.0.1:5760')
        if self.kind.get() == 'Seri / USB':
            self.refresh()

    def config(self):
        return endpoint(self.kind.get(), self.port.get(), self.baud.get()), int(self.baud.get()), self.retry.get(), self.setup.get() and self.kind.get() == 'Seri / USB'

    def connect(self):
        if self.worker and self.worker.is_alive():
            return
        try:
            config = self.config()
        except ValueError as exc:
            messagebox.showerror('Bağlantı bilgileri', str(exc))
            return
        self.start(config)

    def start(self, config):
        self.clear()
        self.last_position = None
        self.last_button['state'] = 'disabled'
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.connect_button['state'] = 'disabled'
        self.session = Session(self.events, self.stop, *config)
        self.worker = threading.Thread(target=self.session.run, daemon=True)
        self.worker.start()

    def switch(self):
        try:
            self.next_config = self.config()
        except ValueError as exc:
            messagebox.showerror('Bağlantı bilgileri', str(exc))
            return
        if self.worker and self.worker.is_alive():
            self.transition = True
            self.disconnect(manual=False)
        else:
            self.start(self.next_config)

    def offline(self):
        self.online = False
        self.position = None
        self.position_request = None
        self.map_button['state'] = 'disabled'
        for key in self.seen:
            self.values[key].set('Güncel değil')
        self.seen.clear()

    def disconnect(self, manual=True):
        if manual:
            self.transition = False
        self.stop.set()
        self.offline()
        self.status.set('Bağlantı kapatılıyor…' if self.worker and self.worker.is_alive() else 'Bağlı değil')

    def show_calibration(self):
        if self.cal_window and self.cal_window.winfo_exists():
            self.cal_window.lift()
            return
        self.cal_window = tk.Toplevel(self.root)
        self.cal_window.title('Fentek Havacılık • Kalibrasyon')
        self.cal_window.geometry('740x350')
        pane = ttk.Frame(self.cal_window, padding=20)
        pane.pack(fill='both', expand=True)
        ttk.Label(pane, textvariable=self.cal_text, wraplength=690).pack(anchor='w', pady=16)
        row = ttk.Frame(pane)
        row.pack(fill='x')
        self.cal_buttons = []
        for title, action in [('Jiroskop', 'gyro'), ('Düz seviye', 'level'), ('İvmeölçer • 6 yön', 'accel')]:
            button = ttk.Button(row, text=title, command=lambda a=action: self.calibrate(a), state='disabled')
            button.pack(side='left', padx=6)
            self.cal_buttons.append(button)
        self.ready = ttk.Button(pane, text='İstenen yönde sabit • Devam', command=lambda: self.calibrate('position'), state='disabled')
        self.ready.pack(anchor='w', pady=20)
        ttk.Label(pane, text='Kartın istediği yönü yerleştirip Devam’a basın.\nPusula, radyo ve hava hızı kalibrasyonları bu sürümde yoktur.\nBağlantı kesilince kalibrasyon otomatik tekrar gönderilmez.', wraplength=690).pack(anchor='w')

    def calibrate(self, action):
        if self.online and self.session:
            self.session.commands.put(action)
            if action == 'position':
                self.position_request = None

    def guide(self):
        messagebox.showinfo('Bağlantı rehberi', 'USB: Seri / USB, kartın COM portu, 115200.\nTelemetri: Alıcının COM portu ve üreticinin seri hızı.\n\nUSB’den geçiş: Yeni adresi seçin, yerde kurulum işaretini kaldırın ve Seçili bağlantıya geç’e basın. Kısa kesinti olabilir.\n\nUDP dinle: Yerel IP:port (0.0.0.0:14550).\nUDP gönder / TCP: Karşı cihazın IP:port adresi.\n\nYeniden bağlanma aynı adreste çalışır; farklı cihazları otomatik seçmez. Seçenekler Bağlan’a basıldığında uygulanır.\n\nMAVLink taşıyan cihazlar desteklenir. Aynı COM portunu Mission Planner’da kapatın. Google Haritalar düğmeye bastığınız konumu açar; canlı harita değildir.')

    def update_values(self, data):
        for key, value in data.items():
            self.values[key].set(value)
            self.seen[key] = time.monotonic()

    def message(self, msg):
        kind = msg.get_type()
        if kind == 'HEARTBEAT':
            from pymavlink import mavutil
            self.update_values({'Uçuş modu': mavutil.mode_string_v10(msg), 'Motor durumu': 'ARMED' if msg.base_mode & 128 else 'DISARMED'})
            self.ardu = msg.autopilot == 3
        elif kind == 'GPS_RAW_INT':
            valid, lat, lon, data = gps_values(msg)
            self.update_values(data)
            self.position = (lat, lon) if valid else None
            if valid:
                self.last_position, self.last_position_time = self.position, time.monotonic()
                self.last_button['state'] = 'normal'
            self.map_button['state'] = 'normal' if valid else 'disabled'
        elif kind == 'ATTITUDE':
            self.update_values({k: f'{v:.1f}°' for k, v in zip(('Yatış', 'Yunuslama', 'Yön'), (math.degrees(msg.roll), math.degrees(msg.pitch), math.degrees(msg.yaw) % 360))})
        elif kind == 'SYS_STATUS':
            self.update_values({'Batarya': 'Bilinmiyor' if msg.voltage_battery == 65535 else f'{msg.voltage_battery / 1000:.2f} V'})
        elif kind == 'STATUSTEXT':
            self.note('Kart: ' + str(msg.text))

    def tick(self):
        for _ in range(300):
            try:
                kind, data = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == 'done':
                self.offline()
                self.connect_button['state'] = 'normal'
                if self.transition:
                    self.root.after(100, self.finish_switch)
                elif self.stop.is_set():
                    self.status.set('Bağlı değil')
            elif kind in ('error', 'lost'):
                self.offline()
                self.status.set(str(data))
                self.note(data)
                self.cal_text.set('Bağlantı yok. Kalibrasyon sonucu bilinmiyorsa kart durumunu kontrol edin.')
            elif not self.stop.is_set():
                if kind in ('status', 'online'):
                    self.online = kind == 'online'
                    self.status.set(data)
                    self.note(data)
                elif kind == 'message':
                    self.message(data)
                elif kind == 'cal':
                    self.cal_text.set(data)
                    self.note(data)
                elif kind == 'position':
                    self.position_request = data
                    if data:
                        directions = {1: 'Düz', 2: 'Sol yan', 3: 'Sağ yan', 4: 'Burun aşağı', 5: 'Burun yukarı', 6: 'Ters / sırt üstü'}
                        self.cal_text.set('Aracı yerleştirin: ' + directions[data] + '\nHareket durunca Devam’a basın.')
        now = time.monotonic()
        for key in list(self.seen):
            if now - self.seen[key] > 5:
                self.values[key].set('Güncel değil')
                del self.seen[key]
        if self.position and now - self.last_position_time > 5:
            self.position = None
            self.map_button['state'] = 'disabled'
        self.age.set(f"{'Güncel' if self.position and self.online else 'Son bilinen'} konum: {self.last_position[0]:.7f}, {self.last_position[1]:.7f} • {now - self.last_position_time:.0f} saniye önce" if self.last_position else 'Henüz geçerli konum alınmadı.')
        if self.cal_window and self.cal_window.winfo_exists():
            allowed = self.online and self.session.calibration and getattr(self, 'ardu', False) and self.values['Motor durumu'].get() == 'DISARMED' and now - self.seen.get('Motor durumu', 0) < 2
            for button in self.cal_buttons:
                button['state'] = 'normal' if allowed else 'disabled'
            self.ready['state'] = 'normal' if allowed and self.position_request else 'disabled'
        self.root.after(100, self.tick)

    def finish_switch(self):
        if not self.transition:
            return
        if self.worker and self.worker.is_alive():
            self.root.after(100, self.finish_switch)
            return
        self.transition = False
        self.start(self.next_config)

    def open_map(self, last=False):
        position = self.last_position if last else self.position
        if not last and (not self.online or time.monotonic() - self.last_position_time > 5):
            return
        if position:
            lat, lon = position
            webbrowser.open(f'https://www.google.com/maps/search/?api=1&query={lat:.7f}%2C{lon:.7f}')


if __name__ == '__main__':
    root = tk.Tk()
    Station(root)
    root.mainloop()
