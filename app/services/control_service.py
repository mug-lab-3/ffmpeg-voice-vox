"""
Service Handlers for Control Domain.

IMPORTANT:
The implementation in this file must strictly follow the specifications
documented in `doc/specification/api-server.md`.
Please ensure any changes here are synchronized with the specification.
"""

import os
import tkinter as tk
from tkinter import filedialog
import winsound
import ctypes
from app.config import config


def browse_directory_handler() -> str:
    """Opens a native directory selection dialog."""
    try:
        # Enable High DPI Awareness (Windows)
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

        winsound.MessageBeep(winsound.MB_ICONASTERISK)

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        root.lift()
        root.focus_force()

        path = filedialog.askdirectory(title="Select Output Directory", parent=root)
        root.destroy()

        if path:
            return os.path.abspath(path)
        return None
    except Exception as e:
        print(f"[Service] Browse Error: {e}")
        raise


def browse_file_handler() -> str:
    """Opens a native file selection dialog."""
    try:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

        winsound.MessageBeep(winsound.MB_ICONASTERISK)

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        root.lift()
        root.focus_force()

        file_types = [
            ("All Files", "*.*"),
            ("Executables", "*.exe"),
            ("Models", "*.bin"),
        ]
        path = filedialog.askopenfilename(
            title="Select File", parent=root, filetypes=file_types
        )
        root.destroy()

        if path:
            return os.path.abspath(path)
        return None
    except Exception as e:
        print(f"[Service] Browse File Error: {e}")
        raise


def handle_control_state_logic(
    enabled: bool, vv_client, audio_manager, ffmpeg_client, request_host: str
):
    """Handles the logic of starting/stopping synthesis."""
    if enabled:
        if not vv_client.is_available():
            raise ValueError("VOICEVOX is disconnected. Please start VOICEVOX.")

        current_output = config.get("system.output_dir")
        if not audio_manager.validate_output_dir(current_output):
            raise ValueError("Invalid or non-writable output directory")

        # Runtime Validation: Model Path
        model_path = config.get("ffmpeg.model_path")
        if not model_path:
            raise ValueError("Model Path is not configured. Please set it in Settings.")
        if not os.path.exists(model_path):
            raise ValueError(f"Model Path does not exist: {model_path}")
        if not os.path.isfile(model_path):
            raise ValueError(f"Model Path must be a file: {model_path}")

        # Runtime Validation: FFmpeg Path
        ffmpeg_path = config.get("ffmpeg.ffmpeg_path")
        if not ffmpeg_path:
            raise ValueError(
                "FFmpeg Path is not configured. Please set it in Settings."
            )
        if not os.path.exists(ffmpeg_path):
            raise ValueError(f"FFmpeg Path does not exist: {ffmpeg_path}")
        if not os.path.isfile(ffmpeg_path):
            raise ValueError(f"FFmpeg Path must be a file: {ffmpeg_path}")

        # Runtime Validation: Input Device
        input_device = config.get("ffmpeg.input_device")
        if not input_device:
            raise ValueError(
                "Input Device is not selected. Please select one in Settings."
            )

        current_port = None
        if ":" in request_host:
            current_port = request_host.split(":")[-1]

        success, msg = ffmpeg_client.start_process(
            config.get("ffmpeg"), port_override=current_port
        )
        if not success:
            raise ValueError(f"FFmpeg Start Error: {msg}")
    else:
        ffmpeg_client.stop_process()

    config.update("system.is_synthesis_enabled", enabled)

    from app.core.events import event_manager

    event_manager.publish("state_update", {"is_enabled": enabled})

    return config.get("system.is_synthesis_enabled")


def ensure_audio_file(db_id: int, audio_manager, processor) -> str:
    """Check if file exists by DB ID, if not, trigger synthesis."""
    # 1. Fetch from DB
    from app.core.database import db_manager

    record = db_manager.get_transcription(db_id)
    if not record:
        raise ValueError(f"Record not found: {db_id}")

    filename = record["output_path"]
    duration = record["audio_duration"]

    output_dir = audio_manager.get_output_dir()

    # If filename is None or duration is 0, it needs synthesis
    if not filename or duration <= 0:
        print(
            f"[Service] Audio missing/pending for ID {db_id}. Triggering synthesis..."
        )
        new_filename, _ = processor.synthesize_item(db_id)
        return new_filename

    abs_path = os.path.join(output_dir, filename)
    if not os.path.exists(abs_path):
        # File recorded in DB but missing on disk -> Re-synthesize
        print(
            f"[Service] File recorded but missing on disk for ID {db_id}. Retriggering..."
        )
        new_filename, _ = processor.synthesize_item(db_id)
        return new_filename

    return filename


def resolve_insert_handler(
    db_id: int, audio_manager, processor, get_resolve_client, database
):
    """Inserts a file into Resolve by ID, synthesizing if necessary."""
    filename = ensure_audio_file(db_id, audio_manager, processor)

    transcription = database.get_transcription(db_id)
    if not transcription:
        raise ValueError(f"Transcription not found for ID {db_id}")

    output_dir = audio_manager.get_output_dir()
    abs_path = os.path.join(output_dir, filename)
    abs_path = os.path.abspath(abs_path)

    client = get_resolve_client()

    text = transcription.get("text")

    if not client.insert_file(abs_path, text=text):
        raise ValueError("Failed to insert into Resolve timeline")
    return True


def play_audio_handler(db_id: int, audio_manager, processor, request_id: str = None):
    """Plays an audio file by ID, synthesizing if necessary."""
    filename = ensure_audio_file(db_id, audio_manager, processor)
    return audio_manager.play_audio(filename, request_id=request_id)


def delete_audio_handler(db_id: int, audio_manager, processor):
    """Deletes an audio file and its log entry by ID."""
    filename = processor.delete_log(db_id)
    success = False
    if filename:
        success = audio_manager.delete_file(filename)

    from app.core.events import event_manager

    event_manager.publish("log_update", {})
    return [filename] if (filename and success) else []


def update_text_handler(db_id: int, new_text: str, processor):
    """Updates log text by ID."""
    processor.update_log_text(db_id, new_text)
    return True
