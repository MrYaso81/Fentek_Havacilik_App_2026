"""Review a frozen map route before an explicitly requested mission upload."""
import queue
import threading
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk,messagebox
from connection import endpoint
from mission_transfer import Transfer,validate_points,validate_servo_actions


def open_mission(app):
    existing=getattr(app,'mission_window',None)
    if existing and existing.winfo_exists():existing.lift();return
    if not app.markers:
        messagebox.showinfo('Görev','Önce haritaya nokta ekleyin.');return
    window=tk.Toplevel(app.root)
    app.mission_window=window
    window.title('Görevi gözden geçir ve karta yükle')
    window.geometry('780x760')
    window.configure(bg='#17191c')
    body=ttk.Frame(window,padding=16);body.pack(fill='both',expand=True)
    ttk.Label(body,text='Haritadaki noktaların anlık kopyası • Son komut: Eve dönüş (RTL)',wraplength=720).pack(anchor='w')
    ttk.Label(body,text='İrtifalar kartın HOME yüksekliğine göredir; zeminden yükseklik değildir.\nKalkış komutu yoktur. Görev yükleme, ARM veya AUTO komutu göndermez.',wraplength=720).pack(anchor='w',pady=8)
    tabs=ttk.Notebook(body);tabs.pack(fill='both',expand=True)
    route_tab=ttk.Frame(tabs,padding=8);servo_tab=ttk.Frame(tabs,padding=8)
    tabs.add(route_tab,text='Rota noktaları');tabs.add(servo_tab,text='Servo komutları')
    table=ttk.Treeview(route_tab,columns=('lat','lon','alt'),show='headings',height=10)
    for col,text in [('lat','Enlem'),('lon','Boylam'),('alt','HOME üstü irtifa (m)')]:
        table.heading(col,text=text);table.column(col,width=210)
    table.pack(fill='x')
    snapshot=[tuple(p) for p in app.markers]
    for i,p in enumerate(snapshot):table.insert('','end',iid=str(i),values=(f'{p[0]:.7f}',f'{p[1]:.7f}',p[2] if len(p)>2 and p[2]>0 else 'GİRİN'))
    edit=ttk.Frame(route_tab);edit.pack(fill='x',pady=8)
    altitude=tk.StringVar()
    ttk.Label(edit,text='Seçili noktanın irtifası:').pack(side='left')
    ttk.Entry(edit,textvariable=altitude,width=10).pack(side='left',padx=6)
    def set_alt():
        try:
            value=float(altitude.get().replace(',','.'))
            validate_points([(0,0,value)])
            for row in table.selection():table.set(row,'alt',str(value))
        except ValueError as exc:messagebox.showerror('İrtifa',str(exc),parent=window)
    ttk.Button(edit,text='Seçili noktalara uygula',command=set_alt).pack(side='left')
    servo_actions=[]
    servo_box=ttk.LabelFrame(servo_tab,text='Görev içi servo hareketleri')
    servo_box.pack(fill='x',pady=(4,8))
    ttk.Label(servo_box,text='Seçili rota noktasından hemen sonra çalışır. PWM 1000–2000 µs.').pack(anchor='w',padx=8,pady=(6,2))
    servo_table=ttk.Treeview(servo_box,columns=('waypoint','channel','pwm'),show='headings',height=3)
    for col,text,width in [('waypoint','Noktadan sonra',180),('channel','Servo kanalı',150),('pwm','PWM (µs)',150)]:
        servo_table.heading(col,text=text);servo_table.column(col,width=width)
    servo_table.pack(fill='x',padx=8)
    servo_row=ttk.Frame(servo_box);servo_row.pack(fill='x',padx=8,pady=6)
    channel=tk.StringVar(value='8');pwm=tk.StringVar(value='1700')
    ttk.Label(servo_row,text='Kanal').pack(side='left')
    ttk.Entry(servo_row,textvariable=channel,width=5).pack(side='left',padx=4)
    ttk.Label(servo_row,text='PWM').pack(side='left')
    ttk.Entry(servo_row,textvariable=pwm,width=7).pack(side='left',padx=4)
    def add_servo():
        selected=table.selection()
        if len(selected)!=1:
            messagebox.showinfo('Servo komutu','Önce rota listesinden bir nokta seçin.',parent=window);return
        try:
            action=(int(selected[0])+1,int(channel.get()),int(pwm.get()))
            validate_servo_actions([action],len(snapshot))
        except ValueError as exc:messagebox.showerror('Servo komutu',str(exc),parent=window);return
        servo_actions.append(action)
        servo_table.insert('','end',values=action)
    def remove_servo():
        for row in reversed(servo_table.selection()):
            servo_actions.pop(servo_table.index(row));servo_table.delete(row)
    ttk.Button(servo_row,text='Seçili noktaya ekle',command=add_servo).pack(side='left',padx=8)
    ttk.Button(servo_row,text='Seçili servo komutunu sil',command=remove_servo).pack(side='left')
    ttk.Label(route_tab,text='Bağlantı: COM portunu başka uygulamalarda kapatın. Araç kimliği Cube modelini doğrulamaz.',wraplength=720).pack(anchor='w',pady=8)
    bar=ttk.Frame(route_tab);bar.pack(fill='x')
    kind=ttk.Combobox(bar,values=['Seri / USB','UDP dinle','UDP gönder','TCP'],state='readonly',width=14);kind.set('Seri / USB');kind.pack(side='left')
    address=ttk.Entry(bar,width=23);address.pack(side='left',padx=4)
    baud=ttk.Entry(bar,width=9);baud.insert(0,'115200');baud.pack(side='left')
    ttk.Label(bar,text='Araç ID').pack(side='left',padx=4)
    system=ttk.Entry(bar,width=4);system.insert(0,'1');system.pack(side='left')
    status=tk.StringVar(value='Henüz karta bağlanılmadı. İrtifaları girip görevi gözden geçirin.')
    ttk.Label(route_tab,textvariable=status,wraplength=710).pack(anchor='w',pady=12)
    events=queue.Queue();stop=threading.Event();busy=False
    def upload():
        nonlocal busy
        if busy:return
        live=getattr(app,'live_map',None)
        if live and live.thread and live.thread.is_alive():
            messagebox.showinfo('Bağlantı','Önce canlı harita bağlantısını kesin; ardından görev yükleyin.',parent=window);return
        try:
            points=[tuple(float(v) for v in table.item(row,'values')) for row in table.get_children()]
            validate_points(points);validate_servo_actions(servo_actions,len(points))
            speed=int(baud.get());target=int(system.get())
            if not 1<=target<=254:raise ValueError('Araç ID 1–254 arasında olmalı.')
            dest=endpoint(kind.get(),address.get(),speed)
        except ValueError as exc:
            messagebox.showerror('Görev',str(exc),parent=window);return
        if not messagebox.askyesno('Karttaki görevi değiştir',f'{dest} / araç {target}:\n{len(points)} nokta + {len(servo_actions)} servo komutu + RTL yüklenecek. Kartın mevcut görevi değiştirilecek.\nServo kanalı ve PWM değerlerini kontrol ettiniz mi?\nUçuş başlatılmayacak.',parent=window):return
        busy=True;app.mission_busy=True;button.configure(state='disabled');stop.clear()
        status.set('Seçilen araca bağlanılıyor…')
        def worker():
            link=None
            try:
                sys.path.insert(0,str(Path(__file__).parent/'vendor'))
                from pymavlink import mavutil
                link=mavutil.mavlink_connection(dest,baud=speed,source_system=255,source_component=190,dialect='ardupilotmega')
                Transfer(link,target,stop,lambda text:events.put(text)).run(points,tuple(servo_actions))
            except ImportError:events.put('pymavlink eksik. KUR.bat ile bağımlılıkları yükleyin.')
            except Exception as exc:events.put('Doğrulanmadı: '+str(exc))
            finally:
                if link:link.close()
                events.put(None)
        threading.Thread(target=worker,daemon=True).start()
    button=ttk.Button(route_tab,text='Görevi karta yükle ve doğrula',command=upload);button.pack(anchor='w')
    def poll():
        nonlocal busy
        try:
            while True:
                text=events.get_nowait()
                if text is None:busy=False;app.mission_busy=False;button.configure(state='normal')
                else:status.set(text)
        except queue.Empty:pass
        window._poll=window.after(100,poll)
    def close():
        stop.set()
        window.after_cancel(window._poll)
        window.destroy()
    window.protocol('WM_DELETE_WINDOW',close)
    window.bind('<Destroy>',lambda e:stop.set() if e.widget==window else None,add='+')
    poll()
