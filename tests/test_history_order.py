import pytest
import sqlite3
import os
import tempfile
import shutil
from unittest.mock import MagicMock, patch
from app.core.database import DatabaseManager
from app.services.processor import StreamProcessor
from app.core.voicevox import VoiceVoxClient
from app.core.audio import AudioManager

class TestHistoryOrder:
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.test_dir = tempfile.mkdtemp()
        with patch("app.config.config.get", side_effect=lambda key, default=None: self.test_dir if key == "system.output_dir" else default):
            self.db_manager = DatabaseManager()
            self.audio_manager = AudioManager()
            self.mock_vv = MagicMock(spec=VoiceVoxClient)
            
            # Setup initial DB
            conn = self.db_manager._get_connection()
            # タイムスタンプが全く同じレコードを3つ挿入
            # timestampは '2026-01-12 12:00:00' で固定
            fixed_ts = "2026-01-12 12:00:00"
            for i in range(1, 4):
                conn.execute(
                    "INSERT INTO transcriptions (timestamp, text, speaker_id, speed_scale, pitch_scale, intonation_scale, volume_scale, pre_phoneme_length, post_phoneme_length) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (fixed_ts, f"Record {i}", 1, 1.0, 0.0, 1.0, 1.0, 0.1, 0.1)
                )
            conn.commit()
            conn.close()
            
            yield
            
        shutil.rmtree(self.test_dir)

    def test_database_order(self):
        # DBから取得した際、IDの降順（最新＝大きいIDが先）であることを確認
        logs = self.db_manager.get_recent_logs()
        assert len(logs) == 3
        assert logs[0]["id"] == 3
        assert logs[1]["id"] == 2
        assert logs[2]["id"] == 1
        assert logs[0]["text"] == "Record 3"
        assert logs[1]["text"] == "Record 2"
        assert logs[2]["text"] == "Record 1"

    def test_processor_loading_order(self):
        # StreamProcessorが読み込んだ際、UI表示用に古いものから順にリストに入っていることを確認
        # (Processorは get_recent_logs の結果を reversed() して append する)
        processor = StreamProcessor(self.mock_vv, self.audio_manager)
        logs = processor.get_logs()
        
        assert len(logs) == 3
        # UI上は古いもの(ID=1)が先頭、新しいもの(ID=3)が末尾
        assert logs[0]["id"] == 1
        assert logs[1]["id"] == 2
        assert logs[2]["id"] == 3
        assert logs[0]["text"] == "Record 1"
        assert logs[2]["text"] == "Record 3"
