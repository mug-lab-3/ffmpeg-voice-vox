import os
import threading
import queue
import numpy as np
import time
from faster_whisper import WhisperModel
from typing import Optional, Callable
from app.config.schemas import TranscriptionConfig


class TranscriptionService:
    def __init__(self, config: TranscriptionConfig):
        self.config = config
        self.model: Optional[WhisperModel] = None
        self._lock = threading.Lock()
        self.is_running = False
        self.is_loading = False
        self.worker_thread: Optional[threading.Thread] = None
        self.audio_queue = queue.Queue()
        self.on_transcription_callback: Optional[Callable[[str], None]] = None

    def _load_model_internal(self):
        """Internal method to load the model with fallback logic (Compute Type & Device)."""
        try:
            # Strategies to try in order: (device, compute_type)
            strategies = []
            
            # 1. User requested strategy
            strategies.append((self.config.device, self.config.compute_type))
            
            # 2. CUDA fallbacks if applicable
            if self.config.device == "cuda" or self.config.device == "auto":
                target_device = "cuda"
                # Try common CUDA compute types
                for ct in ["float16", "default", "int8_float16", "int8"]:
                    if (target_device, ct) not in strategies:
                        strategies.append((target_device, ct))
            
            # 3. CPU fallbacks as final resort
            # Always have a CPU float32/int8 fallback
            for ct in ["default", "int8", "float32"]:
                if ("cpu", ct) not in strategies:
                    strategies.append(("cpu", ct))

            last_error = None
            for device, ct in strategies:
                try:
                    print(f"[Transcription] Trying to load model: {self.config.model_size} ({device}, {ct})")
                    
                    model = WhisperModel(
                        self.config.model_size,
                        device=device,
                        compute_type=ct,
                        download_root=os.path.join("models", "whisper"),
                    )
                    
                    # IMPORTANT: Verify it actually works (checks for missing DLLs like cublas)
                    # We run a very short dummy inference
                    dummy_audio = np.zeros(1600, dtype=np.float32) # 100ms of silence
                    list(model.transcribe(dummy_audio))
                    
                    with self._lock:
                        self.model = model
                        self.is_loading = False
                    print(f"[Transcription] Model loaded and verified successfully on {device} ({ct}).")
                    return
                except Exception as e:
                    last_error = e
                    err_msg = str(e).lower()
                    print(f"[Transcription] Failed with {device}/{ct}: {e}")
                    
                    # If it's a "not supported" or "library not found" error, we continue to next strategy
                    if any(msg in err_msg for msg in ["compute type", "not support", "library", "cublas", "cudnn", "cuda"]):
                        continue
                    else:
                        # If it's something else (e.g. out of memory), we might still want to try CPU
                        if device == "cuda":
                            continue
                        raise # Fatal other error on CPU

            raise last_error if last_error else RuntimeError("All load strategies failed")

        except Exception as e:
            with self._lock:
                self.is_loading = False
            print(f"[Transcription] CRITICAL: Failed to load model after all fallbacks: {e}")
            import traceback
            traceback.print_exc()

    def start(self, on_transcription: Callable[[str], None]):
        """Starts the transcription service (Non-blocking)."""
        with self._lock:
            if self.is_running:
                print("[Transcription] Service is already running.")
                return
            self.is_running = True
            self.on_transcription_callback = on_transcription

            # Trigger background load if not already loaded or loading
            if self.model is None and not self.is_loading:
                self.is_loading = True
                threading.Thread(target=self._load_model_internal, daemon=True).start()

        # Start worker thread immediately
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def stop(self):
        """Stops the transcription service."""
        with self._lock:
            if not self.is_running:
                return
            self.is_running = False

        if self.worker_thread:
            # We don't join for long because it might be transcribing
            self.worker_thread.join(timeout=0.5)
            self.worker_thread = None

        # Clear queue
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
        print("[Transcription] Service stopped.")

    def push_audio(self, chunk: np.ndarray):
        """Pushes audio chunk to the queue."""
        if self.is_running:
            # print(f"[Transcription] Audio chunk received: {chunk.shape}") # Too noisy for long runs
            self.audio_queue.put(chunk)

    def _worker_loop(self):
        """Internal worker loop for transcribing audio chunks."""
        print("[Transcription] Worker loop started.")
        buffer = []

        while True:
            with self._lock:
                if not self.is_running:
                    break
                model = self.model
            
            # If model is not ready, just wait a bit and keep buffer
            if model is None:
                time.sleep(0.5)
                continue

            try:
                # Use a short timeout to check is_running frequently
                chunk = self.audio_queue.get(timeout=0.1)
                buffer.append(chunk)

                # Wait until we have enough buffer (~3 seconds minimum for stable Whisper)
                if len(buffer) >= 30:
                    audio_data = np.concatenate(buffer).flatten()
                    buffer = []
                    
                    # Use provided beam_size
                    segments, info = model.transcribe(
                        audio_data,
                        beam_size=self.config.beam_size,
                        language=self.config.language,
                        vad_filter=True,
                        vad_parameters=dict(min_silence_duration_ms=500),
                    )

                    segments = list(segments) # Force execution
                    
                    full_text = "".join([s.text for s in segments])

                    if full_text.strip():
                        print(f"[Transcription] Result: {full_text.strip()}")
                        if self.on_transcription_callback:
                            self.on_transcription_callback(full_text.strip())

            except queue.Empty:
                continue
            except Exception as e:
                print(f"[Transcription] Error in worker loop: {e}")
                # Don't break loop on single error
        
        print("[Transcription] Worker loop finished.")
