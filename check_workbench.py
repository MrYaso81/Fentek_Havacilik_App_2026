import time
import tkinter as tk
from workbench import Workbench

root=tk.Tk()
a=Workbench(root)
root.geometry('1060x720')
a.select('Kurulum ve test')
root.update()
for index in range(3):
    a.test_tabs.select(index)
    root.update()
    def check(widget):
        for child in widget.winfo_children():
            if child.winfo_ismapped() and child.winfo_class() in ('TButton','Button'):
                assert child.winfo_rooty()+child.winfo_height()<=root.winfo_rooty()+root.winfo_height(),child.cget('text')
            check(child)
    check(a.pages['Kurulum ve test'])
a.begin_cal()
for _ in range(6):a.next_cal()
assert a.cal_step is None and a.cal_progress['value']==6
a.percent.set('20')
a.seconds.set('1')
a.start_motor()
assert a.motor_active and a.motor_percent==20
end=time.monotonic()+1.2
while time.monotonic()<end:
    root.update()
    time.sleep(.01)
assert not a.motor_active
a.start_motor()
a.link=False
end=time.monotonic()+.1
while time.monotonic()<end:
    root.update()
    time.sleep(.01)
assert not a.motor_active
a.param_vars['DEMO_TEST_PERCENT'].set('nan')
assert not a.apply_params()
a.param_vars['DEMO_TEST_PERCENT'].set('20')
assert a.apply_params()
a.close()
print('Calibration steps, 20% motor demo, timeout, link loss, parameter validation and tab layout passed.')
