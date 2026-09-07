"""Central-map cockpit with synthetic balance mode controls."""
import time
import tkinter as tk
from tkinter import ttk
from atlas import Atlas
from branded import BLACK,SURFACE,LINE,YELLOW,WHITE,GRAY
from demo import CENTER


class Cockpit(Atlas):
    def __init__(self,root,autoload=True):
        self.balance_mode=True
        self.balance_changed=time.monotonic()
        self.arm_state=False
        self.arm_initialized=False
        super().__init__(root,autoload=False)
        root.title('Fentek Havacılık • İHA Kontrol Merkezi')
        self.build_flight_page()
        if autoload:root.after(250,self.load_map)

    def build_flight_page(self):
        live=self.pages['Uçuş ekranı']
        for child in live.winfo_children():child.destroy()
        title=tk.Frame(live,bg=BLACK)
        title.pack(fill='x',pady=(0,10))
        self.label(title,'CANLI UÇUŞ MERKEZİ',19,WHITE,True).pack(side='left')
        self.balance_badge=tk.Label(title,text='  DENGE MODU AÇIK  ',bg='#3b3519',fg=YELLOW,font=('Segoe UI',10,'bold'),padx=12,pady=8)
        self.balance_badge.pack(side='right')
        area=tk.Frame(live,bg=BLACK)
        area.pack(fill='both',expand=True)
        left=tk.Frame(area,bg=SURFACE,width=215,padx=12,pady=12,highlightthickness=1,highlightbackground=LINE)
        left.pack(side='left',fill='y')
        left.pack_propagate(False)
        center=tk.Frame(area,bg=SURFACE,padx=8,pady=8,highlightthickness=1,highlightbackground=LINE)
        center.pack(side='left',fill='both',expand=True,padx=10)
        right=tk.Frame(area,bg=SURFACE,width=260,padx=12,pady=12,highlightthickness=1,highlightbackground=LINE)
        # Reserve the side panel before giving the map the remaining width.
        right.pack(side='right',fill='y',before=center)
        right.pack_propagate(False)
        self.side_heading(left,'UÇUŞ BİLGİLERİ')
        self.cockpit_rows={}
        for key,label in [('altitude','İrtifa'),('speed','Yer hızı'),('heading','Yön'),('mode','Uçuş modu'),('elapsed','Görev süresi')]:
            self.info_row(left,key,label)
        self.side_heading(left,'KONUM')
        for key in ('lat','lon'):self.cockpit_rows[key]=tk.StringVar(value='—')
        for key,label in [('pos_x','X / Kuzey (m)'),('pos_y','Y / Doğu (m)'),('pos_z','Z / Aşağı (m)')]:self.info_row(left,key,label)
        self.cockpit_rows['home']=tk.StringVar(value='—')
        self.layer=tk.StringVar(value='OPENSTREETMAP • SENTETİK İHA')
        top=tk.Frame(center,bg=SURFACE)
        top.pack(fill='x',pady=(0,7))
        tk.Label(top,textvariable=self.layer,bg=SURFACE,fg=YELLOW,font=('Segoe UI',9,'bold')).pack(side='left')
        self.label(top,'Sürükle • Tekerlekle yakınlaştır • Çift tıkla merkezle',8,GRAY).pack(side='right')
        self.canvas=tk.Canvas(center,bg='#161917',highlightthickness=0,width=560,height=420)
        self.canvas.pack(fill='both',expand=True)
        self.canvas.bind('<Configure>',lambda e:self.draw_map())
        self.canvas.bind('<ButtonPress-1>',self.map_press)
        self.canvas.bind('<B1-Motion>',self.map_drag)
        self.canvas.bind('<ButtonRelease-1>',self.map_release)
        self.canvas.bind('<MouseWheel>',self.map_wheel)
        self.canvas.bind('<Double-Button-1>',self.center_vehicle)
        self.canvas.configure(cursor='fleur')
        mapbar=tk.Frame(center,bg=SURFACE,pady=7)
        mapbar.pack(fill='x')
        self.mapbar_location_host=mapbar
        def map_button(text,command,primary=False):
            return tk.Button(mapbar,text=text,command=command,bg=YELLOW if primary else '#292b2f',fg=BLACK if primary else WHITE,
                             activebackground='#ffe36a' if primary else '#3b3e43',activeforeground=BLACK if primary else WHITE,
                             relief='flat',bd=0,padx=10,pady=6,font=('Segoe UI',9,'bold'),cursor='hand2')
        map_button('⌖  Merkezle',self.center_vehicle,True).pack(side='left',padx=(0,5))
        self.mark_button=map_button('＋  Nokta ekle',self.toggle_marking,True)
        self.mark_button.pack(side='left',padx=5)
        self.remove_marker_button=map_button('↶  Sonuncuyu sil',self.remove_last_marker)
        self.remove_marker_button.pack(side='left',padx=5)
        self.clear_marker_button=map_button('×  Tümünü sil',self.clear_markers)
        self.clear_marker_button.pack(side='left',padx=5)
        self.canvas.bind('<Button-3>',self.remove_marker_at)
        self.canvas.bind('<Delete>',self.remove_last_marker)
        self.map_status=tk.StringVar(value='Harita hazırlanıyor…')
        tk.Label(center,textvariable=self.map_status,bg=SURFACE,fg=GRAY,font=('Segoe UI',8),anchor='w').pack(fill='x')
        self.side_heading(right,'SİSTEM DURUMU')
        self.horizon=tk.Canvas(right,height=90,bg='#202327',highlightthickness=0)
        self.horizon.pack(fill='x',pady=(0,8))
        for key,label in [('arm','ARM'),('battery','Batarya'),('gps','GPS'),('link','Telemetri'),('data_age','Veri yaşı')]:
            value=self.compact_info_row(right,key,label)
            if key=='arm':self.arm_panel_label=value
        self.side_heading(right,'UÇUŞ KONTROLÜ')
        self.balance_button=ttk.Button(right,text='Denge modunu kapat',command=self.toggle_balance)
        self.balance_button.pack(fill='x',pady=8)
        ttk.Button(right,text='Demo kontrolleri',command=lambda:self.select('Demo kontrolleri'),style='Dark.TButton').pack(fill='x',pady=5)
        self.balance_note=tk.StringVar(value='Sentetik STABILIZE etkin. Gerçek karta komut gönderilmez.')
        tk.Label(right,textvariable=self.balance_note,bg=SURFACE,fg=GRAY,wraplength=195,justify='left',font=('Segoe UI',9)).pack(anchor='w',pady=12)
        self.side_heading(right,'KONUM / YEREL EKSEN')
        for key,label in [('city','Şehir'),('country','Ülke'),('x','X / Doğu'),('y','Y / Kuzey'),('z','Z / İrtifa')]:
            self.compact_info_row(right,key,label)
        self.update_cockpit_rows()

    def side_heading(self,parent,text):
        tk.Label(parent,text=text,bg=SURFACE,fg=YELLOW,font=('Segoe UI',10,'bold')).pack(anchor='w',pady=(4,8))
        tk.Frame(parent,bg=LINE,height=1).pack(fill='x',pady=(0,5))

    def info_row(self,parent,key,label):
        row=tk.Frame(parent,bg=SURFACE,pady=6)
        row.pack(fill='x')
        tk.Label(row,text=label,bg=SURFACE,fg=GRAY,font=('Segoe UI',9)).pack(anchor='w')
        var=tk.StringVar(value='—')
        self.cockpit_rows[key]=var
        tk.Label(row,textvariable=var,bg=SURFACE,fg=WHITE,font=('Segoe UI',12,'bold')).pack(anchor='w',pady=(2,0))

    def compact_info_row(self,parent,key,label):
        row=tk.Frame(parent,bg=SURFACE,pady=2)
        row.pack(fill='x')
        tk.Label(row,text=label,bg=SURFACE,fg=GRAY,font=('Segoe UI',8)).pack(side='left')
        var=tk.StringVar(value='—')
        self.cockpit_rows[key]=var
        value=tk.Label(row,textvariable=var,bg=SURFACE,fg=WHITE,font=('Segoe UI',9,'bold'))
        value.pack(side='right')
        return value

    def toggle_balance(self):
        self.balance_mode=not self.balance_mode
        self.balance_changed=time.monotonic()
        if self.balance_mode:
            self.balance_button['text']='Denge modunu kapat'
            self.balance_badge.configure(text='  DENGE MODU AÇIK  ',bg='#3b3519',fg=YELLOW)
            self.balance_note.set('Sentetik STABILIZE etkin. Yatış ve yunuslama azaltılır.')
            self.event('Sentetik denge modu uzaktan AÇILDI. Gerçek karta komut gönderilmedi.')
        else:
            self.balance_button['text']='Denge modunu aç'
            self.balance_badge.configure(text='  DENGE MODU KAPALI  ',bg='#3b2020',fg='#ff8d79')
            self.balance_note.set('Sentetik MANUAL etkin. Gerçek karta komut gönderilmez.')
            self.event('Sentetik denge modu uzaktan KAPATILDI. Gerçek karta komut gönderilmedi.')
        self.update_cockpit_rows()

    def update_display(self):
        if self.balance_mode and not (getattr(self,'live_map',None) and self.live_map.enabled):
            self.data['roll']*=.25
            self.data['pitch']*=.25
        super().update_display()
        if hasattr(self,'cockpit_rows'):self.update_cockpit_rows()

    def update_cockpit_rows(self):
        if getattr(self,'live_map',None) and self.live_map.enabled:return
        if not hasattr(self,'cockpit_rows'):return
        d=self.data
        home=getattr(self,'flight_center',CENTER)
        north=(d['lat']-home[0])*111320
        east=(d['lon']-home[1])*111320*__import__('math').cos(__import__('math').radians(home[0]))
        armed=d['altitude']>1.5
        if self.arm_initialized and armed!=self.arm_state:
            self.event('ARM • İHA havalandı; motor güvenlik durumu AÇIK.' if armed else 'DISARM • İHA yere indi; motor güvenlik durumu KAPALI.')
        self.arm_state=armed
        self.arm_initialized=True
        if hasattr(self,'arm_panel_label'):
            self.arm_panel_label.configure(fg=YELLOW if armed else GRAY)
        values={'altitude':f"{d['altitude']:.1f} m",'speed':f"{d['speed']:.1f} m/s",'heading':f"{d['heading']:03.0f}°",'mode':'STABILIZE' if self.balance_mode else 'MANUAL','elapsed':f'{int(self.t)//60:02}:{int(self.t)%60:02}','lat':f"{d['lat']:.7f}",'lon':f"{d['lon']:.7f}",'home':f'{(north*north+east*east)**.5:.0f} m','arm':'ARM • UÇUŞTA' if armed else 'DISARM • YERDE','battery':f"%{d['battery']:.0f}",'gps':f"3D FIX • {d['satellites']} uydu",'link':'BAĞLI' if self.link else 'KOPTU','data_age':f'{time.monotonic()-self.last_received:.1f} sn','city':getattr(self,'place_city','Aranıyor…'),'country':getattr(self,'place_country','—'),'x':f'{east:+.1f} m','y':f'{north:+.1f} m','z':f"{d['altitude']:+.1f} m"}
        values.update(pos_x=f'{north:+.2f}',pos_y=f'{east:+.2f}',pos_z=f"{-d['altitude']:+.2f}")
        for key,value in values.items():self.cockpit_rows[key].set(value)

    def tick(self):
        super().tick()
        self.update_cockpit_rows()


if __name__=='__main__':
    root=tk.Tk()
    Cockpit(root)
    root.mainloop()
