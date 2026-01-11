import os
import re
import wave
import threading
import time
import sounddevice as sd
import soundfile as sf
from datetime import datetime

from app.config import config

class AudioManager:
    def __init__(self):
        # We no longer set a fixed output_dir here.
        # It is retrieved dynamically from config.

        self.playback_status = {
            "is_playing": False,
            "filename": None,
            "start_time": 0,
            "duration": 0
        }
        self.playback_lock = threading.Lock()

    def get_output_dir(self):
        """Get current output directory from config."""
        path = config.get("system.output_dir", "")
        return path

    def validate_output_dir(self, path: str) -> bool:
        """
        Validate if the output directory is usable.
        Checks for existence and write permissions.
        """
        if not path:
            return False

        if not os.path.exists(path):
            try:
                os.makedirs(path)
            except OSError:
                return False

        if not os.access(path, os.W_OK):
            return False

        return True

    def get_wav_duration(self, filepath: str) -> float:
        try:
            return sf.info(filepath).duration
        except Exception as e:
            print(f"Error getting wav duration: {e}")
            return 0.0

    def format_srt_time(self, seconds: float) -> str:
        millis = int((seconds - int(seconds)) * 1000)
        seconds = int(seconds)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"

    def save_audio(self, audio_data: bytes, text: str, db_id: int) -> tuple:
        """Saves audio data to a WAV file."""
        output_dir = self.get_output_dir()
        if not self.validate_output_dir(output_dir):
            raise ValueError(f"Invalid output directory: {output_dir}")

        # Sanitize text for filename (safely truncated)
        safe_text = re.sub(r'[\\/:*?"<>|]+', '', text)
        safe_text = safe_text.replace('\n', '').replace('\r', '')
        prefix_text = safe_text[:8]

        filename_base = f"{db_id}_{prefix_text}"
        wav_filename = f"{filename_base}.wav"
        wav_path = os.path.join(output_dir, wav_filename)

        # Write WAV
        with open(wav_path, "wb") as f:
            f.write(audio_data)

        # Calculate duration
        actual_duration = self.get_wav_duration(wav_path)
        duration = max(0.0, actual_duration)

        return wav_filename, duration

    def play_audio(self, filename: str):
        output_dir = self.get_output_dir()
        wav_path = os.path.join(output_dir, filename)
        if not os.path.exists(wav_path):
            raise FileNotFoundError(f"File not found: {filename}")

        duration = self.get_wav_duration(wav_path)
        start_time = time.time()

        # Use a unique ID to prevent race conditions
        import uuid
        playback_id = str(uuid.uuid4())

        with self.playback_lock:
            self.playback_status["is_playing"] = True
            self.playback_status["filename"] = filename
            self.playback_status["playback_id"] = playback_id

        def play_worker(path, dur, pid):
            from app.core.events import event_manager
            try:
                # Notify Start
                event_manager.publish("playback_change", {
                    "is_playing": True,
                    "filename": filename
                })

                # Use sounddevice + soundfile for cross-platform playback
                # Read file
                data, fs = sf.read(path)
                # Play (async)
                sd.play(data, fs)

                # Sleep manually to maintain 'is_playing' state for the duration
                # sd.wait() would block, which is fine in a thread, but we use sleep pattern here
                time.sleep(dur)

                # Stop if needed (though sleep should match duration)
                sd.stop()
            except Exception as e:
                print(f"Play Worker Error: {e}")
            finally:
                with self.playback_lock:
                    if self.playback_status.get("playback_id") == pid:
                        self.playback_status["is_playing"] = False

                        # Notify End
                        event_manager.publish("playback_change", {
                            "is_playing": False,
                            "filename": None
                        })

        threading.Thread(target=play_worker, args=(wav_path, duration, playback_id), daemon=True).start()
        return duration, start_time

    def get_playback_status(self):
        current_status = {}
        with self.playback_lock:
            current_status = self.playback_status.copy()

        remaining = 0
        if current_status["is_playing"]:
            elapsed = time.time() - current_status["start_time"]
            remaining = max(0, current_status["duration"] - elapsed)
            if remaining == 0:
                with self.playback_lock:
                    self.playback_status["is_playing"] = False
                    self.playback_status["filename"] = None

        return {
            "is_playing": current_status["is_playing"] and remaining > 0,
            "filename": current_status["filename"],
            "remaining": remaining
        }

    def delete_file(self, filename: str) -> bool:
        """Deletes a WAV file from the output directory."""
        output_dir = self.get_output_dir()
        wav_path = os.path.join(output_dir, filename)

        success = True
        try:
            if os.path.exists(wav_path):
                os.remove(wav_path)
            else:
                success = False
        except Exception as e:
            print(f"Error deleting file {wav_path}: {e}")
            success = False

        return success

    def scan_output_dir(self, limit: int = 50) -> list:
        """
        Scans output directory for existing .wav files matching the naming convention.
        Returns a list of dictionaries with metadata.
        """
        output_dir = self.get_output_dir()
        if not self.validate_output_dir(output_dir):
            return []

        # Get list of WAV files
        try:
            files = [f for f in os.listdir(output_dir) if f.endswith(".wav")]
        except Exception as e:
            print(f"Error listing directory {output_dir}: {e}")
            return []

        logs = []
        for filename in files:
            # Parse db_id from filename (if possible)
            # Format: {id}_{text}.wav
            match = re.match(r"^(\d+)_", filename)
            if match:
                db_id = int(match.group(1))
                wav_path = os.path.join(output_dir, filename)

                # Use duration from file itself
                duration = self.get_wav_duration(wav_path)

                # Check if file exists (redundant but safe)
                if os.path.exists(wav_path):
                    logs.append({
                        "id": db_id,
                        "filename": filename,
                        "duration": duration
                    })

        return logs
