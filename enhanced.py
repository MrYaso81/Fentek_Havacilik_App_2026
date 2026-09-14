"""Extended synthetic station: plots, map annotations and event history."""
import csv
import math
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from branded import SchoolStation, BLACK, SURFACE, YELLOW, WHITE, GRAY
from demo import CENTER, world


class EnhancedStation(SchoolStation):
    def __init__(self,root):
        self.history=[]
        self.events_log=[]
        self.markers=[]
        self.marking=False
        self.show_trace=True
        self.last_history=-1
        super().__init__(root)
        root.title('Fentek Havacılık • İHA Kontrol Merkezi')
        nav=next(iter(self.nav_buttons.values())).master
        for name in ('Uçuş analizi','Olay günlüğü'):
            self.pages[name]=tk.Frame(self.deck,bg=BLACK)
            button=tk.Button(nav,text=name,anchor='w',command=lambda n=name:self.select(n),bg='#111214',fg=WHITE,activebackground=YELLOW,activeforeground=BLACK,relief='flat',bd=0,padx=12,pady=15,font=('Segoe UI',11,'bold'),cursor='hand2')
            button.pack(fill='x',pady=4)
            self.nav_buttons[name]=button
        analysis=self.pages['Uçuş analizi']
        self.heading(analysis,'UÇUŞ ANALİZİ','Son 120 örnek • İrtifa, hız ve batarya eğilimleri')
        self.charts=[]
        for title,key,color in [('İRTİFA  /  m','altitude',YELLOW),('YER HIZI  /  m/s','speed','#e4e6e9'),('BATARYA  /  %','battery','#c2a64a')]:
            chart=tk.Canvas(analysis,bg=SURFACE,height=132,highlightthickness=0)
            chart.pack(fill='both',expand=True,pady=5)
            chart.bind('<Configure>',lambda e:self.draw_charts())
            self.charts.append((chart,title,key,color))
        events=self.pages['Olay günlüğü']
        self.heading(events,'OLAY GÜNLÜĞÜ','Demo oturumundaki işlemler ve bağlantı değişimleri')
        self.event_text=tk.Text(events,bg=SURFACE,fg=WHITE,insertbackground=YELLOW,font=('Consolas',11),relief='flat',padx=16,pady=16,wrap='word',state='disabled')
        self.event_text.pack(fill='both',expand=True)
        tools=tk.Frame(events,bg=BLACK)
        tools.pack(fill='x',pady=12)
        ttk.Button(tools,text='Günlüğü kaydet',command=self.export_events).pack(side='left')
        ttk.Button(tools,text='Günlüğü temizle',command=self.clear_events,style='Dark.TButton').pack(side='left',padx=12)
        # Place a map toolbar underneath existing live information without crowding other tabs.
        live=self.pages['Uçuş ekranı']
        toolbar=tk.Frame(live,bg=BLACK,pady=6)
        toolbar.pack(side='bottom',fill='x',before=live.winfo_children()[-2])
        self.mark_button=ttk.Button(toolbar,text='Haritaya işaret ekle',command=self.toggle_marking)
        self.mark_button.pack(side='left',padx=(0,8))
        ttk.Button(toolbar,text='İşaretleri temizle',command=self.clear_markers,style='Dark.TButton').pack(side='left',padx=8)
        self.trace_button=ttk.Button(toolbar,text='İzi gizle',command=self.toggle_trace,style='Dark.TButton')
        self.trace_button.pack(side='left',padx=8)
        self.canvas.bind('<Button-1>',self.add_marker)
        self.event('Demo başlatıldı. Veriler sentetik; araç bağlı değil.')

    def event(self,text):
        self.events_log.append(f'{time.strftime("%H:%M:%S")}  {text}')
        self.events_log=self.events_log[-300:]
        if hasattr(self,'event_text'):
            self.event_text.configure(state='normal')
            self.event_text.delete('1.0','end')
            self.event_text.insert('end','\n'.join(self.events_log))
            self.event_text.see('end')
            self.event_text.configure(state='disabled')

    def pause(self):
        super().pause()
        self.event('Simülasyon devam ediyor.' if self.running else 'Simülasyon duraklatıldı.')

    def toggle_link(self):
        super().toggle_link()
        self.event('Demo bağlantısı geri geldi.' if self.link else 'Bağlantı kaybı denemesi: son alınan veri korunuyor.')

    def reset(self):
        self.history=[]
        self.last_history=-1
        super().reset()
        self.event('Uçuş başlangıca döndürüldü; grafik geçmişi sıfırlandı.')

    def update_display(self):
        super().update_display()
        if self.t-self.last_history>=1:
            self.history.append((self.t,dict(self.data)))
            self.history=self.history[-120:]
            self.last_history=self.t
        if hasattr(self,'charts'): self.draw_charts()

    def draw_charts(self):
        for canvas,title,key,color in getattr(self,'charts',[]):
            canvas.delete('all')
            w,h=canvas.winfo_width(),canvas.winfo_height()
            if w<80: continue
            canvas.create_text(16,18,text=title,anchor='w',fill=GRAY,font=('Segoe UI',9,'bold'))
            samples=[d[key] for _,d in self.history]
            if not samples: continue
            low,high=min(samples),max(samples)
            padding=max((high-low)*.15,.5)
            low,high=low-padding,high+padding
            canvas.create_text(w-18,18,text=f'{samples[-1]:.1f}',anchor='e',fill=color,font=('Segoe UI',14,'bold'))
            for fraction in (0,.5,1):
                y=40+fraction*(h-62)
                canvas.create_line(55,y,w-18,y,fill='#303238')
                canvas.create_text(44,y,text=f'{high-fraction*(high-low):.1f}',anchor='e',fill=GRAY,font=('Segoe UI',8))
            points=[]
            for i,value in enumerate(samples):
                points.extend((55+i/max(1,len(samples)-1)*(w-73),40+(high-value)/(high-low)*(h-62)))
            if len(points)>=4: canvas.create_line(*points,fill=color,width=2)
            canvas.create_text(56,h-9,text=f'{len(samples)} örnek • sentetik veri',anchor='w',fill=GRAY,font=('Segoe UI',8))

    def toggle_marking(self):
        self.marking=not self.marking
        self.mark_button['text']='✓  Haritaya tıkla' if self.marking else '＋  Nokta ekle'
        self.canvas.configure(cursor='crosshair' if self.marking else '')
        self.event('Haritaya tıklayarak not noktası ekleyin. Bu noktalar uçuş rotasını değiştirmez.' if self.marking else 'İşaretleme kapatıldı.')

    def add_marker(self,event):
        if not self.marking: return
        # Inverse Web Mercator uses the same center/zoom as the actual background.
        cx,cy=world(*CENTER)
        x=cx+event.x-self.canvas.winfo_width()/2
        y=cy+event.y-self.canvas.winfo_height()/2
        size=256*2**17
        lat=math.degrees(math.atan(math.sinh(math.pi*(1-2*y/size))))
        lon=x/size*360-180
        self.markers.append((lat,lon,0.0))
        self.event(f'Not noktası {len(self.markers):02}: {lat:.6f}, {lon:.6f} (demo).')
        self.update_marker_buttons()
        self.draw_map()

    def remove_last_marker(self,event=None):
        if not self.markers:
            self.event('Silinecek harita noktası yok.')
            return
        number=len(self.markers)
        self.markers.pop()
        self.marking=False
        self.mark_button['text']='＋  Nokta ekle'
        self.update_marker_buttons()
        self.draw_map()
        self.event(f'Not noktası {number:02} silindi.')

    def remove_marker_at(self,event):
        if not self.markers:return
        distances=[]
        for index,marker in enumerate(self.markers):
            lat,lon=marker[:2]
            x,y=self.marker_xy(marker)
            distances.append((min((x-event.x)**2+(y-event.y)**2,(x-event.x)**2+(y-23-event.y)**2),index))
        distance,index=min(distances)
        if distance>28**2:return
        self.markers.pop(index)
        self.update_marker_buttons()
        self.draw_map()
        self.event(f'Haritadaki {index+1:02} numaralı nokta sağ tıklamayla silindi.')

    def clear_markers(self):
        count=len(self.markers)
        self.markers=[]
        self.marking=False
        self.mark_button['text']='＋  Nokta ekle'
        self.update_marker_buttons()
        self.draw_map()
        self.event(f'Haritadaki {count} not noktası temizlendi.' if count else 'Silinecek harita noktası yok.')

    def update_marker_buttons(self):
        # Keep deletion actions visible and clickable even when the list is empty.
        if hasattr(self,'remove_marker_button'):self.remove_marker_button.configure(state='normal')
        if hasattr(self,'clear_marker_button'):self.clear_marker_button.configure(state='normal')

    def toggle_trace(self):
        self.show_trace=not self.show_trace
        self.trace_button['text']='İzi gizle' if self.show_trace else 'İzi göster'
        self.draw_map()

    def draw_map(self):
        saved=self.track
        if not self.show_trace: self.track=[]
        try: super().draw_map()
        finally: self.track=saved
        self.draw_map_markers()

    def marker_xy(self,marker):
        return self.map_xy(*marker[:2])

    def draw_map_markers(self):
        route=[self.marker_xy(marker) for marker in self.markers]
        for start,end in zip(route,route[1:]):
            if start==end:continue
            self.canvas.create_line(*start,*end,fill='#fff4c2',width=7)
            self.canvas.create_line(*start,*end,fill='#101010',width=4)
            # Place a direction arrow mid-segment so the destination pin cannot hide it.
            ax,ay=start;bx,by=end
            self.canvas.create_line(ax+(bx-ax)*.40,ay+(by-ay)*.40,
                                    ax+(bx-ax)*.60,ay+(by-ay)*.60,
                                    fill='#101010',width=4,arrow='last',arrowshape=(12,14,6))
        if len(route)>1:
            self.canvas.create_text(12,42,anchor='nw',text='ROTA TASLAĞI • Karta gönderilmedi',
                                    fill=YELLOW,font=('Segoe UI',9,'bold'))
        for i,marker in enumerate(self.markers,1):
            lat,lon=marker[:2]
            altitude=marker[2] if len(marker)>2 else 0.0
            x,y=self.marker_xy(marker)
            # Leave the bottom image attribution area unobstructed.
            if y>self.canvas.winfo_height()-35: continue
            # The pointed tip is exactly at the stored map coordinate.
            points=[x,y,x-6,y-10,x-14,y-21,x-13,y-31,x-6,y-38,
                    x+6,y-38,x+13,y-31,x+14,y-21,x+6,y-10,x,y]
            self.canvas.create_polygon(*points,fill=YELLOW,outline='#6f5310',width=2,smooth=True,splinesteps=24)
            self.canvas.create_oval(x-8,y-31,x+8,y-15,fill='#fff4c2',outline='')
            self.canvas.create_text(x,y-23,text=str(i),fill=BLACK,font=('Segoe UI',9,'bold'))
            self.canvas.create_oval(x-2,y-2,x+2,y+2,fill='#ffd42a',outline='#6f5310')
            if altitude:
                self.canvas.create_text(x,y+20,text=f'Z {altitude:g} m',fill=WHITE,font=('Segoe UI',8,'bold'))
        rally=getattr(getattr(self,'operations',None),'rally_points',())
        for i,marker in enumerate(rally,1):
            x,y=self.marker_xy(marker)
            if y>self.canvas.winfo_height()-35:continue
            self.canvas.create_polygon(x,y-15,x-13,y+10,x+13,y+10,fill='#62bfff',outline='#e7f6ff',width=2)
            self.canvas.create_text(x,y+1,text='R'+str(i),fill=BLACK,font=('Segoe UI',7,'bold'))
            self.canvas.create_text(x,y+24,text=f'RALLY • {marker[2]:g} m',fill='#8fd2ff',font=('Segoe UI',8,'bold'))

    def export_events(self):
        path=filedialog.asksaveasfilename(defaultextension='.txt',initialfile='demo_olay_gunlugu.txt',filetypes=[('Metin','*.txt')])
        if path:
            try:
                with open(path,'w',encoding='utf-8') as f: f.write('SENTETİK DEMO OLAY GÜNLÜĞÜ\n'+'\n'.join(self.events_log))
                self.event('Olay günlüğü kaydedildi.')
            except OSError: messagebox.showerror('Kayıt hatası','Dosya yazılamadı.')

    def clear_events(self):
        self.events_log=[]
        self.event('Günlük temizlendi.')


if __name__=='__main__':
    root=tk.Tk()
    EnhancedStation(root)
    root.mainloop()
