import unittest
import json
from app import create_app


class TestConfigSync(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.testing = True
        self.client = self.app.test_client()

    def test_synthesis_update_returns_full_config_lsync(self):
        """L-Sync: 音声合成設定の更新が最新の全設定データを返すか検証"""
        res = self.client.post("/api/config/synthesis", json={"speed_scale": 1.25})
        self.assertEqual(res.status_code, 200)

        data = res.get_json()
        self.assertEqual(data["status"], "ok")
        # should contain full config state
        self.assertIn("config", data)
        self.assertIn("speed_scale", data["config"])
        self.assertEqual(data["config"]["speed_scale"], 1.25)
        self.assertIn("outputDir", data)

    def test_resolve_update_returns_full_config_lsync(self):
        """L-Sync: Resolve設定の更新が最新の全設定データを返すか検証"""
        res = self.client.post("/api/config/resolve", json={"audio_track_index": 3})
        self.assertEqual(res.status_code, 200)

        data = res.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("config", data)
        self.assertEqual(data["config"]["resolve"]["audio_track_index"], 3)

    def test_ffmpeg_update_returns_status_only_hsync(self):
        """H-Sync: FFmpeg設定の更新がステータスのみを返す(全データは返さない)か検証"""
        res = self.client.post(
            "/api/config/ffmpeg", json={"ffmpeg_path": "Z:/ffmpeg.exe"}
        )
        self.assertEqual(res.status_code, 200)

        data = res.get_json()
        self.assertEqual(data["status"], "ok")
        # should NOT contain full config state to minimize heavy response during dialog flow
        self.assertNotIn("config", data)

    def test_system_update_returns_status_only_hsync(self):
        """H-Sync: システム設定の更新がステータスのみを返すか検証"""
        res = self.client.post("/api/config/system", json={"output_dir": "Z:/out"})
        self.assertEqual(res.status_code, 200)

        data = res.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertNotIn("config", data)


if __name__ == "__main__":
    unittest.main()
