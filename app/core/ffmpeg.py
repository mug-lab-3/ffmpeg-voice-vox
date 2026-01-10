
import subprocess
import threading
import os
import signal
import platform
import shlex

class FFmpegClient:
    def __init__(self):
        self._process = None
        self._lock = threading.Lock()

    def validate_config(self, config_data):
        """
        Validates the FFmpeg configuration.
        Returns (True, None) if valid, (False, error_message) otherwise.
        """
        required_keys = ["ffmpeg_path", "input_device", "model_path", "vad_model_path", "port", "queue_length"]
        for key in required_keys:
            if not config_data.get(key):
                return False, f"Missing required setting: {key}"
        
        # Basic formatting checks could go here
        if not config_data.get("host"):
             return False, "Missing required setting: host"

        return True, None

    def start_process(self, config_data):
        """
        Starts the FFmpeg process with the given configuration.
        """
        with self._lock:
            if self._process and self._process.poll() is None:
                return False, "FFmpeg is already running"

            valid, error = self.validate_config(config_data)
            if not valid:
                return False, error

            ffmpeg_path = config_data["ffmpeg_path"]
            input_device = config_data["input_device"]
            model_path = config_data["model_path"]
            vad_model_path = config_data["vad_model_path"]
            host = config_data["host"]
            port = config_data["port"]
            queue_length = config_data["queue_length"]

            # Construct command
            # ./ffmpeg -f dshow -i audio="[input_device]" -vn -af 'whisper=model=[model_path]:queue=[queue]:destination=http\://[host]\:[port]:format=json:vad_model=[vad_model_path]' -f null -
            
            # Note: On Windows, simple string command with shell=False or formatted list is safer/cleaner.
            # However, the user provided example uses quotes for the filter string which might need careful handling.
            # We will use a list of arguments for subprocess.
            
            # Audio filter string
            # Important: Escape generated colons if needed, though here we are constructing it.
            # The destination URL needs escaped colons in the filter string syntax if passed directly in some shells,
            # but usually in subprocess list, we just pass the string.
            # However, ffmpeg filter syntax often requires escaping colons as \:
            
            dest_url = f"http\\://{host}\\:{port}"
            filter_arg = f"whisper=model={model_path}:queue={queue_length}:destination={dest_url}:format=json:vad_model={vad_model_path}"
            
            cmd = [
                ffmpeg_path,
                "-f", "dshow",
                "-i", f"audio={input_device}",
                "-vn",
                "-af", filter_arg,
                "-f", "null",
                "-"
            ]
            
            print(f"[FFmpeg] Starting with command: {' '.join(cmd)}")

            try:
                # Run in background
                # We do not capture stdout/stderr to pipe to avoid buffer filling if not read.
                # Or we can redirect to DEVNULL if we don't want to see it in the console.
                # If the user wants to see ffmpeg output in the main app console, we can leave it inherited.
                # For now, let's inherit stdout/stderr so it shows up in the terminal running the server.
                self._process = subprocess.Popen(cmd)
                return True, "Started"
            except Exception as e:
                print(f"[FFmpeg] Start Error: {e}")
                return False, str(e)

    def stop_process(self):
        """
        Stops the FFmpeg process.
        """
        with self._lock:
            if not self._process:
                return
            
            print("[FFmpeg] Stopping process...")
            try:
                # Graceful termination first
                self._process.terminate()
                try:
                    self._process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self._process.kill()
            except Exception as e:
                print(f"[FFmpeg] Stop Error: {e}")
            finally:
                self._process = None

    def is_running(self):
        with self._lock:
            return self._process is not None and self._process.poll() is None
