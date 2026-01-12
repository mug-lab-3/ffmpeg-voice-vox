import os
import sqlite3
import pytest
from app.core.database import DatabaseManager

@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")

@pytest.fixture
def db_mgr(db_path, monkeypatch):
    # Mocking _get_db_path to return our temp path
    monkeypatch.setattr(DatabaseManager, "_get_db_path", lambda self: db_path)
    return DatabaseManager()

def test_database_migration_and_persistence(db_mgr, db_path):
    # 1. 旧形式のテーブルを作成（speaker_name, speaker_style なし）
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE transcriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            text TEXT NOT NULL,
            speaker_id INTEGER,
            speed_scale REAL,
            pitch_scale REAL,
            intonation_scale REAL,
            volume_scale REAL,
            pre_phoneme_length REAL,
            post_phoneme_length REAL,
            output_path TEXT,
            audio_duration REAL DEFAULT 0.0
        )
    """)
    conn.close()

    # 2. DatabaseManagerを初期化（ここでマイグレーションが走るはず）
    # _get_connection を呼ぶことで _init_db_conn が実行される
    conn = db_mgr._get_connection()
    conn.close()

    # 3. カラムが存在することを確認
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("PRAGMA table_info(transcriptions)")
    columns = [row["name"] for row in cursor.fetchall()]
    assert "speaker_name" in columns
    assert "speaker_style" in columns
    conn.close()

    # 4. データの保存と読み出しをテスト
    config_dict = {
        "speed_scale": 1.2,
        "pitch_scale": 0.0,
        "intonation_scale": 1.0,
        "volume_scale": 1.0,
        "pre_phoneme_length": 0.1,
        "post_phoneme_length": 0.1
    }
    
    db_id = db_mgr.add_transcription(
        text="テストメッセージ",
        speaker_id=8,
        config_dict=config_dict,
        speaker_name="ずんだもん",
        speaker_style="あまあま"
    )

    logs = db_mgr.get_recent_logs(limit=1)
    assert len(logs) == 1
    log = logs[0]
    assert log["text"] == "テストメッセージ"
    assert log["speaker_name"] == "ずんだもん"
    assert log["speaker_style"] == "あまあま"

if __name__ == "__main__":
    pytest.main([__file__])
