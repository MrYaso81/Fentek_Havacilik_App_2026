import queue
import threading
import unittest
from types import SimpleNamespace
from parameter_manager import ParameterClient


def msg(name,value,system=1,component=1):
    return SimpleNamespace(get_type=lambda:'PARAM_VALUE',get_srcSystem=lambda:system,get_srcComponent=lambda:component,param_id=name.encode(),param_value=value)


class Mav:
    def __init__(self):self.calls=[]
    def __getattr__(self,name):return lambda *args:self.calls.append((name,args))


class ParameterTests(unittest.TestCase):
    def test_read_allow_list(self):
        names=('FS_GCS_ENABLE','FS_GCS_TIMEOUT','FS_THR_ENABLE','FS_EKF_ACTION','FS_BATT_ENABLE')
        wire=SimpleNamespace(mav=Mav(),recv_match=lambda **k: msg(names[len(wire.mav.calls)-len(names)] if False else 'FS_GCS_ENABLE',2))
        # Return each requested parameter in order; the client only accepts matching names.
        values=iter([msg(name,index) for index,name in enumerate(names)])
        wire.recv_match=lambda **k: next(values,None)
        client=ParameterClient(wire,1,stop=threading.Event())
        result=client.read_failsafes()
        self.assertEqual(set(result),set(names));self.assertEqual(len(wire.mav.calls),5)

    def test_write_is_allow_list_and_read_back(self):
        wire=SimpleNamespace(mav=Mav(),recv_match=lambda **k: msg('FS_GCS_ENABLE',2))
        client=ParameterClient(wire,1,stop=threading.Event())
        self.assertEqual(client.set_failsafe('FS_GCS_ENABLE',2),2)
        self.assertEqual(wire.mav.calls[0][0],'param_set_send')
        with self.assertRaises(ValueError):client.set_failsafe('SERVO1_FUNCTION',0)

    def test_stale_other_system_is_ignored(self):
        values=iter([msg('FS_GCS_ENABLE',2,system=2),msg('FS_GCS_ENABLE',3)])
        wire=SimpleNamespace(mav=Mav(),recv_match=lambda **k: next(values,None))
        client=ParameterClient(wire,1,stop=threading.Event())
        self.assertEqual(client.set_failsafe('FS_GCS_ENABLE',3),3)


if __name__=='__main__':unittest.main()
