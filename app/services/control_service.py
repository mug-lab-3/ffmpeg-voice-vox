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


def ensure_audio_file(filename: str, audio_manager, processor) -> str:
    """Check if file exists, if not and it's a pending file, trigger synthesis."""
    output_dir = audio_manager.get_output_dir()
    abs_path = os.path.join(output_dir, filename)

    if not os.path.exists(abs_path):
        # Check if it's a pending filename pattern: pending_{id}.wav or {id}_{prefix}.wav
        import re

        db_id = None
        if filename.startswith("pending_"):
            match = re.search(r"pending_(\d+)", filename)
            if match:
                db_id = int(match.group(1))
        else:
            # Try to extract ID from standard filename {ID}_{prefix}.wav
            match = re.match(r"^(\d+)_", filename)
            if match:
                db_id = int(match.group(1))

        if db_id:
            print(
                f"[Service] Audio missing/pending for ID {db_id}. Triggering synthesis..."
            )
            new_filename, _ = processor.synthesize_item(db_id)
            return new_filename
        else:
            raise ValueError(f"Audio file not found: {filename}")

    return filename


def resolve_insert_handler(
    filename: str, audio_manager, processor, get_resolve_client, database
):
    """Inserts a file into Resolve, synthesizing if necessary."""
    filename = ensure_audio_file(filename, audio_manager, processor)

    # Extract db_id from filename if possible for logging
    db_id = None
    import re

    if filename.startswith("pending_"):
        match = re.search(r"pending_(\d+)", filename)
        if match:
            db_id = int(match.group(1))
    else:
        match = re.match(r"^(\d+)_", filename)
        if match:
            db_id = int(match.group(1))

    transcription = None
    if db_id:
        transcription = database.get_transcription(db_id)

    if transcription:
        # Debug logging if needed, or just proceed
        pass

    output_dir = audio_manager.get_output_dir()
    abs_path = os.path.join(output_dir, filename)
    abs_path = os.path.abspath(abs_path)

    client = get_resolve_client()

    text = None
    if transcription:
        text = transcription.get("text")

    if not client.insert_file(abs_path, text=text):
        raise ValueError("Failed to insert into Resolve timeline")
    return True


def play_audio_handler(filename: str, audio_manager, processor, request_id: str = None):
    """Plays an audio file, synthesizing if necessary."""
    filename = ensure_audio_file(filename, audio_manager, processor)
    return audio_manager.play_audio(filename, request_id=request_id)


def delete_audio_handler(filename: str, audio_manager, processor):
    """Deletes an audio file and its log entry."""
    processor.delete_log(filename)
    success = audio_manager.delete_file(filename)

    from app.core.events import event_manager

    event_manager.publish("log_update", {})
    return [filename] if success else []
