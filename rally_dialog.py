"""Small reviewed dialog for MAVLink 2 rally-point transfer."""
import queue
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
from connection import endpoint
from rally_transfer import RallyTransfer, validate_rally_points


def open_rally_upload(app, points):
    try: points=validate_rally_points(points)
    except ValueError as exc: messagebox.showerror('Rally noktaları',str(exc),parent=app.root);return
    w=tk.Toplevel(app.root);w.title('Rally noktalarını Cube’a yükle');w.geometry('720x430');w.configure(bg='#17191c')
    body=ttk.Frame(w,padding=16);body.pack(fill='both',expand=True)
    ttk.Label(body,text='MAVLink 2 • Rally / alternatif dönüş noktaları',font=('Segoe UI',14,'bold')).pack(anchor='w')
    ttk.Label(body,text='Aktarım yalnız DISARMED ArduPilot karta yapılır ve geri okunarak doğrulanır. Mevcut rally listesi değiştirilir.',wraplength=670).pack(anchor='w',pady=8)
    table=ttk.Treeview(body,columns=('lat','lon','alt'),show='headings',height=6)
    for key,title in [('lat','Enlem'),('lon','Boylam'),('alt','HOME üstü irtifa')]:table.heading(key,text=title);table.column(key,width=190)
    table.pack(fill='x')
    for i,p in enumerate(points):table.insert('','end',values=(f'{p[0]:.7f}',f'{p[1]:.7f}',f'{p[2]:.1f} m'))
    row=ttk.Frame(body);row.pack(fill='x',pady=10)
    kind=ttk.Combobox(row,values=['Seri / USB','UDP dinle','UDP gönder','TCP'],state='readonly',width=13);kind.set('Seri / USB');kind.pack(side='left')
    address=ttk.Entry(row,width=18);address.pack(side='left',padx=5)
    baud=ttk.Entry(row,width=8);baud.insert(0,'115200');baud.pack(side='left')
    ttk.Label(row,text='Araç ID').pack(side='left',padx=(10,3));system=ttk.Entry(row,width=4);system.insert(0,'1');system.pack(side='left')
    status=tk.StringVar(value='Canlı bağlantı açıksa önce bağlantıyı kesin.')
    ttk.Label(body,textvariable=status,wraplength=670).pack(anchor='w',pady=8)
    events=queue.Queue();stop=threading.Event();busy=False
    def upload():
        nonlocal busy
        if busy:return
        if app.live_map.thread and app.live_map.thread.is_alive():messagebox.showinfo('Bağlantı','Önce canlı Cube bağlantısını kesin.',parent=w);return
        try:
            speed=int(baud.get());target=int(system.get());dest=endpoint(kind.get(),address.get(),speed)
            if not 1<=target<=254:raise ValueError('Araç ID 1–254 arasında olmalı.')
        except ValueError as exc:messagebox.showerror('Bağlantı',str(exc),parent=w);return
        if not messagebox.askyesno('Rally listesini değiştir',f'{len(points)} rally noktası {dest} üzerindeki araç {target} için yüklensin mi?',parent=w):return
        busy=True;button.configure(state='disabled');status.set('Rally aktarımı başlıyor…')
        def worker():
            link=None
            try:
                sys.path.insert(0,str(Path(__file__).parent/'vendor'))
                from pymavlink import mavutil
                link=mavutil.mavlink_connection(dest,baud=speed,source_system=255,source_component=190,dialect='ardupilotmega')
                RallyTransfer(link,target,stop,events.put).run(points)
            except Exception as exc:events.put('DOĞRULANMADI • '+str(exc))
            finally:
                if link:link.close()
                events.put(None)
        threading.Thread(target=worker,daemon=True).start()
    button=ttk.Button(body,text='Rally listesini yükle ve geri doğrula',command=upload);button.pack(anchor='w')
    def poll():
        nonlocal busy
        try:
            while True:
                value=events.get_nowait()
                if value is None:busy=False;button.configure(state='normal')
                else:status.set(value)
        except queue.Empty:pass
        if w.winfo_exists():w._poll=w.after(100,poll)
    def close():stop.set();w.destroy()
    w.protocol('WM_DELETE_WINDOW',close);poll()
