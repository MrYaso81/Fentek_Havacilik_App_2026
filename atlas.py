"""Keyless map viewport and full parameter-file inspector."""
import base64
import concurrent.futures
import math
import queue
import re
import threading
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from workbench import Workbench
from branded import BLACK,SURFACE,YELLOW,WHITE,GRAY
from demo import CENTER,world


def parse_parameters(text):
    values={}
    for number,line in enumerate(text.splitlines(),1):
        line=line.strip()
        if not line or line.startswith(('#',';')):continue
        parts=re.split(r'[,\s]+',line)
        if len(parts)==2:name,value=parts
        elif len(parts)==5:name,value=parts[2:4] # QGroundControl sys/comp/name/value/type
        else:raise ValueError(f'{number}. satır: NAME,VALUE biçimi bekleniyor.')
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}',name):raise ValueError(f'{number}. satır: geçersiz ad.')
        if not math.isfinite(float(value)):raise ValueError(f'{number}. satır: sonlu sayı gerekli.')
        if name in values:raise ValueError(f'{number}. satır: yinelenen parametre {name}.')
        values[name]=value
    if not values:raise ValueError('Dosyada parametre bulunamadı.')
    return values


def esri_png_url(zoom,x,y):
    """Request the same World Imagery service as a PNG Tk can display natively."""
    edge=20037508.342789244
    scale=2*edge/(2**zoom)
    xmin=-edge+x*scale
    xmax=xmin+scale
    ymax=edge-y*scale
    ymin=ymax-scale
    query=urlencode({
        'bbox':f'{xmin},{ymin},{xmax},{ymax}',
        'bboxSR':'3857','imageSR':'3857','size':'256,256',
        'format':'png32','transparent':'false','f':'image'})
    return 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/export?'+query


class Atlas(Workbench):
    def __init__(self,root,autoload=True):
        self.view_center=list(CENTER)
        self.view_zoom=17
        self.drag_start=None
        self.drag_center_world=None
        self.tiles={}
        self.tile_times={}
        self.tile_queue=queue.Queue()
        self.tile_loading=False
        self.tile_loading_source=None
        self.tile_reload_pending=False
        self.tile_cancel=threading.Event()
        self.osm_enabled=True
        self.map_tile_source='osm'
        self.atlas_job=None
        self.parameters={}
        super().__init__(root)
        root.title('Fentek Havacılık • Harita ve Parametre Merkezi')
        nav=next(iter(self.nav_buttons.values())).master
        for widget in nav.winfo_children():
            if isinstance(widget,ttk.Checkbutton):widget.destroy()
        self.motion=True
        self.canvas.bind('<ButtonPress-1>',self.map_press)
        self.canvas.bind('<B1-Motion>',self.map_drag)
        self.canvas.bind('<ButtonRelease-1>',self.map_release)
        self.canvas.bind('<MouseWheel>',self.map_wheel)
        self.canvas.bind('<Double-Button-1>',self.center_vehicle)
        self.canvas.configure(cursor='fleur')
        maps=self.pages['Harita ayarları']
        ttk.Button(maps,text='OpenStreetMap haritasını yükle',command=self.load_map).pack(anchor='w',pady=8)
        page=tk.Frame(self.test_tabs,bg=BLACK,padx=12,pady=12)
        self.test_tabs.add(page,text='Tüm parametreler')
        self.label(page,'KART PARAMETRE DOSYASI',13,YELLOW,True).pack(anchor='w')
        self.label(page,'Mission Planner .param veya QGroundControl dosyası • Karta yazılmaz',9,GRAY).pack(anchor='w',pady=6)
        bar=tk.Frame(page,bg=BLACK)
        bar.pack(fill='x',pady=8)
        ttk.Button(bar,text='Parametre dosyasını aç',command=self.import_params).pack(side='left')
        self.search=tk.StringVar()
        ttk.Entry(bar,textvariable=self.search,width=22).pack(side='right')
        self.label(bar,'Ara: ',10,GRAY).pack(side='right')
        self.search.trace_add('write',lambda *args:self.filter_params())
        style=ttk.Style()
        style.configure('Treeview',background=SURFACE,fieldbackground=SURFACE,foreground=WHITE,rowheight=28,font=('Consolas',10))
        style.configure('Treeview.Heading',background='#292b2e',foreground=YELLOW,font=('Segoe UI',10,'bold'))
        tablebox=tk.Frame(page,bg=BLACK)
        tablebox.pack(fill='both',expand=True)
        self.table=ttk.Treeview(tablebox,columns=('name','value','group'),show='headings',height=8)
        for key,title,width in [('name','Parametre',240),('value','Dosyadaki değer',150),('group','Grup',160)]:
            self.table.heading(key,text=title)
            self.table.column(key,width=width)
        scroll=ttk.Scrollbar(tablebox,orient='vertical',command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y')
        self.table.pack(fill='both',expand=True)
        self.param_count=tk.StringVar(value='Henüz dosya yok. Gerçek parametre listesi kart/firmware sürümünden alınmalıdır.')
        tk.Label(page,textvariable=self.param_count,bg=BLACK,fg=GRAY,wraplength=700,font=('Segoe UI',9)).pack(anchor='w',pady=8)
        self.atlas_job=root.after(100,self.poll_tiles)
        if autoload:root.after(250,self.load_map)

    def import_params(self):
        path=filedialog.askopenfilename(filetypes=[('Parametre dosyaları','*.param *.params *.txt'),('Tüm dosyalar','*.*')])
        if not path:return
        try:
            if Path(path).stat().st_size>2_000_000:raise ValueError('Dosya 2 MB sınırını aşıyor.')
            parsed=parse_parameters(Path(path).read_text(encoding='utf-8-sig'))
        except (OSError,ValueError) as exc:
            messagebox.showerror('Parametre dosyası',str(exc));return
        self.parameters=parsed
        self.filter_params()
        self.event(f'{len(parsed)} parametre dosyadan okundu. Karta yazılmadı.')

    def filter_params(self):
        self.table.delete(*self.table.get_children())
        query=self.search.get().strip().upper()
        count=0
        for name,value in sorted(self.parameters.items()):
            if query not in name.upper():continue
            self.table.insert('', 'end',values=(name,value,name.split('_')[0]))
            count+=1
        self.param_count.set(f'{count} / {len(self.parameters)} parametre • Dosyadan okundu; bağlı kartla doğrulanmadı.')

    def load_map(self):
        source=getattr(self,'map_tile_source','osm')
        if self.tile_loading:
            # A pan, zoom or layer switch occurred during the active download.
            self.tile_reload_pending=True
            self.tile_cancel.set()
            return
        self.osm_enabled=True
        self.image=None
        self.root.update_idletasks()
        w,h=max(300,self.canvas.winfo_width()),max(200,self.canvas.winfo_height())
        zoom=self.view_zoom
        cx,cy=world(*self.view_center,zoom)
        keys=[(x,y) for x in range(int((cx-w/2)//256),int((cx+w/2)//256)+1) for y in range(int((cy-h/2)//256),int((cy+h/2)//256)+1)]
        ttl=86400 if source=='esri' else 7*86400
        missing=[k for k in keys if (source,zoom,*k) not in self.tiles or time.time()-self.tile_times.get((source,zoom,*k),0)>=ttl]
        if not missing:
            self.draw_map()
            label='Esri World Imagery uydu katmanı' if source=='esri' else 'OpenStreetMap'
            self.map_status.set(label+' önbellekten hazır • İHA konumu sentetiktir.')
            return
        # Show center tiles first so the useful part of the map appears immediately.
        tile_cx,tile_cy=cx/256,cy/256
        missing.sort(key=lambda item:(item[0]-tile_cx)**2+(item[1]-tile_cy)**2)
        self.tile_loading=True
        cancel=threading.Event()
        self.tile_cancel=cancel
        self.tile_loading_source=source
        self.tile_reload_pending=False
        self.map_status.set('Uydu görüntüleri yükleniyor…' if source=='esri' else 'OpenStreetMap yükleniyor… Gerçek sokak haritasıdır.')
        cache=Path(__file__).parent/'map_cache'
        def worker():
            try:cache.mkdir(exist_ok=True)
            except OSError:
                self.tile_queue.put(('error',(source,'Harita önbelleği açılamadı.')))
                return
            # Publish disk hits before network work so one slow request cannot hide them.
            pending=[]
            success=failed=0
            for x,y in missing:
                if cancel.is_set():break
                file=cache/f'{source}_{zoom}_{x}_{y}.png'
                try:
                    data=file.read_bytes()
                    if not data.startswith(b'\x89PNG'):raise ValueError('Invalid PNG')
                    self.tile_queue.put(('tile',(source,zoom,x,y,data)))
                    if time.time()-file.stat().st_mtime<ttl:
                        success+=1
                        continue
                except (OSError,ValueError):pass
                pending.append((x,y))
            def fetch_tile(point):
                if cancel.is_set():return None
                x,y=point
                try:
                    file=cache/f'{source}_{zoom}_{x}_{y}.png'
                    if file.exists() and time.time()-file.stat().st_mtime<ttl:data=file.read_bytes()
                    else:
                        url=(esri_png_url(zoom,x,y) if source=='esri'
                             else f'https://tile.openstreetmap.org/{zoom}/{x}/{y}.png')
                        req=Request(url,headers={'User-Agent':'Fentek-Havacilik/1.0 (desktop flight simulation)'})
                        with urlopen(req,timeout=12) as response:data=response.read(1000000)
                        if not data.startswith(b'\x89PNG'):raise ValueError('Görüntü biçimi geçersiz')
                        file.write_bytes(data)
                    return x,y,data
                except Exception:return None
            workers=4 if source=='esri' else 2
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                futures=[pool.submit(fetch_tile,point) for point in pending]
                for future in concurrent.futures.as_completed(futures):
                    result=future.result()
                    if result is None:
                        failed+=1
                        continue
                    x,y,data=result
                    success+=1
                    self.tile_queue.put(('tile',(source,zoom,x,y,data)))
            if success:self.tile_queue.put(('done',(source,failed)))
            else:self.tile_queue.put(('error',(source,'Harita alınamadı. İnternet bağlantısını kontrol edip Harita ayarlarından tekrar deneyin.')))
        threading.Thread(target=worker,daemon=True).start()

    def poll_tiles(self):
        dirty=False
        try:
            for _ in range(16):
                kind,value=self.tile_queue.get_nowait()
                if kind=='tile':
                    source,zoom,x,y,data=value
                    try:self.tiles[source,zoom,x,y]=tk.PhotoImage(data=base64.b64encode(data))
                    except tk.TclError:continue
                    cache_file=Path(__file__).parent/'map_cache'/f'{source}_{zoom}_{x}_{y}.png'
                    self.tile_times[source,zoom,x,y]=cache_file.stat().st_mtime if cache_file.exists() else time.time()
                    dirty=True
                else:
                    completed_source=value[0]
                    failed=value[1] if kind=='done' else 0
                    error_text=None if kind=='done' else value[1]
                    reload_needed=self.tile_reload_pending or getattr(self,'map_tile_source','osm')!=completed_source
                    self.tile_loading=False
                    self.tile_loading_source=None
                    self.tile_reload_pending=False
                    if kind=='done':
                        label='Esri World Imagery uydu katmanı' if completed_source=='esri' else 'OpenStreetMap'
                        suffix=f' • {failed} parça alınamadı' if failed else ''
                        self.map_status.set(label+' hazır • İHA konumu sentetiktir.'+suffix)
                    else:self.map_status.set(error_text)
                    if reload_needed:
                        self.root.after_idle(self.load_map)
        except queue.Empty:pass
        if dirty:self.draw_map()
        self.atlas_job=self.root.after(40,self.poll_tiles)

    def draw_map(self):
        super().draw_map()
        if not self.osm_enabled or self.image:return
        if self.tiles:
            w,h=self.canvas.winfo_width(),self.canvas.winfo_height()
            cx,cy=world(*self.view_center,self.view_zoom)
            source=getattr(self,'map_tile_source','osm')
            for (tile_source,zoom,x,y),photo in self.tiles.items():
                if tile_source!=source or zoom!=self.view_zoom:continue
                if not (-256<x*256-cx+w/2<w and -256<y*256-cy+h/2<h):continue
                item=self.canvas.create_image(w/2+x*256-cx,h/2+y*256-cy,image=photo,anchor='nw')
                self.canvas.tag_lower(item)
            self.layer.set(('ESRI WORLD IMAGERY • UYDU GÖRÜNTÜSÜ' if source=='esri' else 'OPENSTREETMAP • DÜNYA HARİTASI')+' • SENTETİK İHA')
        # Animated locator rings only indicate the simulated vehicle; no extra map requests.
        if getattr(self,'live_map',None) and self.live_map.enabled:return
        x,y=self.map_xy(self.data['lat'],self.data['lon'])
        radius=24+(time.monotonic()%2)/2*22
        self.canvas.create_oval(x-radius,y-radius,x+radius,y+radius,outline='#bfa746',width=1)

    def map_xy(self,lat,lon):
        w,h=self.canvas.winfo_width(),self.canvas.winfo_height()
        cx,cy=world(*self.view_center,self.view_zoom)
        x,y=world(lat,lon,self.view_zoom)
        return w/2+x-cx,h/2+y-cy

    def map_press(self,event):
        if self.marking:
            self.add_marker(event)
            return
        self.drag_start=(event.x,event.y)
        self.drag_center_world=world(*self.view_center,self.view_zoom)
        self.canvas.configure(cursor='hand2')

    def map_drag(self,event):
        if not self.drag_start or self.marking:return
        dx=event.x-self.drag_start[0]
        dy=event.y-self.drag_start[1]
        self.set_center_world(self.drag_center_world[0]-dx,self.drag_center_world[1]-dy)
        self.draw_map()

    def map_release(self,event):
        if self.marking:return
        moved=self.drag_start and (abs(event.x-self.drag_start[0])>3 or abs(event.y-self.drag_start[1])>3)
        self.drag_start=self.drag_center_world=None
        self.canvas.configure(cursor='fleur')
        if moved:
            self.event(f'Harita kaydırıldı: {self.view_center[0]:.5f}, {self.view_center[1]:.5f}')
            self.load_map()

    def set_center_world(self,x,y):
        size=256*2**self.view_zoom
        x=x%size
        y=max(0,min(size,y))
        self.view_center[1]=x/size*360-180
        self.view_center[0]=math.degrees(math.atan(math.sinh(math.pi*(1-2*y/size))))

    def map_wheel(self,event):
        new_zoom=max(3,min(19,self.view_zoom+(1 if event.delta>0 else -1)))
        if new_zoom==self.view_zoom:return
        # Keep the geographic point under the cursor in the same screen position.
        old_x,old_y=world(*self.view_center,self.view_zoom)
        point_x=old_x+event.x-self.canvas.winfo_width()/2
        point_y=old_y+event.y-self.canvas.winfo_height()/2
        scale=2**(new_zoom-self.view_zoom)
        self.view_zoom=new_zoom
        new_point_x,new_point_y=point_x*scale,point_y*scale
        self.set_center_world(new_point_x-(event.x-self.canvas.winfo_width()/2),new_point_y-(event.y-self.canvas.winfo_height()/2))
        self.draw_map()
        self.map_status.set(f'Yakınlaştırma: {self.view_zoom} • Harita yükleniyor…')
        self.load_map()

    def center_vehicle(self,event=None):
        self.view_center[:]=[self.data['lat'],self.data['lon']]
        self.draw_map()
        self.load_map()
        self.event('Harita sentetik İHA konumuna merkezlendi.')

    def add_marker(self,event):
        if not self.marking:return
        if len(self.markers)>=10:
            messagebox.showinfo('İşaretler','En fazla 10 not noktası ekleyebilirsiniz.')
            return
        cx,cy=world(*self.view_center,self.view_zoom)
        x=cx+event.x-self.canvas.winfo_width()/2
        y=cy+event.y-self.canvas.winfo_height()/2
        size=256*2**self.view_zoom
        lat=math.degrees(math.atan(math.sinh(math.pi*(1-2*y/size))))
        lon=x/size*360-180
        self.markers.append((lat,lon,0.0))
        self.event(f'Not noktası {len(self.markers):02}: {lat:.6f}, {lon:.6f} (demo).')
        self.update_marker_buttons()
        self.draw_map()

    def offline_map(self):
        self.osm_enabled=False
        super().offline_map()

    def close(self):
        self.tile_cancel.set()
        if self.atlas_job:self.root.after_cancel(self.atlas_job)
        super().close()


if __name__=='__main__':
    root=tk.Tk()
    Atlas(root)
    root.mainloop()
