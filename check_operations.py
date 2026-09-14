"""UI smoke check; never connects to a vehicle or sends hardware commands."""
import tkinter as tk
import queue
import tempfile
import time
from types import SimpleNamespace
from pathlib import Path
from tkinter import messagebox
import operations as operations_module
from flight_pro import FlightPro

root=tk.Tk();root.geometry('1600x900');errors=[]
root.report_callback_exception=lambda *args:errors.append(args)
app=FlightPro(root,autoload=False)
assert len(app.nav_buttons)==len(app.pages)
assert all(button.winfo_ismapped() for button in app.nav_buttons.values())
assert all(button.cget('text').strip() for button in app.nav_buttons.values())
assert list(app.pages)[:2]==['Uçuş ekranı','Pilot Arı']
assert app.pilot_ari.send_button.cget('text')=='GÖNDER  ➜'
assert app.pilot_ari.send_button.cget('fg')=='#0c0d0f'
assert app.pilot_ari.entry.cget('state')=='normal'
assert app.pilot_ari.ai_settings_button.cget('text')=='⚙  AI ayarları'
assert not app.pilot_ari.ai_enabled
app.select('Pilot Arı');root.update_idletasks()
assert app.pilot_ari.entry.winfo_height()>=30
assert app.pilot_ari.entry.master.master.winfo_height()>=90
app.pilot_ari.entry.insert(0,'Pilot Arı yazı testi')
assert app.pilot_ari.entry.get()=='Pilot Arı yazı testi'
app.pilot_ari.entry.delete(0,'end')
for name in ('Uçuş modu özellikleri','Doğrudan kontrol','Görev planlama','Ölçüm araçları','Rally / Güvenli iniş','Parametreler','Güvenlik','ArduPilot SITL Testi','Kablosuz Telemetri','Telemetri','Yardımcı donanım','Bilgi ve Kılavuz','Uyarılar','Pilot Arı','Kamera görüntüsü','Uçuş ekranı'):
    app.select(name);root.update()
    assert app.pages[name].winfo_ismapped(),name
app.select('Kurulum ve test');root.update()
assert app.ground_tools.motor_button.cget('state')=='disabled'
assert app.ground_tools.servo_button.cget('state')=='disabled'
assert app.ground_tools.next_button.cget('state')=='disabled'
assert len(app.ground_tools.cal_buttons)==6
app.select('Kamera görüntüsü');root.update()
assert app.camera_view.start_button.cget('state')=='normal'
assert app.camera_view.record_button.cget('text')=='●  Kaydı başlat'
app.camera_view.test_pattern();root.update()
assert 'TEST GÖRÜNTÜSÜ' in app.camera_view.status.get()
ops=app.operations
assert not ops.live()
assert app.balance_button.cget('text')=='Demo denge: AÇIK'
assert app.demo_controls_button.cget('text')=='Diğer demo kontrolleri'
assert 'STABILIZE' in ops.mode_box.cget('values') and ops.mode.get()=='STABILIZE'
app.update_battery_gauge(76,16.42,12.34,845,live=True,fresh=True)
assert app.battery_big.cget('text')=='%76' and app.battery_source.cget('text')=='CANLI CUBE'
assert app.battery_big.cget('fg')=='#72d6a0'
app.update_battery_gauge(45,15.70,8.2,1240,live=True,fresh=True)
assert app.battery_big.cget('fg')=='#ffd42a'
app.update_battery_gauge(18,14.20,6.1,3200,live=True,fresh=True)
assert app.battery_big.cget('fg')=='#ff6259'
app.update_battery_gauge(76,16.42,12.34,845,live=True,fresh=False)
assert app.battery_source.cget('text')=='SON VERİ' and 'GÜNCEL DEĞİL' in app.battery_detail.cget('text')
app.update_battery_gauge(app.data['battery'],demo=True)
# The cockpit balance button must dispatch the verified real mode command while live.
sent=queue.Queue();app.live_map.enabled=True;app.link=True
app.live_map.session=SimpleNamespace(link=object(),commands=sent);app.live_map.state.mode='LOITER'
askyesno=messagebox.askyesno;messagebox.askyesno=lambda *args,**kwargs:True
app.toggle_balance();messagebox.askyesno=askyesno
assert sent.get_nowait()==('mode','STABILIZE')
app.live_map.state.armed=True;app.live_map.state.heartbeat_time=time.monotonic();app.live_map.state.autopilot=3
ops.params.update({'MAV_OPTIONS':(1,6),'MAV_GCS_SYSID':(255,6)})
messagebox.askyesno=lambda *args,**kwargs:True;ops.enable_direct();ops.start_direct((1,0,0));ops.stop_direct();messagebox.askyesno=askyesno
assert sent.get_nowait()==('manual_control',250,0,32767,0)
assert sent.get_nowait()==('manual_control',32767,32767,32767,32767)
app.live_map.enabled=False;app.link=False;app.live_map.session=None
app.aircraft_var.set('Sabit kanat');app.change_aircraft();assert 'FBWA' in ops.mode_box.cget('values')
app.aircraft_var.set('Döner kanat');app.change_aircraft();assert 'LOITER' in ops.mode_box.cget('values')
for mode in ('Dünya Haritası','Uydu Görüntüsü','Google Uydu','Simülasyon Haritası (3D)'):
    app.map_mode_var.set(mode);app.change_map_mode();root.update()
    expected='Uydu Görüntüsü' if mode=='Google Uydu' and not app.google_maps_key else mode
    assert app.map_mode==expected and app.canvas.find_all()
ops.lat.set('41');ops.lon.set('29');ops.alt.set('60');ops.edit_point(False)
assert app.markers[-1]==(41.,29.,60.)
ops.route.selection_set(str(len(app.markers)-1));ops.delete_point()
app.markers=[(41+i/100000,29,60.) for i in range(25)];ops.route_changed();root.update()
assert len(ops.route.get_children())==25
assert 'Toplam rota:' in ops.measure_result.cget('text') and len(ops.measure_legs.get_children())==24
app.markers=[];ops.route_changed()
ops.rally_lat.set('41');ops.rally_lon.set('29');ops.rally_alt.set('60');ops.edit_rally(False)
assert ops.rally_points==[(41.,29.,60.)]
ops.event('parameter',('BATT_CAPACITY',5000.,6,0,2));ops.query.set('BATT');ops.render_params()
assert len(ops.param_table.get_children())==1
assert len(ops.indices)<ops.count
ops.event('parameter',('FS_GCS_ENABLE',1.,6,1,2));ops.scenario.set('Yer istasyonu bağlantısı kesilirse');ops.run_safety_scenario()
assert 'YAPILANDIRILMIŞ' in ops.scenario_result.cget('text') and 'gerçek failsafe tetiklenmedi' in ops.scenario_result.cget('text')
app.select('Parametreler');ops.param_table.selection_set('BATT_CAPACITY');ops.explain_selected_param();root.update()
assert app.active_page=='Bilgi ve Kılavuz' and ops.guide_return_page=='Parametreler'
ops.guide_back();root.update();assert app.active_page=='Parametreler' and ops.param_table.selection()==('BATT_CAPACITY',)
app.select('Bilgi ve Kılavuz');ops.guide_query.set('ARM');ops.render_guide();root.update()
assert ops.guide_tree.get_children()
def button_texts(widget):
    values=[]
    for child in widget.winfo_children():
        if isinstance(child,tk.Button):values.append(child.cget('text'))
        values.extend(button_texts(child))
    return values
guide_buttons=button_texts(app.pages['Bilgi ve Kılavuz'])
assert any('Bilgi Kılavuzunu İndir' in value for value in guide_buttons)
target=Path(tempfile.gettempdir())/'fentek-guide-download-test.pdf'
save=operations_module.filedialog.asksaveasfilename;info=operations_module.messagebox.showinfo
operations_module.filedialog.asksaveasfilename=lambda **kwargs:str(target)
operations_module.messagebox.showinfo=lambda *args,**kwargs:None
ops.download_guide_pdf()
operations_module.filedialog.asksaveasfilename=save;operations_module.messagebox.showinfo=info
assert target.read_bytes()==(Path(__file__).parent/'assets'/'Fentek_Havacilik_Bilgi_Kilavuzu.pdf').read_bytes();target.unlink()
ops.explain_parameter('BATT_CAPACITY');assert 'mAh' in ops.guide_param_result.cget('text')
ops.explain_parameter('UNKNOWN_FIRMWARE_VALUE');assert 'doğrulanmış açıklama yok' in ops.guide_param_result.cget('text')
app.select('Telemetri');root.update()
canvas=app.pages['Telemetri']._scroll_canvas
canvas.yview_moveto(1);root.update();assert canvas.yview()[0]>0
assert not errors,errors
app.close()
print('Operational pages, scroll, route editing, partial parameter list: OK')
