import sounddevice as sd
import numpy as np
import threading
import queue
from typing import Optional, Callable


class AudioCaptureService:
    def __init__(self):
        self.stream: Optional[sd.InputStream] = None
        self.queue = queue.Queue()
        self.is_running = False
        self._lock = threading.Lock()
        self.sample_rate = 16000
        self.channels = 1
        self.dtype = "float32"
        self.callback_count = 0  # Added for debug tracking

    @property
    def is_capturing(self):
        with self._lock:
            return self.is_running

    def list_devices(self):
        """Returns a list of available audio input devices."""
        devices = sd.query_devices()
        input_devices = []
        for i, d in enumerate(devices):
            if d["max_input_channels"] > 0:
                input_devices.append({"index": i, "name": d["name"]})
        return input_devices

    def start_capture(
        self,
        device_name: Optional[str] = None,
        callback: Optional[Callable[[np.ndarray], None]] = None,
    ):
        with self._lock:
            if self.is_running:
                return False, "Capture is already running"

            try:
                # Find device index if name is provided
                device_index = None
                if device_name:
                    devices = sd.query_devices()
                    for i, d in enumerate(devices):
                        if d["name"] == device_name:
                            device_index = i
                            break
                    if device_index is None:
                        return False, f"Device not found: {device_name}"

                self.callback_count = 0

                def audio_callback(indata, frames, time, status):
                    if status:
                        print(f"[Capture] Error: {status}")
                    
                    self.callback_count += 1
                    data = indata.copy()
                    if callback:
                        callback(data)
                    else:
                        self.queue.put(data)

                self.stream = sd.InputStream(
                    device=device_index,
                    channels=self.channels,
                    samplerate=self.sample_rate,
                    dtype=self.dtype,
                    callback=audio_callback,
                    blocksize=int(self.sample_rate * 0.1),  # 100ms chunks
                )
                self.stream.start()
                print(f"[Capture] Stream started on device: {device_index}")
                self.is_running = True
                return True, "Started"
            except Exception as e:
                print(f"[Capture] Start Error: {e}")
                return False, str(e)

    def stop_capture(self):
        with self._lock:
            if not self.is_running:
                return

            if self.stream:
                try:
                    self.stream.stop()
                    self.stream.close()
                except:
                    pass
                self.stream = None

            self.is_running = False
            # Clear queue
            while not self.queue.empty():
                try:
                    self.queue.get_nowait()
                except queue.Empty:
                    break
            print("[Capture] Stopped.")

    def get_audio_chunks(self):
        """Generator that yields audio chunks from the queue."""
        while True:
            with self._lock:
                running = self.is_running
            
            if not running and self.queue.empty():
                break

            try:
                yield self.queue.get(timeout=0.1)
            except queue.Empty:
                continue
