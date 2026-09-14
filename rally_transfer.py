"""MAVLink 2 rally-point upload and read-back verification."""
import math
import time

MISSION_TYPE_RALLY = 2
MAV_CMD_NAV_RALLY_POINT = 5100
MAV_FRAME_GLOBAL_RELATIVE_ALT_INT = 6


def validate_rally_points(points):
    result = []
    for point in points:
        if len(point) < 3:
            raise ValueError('Rally noktası enlem, boylam ve irtifa içermeli.')
        lat, lon, alt = map(float, point[:3])
        if not all(map(math.isfinite, (lat, lon, alt))) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise ValueError('Rally koordinatı geçersiz.')
        if not 0 < alt <= 10_000:
            raise ValueError('Rally irtifası HOME üstünde 0–10000 m arasında olmalı.')
        result.append((lat, lon, alt))
    if not result:
        raise ValueError('En az bir rally noktası gerekir.')
    if len(result) > 255:
        raise ValueError('En fazla 255 rally noktası desteklenir.')
    return result


class RallyTransfer:
    def __init__(self, link, system, stop, report):
        self.link, self.system, self.stop, self.report = link, int(system), stop, report
        self.component = 1

    def receive(self, kinds, timeout=8):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and not self.stop.is_set():
            msg = self.link.recv_match(blocking=True, timeout=.25)
            if msg is None:
                continue
            if (msg.get_srcSystem(), msg.get_srcComponent()) != (self.system, self.component):
                continue
            if msg.get_type() in kinds:
                return msg
        raise TimeoutError('Rally aktarımı sırasında kart yanıtı alınamadı.')

    def run(self, points):
        points = validate_rally_points(points)
        hb = self.receive({'HEARTBEAT'})
        if getattr(hb, 'autopilot', None) != 3:
            raise RuntimeError('Seçilen araç ArduPilot olarak doğrulanmadı.')
        if getattr(hb, 'base_mode', 0) & 128:
            raise RuntimeError('Kart ARMED; rally aktarımı durduruldu.')
        if hasattr(self.link, 'mavlink20') and not self.link.mavlink20():
            raise RuntimeError('Rally aktarımı MAVLink 2 bağlantısı gerektirir.')
        self.report(f'{len(points)} rally noktası gönderiliyor…')
        self.link.mav.mission_count_send(self.system, self.component, len(points), MISSION_TYPE_RALLY)
        sent = set()
        while len(sent) < len(points):
            msg = self.receive({'MISSION_REQUEST_INT', 'MISSION_REQUEST', 'MISSION_ACK'})
            if msg.get_type() == 'MISSION_ACK':
                raise RuntimeError(f'Kart rally listesini erken reddetti: sonuç {msg.type}')
            seq = int(msg.seq)
            if not 0 <= seq < len(points):
                raise RuntimeError('Kart geçersiz rally sıra numarası istedi.')
            lat, lon, alt = points[seq]
            self.link.mav.mission_item_int_send(
                self.system, self.component, seq, MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                MAV_CMD_NAV_RALLY_POINT, 0, 1, 0, 0, 0, 0,
                int(round(lat * 1e7)), int(round(lon * 1e7)), alt, MISSION_TYPE_RALLY)
            sent.add(seq)
        ack = self.receive({'MISSION_ACK'})
        if int(ack.type) != 0:
            raise RuntimeError(f'Kart rally listesini reddetti: sonuç {ack.type}')
        self.link.mav.mission_request_list_send(self.system, self.component, MISSION_TYPE_RALLY)
        count = self.receive({'MISSION_COUNT'})
        if int(count.count) != len(points):
            raise RuntimeError(f'Geri okunan rally sayısı farklı: {count.count}/{len(points)}')
        readback = []
        for seq in range(len(points)):
            self.link.mav.mission_request_int_send(self.system, self.component, seq, MISSION_TYPE_RALLY)
            item = self.receive({'MISSION_ITEM_INT'})
            readback.append((item.x / 1e7, item.y / 1e7, float(item.z)))
        for expected, actual in zip(points, readback):
            if abs(expected[0] - actual[0]) > 1e-7 or abs(expected[1] - actual[1]) > 1e-7 or abs(expected[2] - actual[2]) > .1:
                raise RuntimeError('Karttan geri okunan rally noktası farklı.')
        self.report(f'DOĞRULANDI • {len(points)} rally noktası Cube üzerinde geri okundu.')
        return readback
