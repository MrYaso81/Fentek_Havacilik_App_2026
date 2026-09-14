"""Guarded real calibration and output tests for the main application."""
from __future__ import annotations

import json
import math
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk,messagebox,filedialog

from branded import BLACK,SURFACE,YELLOW,WHITE,GRAY


class GroundTools:
    def __init__(self,app):
        self.app=app;self.job=None;self.position_request=None;self.motor_notes={};self.servo_notes={}
        self._build();self.job=app.root.after(500,self.refresh)

    def _build(self):
        page=self.app.pages['Kurulum ve test']
        for child in page.winfo_children():child.destroy()
        self.app.heading(page,'GERÇEK KURULUM VE YER TESTİ','Canlı Cube • USB yer kurulumu • DISARMED • Pervaneler sökülü')
        self.connection_status=tk.StringVar(value='KİLİTLİ • Cube bağlantısında USB yer kurulumu seçilmelidir.')
        tk.Label(page,textvariable=self.connection_status,bg='#302a12',fg=YELLOW,anchor='w',padx=12,pady=8,font=('Segoe UI',10,'bold')).pack(fill='x',pady=(0,8))
        tabs=ttk.Notebook(page);tabs.pack(fill='both',expand=True)
        cal=tk.Frame(tabs,bg=BLACK,padx=14,pady=14);outputs=tk.Frame(tabs,bg=BLACK,padx=14,pady=14)
        tabs.add(cal,text='Gerçek kalibrasyon');tabs.add(outputs,text='Motor ve servo testi')
        self._build_calibration(cal);self._build_outputs(outputs)

    def _label(self,parent,text,size=10,color=WHITE):
        w=tk.Label(parent,text=text,bg=parent.cget('bg'),fg=color,font=('Segoe UI',size),anchor='w',justify='left',wraplength=1100)
        w.pack(fill='x',pady=5);return w

    def _button(self,parent,text,command):
        b=tk.Button(parent,text=text,command=command,bg='#30343a',fg=WHITE,activebackground=YELLOW,activeforeground=BLACK,relief='flat',padx=12,pady=8,font=('Segoe UI',9,'bold'),cursor='hand2')
        b.pack(side='left',padx=(0,7));return b

    def _build_calibration(self,p):
        self._label(p,'KALİBRASYON MERKEZİ',14,YELLOW)
        self._label(p,'Kartı sabit ve titreşimsiz tutun. Kart sonucu gelmeden başka kalibrasyon başlatılmaz. İvmeölçerde kartın istediği altı yön sırayla onaylanır.')
        self.cal_buttons=[]
        specs=(('Jiroskop','gyro'),('Düz seviye','level'),('İvmeölçer • 6 yön','accel'),('Pusula','compass'),('RC kumanda','rc'),('Hava hızı','airspeed'))
        for start in (0,3):
            row=tk.Frame(p,bg=BLACK);row.pack(fill='x',pady=5)
            for title,action in specs[start:start+3]:self.cal_buttons.append(self._button(row,title,lambda a=action:self.calibrate(a)))
        row=tk.Frame(p,bg=BLACK);row.pack(fill='x',pady=7)
        self.next_button=self._button(row,'İstenen yönde sabit • Devam',lambda:self.calibrate('position'));self.next_button.configure(state='disabled')
        self.cal_status=tk.StringVar(value='Kalibrasyon bekleniyor.')
        tk.Label(p,textvariable=self.cal_status,bg=SURFACE,fg=YELLOW,padx=12,pady=12,anchor='w',justify='left',wraplength=1000,font=('Segoe UI',10,'bold')).pack(fill='x',pady=8)
        self._label(p,'ESC kalibrasyonu ayrı güvenlik onayı ister. Uygulama komutun kabulünü gösterir; ESC seslerini, enerji sırasını ve üretici prosedürünü kendiliğinden doğrulayamaz.',9,GRAY)
        row=tk.Frame(p,bg=BLACK);row.pack(fill='x',pady=6)
        self.esc_guard=tk.BooleanVar(value=False);ttk.Checkbutton(row,text='Pervaneler fiziksel olarak söküldü',variable=self.esc_guard).pack(side='left',padx=(0,12))
        self.esc_button=self._button(row,'ESC kalibrasyonu',lambda:self.calibrate('esc'))

    def _build_outputs(self,p):
        self._label(p,'GÜVENLİK KİLİDİ',14,YELLOW)
        self._label(p,'Gerçek çıkış testleri hareket oluşturabilir. Testler en fazla %30 gaz/5 saniye ve servo için 3 saniyedir. Bağlantı kaybında motor komutunun kendi süresi dolar; acil durdurma düğmesi ayrıca %0 gönderir.')
        guard=tk.Frame(p,bg=SURFACE,padx=12,pady=10);guard.pack(fill='x',pady=6)
        self.output_guard=tk.BooleanVar(value=False);ttk.Checkbutton(guard,text='Pervaneler söküldü ve servo mekanizmalarının çevresi boş',variable=self.output_guard).pack(side='left')
        self.guard_text=tk.StringVar();tk.Entry(guard,textvariable=self.guard_text,width=28,bg='#25282d',fg=WHITE,insertbackground=YELLOW,relief='flat').pack(side='left',padx=12)
        tk.Label(guard,text='PERVANELER SÖKÜLDÜ yazın',bg=SURFACE,fg=GRAY).pack(side='left')
        emergency=tk.Button(p,text='■  ACİL DURDUR • MOTOR %0 / SERVO NÖTR',command=self.emergency,bg='#a92720',fg='white',activebackground='#d23b31',relief='flat',padx=16,pady=11,font=('Segoe UI',10,'bold'),cursor='hand2')
        emergency.pack(anchor='w',pady=8)
        self._label(p,'MOTOR SIRASI VE DÖNÜŞ YÖNÜ',12,YELLOW)
        row=tk.Frame(p,bg=BLACK);row.pack(fill='x',pady=5)
        self.motor=tk.StringVar(value='1');self.percent=tk.StringVar(value='10');self.motor_seconds=tk.StringVar(value='2');self.direction=tk.StringVar(value='Gözlenmedi')
        for title,var,values,width in (('Motor',self.motor,tuple(map(str,range(1,13))),6),('Gaz %',self.percent,('5','10','15','20','25','30'),7),('Süre',self.motor_seconds,('1','2','3','4','5'),7),('Gözlenen yön',self.direction,('Gözlenmedi','Saat yönü','Saat yönü tersi'),18)):
            tk.Label(row,text=title,bg=BLACK,fg=GRAY).pack(side='left',padx=(0,4));ttk.Combobox(row,textvariable=var,values=values,state='readonly',width=width).pack(side='left',padx=(0,10))
        self.motor_button=self._button(row,'Motoru kısa test et',self.motor_test);self._button(row,'Yönü kaydet',self.save_motor_note)
        self._label(p,'SERVO ÇIKIŞ EŞLEMESİ',12,YELLOW)
        row=tk.Frame(p,bg=BLACK);row.pack(fill='x',pady=5)
        self.servo=tk.StringVar(value='1');self.pwm=tk.StringVar(value='1500');self.neutral=tk.StringVar(value='1500');self.servo_seconds=tk.StringVar(value='1');self.servo_function=tk.StringVar(value='')
        for title,var,values,width in (('Servo',self.servo,tuple(map(str,range(1,17))),6),('PWM',self.pwm,('1000','1250','1500','1750','2000'),7),('Nötr',self.neutral,('1000','1500','2000'),7),('Süre',self.servo_seconds,('0.5','1','2','3'),7)):
            tk.Label(row,text=title,bg=BLACK,fg=GRAY).pack(side='left',padx=(0,4));ttk.Combobox(row,textvariable=var,values=values,state='readonly',width=width).pack(side='left',padx=(0,9))
        self.servo_button=self._button(row,'Servoyu test et',self.servo_test)
        row=tk.Frame(p,bg=BLACK);row.pack(fill='x',pady=5);tk.Label(row,text='Gözlenen işlev',bg=BLACK,fg=GRAY).pack(side='left')
        tk.Entry(row,textvariable=self.servo_function,width=32,bg='#25282d',fg=WHITE,insertbackground=YELLOW,relief='flat').pack(side='left',padx=8);self._button(row,'Eşlemeyi kaydet',self.save_servo_note);self._button(row,'Eşleme raporunu kaydet',self.export_notes)
        self.output_status=tk.StringVar(value='Çıkış testi bekleniyor.')
        tk.Label(p,textvariable=self.output_status,bg=SURFACE,fg=YELLOW,padx=12,pady=10,anchor='w',font=('Segoe UI',10,'bold')).pack(fill='x',pady=8)

    def ground_ready(self):
        live=self.app.live_map;state=live.state
        return bool(live.enabled and live.session and live.session.link and live.session.calibration and state.armed is False and time.monotonic()-state.heartbeat_time<2)

    def calibrate(self,action):
        if not self.ground_ready():messagebox.showwarning('Yer testi kilitli','Cube’a yeniden bağlanırken “USB yer kurulumu” seçilmeli ve kart DISARMED olmalı.',parent=self.app.root);return
        if action=='esc':
            if not self.esc_guard.get():messagebox.showwarning('ESC kalibrasyonu','Pervanelerin fiziksel olarak söküldüğünü onaylayın.',parent=self.app.root);return
            prompt='ESC kalibrasyonu gerçek karta gönderilecek. Pervaneler sökülü, araç sabit ve üretici enerji sırası hazır mı?'
        else:prompt=f'{action.upper()} kalibrasyon komutu gerçek Cube karta gönderilsin mi?'
        if messagebox.askyesno('Gerçek kalibrasyon',prompt,parent=self.app.root):self.app.live_map.session.commands.put(action);self.cal_status.set('Komut gönderildi; kart sonucu bekleniyor…')

    def guard_ok(self):return self.output_guard.get() and self.guard_text.get().strip().upper()=='PERVANELER SÖKÜLDÜ'

    def motor_test(self):
        if not self.ground_ready() or not self.guard_ok():messagebox.showwarning('Motor testi kilitli','USB yer kurulumu, DISARMED durumu, onay kutusu ve tam “PERVANELER SÖKÜLDÜ” metni gerekir.',parent=self.app.root);return
        try:m=int(self.motor.get());p=float(self.percent.get());s=float(self.motor_seconds.get());assert 1<=m<=12 and 1<=p<=30 and .5<=s<=5
        except (ValueError,AssertionError):messagebox.showerror('Motor testi','Motor 1–12, gaz %1–30, süre 0,5–5 sn olmalı.',parent=self.app.root);return
        if messagebox.askyesno('Gerçek motor testi',f'Motor {m}, %{p:g}, {s:g} saniye çalıştırılsın mı?',parent=self.app.root):self.app.live_map.session.commands.put(('motor_test',m,p,s));self.output_status.set('Motor komutu gönderildi; ACK ve süre sonu bekleniyor…')

    def servo_test(self):
        if not self.ground_ready() or not self.guard_ok():messagebox.showwarning('Servo testi kilitli','USB yer kurulumu, DISARMED durumu ve fiziksel güvenlik onayı gerekir.',parent=self.app.root);return
        try:c=int(self.servo.get());p=int(self.pwm.get());n=int(self.neutral.get());s=float(self.servo_seconds.get());assert 1<=c<=16 and 1000<=p<=2000 and 1000<=n<=2000 and .5<=s<=3
        except (ValueError,AssertionError):messagebox.showerror('Servo testi','Servo 1–16, PWM/nötr 1000–2000, süre 0,5–3 sn olmalı.',parent=self.app.root);return
        if messagebox.askyesno('Gerçek servo testi',f'Servo {c}, {p} µs değerine {s:g} saniye gidip {n} µs nötre dönsün mü?',parent=self.app.root):self.app.live_map.session.commands.put(('servo_test',c,p,s,n));self.output_status.set('Servo komutu gönderildi; otomatik nötr bekleniyor…')

    def emergency(self):
        live=self.app.live_map
        if live.session and live.session.link:live.session.commands.put(('output_stop',));self.output_status.set('ACİL DURDURMA gönderildi.')

    def save_motor_note(self):
        self.motor_notes[self.motor.get()]=self.direction.get();self.output_status.set(f'Motor {self.motor.get()} yönü kaydedildi: {self.direction.get()}')

    def save_servo_note(self):
        text=self.servo_function.get().strip()
        if not text:messagebox.showinfo('Servo eşleme','Gözlenen işlevi yazın.',parent=self.app.root);return
        self.servo_notes[self.servo.get()]=text;self.output_status.set(f'Servo {self.servo.get()} eşlemesi kaydedildi.')

    def export_notes(self):
        path=filedialog.asksaveasfilename(parent=self.app.root,defaultextension='.json',initialfile='Fentek_Cikis_Eslemesi.json',filetypes=[('JSON','*.json')])
        if path:
            try:Path(path).write_text(json.dumps({'motors':self.motor_notes,'servos':self.servo_notes,'created':time.strftime('%Y-%m-%d %H:%M:%S')},ensure_ascii=False,indent=2),encoding='utf-8')
            except OSError as exc:messagebox.showerror('Eşleme raporu',str(exc),parent=self.app.root)

    def event(self,kind,value):
        if kind=='cal':self.cal_status.set(str(value))
        elif kind=='ground':self.output_status.set(str(value))
        elif kind=='position':
            self.position_request=value
            names={1:'Düz',2:'Sol yan',3:'Sağ yan',4:'Burun aşağı',5:'Burun yukarı',6:'Ters / sırt üstü'}
            if value:self.cal_status.set(f'Aracı {names.get(value,value)} konuma getirin, sabitleyin ve Devam’a basın.')
        elif kind in ('lost','error','done'):
            self.position_request=None;self.output_guard.set(False);self.guard_text.set('');self.output_status.set('Bağlantı kesildi • Çıkış testi kilitlendi.')

    def refresh(self):
        ready=self.ground_ready();state='normal' if ready else 'disabled'
        for button in self.cal_buttons+[self.esc_button,self.motor_button,self.servo_button]:button.configure(state=state)
        self.next_button.configure(state='normal' if ready and self.position_request else 'disabled')
        self.connection_status.set('HAZIR • Canlı USB yer kurulumu ve DISARMED Cube doğrulandı.' if ready else 'KİLİTLİ • Cube bağlantısında USB yer kurulumu seçilmeli ve kart DISARMED olmalı.')
        try:self.job=self.app.root.after(500,self.refresh)
        except tk.TclError:self.job=None

    def close(self):
        if self.job:
            try:self.app.root.after_cancel(self.job)
            except tk.TclError:pass
