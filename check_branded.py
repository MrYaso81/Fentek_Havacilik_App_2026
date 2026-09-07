import tkinter as tk
from premium import PremiumStation as SchoolStation

root=tk.Tk()
app=SchoolStation(root)
root.update()
for geometry in ('1280x820','1060x720'):
    root.geometry(geometry)
    root.update()
    for name,page in app.pages.items():
        app.select(name)
        root.update()
        def check(widget):
            for child in widget.winfo_children():
                if child.winfo_ismapped() and child.winfo_class() in ('TButton','Button'):
                    assert child.winfo_rooty()+child.winfo_height() <= root.winfo_rooty()+root.winfo_height(), (geometry,name,child.cget('text'))
                    assert child.winfo_rootx()+child.winfo_width() <= root.winfo_rootx()+root.winfo_width(), (geometry,name,child.cget('text'))
                check(child)
        check(page)
app.pause()
assert not app.running
app.toggle_link()
assert not app.link
app.reset()
assert app.running and app.link
app.toggle_trace()
assert not app.show_trace
app.toggle_marking()
assert app.marking
from types import SimpleNamespace
app.add_marker(SimpleNamespace(x=150,y=150))
assert len(app.markers)==1
app.clear_markers()
assert len(app.markers)==0
app.t=5
app.update_display()
assert app.history
assert app.events_log
app.select('Uçuş ekranı')
root.geometry('1280x820')
root.update()
try:
    from PIL import ImageGrab
    ImageGrab.grab(bbox=(root.winfo_rootx(),root.winfo_rooty(),root.winfo_rootx()+root.winfo_width(),root.winfo_rooty()+root.winfo_height())).save('cube_station/arayuz_onizleme.png')
except ImportError:
    pass
app.close()
print('6 tabs, two window sizes, visible buttons, charts, markers and events passed.')
