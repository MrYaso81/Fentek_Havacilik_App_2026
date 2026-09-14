import unittest

from camera_view import source_value


class CameraViewTests(unittest.TestCase):
    def test_usb_sources(self):
        self.assertEqual(source_value('USB Kamera 0'),0)
        self.assertEqual(source_value('USB Kamera 1'),1)

    def test_network_sources(self):
        self.assertEqual(source_value('Ağ kamerası (RTSP / HTTP)','rtsp://192.168.1.20/live'),'rtsp://192.168.1.20/live')
        self.assertEqual(source_value('Ağ kamerası (RTSP / HTTP)','https://cam.test/mjpeg'),'https://cam.test/mjpeg')

    def test_local_files_and_invalid_addresses_are_rejected(self):
        for value in ('','kamera.mp4','ftp://example.test/cam'):
            with self.assertRaises(ValueError):source_value('Ağ kamerası (RTSP / HTTP)',value)


if __name__=='__main__':unittest.main()
