import unittest
from types import SimpleNamespace
from pilot_ari import normalize,mode_answer,weather_answer,knowledge_answer,PilotAdvisor,PilotAri


class PilotAriTests(unittest.TestCase):
    def test_mode_comparison(self):
        text=mode_answer('STABILIZE ile LOITER arasındaki fark nedir?')
        self.assertIn('konum',text);self.assertIn('STABILIZE',text)

    def test_weather_requires_measurements(self):
        self.assertIn('rüzgâr',weather_answer('Hava uçuşa uygun mu?'))
        self.assertIn('5.0 m/s',weather_answer('Rüzgar 18 km/h ve yağmur yok'))

    def test_offline_status_does_not_guess(self):
        app=SimpleNamespace(live_map=SimpleNamespace(enabled=False),aircraft_type='Döner kanat')
        self.assertIn('bağlantısı yok',PilotAdvisor(app).status())

    def test_everyday_chat_and_typos(self):
        app=SimpleNamespace(live_map=SimpleNamespace(enabled=False),aircraft_type='Döner kanat')
        bot=PilotAdvisor(app)
        self.assertIn('Aleyküm selam',bot.reply('SA naslsnAS'))
        self.assertIn('Pilot Arı',bot.reply('sen kimsin'))
        self.assertIn('Rica ederim',bot.reply('teşekürler'))

    def test_typo_normalizer_recovers_domain_intents(self):
        self.assertEqual(normalize('telemteri baglanmyo nsl baglycam'),'telemetri baglanmiyor nasil baglayacagim')
        self.assertIn('DroneCAN',knowledge_answer('Orance Cub ve Her3 nasl calisyo'))
        app=SimpleNamespace(live_map=SimpleNamespace(enabled=False,serial_ports=lambda:[]),aircraft_type='Döner kanat')
        bot=PilotAdvisor(app)
        self.assertIn('Bağlantı sırası',bot.reply('telemteri baglanmyo nsl baglycam'))
        self.assertIn('güç modülünün',bot.reply('batrya gostrgesi gorunmyo'))

    def test_broad_typo_and_joined_word_matrix(self):
        cases={
            'gpss sinyli gelymi':'gps sinyal gelmiyor',
            'guvnlik failsef ayrlari nsl':'guvenlik failsafe ayarlari nasil',
            'ucusmodnu loytera alabilrmym':'ucus modu loiter',
            'gorevplanlama veypoint silemiyrm':'gorev planlama waypoint silemiyorum',
            'bilgisyara comu baglayamiyrm':'bilgisayar com baglayamiyorum',
            'ardupolt mavlnk firmwere':'ardupilot mavlink firmware',
            'motorum 2300 kv pervene tasirmi':'motor 2300 kv pervane tasir mi',
            'uyduharitasi cok yvas yuklenmyo':'uydu harita cok yavas yuklenmiyor',
            'slm nbr bugn naslsn':'selam naber bugun nasilsin',
        }
        for raw,expected in cases.items():
            corrected=normalize(raw)
            for token in expected.split():self.assertIn(token,corrected.split(),(raw,corrected))

    def test_broad_typos_route_to_useful_answers(self):
        app=SimpleNamespace(live_map=SimpleNamespace(enabled=False,serial_ports=lambda:[]),aircraft_type='Döner kanat')
        self.assertIn('Here3',PilotAdvisor(app).reply('gpss sinyli gelymi'))
        self.assertIn('Failsafe',PilotAdvisor(app).reply('guvnlik failsef ayrlari nsl olmali'))
        self.assertIn('LOITER',PilotAdvisor(app).reply('ucusmodnu loytera alabilrmym'))
        self.assertIn('OpenStreetMap',PilotAdvisor(app).reply('uyduharitasi cok yvas yuklenmyo'))

    def test_natural_paraphrases_route_without_mode_names(self):
        app=SimpleNamespace(live_map=SimpleNamespace(enabled=False,serial_ports=lambda:[]),aircraft_type='Döner kanat')
        self.assertIn('LOITER',PilotAdvisor(app).reply('İHA havada aynı noktada dursun, ne seçmeliyim?'))
        self.assertIn('ALT_HOLD',PilotAdvisor(app).reply('Konumu önemli değil ama yüksekliği korusun'))
        self.assertIn('RTL',PilotAdvisor(app).reply('Kalktığı yere kendi geri dönsün'))
        self.assertIn('AUTO',PilotAdvisor(app).reply('Yüklediğim rotayı kendi izlesin'))
        self.assertIn('güç modülünün',PilotAdvisor(app).reply('Pil seviyesini okuyamıyorum'))

    def test_followup_rephrases_and_lists_previous_answer(self):
        app=SimpleNamespace(live_map=SimpleNamespace(enabled=False),aircraft_type='Döner kanat')
        bot=PilotAdvisor(app);bot.reply('Here3 GPS nasıl çalışır?')
        self.assertIn('Daha basit',bot.reply('anlamadım daha basit anlat'))
        self.assertIn('•',bot.reply('madde madde liste yap'))

    def test_conversation_context(self):
        app=SimpleNamespace(live_map=SimpleNamespace(enabled=False),aircraft_type='Döner kanat')
        bot=PilotAdvisor(app);bot.reply('STABILIZE ile LOITER farkı ne')
        self.assertIn('Tek bir',bot.reply('peki hangisi daha iyi'))

    def test_technical_knowledge_and_parameters(self):
        self.assertIn('DroneCAN',knowledge_answer('Here3 gps nasıl çalışır'))
        self.assertIn('MAVLink',knowledge_answer('telemetri radyosu nedir'))
        self.assertIn('mAh',knowledge_answer('BATT_CAPACITY ne demek'))

    def test_nasil_calisir_is_not_how_are_you(self):
        app=SimpleNamespace(live_map=SimpleNamespace(enabled=False),aircraft_type='Döner kanat')
        answer=PilotAdvisor(app).reply('Cube Orange ve Here3 nasıl çalışır?')
        self.assertIn('DroneCAN',answer)
        self.assertNotIn('Sen nasılsın',answer)

    def test_telemetry_troubleshooting(self):
        app=SimpleNamespace(live_map=SimpleNamespace(enabled=False,serial_ports=lambda:[]),aircraft_type='Döner kanat')
        bot=PilotAdvisor(app)
        answer=bot.reply('Telemetri çalışmıyor nasıl bağlayabilirim?')
        self.assertIn('COM',answer);self.assertIn('57600',answer);self.assertIn('TELEM',answer)

    def test_status_and_troubleshooting_are_distinct(self):
        app=SimpleNamespace(live_map=SimpleNamespace(enabled=False,serial_ports=lambda:[]),aircraft_type='Döner kanat')
        bot=PilotAdvisor(app)
        self.assertIn('bağlantısı yok',bot.reply('telemetri ne durumda'))
        self.assertIn('Bağlantı sırası',bot.reply('telemetri bağlanmıyor'))

    def test_under_specified_mode_asks_for_goal(self):
        app=SimpleNamespace(live_map=SimpleNamespace(enabled=False),aircraft_type='Döner kanat')
        bot=PilotAdvisor(app)
        self.assertIn('amacını',bot.reply('hangi modda uçurmalıyım').lower())
        self.assertIn('LOITER',bot.reply('konumda beklemek istiyorum'))

    def test_unknown_question_asks_for_clarification(self):
        app=SimpleNamespace(live_map=SimpleNamespace(enabled=False),aircraft_type='Döner kanat')
        answer=PilotAdvisor(app).reply('orada bir şey oldu')
        self.assertIn('ayrıntı',answer)

    def test_local_long_message_answers_multiple_problems(self):
        app=SimpleNamespace(live_map=SimpleNamespace(enabled=False,serial_ports=lambda:[]),aircraft_type='Döner kanat')
        answer=PilotAdvisor(app).reply('Telemetri bağlanmıyor, GPS yok ve batarya da görünmüyor; nereden başlamalıyım?')
        self.assertIn('TELEMETRİ',answer);self.assertIn('GPS / HERE3',answer);self.assertIn('BATARYA',answer)

    def test_local_followup_can_summarize_and_give_example(self):
        app=SimpleNamespace(live_map=SimpleNamespace(enabled=False),aircraft_type='Döner kanat')
        bot=PilotAdvisor(app);bot.reply('LOITER modu nedir?')
        self.assertIn('Kısaca',bot.reply('bunu kısaca özetle'))
        self.assertIn('Örnek',bot.reply('bir örnek ver'))

    def test_clarification_uses_previous_message(self):
        app=SimpleNamespace(live_map=SimpleNamespace(enabled=False),aircraft_type='Döner kanat')
        bot=PilotAdvisor(app);bot.reply('oradaki cihazı anlamadım')
        answer=bot.reply('Here3 GPS kısmını soruyorum')
        self.assertIn('DroneCAN',answer)

    def test_more_everyday_chat(self):
        app=SimpleNamespace(live_map=SimpleNamespace(enabled=False),aircraft_type='Döner kanat')
        bot=PilotAdvisor(app)
        self.assertIn('ara vermek',bot.reply('bugün çok yoruldum'))
        self.assertIn('bilgi oyunu',bot.reply('canım sıkılıyor'))

    def test_hardware_performance_conversation_collects_values(self):
        app=SimpleNamespace(live_map=SimpleNamespace(enabled=False),aircraft_type='Döner kanat')
        bot=PilotAdvisor(app)
        first=bot.reply('İHA kaç gram olmalı ve uçuş süresi ne olur?')
        self.assertIn('sayısal donanım',first)
        second=bot.reply('Toplam ağırlık 1500 g, 4 motor, itki 850 g, batarya 5200 mAh, ortalama akım 20 A')
        self.assertIn('İtki/ağırlık',second);self.assertIn('12.5 dakika',second)

    def test_hardware_numbers_survive_common_typos(self):
        app=SimpleNamespace(live_map=SimpleNamespace(enabled=False),aircraft_type='Döner kanat')
        answer=PilotAdvisor(app).reply('toplm agrlik 1500 g, 4 motro, itkii 850 g, batrya 5200 mah, ortalma akm 20 a')
        self.assertIn('2.27',answer);self.assertIn('12.5 dakika',answer)

    def test_component_advisor_remembers_parts_and_finds_missing(self):
        app=SimpleNamespace(live_map=SimpleNamespace(enabled=False),aircraft_type='Döner kanat')
        bot=PilotAdvisor(app)
        first=bot.reply('Elimde Cube Orange, Here3 GPS, 4 motor ve ESC var, başka ne gerekli?')
        self.assertIn('Pervaneler',first);self.assertIn('Uçuş bataryası',first)
        second=bot.reply('Batarya, kumanda ve alıcı da var; şimdi eksik ne kaldı?')
        self.assertIn('Güç modülü',second);self.assertNotIn('• Uçuş bataryası\n',second.split('Temel sistemde henüz belirtilmeyenler:')[-1].split('\n\n')[0])

    def test_live_weather_intent_and_location_priority(self):
        self.assertTrue(PilotAri._weather_intent('Hava uçuş için uygun mu?'))
        state=SimpleNamespace(fresh=lambda:True,position={'lat':41.0,'lon':29.0})
        app=SimpleNamespace(live_map=SimpleNamespace(enabled=True,state=state),pc_location=(40.8,31.1))
        ui=object.__new__(PilotAri);ui.app=app
        location=ui._automatic_location()
        self.assertEqual(location.label,'İHA canlı konumu')
        self.assertEqual(location.latitude,41.0)


if __name__=='__main__':unittest.main()
