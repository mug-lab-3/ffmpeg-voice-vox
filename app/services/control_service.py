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
        root.attributes('-topmost', True)
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
        root.attributes('-topmost', True) 
        root.lift()
        root.focus_force() 
        
        file_types = [("All Files", "*.*"), ("Executables", "*.exe"), ("Models", "*.bin")]
        path = filedialog.askopenfilename(title="Select File", parent=root, filetypes=file_types)
        root.destroy() 
        
        if path:
            return os.path.abspath(path)
        return None
    except Exception as e:
        print(f"[Service] Browse File Error: {e}")
        raise

def handle_control_state_logic(enabled: bool, vv_client, audio_manager, ffmpeg_client, request_host: str):
    """Handles the logic of starting/stopping synthesis."""
    if enabled:
        if not vv_client.is_available():
            raise ValueError("VOICEVOX is disconnected. Please start VOICEVOX.")

        current_output = config.get("system.output_dir")
        if not audio_manager.validate_output_dir(current_output):
            raise ValueError("Invalid or non-writable output directory")
    
        current_port = None
        if ':' in request_host:
            current_port = request_host.split(':')[-1]
        
        success, msg = ffmpeg_client.start_process(config.get("ffmpeg"), port_override=current_port)
        if not success:
            raise ValueError(f"FFmpeg Start Error: {msg}")
    else:
        ffmpeg_client.stop_process()
    
    config.update("system.is_synthesis_enabled", enabled)
    
    from app.core.events import event_manager
    event_manager.publish("state_update", {"is_enabled": enabled})
    
    return config.get("system.is_synthesis_enabled")

def resolve_insert_handler(filename: str, audio_manager, get_resolve_client):
    """Inserts a file into Resolve."""
    output_dir = audio_manager.get_output_dir()
    abs_path = os.path.join(output_dir, filename)
    abs_path = os.path.abspath(abs_path)
    
    client = get_resolve_client()
    if not client.insert_file(abs_path):
         raise ValueError("Failed to insert into Resolve timeline")
    return True

def play_audio_handler(filename: str, audio_manager):
    """Plays an audio file."""
    return audio_manager.play_audio(filename)

def delete_audio_handler(filename: str, audio_manager, processor):
    """Deletes an audio file and its log entry."""
    processor.delete_log(filename)
    deleted_files = audio_manager.delete_file(filename)
    
    from app.core.events import event_manager
    event_manager.publish("log_update", {})
    return deleted_files
