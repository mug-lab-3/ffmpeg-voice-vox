import subprocess
import threading
import os
import signal
import platform
import shlex


class FFmpegClient:
    def __init__(self, config=None):
        self.config = config
        self._process = None
        self._lock = threading.Lock()

    def validate_config(self, config_data):
        """
        Validates the FFmpeg configuration.
        Returns (True, None) if valid, (False, error_message) otherwise.
        """
        if not config_data.ffmpeg_path:
            return False, "Missing required setting: ffmpeg_path"
        if not config_data.input_device:
            return False, "Missing required setting: input_device"
        if not config_data.model_path:
            return False, "Missing required setting: model_path"
        if not config_data.vad_model_path:
            return False, "Missing required setting: vad_model_path"
        if not config_data.queue_length:
            return False, "Missing required setting: queue_length"
        if not config_data.host:
            return False, "Missing required setting: host"

        return True, None

    def start_process(self, config_data=None, port=None):
        """
        Starts the FFmpeg process with the given configuration.
        """
        if config_data is None:
            config_data = self.config

        if config_data is None:
            return False, "No configuration provided for FFmpegClient"

        with self._lock:
            if self._process and self._process.poll() is None:
                return False, "FFmpeg is already running"

            valid, error = self.validate_config(config_data)
            if not valid:
                return False, error

            ffmpeg_path = config_data.ffmpeg_path
            input_device = config_data.input_device
            model_path = config_data.model_path
            vad_model_path = config_data.vad_model_path
            host = config_data.host

            # Resolving Port
            # Use provided port
            if not port:
                return False, "Port not specified and could not be determined."

            queue_length = config_data.queue_length

            # Construct command

            if not os.path.exists(model_path):
                print(f"[FFmpeg] WARNING: Model path not found: {model_path}")

            def _escape(path):
                if not path:
                    return ""
                # Use relative path to avoid drive letter (C:) issues
                try:
                    p = os.path.relpath(path).replace("\\", "/")
                except Exception:
                    p = os.path.abspath(path).replace("\\", "/")
                
                # Double escape colons and spaces for FFmpeg filter parsing
                p = p.replace(":", r"\\:").replace(",", r"\\,").replace(" ", r"\\ ")
                return p

            def _escape_url(path):
                # Double escape URL colons
                return path.replace(":", r"\\:")

            model_path_esc = _escape(model_path)
            vad_model_path_esc = _escape(vad_model_path)

            # Destination URL construction
            dest_url_base = f"http://{host}:{port}"
            dest_url = _escape_url(dest_url_base)

            # Build filter arguments and join with colons
            filter_parts = [
                f"model={model_path_esc}",
                f"queue={queue_length}",
                f"destination={dest_url}",
                "format=json"
            ]
            if vad_model_path_esc:
                filter_parts.append(f"vad_model={vad_model_path_esc}")

            filter_arg = f"whisper={':'.join(filter_parts)}"

            # OS-specific input format and null device
            if platform.system() == "Darwin":
                input_format = "avfoundation"
                null_device = "/dev/null"
                # On Mac, input device is usually an index like ":0" or ":1" for audio
                # If user selects name, we might need index mapping, but let's assume index or name works if ffmpeg supports it
                # avfoundation uses "none:index" or "none:name" for audio only, or "video:audio"
                # Simple approach: "none:DEVICE" if only audio
                formatted_input = (
                    f"none:{input_device}" if ":" not in input_device else input_device
                )
            else:
                input_format = "dshow"
                null_device = "nul"
                formatted_input = f"audio={input_device}"

            cmd = [
                ffmpeg_path,
                "-f",
                input_format,
                "-i",
                formatted_input,
                "-vn",
                "-af",
                filter_arg,
                "-f",
                "null",
                null_device,
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

    def list_audio_devices(self, ffmpeg_path):
        """
        Lists available DirectShow audio devices.
        Returns a list of device names.
        """
        if not ffmpeg_path or not os.path.exists(ffmpeg_path):
            print(f"[FFmpeg] Path not found or empty: {ffmpeg_path}")
            return []

        if platform.system() == "Darwin":
            cmd = [ffmpeg_path, "-list_devices", "true", "-f", "avfoundation", "-i", ""]
        else:
            cmd = [ffmpeg_path, "-list_devices", "true", "-f", "dshow", "-i", "dummy"]

        try:
            # Capture as bytes to handle encoding manually
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            raw_output = result.stderr  # device list is in stderr

            output = ""
            # Try utf-8 strict first.
            # UTF-8 is stricter than CP932. If bytes are valid UTF-8, it's likely UTF-8.
            # If input is Shift-JIS (e.g. 0x83...), utf-8 strict will fail.
            try:
                output = raw_output.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    output = raw_output.decode("cp932")
                except UnicodeDecodeError:
                    output = raw_output.decode("utf-8", errors="replace")

            devices = []

            devices = []

            if platform.system() == "Darwin":
                # Mac avfoundation parsing
                # Look for "AVFoundation audio devices:" then "[index] Name"
                in_audio_section = False
                for line in output.splitlines():
                    if "AVFoundation audio devices:" in line:
                        in_audio_section = True
                        continue
                    if "AVFoundation video devices:" in line:
                        in_audio_section = False
                        continue

                    if in_audio_section:
                        # Match "[0] Some Device"
                        import re

                        match = re.search(r"\[\d+\]\s+(.+)", line)
                        if match:
                            devices.append(match.group(1).strip())
            else:
                # Windows dshow parsing
                # Simple parsing: Look for lines with "(audio)" and quotes
                for line in output.splitlines():
                    if "(audio)" in line:
                        import re

                        match = re.search(r"\"(.+?)\"", line)
                        if match:
                            device_name = match.group(1)
                            if device_name != "dummy":
                                devices.append(device_name)

            print(f"[FFmpeg] Found devices: {devices}")
            if not devices:
                try:
                    print(f"[FFmpeg] Raw output (decoded): {output}")
                except:
                    print(f"[FFmpeg] Raw output (bytes): {raw_output}")

            return devices

        except Exception as e:
            print(f"[FFmpeg] List Devices Error: {e}")
            return []
