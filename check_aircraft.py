import tkinter as tk
from flight_pro import FlightPro

root=tk.Tk()
root.withdraw()
app=FlightPro(root,autoload=False)
try:
    for mode in ['Dünya Haritası','Simülasyon Haritası (3D)']:
        app.map_mode=mode
        for model in ['Sabit kanat','FPV','Döner kanat']:
            app.aircraft_type=model
            for heading in [0,90,180,270]:
                app.canvas.delete('all')
                app.draw_aircraft(app.canvas,100,100,heading)
                assert app.canvas.find_all()
    print('Three aircraft rendered at four headings in 2D and 3D.')
finally:app.close()
