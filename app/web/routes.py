from flask import Blueprint, request, render_template, jsonify
import os
from app.config import config
from app.core.voicevox import VoiceVoxClient
from app.core.audio import AudioManager
from app.core.processor import StreamProcessor

web = Blueprint('web', __name__)

# Initialize services (Simple Dependency Injection)
# In a larger app, we might use current_app or a proper DI framework
vv_client = VoiceVoxClient()
audio_manager = AudioManager()
processor = StreamProcessor(vv_client, audio_manager)

@web.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@web.route('/', methods=['POST'])
def whisper_receiver():
    print("--- データの受信を開始したよ！ ---")
    processor.process_stream(request.stream)
    return "OK", 200

@web.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    if request.method == 'POST':
        new_config = request.json
        print(f"[API] Config Update Request: {new_config}")
        
        # Mapping for backward compatibility with frontend
        mapping = {
            "speaker": "synthesis.speaker_id",
            "speedScale": "synthesis.speed_scale",
            "pitchScale": "synthesis.pitch_scale",
            "intonationScale": "synthesis.intonation_scale",
            "volumeScale": "synthesis.volume_scale",
            "resolveEnabled": "resolve.enabled"
        }
        
        for client_key, config_key in mapping.items():
            if client_key in new_config:
                val = new_config[client_key]
                print(f"[API] Config Update: {client_key} = {val} (Type: {type(val)})")
                
                # Force boolean for specific keys if string passed
                if config_key == "resolve.enabled":
                    if isinstance(val, str):
                        val = (val.lower() == "true")
                    else:
                        val = bool(val)
                
                config.update(config_key, val)

        # Handle output directory
        if "outputDir" in new_config:
            config.update("system.output_dir", new_config["outputDir"])
                
        print(f"  -> Config Updated")
        return jsonify({
            "status": "ok", 
            "config": config.get("synthesis"),
            "outputDir": config.get("system.output_dir")
        })
    else:
        # Return flattened config for frontend compatibility
        syn_config = config.get("synthesis")
        return jsonify({
            "speaker": syn_config["speaker_id"],
            "speedScale": syn_config["speed_scale"],
            "pitchScale": syn_config["pitch_scale"],
            "intonationScale": syn_config["intonation_scale"],
            "volumeScale": syn_config["volume_scale"],
            "outputDir": config.get("system.output_dir")
        })

@web.route('/api/speakers', methods=['GET'])
def get_speakers():
    return jsonify(vv_client.get_speakers())

@web.route('/api/logs', methods=['GET'])
def get_logs():
    return jsonify(processor.get_logs())

@web.route('/api/control/state', methods=['GET', 'POST'])
def handle_control_state():
    if request.method == 'POST':
        data = request.json
        if 'enabled' in data:
            should_enable = bool(data['enabled'])
            
            if should_enable:
                # Validation before enabling
                current_output = config.get("system.output_dir")
                if not audio_manager.validate_output_dir(current_output):
                    print(f"[API] Enable Failed: Invalid Output Directory: '{current_output}'")
                    return jsonify({
                        "status": "error", 
                        "message": "Invalid or non-writable output directory"
                    }), 400
            
            config.update("system.is_synthesis_enabled", should_enable)
            print(f"[API] Synthesis State Updated: {config.get('system.is_synthesis_enabled')}")
            
        return jsonify({"status": "ok", "enabled": config.get("system.is_synthesis_enabled")})
    else:
        status = audio_manager.get_playback_status()
        return jsonify({
            "enabled": config.get("system.is_synthesis_enabled"),
            "playback": status
        })

@web.route('/api/control/play', methods=['POST'])
def handle_control_play():
    try:
        data = request.json
        filename = data.get('filename')
        
        if not filename:
             return jsonify({"status": "error", "message": "No filename provided"}), 400
             
        duration, start_time = audio_manager.play_audio(filename)
        
        return jsonify({
            "status": "ok", 
            "duration": duration,
            "start_time": start_time
        })

    except Exception as e:
        print(f"[API] Play Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@web.route('/api/control/delete', methods=['POST'])
def handle_control_delete():
    try:
        data = request.json
        filename = data.get('filename')
        
        if not filename:
             return jsonify({"status": "error", "message": "No filename provided"}), 400
        
        # Remove from logs
        processor.delete_log(filename)
        
        # Delete files
        deleted_files = audio_manager.delete_file(filename)
                
        print(f"[API] Deleted: {deleted_files}")
        return jsonify({"status": "ok", "deleted": deleted_files})
        
    except Exception as e:
        print(f"[API] Delete Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@web.route('/api/system/browse', methods=['POST'])
def browse_directory():
    """
    Opens a native directory selection dialog on the server machine.
    Returns the selected path.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
        import winsound
        import ctypes
        
        # 0. Enable High DPI Awareness (Windows)
        try:
            # Try newer API (Windows 8.1+)
            # 1 = Process_System_DPI_Aware
            # 2 = Process_Per_Monitor_DPI_Aware
            ctypes.windll.shcore.SetProcessDpiAwareness(1) 
        except Exception:
            try:
                # Fallback for older Windows
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass # Non-Windows or failure

        # 1. Play a system sound to alert the user
        winsound.MessageBeep(winsound.MB_ICONASTERISK)
        
        # 2. Create and force focus on the root window
        root = tk.Tk()
        root.withdraw() # Hide the main window
        root.attributes('-topmost', True) # Keep on top
        root.lift()
        root.focus_force() # Force focus
        
        # 3. Open dialog with explicit parent to inherit topmost
        path = filedialog.askdirectory(title="Select Output Directory", parent=root)
        
        root.destroy() # Cleanup
        
        if path:
            # Normalize path separators
            path = os.path.abspath(path)
            return jsonify({"status": "ok", "path": path})
        else:
            return jsonify({"status": "cancelled"})
            
    except Exception as e:
        print(f"[API] Browse Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@web.route('/api/heartbeat', methods=['GET'])
def handle_heartbeat():
    return jsonify({"status": "alive"})
