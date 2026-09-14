"""Live MAVLink alert evaluation and a compact Tk alert centre."""
import time
import threading
import tkinter as tk
from tkinter import ttk

from branded import BLACK, SURFACE, YELLOW, WHITE, GRAY


# Three short tones are easier to recognise than the Windows notification
# sound and do not depend on the user's selected Windows sound scheme.
ALARM_PATTERNS={
    'warning':((920,130),(920,130),(920,130)),
    'critical':((1180,170),(1180,170),(1180,220)),
}


def play_alarm_pattern(level,beep,pause=time.sleep):
    """Play a compact classic 'dit-dit-dit' pattern."""
    pattern=ALARM_PATTERNS.get(level,ALARM_PATTERNS['warning'])
    for index,(frequency,duration) in enumerate(pattern):
        beep(frequency,duration)
        if index<len(pattern)-1:pause(.10)


def evaluate_alerts(state, now=None, connected_expected=False, started_at=0):
    """Return active alerts without inventing values for missing telemetry."""
    now=time.monotonic() if now is None else now
    alerts=[]
    hb_age=now-state.heartbeat_time if state.heartbeat_time else None
    if connected_expected and ((hb_age is not None and hb_age>6) or (hb_age is None and started_at and now-started_at>12)):
        alerts.append(('telemetry','critical','TELEMETRİ KAYBI','Cube yaşam sinyali 6 saniyeden uzun süredir alınmıyor. Son veriler güncel değildir.'))
    if state.battery is not None:
        if state.battery<=10:
            alerts.append(('battery','critical','KRİTİK BATARYA',f'Kalan batarya %{state.battery:.0f}. Kartın batarya failsafe davranışını izleyin.'))
        elif state.battery<=20:
            alerts.append(('battery','warning','DÜŞÜK BATARYA',f'Kalan batarya %{state.battery:.0f}. Güvenli dönüş/iniş kararını değerlendirin.'))
    if hb_age is not None and hb_age<=3:
        fix_age=now-state.fix_time if state.fix_time else None
        if state.fix is None or state.fix<3 or fix_age is None or fix_age>3:
            alerts.append(('gps','critical' if state.armed else 'warning','GPS KONUMU KAYIP','Güncel 3D GPS çözümü alınmıyor. Konum gerektiren modları kullanmayın.'))
    if state.fence_breach and state.fence_time and now-state.fence_time<=5:
        alerts.append(('fence','critical','SANAL ÇİT İHLALİ','Cube FENCE_STATUS ile sınır ihlali bildirdi.'))
    if state.radio_time and now-state.radio_time<=4:
        margins=[]
        for signal,noise in (('rssi','noise'),('remrssi','remnoise')):
            a,b=state.radio.get(signal),state.radio.get(noise)
            if a not in (None,255) and b not in (None,255):margins.append(int(a)-int(b))
        if margins and min(margins)<20:
            alerts.append(('radio','warning','TELEMETRİ SİNYALİ ZAYIF',f'En düşük sinyal/gürültü farkı {min(margins)} ham birim.'))
    total=state.packet_received+state.packet_lost
    if total>=100:
        loss=100*state.packet_lost/total
        if loss>=10:
            alerts.append(('packet_loss','critical' if loss>=20 else 'warning','PAKET KAYBI YÜKSEK',f'Tahmini MAVLink paket kaybı %{loss:.1f}.'))
    for stamp,severity,text in state.alerts[-5:]:
        if now-stamp<=8:
            level='critical' if severity<=3 else 'warning'
            alerts.append((f'card:{severity}:{text[:80]}',level,'CUBE UYARISI',text))
    return alerts


class AlertManager:
    COLORS={'normal':'#7cdbac','warning':'#ffd42a','critical':'#ff6259'}

    def __init__(self,app):
        self.app=app;self.muted=tk.BooleanVar(value=False);self.active={};self.history=[];self.job=None
        self.sound_playing=False
        self._build_page();self._build_badge()
        self.job=app.root.after(500,self.poll)

    def _build_page(self):
        name='Uyarılar'
        page=tk.Frame(self.app.deck,bg=BLACK);self.app.pages[name]=page
        nav=next(iter(self.app.nav_buttons.values())).master
        button=tk.Button(nav,text='08   Uyarılar',anchor='w',command=lambda:self.app.select(name),bg='#101113',fg=GRAY,
                         activebackground='#25231a',activeforeground=YELLOW,relief='flat',bd=0,padx=15,pady=10,
                         font=('Segoe UI',10,'bold'),cursor='hand2')
        button.pack(fill='x',pady=4);self.app.nav_buttons[name]=button
        self.app.heading(page,'UYARI MERKEZİ','Canlı Cube telemetrisi • Ses susturulsa da renkli uyarılar ve geçmiş devam eder')
        controls=tk.Frame(page,bg=BLACK);controls.pack(fill='x',pady=(0,12))
        self.mute_button=ttk.Button(controls,text='🔊  Uyarı sesi açık',command=self.toggle_mute)
        self.mute_button.pack(side='left')
        ttk.Button(controls,text='Alarmı dene • dit dit dit',command=lambda:self.sound('warning'),style='Dark.TButton').pack(side='left',padx=8)
        ttk.Button(controls,text='Geçmişi temizle',command=self.clear,style='Dark.TButton').pack(side='left',padx=8)
        self.summary=tk.Label(page,text='CANLI BAĞLANTI BEKLENİYOR',bg=SURFACE,fg=GRAY,font=('Segoe UI',14,'bold'),
                              padx=16,pady=14,anchor='w')
        self.summary.pack(fill='x',pady=(0,10))
        self.current=tk.Label(page,text='Etkin uyarı yok.',bg=BLACK,fg=WHITE,justify='left',anchor='nw',
                              wraplength=900,font=('Segoe UI',10),pady=8)
        self.current.pack(fill='x')
        tk.Label(page,text='UYARI GEÇMİŞİ',bg=BLACK,fg=YELLOW,font=('Segoe UI',11,'bold')).pack(anchor='w',pady=(12,6))
        host=tk.Frame(page,bg=BLACK);host.pack(fill='both',expand=True)
        scroll=ttk.Scrollbar(host);scroll.pack(side='right',fill='y')
        self.text=tk.Text(host,bg=SURFACE,fg=WHITE,insertbackground=YELLOW,relief='flat',state='disabled',
                          wrap='word',font=('Consolas',10),padx=14,pady=12,yscrollcommand=scroll.set)
        self.text.pack(side='left',fill='both',expand=True);scroll.configure(command=self.text.yview)

    def _build_badge(self):
        header=self.app.root.winfo_children()[0]
        self.badge=tk.Button(header,text='● UYARILAR BEKLİYOR',command=lambda:self.app.select('Uyarılar'),
                             bg='#292d31',fg=GRAY,activebackground='#41454a',activeforeground=WHITE,
                             relief='flat',bd=0,padx=11,pady=7,font=('Segoe UI',8,'bold'),cursor='hand2')
        self.badge.pack(side='right',padx=7)

    def toggle_mute(self):
        self.muted.set(not self.muted.get())
        self.mute_button.configure(text='🔇  Uyarı sesi kapalı' if self.muted.get() else '🔊  Uyarı sesi açık')
        self.app.event('Uyarı sesi kapatıldı; görsel uyarılar etkin.' if self.muted.get() else 'Uyarı sesi açıldı.')

    def sound(self,level):
        if self.muted.get() or self.sound_playing:return
        self.sound_playing=True
        def worker():
            try:
                import winsound
                play_alarm_pattern(level,winsound.Beep)
            except (ImportError,RuntimeError,OSError):pass
            finally:self.sound_playing=False
        # Beep is blocking, so play it outside Tk's interface thread.
        threading.Thread(target=worker,daemon=True).start()

    def add_history(self,level,title,detail):
        self.history.append(f'{time.strftime("%H:%M:%S")}  {level.upper():8}  {title} • {detail}')
        self.history=self.history[-300:]
        self.text.configure(state='normal');self.text.delete('1.0','end')
        self.text.insert('end','\n'.join(self.history) if self.history else 'Henüz uyarı yok.')
        self.text.see('end');self.text.configure(state='disabled')

    def clear(self):
        self.history=[];self.text.configure(state='normal');self.text.delete('1.0','end')
        self.text.insert('1.0','Uyarı geçmişi temizlendi.');self.text.configure(state='disabled')

    def poll(self):
        live=getattr(self.app,'live_map',None);now=time.monotonic()
        expected=bool(live and live.enabled and not live.stop.is_set())
        found=evaluate_alerts(live.state,now,expected,getattr(live,'started_at',0)) if live else []
        current={item[0]:item[1:] for item in found}
        for key,(level,title,detail) in current.items():
            if key not in self.active:
                self.add_history(level,title,detail);self.app.event(f'{title}: {detail}');self.sound(level)
        for key,(level,title,detail) in self.active.items():
            if key not in current:self.add_history('normal',title+' DÜZELDİ','Koşul artık etkin değil.')
        self.active=current
        if current:
            level='critical' if any(v[0]=='critical' for v in current.values()) else 'warning'
            rows=[f'• {title}: {detail}' for _,title,detail in current.values()]
            self.summary.configure(text=f'{len(current)} ETKİN UYARI',bg='#4a2020' if level=='critical' else '#493d14',fg=self.COLORS[level])
            self.current.configure(text='\n'.join(rows));self.badge.configure(text=f'● {len(current)} UYARI',bg='#5a2424' if level=='critical' else '#554716',fg=self.COLORS[level])
        else:
            label='CANLI İZLEME NORMAL' if expected else 'CANLI BAĞLANTI BEKLENİYOR'
            self.summary.configure(text=label,bg=SURFACE,fg=self.COLORS['normal'] if expected else GRAY)
            self.current.configure(text='Etkin uyarı yok.');self.badge.configure(text='● UYARI YOK' if expected else '● UYARILAR BEKLİYOR',bg='#193c32' if expected else '#292d31',fg=self.COLORS['normal'] if expected else GRAY)
        self.job=self.app.root.after(500,self.poll)

    def close(self):
        if self.job:
            try:self.app.root.after_cancel(self.job)
            except tk.TclError:pass
