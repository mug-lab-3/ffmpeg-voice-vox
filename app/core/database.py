import sqlite3
import os
import json
from datetime import datetime
from app.config import config


class DatabaseManager:
    def __init__(self):
        # We no longer set a fixed db_path here.
        # It will be determined dynamically in _get_connection.
        pass

    def _get_db_path(self):
        """Get the database path based on the current output directory."""
        from app.config import config

        output_dir = config.get("system.output_dir", "")
        if not output_dir:
            # Fallback to data directory if no output_dir is set
            return os.path.join(os.getcwd(), "data", "transcriptions.db")

        return os.path.join(output_dir, "transcriptions.db")

    def _get_connection(self):
        db_path = self._get_db_path()
        db_dir = os.path.dirname(db_path)

        if not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
            except Exception as e:
                print(f"[Database] Failed to create directory {db_dir}: {e}")
                # Fallback to a temporary or default location if needed?
                # For now, let it fail or use fallback path

        # Initialize if not exists
        is_new = not os.path.exists(db_path)

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # Optimization for SSD and Memory usage
        try:
            conn.execute("PRAGMA journal_mode = MEMORY")
            conn.execute("PRAGMA synchronous = OFF")
            conn.execute("PRAGMA cache_size = -64000")
            conn.execute("PRAGMA temp_store = MEMORY")
            conn.execute("PRAGMA mmap_size = 268435456")
        except Exception as e:
            print(f"[Database] Optimization PRAGMAs failed: {e}")

        if is_new:
            self._init_db_conn(conn)

        return conn

    def _init_db_conn(self, conn):
        """Initialize the database schema using an existing connection."""
        conn.execute(
            """
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
        """
        )
        conn.commit()

    def add_transcription(
        self, text, speaker_id, config_dict, output_path=None, audio_duration=0.0
    ):
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                INSERT INTO transcriptions (
                    text, speaker_id, speed_scale, pitch_scale,
                    intonation_scale, volume_scale, pre_phoneme_length, post_phoneme_length,
                    output_path, audio_duration
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    text,
                    speaker_id,
                    config_dict.get("speed_scale"),
                    config_dict.get("pitch_scale"),
                    config_dict.get("intonation_scale"),
                    config_dict.get("volume_scale"),
                    config_dict.get("pre_phoneme_length"),
                    config_dict.get("post_phoneme_length"),
                    output_path,
                    audio_duration,
                ),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def update_audio_info(self, db_id, output_path, audio_duration):
        conn = self._get_connection()
        try:
            conn.execute(
                """
                UPDATE transcriptions
                SET output_path = ?, audio_duration = ?
                WHERE id = ?
            """,
                (output_path, audio_duration, db_id),
            )
            conn.commit()
        finally:
            conn.close()

    def get_recent_logs(self, limit=50):
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT * FROM transcriptions
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def delete_log(self, db_id):
        conn = self._get_connection()
        try:
            conn.execute("DELETE FROM transcriptions WHERE id = ?", (db_id,))
            conn.commit()
        finally:
            conn.close()

    def get_transcription(self, db_id):
        """Retrieves transcription details by ID."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT id, text, output_path, audio_duration FROM transcriptions WHERE id = ?",
                (db_id,),
            )
            row = cursor.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "text": row["text"],
                    "output_path": row["output_path"],
                    "audio_duration": row["audio_duration"],
                }
        finally:
            conn.close()
        return None

    def update_transcription_text(self, db_id, new_text):
        conn = self._get_connection()
        try:
            conn.execute(
                """
                UPDATE transcriptions
                SET text = ?, output_path = NULL, audio_duration = 0.0
                WHERE id = ?
            """,
                (new_text, db_id),
            )
            conn.commit()
        finally:
            conn.close()

    def close_all_connections(self):
        """
        Closes all connections.
        Note: SQLite with WAL mode might still keep files open if not handled carefully,
        but for simple scripts, ensuring no active connection helps.
        """
        # In this simple implementation, we don't keep a pool,
        # but calling this can be a placeholder or we can use it to force a sync.
        pass


db_manager = DatabaseManager()
