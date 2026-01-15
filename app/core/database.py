import sqlite3
import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.config import config


class Transcription(BaseModel):
    id: Optional[int] = None
    timestamp: Optional[str] = None
    text: str
    speaker_id: int
    speaker_name: Optional[str] = None
    speaker_style: Optional[str] = None
    speed_scale: float = 1.0
    pitch_scale: float = 0.0
    intonation_scale: float = 1.0
    volume_scale: float = 1.0
    pre_phoneme_length: float = 0.1
    post_phoneme_length: float = 0.1
    pause_length_scale: float = 1.0
    output_path: Optional[str] = None
    audio_duration: float = -1.0
    kana: Optional[str] = None
    phonemes: Optional[str] = None

    def __getitem__(self, item):
        """Allows dict-like access for backward compatibility (especially in tests)."""
        return getattr(self, item)

    @classmethod
    def from_row(cls, row: Any):
        """Creates a Transcription instance from a sqlite3.Row or a dict."""
        if isinstance(row, sqlite3.Row):
            data = dict(row)
        elif isinstance(row, dict):
            data = row
        else:
            raise TypeError(f"Expected sqlite3.Row or dict, got {type(row)}")
        return cls(**data)


class DatabaseManager:
    def __init__(self):
        pass

    def _get_db_path(self):
        """Get the database path based on the current output directory."""
        output_dir = config.get("system.output_dir", "")
        if not output_dir:
            return None
        return os.path.join(output_dir, "transcriptions.db")

    def _get_connection(self):
        db_path = self._get_db_path()
        if db_path is None:
            return None

        db_dir = os.path.dirname(db_path)
        if not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
            except Exception as e:
                print(f"[Database] Failed to create directory {db_dir}: {e}")
                return None

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        try:
            conn.execute("PRAGMA journal_mode = MEMORY")
            conn.execute("PRAGMA synchronous = OFF")
            conn.execute("PRAGMA cache_size = -64000")
            conn.execute("PRAGMA temp_store = MEMORY")
            conn.execute("PRAGMA mmap_size = 268435456")
        except Exception as e:
            print(f"[Database] Optimization PRAGMAs failed: {e}")

        self._init_db_conn(conn)
        return conn

    def _init_db_conn(self, conn):
        """Initialize the database schema and handle migrations."""
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transcriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                text TEXT NOT NULL,
                speaker_id INTEGER,
                speaker_name TEXT,
                speaker_style TEXT,
                speed_scale REAL,
                pitch_scale REAL,
                intonation_scale REAL,
                volume_scale REAL,
                pre_phoneme_length REAL,
                post_phoneme_length REAL,
                pause_length_scale REAL DEFAULT 1.0,
                output_path TEXT,
                audio_duration REAL DEFAULT -1.0,
                kana TEXT,
                phonemes TEXT
            )
        """
        )

        cursor = conn.execute("PRAGMA table_info(transcriptions)")
        columns = [row["name"] for row in cursor.fetchall()]

        migrations = [
            ("speaker_name", "TEXT"),
            ("speaker_style", "TEXT"),
            ("kana", "TEXT"),
            ("phonemes", "TEXT"),
            ("pause_length_scale", "REAL DEFAULT 1.0"),
        ]

        for col_name, col_type in migrations:
            if col_name not in columns:
                print(f"[Database] Migrating: Adding '{col_name}' column")
                conn.execute(
                    f"ALTER TABLE transcriptions ADD COLUMN {col_name} {col_type}"
                )

        conn.commit()

    def add_transcription(
        self,
        t: Any = None,
        speaker_id: int = None,
        config_dict: dict = None,
        **kwargs,
    ) -> int:
        """
        Adds a new transcription to the database.
        Supports both Transcription model and backward compatible arguments.
        """
        if not isinstance(t, Transcription):
            # Backward compatibility mode
            text = t
            # If text was passed as positional arg t, ensure it's not in kwargs too
            if "text" in kwargs:
                text = kwargs.pop("text")

            t = Transcription(
                text=text,
                speaker_id=speaker_id,
                **config_dict if config_dict else {},
                **kwargs,
            )

        conn = self._get_connection()
        if not conn:
            return 0
        try:
            cursor = conn.execute(
                """
                INSERT INTO transcriptions (
                    text, speaker_id, speaker_name, speaker_style,
                    speed_scale, pitch_scale, intonation_scale, volume_scale,
                    pre_phoneme_length, post_phoneme_length, pause_length_scale,
                    output_path, audio_duration, kana, phonemes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    t.text,
                    t.speaker_id,
                    t.speaker_name,
                    t.speaker_style,
                    t.speed_scale,
                    t.pitch_scale,
                    t.intonation_scale,
                    t.volume_scale,
                    t.pre_phoneme_length,
                    t.post_phoneme_length,
                    t.pause_length_scale,
                    t.output_path,
                    t.audio_duration,
                    t.kana,
                    t.phonemes,
                ),
            )
            conn.commit()
            t.id = cursor.lastrowid
            return t.id
        finally:
            conn.close()

    def update_audio_info(
        self,
        db_id: int,
        output_path: str,
        audio_duration: float,
        kana: Optional[str] = None,
        phonemes: Optional[str] = None,
    ):
        """Updates audio file information."""
        conn = self._get_connection()
        if not conn:
            return
        try:
            conn.execute(
                """
                UPDATE transcriptions
                SET output_path = ?, audio_duration = ?, kana = COALESCE(?, kana), phonemes = COALESCE(?, phonemes)
                WHERE id = ?
            """,
                (output_path, audio_duration, kana, phonemes, db_id),
            )
            conn.commit()
        finally:
            conn.close()

    def get_recent_logs(self, limit: int = 50) -> List[Transcription]:
        """Retrieves recent transcriptions as a list of models."""
        conn = self._get_connection()
        if not conn:
            return []
        try:
            cursor = conn.execute(
                "SELECT * FROM transcriptions ORDER BY id DESC LIMIT ?", (limit,)
            )
            return [Transcription.from_row(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_transcription(self, db_id: int) -> Optional[Transcription]:
        """Retrieves a single transcription by ID."""
        conn = self._get_connection()
        if not conn:
            return None
        try:
            cursor = conn.execute("SELECT * FROM transcriptions WHERE id = ?", (db_id,))
            row = cursor.fetchone()
            if row:
                return Transcription.from_row(row)
        finally:
            conn.close()
        return None

    def update_transcription_text(
        self,
        db_id: int,
        new_text: str,
        kana: Optional[str] = None,
        phonemes: Optional[str] = None,
    ):
        """Updates text and resets audio/derived attributes."""
        conn = self._get_connection()
        if not conn:
            return
        try:
            conn.execute(
                """
                UPDATE transcriptions
                SET text = ?, output_path = NULL, audio_duration = -1.0, kana = ?, phonemes = ?
                WHERE id = ?
            """,
                (new_text, kana, phonemes, db_id),
            )
            conn.commit()
        finally:
            conn.close()

    def delete_log(self, db_id: int):
        conn = self._get_connection()
        if not conn:
            return
        try:
            conn.execute("DELETE FROM transcriptions WHERE id = ?", (db_id,))
            conn.commit()
        finally:
            conn.close()

    def close_all_connections(self):
        pass


db_manager = DatabaseManager()
