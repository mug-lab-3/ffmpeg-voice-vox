import sqlite3
import os
import json
from datetime import datetime
from app.config import config

class DatabaseManager:
    def __init__(self):
        # Now located in 'data' directory
        self.db_path = os.path.join(os.getcwd(), "data", "transcriptions.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._migrate_old_db()
        self._init_db()

    def _migrate_old_db(self):
        """Migrate DB from logs/ to data/ if needed."""
        old_path = os.path.join(os.getcwd(), "logs", "transcriptions.db")
        if os.path.exists(old_path) and not os.path.exists(self.db_path):
            try:
                print(f"[Database] Migrating DB to {self.db_path}")
                import shutil
                shutil.move(old_path, self.db_path)
            except Exception as e:
                print(f"[Database] Migration failed: {e}")

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS transcriptions (
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
            conn.commit()

    def add_transcription(self, text, speaker_id, config_dict, output_path=None, audio_duration=0.0):
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO transcriptions (
                    text, speaker_id, speed_scale, pitch_scale, 
                    intonation_scale, volume_scale, pre_phoneme_length, post_phoneme_length,
                    output_path, audio_duration
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                text, speaker_id, 
                config_dict.get("speed_scale"), 
                config_dict.get("pitch_scale"),
                config_dict.get("intonation_scale"), 
                config_dict.get("volume_scale"),
                config_dict.get("pre_phoneme_length"), 
                config_dict.get("post_phoneme_length"),
                output_path, audio_duration
            ))
            conn.commit()
            return cursor.lastrowid

    def update_audio_info(self, db_id, output_path, audio_duration):
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE transcriptions 
                SET output_path = ?, audio_duration = ?
                WHERE id = ?
            """, (output_path, audio_duration, db_id))
            conn.commit()

    def get_recent_logs(self, limit=50):
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM transcriptions 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def delete_log(self, db_id):
        with self._get_connection() as conn:
            conn.execute("DELETE FROM transcriptions WHERE id = ?", (db_id,))
            conn.commit()

db_manager = DatabaseManager()
