import unittest

from cloud_pilot import CloudPilotError, OpenAIPilotClient, extract_output_text


class CloudPilotTests(unittest.TestCase):
    def test_extracts_response_text(self):
        data={"output":[{"type":"message","content":[{"type":"output_text","text":"Merhaba!"}]}]}
        self.assertEqual(extract_output_text(data),"Merhaba!")

    def test_request_is_private_read_only_and_context_limited(self):
        captured={}
        def fetch(payload,key):
            captured.update(payload);self.assertEqual(key,"sk-test-12345678901234567890")
            return {"output":[{"type":"message","content":[{"type":"output_text","text":"Kontrol edelim."}]}]}
        client=OpenAIPilotClient("sk-test-12345678901234567890",fetch=fetch)
        answer=client.reply("GPS nasıl?",[("user","Selam"),("assistant","Merhaba")],"GPS: 3D fix")
        self.assertEqual(answer,"Kontrol edelim.")
        self.assertFalse(captured["store"])
        self.assertEqual(captured["model"],"gpt-5.4-mini")
        self.assertIn("komutu gönderemezsin",captured["instructions"])
        self.assertNotIn("sk-test",str(captured))
        self.assertIn("GPS: 3D fix",captured["input"][-1]["content"])

    def test_rejects_missing_key_and_unknown_model(self):
        with self.assertRaises(CloudPilotError):OpenAIPilotClient("").reply("Merhaba")
        with self.assertRaises(CloudPilotError):OpenAIPilotClient("sk-test-12345678901234567890","unknown").reply("Merhaba")

    def test_missing_text_is_an_error(self):
        with self.assertRaises(CloudPilotError):extract_output_text({"output":[]})


if __name__=='__main__':unittest.main()
