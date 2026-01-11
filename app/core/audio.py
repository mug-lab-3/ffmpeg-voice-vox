import os
import re
import wave
import queue
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
            "duration": 0,
            "playback_id": None,
            "request_id": None,
        }
        self.playback_lock = threading.Lock()

        # Shutdown Flag
        self.shutdown_flag = threading.Event()

        # Playback Queue
        self.play_queue = queue.Queue()

        # Worker Thread
        self.worker_thread = threading.Thread(
            target=self._play_worker_loop, daemon=True
        )
        self.worker_thread.start()

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
        safe_text = re.sub(r'[\\/:*?"<>|]+', "", text)
        safe_text = safe_text.replace("\n", "").replace("\r", "")
        prefix_text = safe_text[:8]

        filename_base = f"{db_id:03d}_{prefix_text}"
        wav_filename = f"{filename_base}.wav"
        wav_path = os.path.join(output_dir, wav_filename)

        # Write WAV
        try:
            with open(wav_path, "wb") as f:
                f.write(audio_data)

            # Calculate duration
            actual_duration = self.get_wav_duration(wav_path)
            duration = max(0.0, actual_duration)

            return wav_filename, duration
        except Exception as e:
            print(f"[AudioManager] Critical Error in save_audio: {e}")
            import traceback

            traceback.print_exc()
            raise

    def play_audio(self, filename: str, request_id: str = None):
        """
        Enqueues audio for playback.
        Returns duration and approximate start time (now).
        """
        if self.shutdown_flag.is_set():
            raise RuntimeError("System is shutting down")

        output_dir = self.get_output_dir()
        wav_path = os.path.join(output_dir, filename)
        if not os.path.exists(wav_path):
            raise FileNotFoundError(f"File not found: {filename}")

        duration = self.get_wav_duration(wav_path)

        # Enqueue the request
        self.play_queue.put(
            {
                "filename": filename,
                "path": wav_path,
                "duration": duration,
                "request_id": request_id,
            }
        )

        return duration, time.time()

    def _play_worker_loop(self):
        """
        Worker loop that processes the playback queue sequentially.
        """
        from app.core.events import event_manager
        import uuid

        while True:
            # Block until an item is available
            item = self.play_queue.get()

            # Check for Sentinel (Shutdown)
            if item is None:
                self.play_queue.task_done()
                break

            # Double-check shutdown flag before playing
            # If shutdown started while we were waiting or just retrieved item
            if self.shutdown_flag.is_set():
                # Notify Cancel
                event_manager.publish(
                    "playback_change",
                    {
                        "is_playing": False,
                        "filename": None,
                        "request_id": item.get("request_id"),
                    },
                )
                self.play_queue.task_done()
                continue

            filename = item["filename"]
            wav_path = item["path"]
            duration = item["duration"]
            req_id = item["request_id"]

            playback_id = str(uuid.uuid4())
            start_time = time.time()

            # Update Status: Playing
            with self.playback_lock:
                self.playback_status["is_playing"] = True
                self.playback_status["filename"] = filename
                self.playback_status["start_time"] = start_time
                self.playback_status["duration"] = duration
                self.playback_status["playback_id"] = playback_id
                self.playback_status["request_id"] = req_id

            # Notify Start
            event_manager.publish(
                "playback_change",
                {"is_playing": True, "filename": filename, "request_id": req_id},
            )

            try:
                # Play
                data, fs = sf.read(wav_path)
                sd.play(data, fs)

                # Wait for duration (blocking this thread is what we want for sequential playback)
                # But use sd.wait() so we can interrupt it if needed via sd.stop()
                sd.wait()

                # Check directly if we need to stop (although sd.wait returns on stop())
                sd.stop()
            except Exception as e:
                print(f"Play Worker Error: {e}")
            finally:
                # Update Status: Finished
                with self.playback_lock:
                    # Only reset if we are still the current playback
                    # (should be true since we are sequential, but good practice)
                    if self.playback_status.get("playback_id") == playback_id:
                        self.playback_status["is_playing"] = False
                        self.playback_status["filename"] = (
                            None  # Optional: keep last filename? No, clear it.
                        )

                # Notify End
                event_manager.publish(
                    "playback_change",
                    {"is_playing": False, "filename": None, "request_id": req_id},
                )

                self.play_queue.task_done()

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
            "remaining": remaining,
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
                    logs.append(
                        {"id": db_id, "filename": filename, "duration": duration}
                    )

        return logs

    def shutdown(self):
        """
        Gracefully shuts down the audio manager.
        Stops playback, clears queue, and joins worker thread.
        """
        print("[AudioManager] Shutting down...")
        self.shutdown_flag.set()

        # 1. Stop current playback immediately
        try:
            sd.stop()
        except:
            pass

        # 2. Drain the queue and notify cancellation
        from app.core.events import event_manager

        while True:
            try:
                item = self.play_queue.get_nowait()
                if item is None:
                    # If we hit sentinel (unlikely if we just started shutdown, but possible if called twice)
                    self.play_queue.task_done()
                    continue

                # Notify cancellation
                event_manager.publish(
                    "playback_change",
                    {
                        "is_playing": False,
                        "filename": item.get("filename"),
                        "request_id": item.get("request_id"),
                    },
                )
                self.play_queue.task_done()
            except queue.Empty:
                break

        # 3. Signal worker to exit
        self.play_queue.put(None)

        # 4. Join thread
        if self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2.0)
            if self.worker_thread.is_alive():
                print("[AudioManager] Worker thread did not exit cleanly.")

        print("[AudioManager] Shutdown complete.")
