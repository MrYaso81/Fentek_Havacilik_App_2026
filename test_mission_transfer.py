import threading
import unittest
from types import SimpleNamespace
from mission_transfer import Transfer,validate_points


def msg(kind,**fields):
    return SimpleNamespace(get_type=lambda:kind,get_srcSystem=lambda:1,get_srcComponent=lambda:1,**fields)


class Mav:
    def __init__(self):self.calls=[]
    def __getattr__(self,name):
        return lambda *args:self.calls.append((name,args))


class MissionTests(unittest.TestCase):
    def make(self,messages):
        mav=Mav()
        link=SimpleNamespace(mav=mav,recv_match=lambda **kw:messages.pop(0) if messages else None)
        report=[]
        return Transfer(link,1,threading.Event(),report.append),mav,report

    def sequence(self):
        return [msg('HEARTBEAT',autopilot=3,base_mode=0),
                msg('HOME_POSITION',latitude=410000000,longitude=290000000,altitude=100000),
                msg('MISSION_REQUEST_INT',seq=0),msg('MISSION_REQUEST_INT',seq=1),
                msg('MISSION_REQUEST_INT',seq=1),msg('MISSION_REQUEST_INT',seq=2),
                msg('MISSION_ACK',type=0),msg('MISSION_COUNT',count=3),
                msg('MISSION_ITEM_INT',seq=0,command=16),
                msg('MISSION_ITEM_INT',seq=1,command=16,frame=3,x=410000000,y=290000000,z=40,autocontinue=1,param1=0,param2=0,param3=0,param4=0),
                msg('MISSION_ITEM_INT',seq=2,command=20)]

    def test_upload_and_readback(self):
        transfer,mav,report=self.make(self.sequence())
        transfer.run([(41,29,40)])
        self.assertTrue(report[-1].startswith('DOĞRULANDI'))
        self.assertEqual([a[2] for n,a in mav.calls if n=='mission_item_int_send'],[0,1,1,2])
        self.assertFalse(any(n in ('set_mode_send','mission_clear_all_send') for n,a in mav.calls))
        self.assertEqual([a[2] for n,a in mav.calls if n=='command_long_send'],[512])

    def test_armed_blocks_upload(self):
        t,m,_=self.make([msg('HEARTBEAT',autopilot=3,base_mode=128)])
        with self.assertRaisesRegex(RuntimeError,'ARMED'):t.run([(41,29,40)])
        self.assertFalse(any(n=='mission_count_send' for n,a in m.calls))

    def test_reject_ack(self):
        messages=self.sequence();messages[6].type=3
        t,_,_=self.make(messages)
        with self.assertRaisesRegex(RuntimeError,'reddetti'):t.run([(41,29,40)])

    def test_readback_mismatch(self):
        messages=self.sequence();messages[9].z=80
        t,_,report=self.make(messages)
        with self.assertRaisesRegex(RuntimeError,'farklı'):t.run([(41,29,40)])
        self.assertFalse(any(s.startswith('DOĞRULANDI') for s in report))

    def test_validation(self):
        for p in ([],[(41,29,0)],[(91,29,40)],[(41,29,float('nan'))]):
            with self.assertRaises(ValueError):validate_points(p)

    def test_more_than_ten_points_are_allowed(self):
        points=[(41+i/100000,29,40) for i in range(250)]
        self.assertEqual(len(validate_points(points)),250)

    def test_cancel(self):
        t,m,_=self.make([]);t.stop.set()
        with self.assertRaisesRegex(RuntimeError,'iptal'):t.run([(41,29,40)])
        self.assertEqual(m.calls,[])


if __name__=='__main__':unittest.main()
