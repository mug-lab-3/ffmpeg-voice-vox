import os
import re
import wave
import winsound
import threading
import time
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
            with wave.open(filepath, 'rb') as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                return frames / float(rate)
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

    def save_audio(self, audio_data: bytes, text: str, speaker_name: str, start_time_ms: float, end_time_ms: float) -> tuple:
        """
        Saves audio data to WAV and creates a corresponding SRT file.
        Returns (filename, duration_sec).
        """
        output_dir = self.get_output_dir()
        if not self.validate_output_dir(output_dir):
            raise ValueError(f"Invalid output directory: {output_dir}")

        # Clean filename
        safe_text = re.sub(r'[\\/:*?"<>|]+', '', text)
        safe_text = safe_text.replace('\n', '').replace('\r', '')
        prefix_text = safe_text[:8]
        
        filename_base = f"{int(start_time_ms):06d}_{speaker_name}_{prefix_text}"
        wav_filename = f"{filename_base}.wav"
        srt_filename = f"{filename_base}.srt"
        
        wav_path = os.path.join(output_dir, wav_filename)
        srt_path = os.path.join(output_dir, srt_filename)
        
        # Write WAV
        with open(wav_path, "wb") as f:
            f.write(audio_data)

        # Automatic Resolve insertion removed.
            
        # Calculate duration
        # Default to JSON duration if WAV calculation fails, but try WAV first
        actual_duration = self.get_wav_duration(wav_path)
        if actual_duration > 0:
            duration = actual_duration
        else:
            raw_duration = end_time_ms - start_time_ms
            duration = max(0, raw_duration / 1000.0)

        # Write SRT
        srt_content = f"1\n00:00:00,000 --> {self.format_srt_time(duration)}\n{text}\n"
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)
            
        return wav_filename, duration

    def play_audio(self, filename: str):
        output_dir = self.get_output_dir()
        wav_path = os.path.join(output_dir, filename)
        if not os.path.exists(wav_path):
            raise FileNotFoundError(f"File not found: {filename}")
            
        duration = self.get_wav_duration(wav_path)
        start_time = time.time()
        
        with self.playback_lock:
            self.playback_status["is_playing"] = True
            self.playback_status["filename"] = filename
            self.playback_status["start_time"] = start_time
            self.playback_status["duration"] = duration

        def play_worker(path):
            try:
                winsound.PlaySound(path, winsound.SND_FILENAME)
            except Exception as e:
                print(f"Play Worker Error: {e}")
            finally:
                with self.playback_lock:
                    if self.playback_status["filename"] == filename:
                        self.playback_status["is_playing"] = False
        
        threading.Thread(target=play_worker, args=(wav_path,), daemon=True).start()
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

    def delete_file(self, filename: str) -> list:
        output_dir = self.get_output_dir()
        wav_path = os.path.join(output_dir, filename)
        srt_path = wav_path.replace(".wav", ".srt")
        deleted = []
        
        if os.path.exists(wav_path):
            os.remove(wav_path)
            deleted.append(filename)
            
        if os.path.exists(srt_path):
            os.remove(srt_path)
            deleted.append(os.path.basename(srt_path))
            
        return deleted
