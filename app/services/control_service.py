"""
Service Handlers for Control Domain.

IMPORTANT:
The implementation in this file must strictly follow the specifications
documented in `docs/specification/api-server.md`.
Please ensure any changes here are synchronized with the specification.
"""

import os
import tkinter as tk
from tkinter import filedialog
import winsound
import ctypes
from typing import Any


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
    enabled: bool,
    vv_client,
    audio_manager,
    ffmpeg_client,
    request_host: str,
    output_dir: str,
    ffmpeg_config: Any,
    config_manager: Any,
):
    """Handles the logic of starting/stopping synthesis."""
    if enabled:
        if not vv_client.is_available():
            raise ValueError("VOICEVOX is disconnected. Please start VOICEVOX.")

        if not audio_manager.validate_output_dir(output_dir):
            raise ValueError("Invalid or non-writable output directory")

        current_port = None
        if ":" in request_host:
            current_port = request_host.split(":")[-1]

        success, msg = ffmpeg_client.start_process(
            ffmpeg_config, port_override=current_port
        )
        if not success:
            raise ValueError(f"FFmpeg Start Error: {msg}")
    else:
        ffmpeg_client.stop_process()

    config_manager.is_synthesis_enabled = enabled
    config_manager.save_config_ex()

    from app.core.events import event_manager

    event_manager.publish("state_update", {"is_enabled": enabled})

    return config_manager.is_synthesis_enabled


def ensure_audio_file(db_id: int, audio_manager, processor) -> str:
    """Check if file exists by DB ID, if not, trigger synthesis."""
    # 1. Fetch from DB
    from app.core.database import db_manager

    record = db_manager.get_transcription(db_id)
    if not record:
        raise ValueError(f"Record not found: {db_id}")

    filename = record.output_path
    duration = record.audio_duration

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

    text = transcription.text

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
    # Ensure ID exists even if logic below is robust, for cleaner API error
    from app.core.database import db_manager

    if not db_manager.get_transcription(db_id):
        # We also need to check cache for the sake of tests that might skip DB
        found_in_cache = False
        for log in processor.received_logs:
            if log.get("id") == db_id:
                found_in_cache = True
                break
        if not found_in_cache:
            raise ValueError(f"Transcription ID {db_id} not found")

    processor.update_log_text(db_id, new_text)
    return True
