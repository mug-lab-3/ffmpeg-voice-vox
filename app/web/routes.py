from flask import Blueprint, request, render_template, jsonify, Response
import os
from app.config import config
from app.core.voicevox import VoiceVoxClient
from app.core.audio import AudioManager
from app.core.processor import StreamProcessor
from app.core.events import event_manager

web = Blueprint('web', __name__)

# Initialize services (Simple Dependency Injection)
# In a larger app, we might use current_app or a proper DI framework
from app.core.resolve import ResolveClient
vv_client = VoiceVoxClient()
audio_manager = AudioManager()
processor = StreamProcessor(vv_client, audio_manager)
processor = StreamProcessor(vv_client, audio_manager)

# Lazy initialization for ResolveClient to verify preventing multiprocessing recursion
_resolve_client = None

def get_resolve_client():
    global _resolve_client
    if _resolve_client is None:
        _resolve_client = ResolveClient()
    return _resolve_client

@web.route('/api/stream')
def stream():
    def generator():
        q = event_manager.subscribe()
        try:
            while True:
                data = q.get()
                yield data
        except GeneratorExit:
            event_manager.unsubscribe(q)
            
    return Response(generator(), mimetype='text/event-stream')

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
            "volumeScale": "synthesis.volume_scale"
        }
        
        for client_key, config_key in mapping.items():
            if client_key in new_config:
                val = new_config[client_key]
                print(f"[API] Config Update: {client_key} = {val} (Type: {type(val)})")
                config.update(config_key, val)

        # Handle output directory
        if "outputDir" in new_config:
            config.update("system.output_dir", new_config["outputDir"])
            # Reload history logs from the new directory
            processor.reload_history()
                
        print(f"  -> Config Updated")
        
        # Publish event
        event_manager.publish("config_update", {})

        resolve_available = resolve_client.is_available()

        return jsonify({
            "status": "ok", 
            "config": config.get("synthesis"),
            "outputDir": config.get("system.output_dir"),
            "resolve_available": resolve_available
        })
    else:
        # Return flattened config for frontend compatibility
        syn_config = config.get("synthesis")
        resolve_available = get_resolve_client().is_available()

        return jsonify({
            "speaker": syn_config["speaker_id"],
            "speedScale": syn_config["speed_scale"],
            "pitchScale": syn_config["pitch_scale"],
            "intonationScale": syn_config["intonation_scale"],
            "volumeScale": syn_config["volume_scale"],
            "outputDir": config.get("system.output_dir"),
            "resolve_available": resolve_available
        })

@web.route('/api/speakers', methods=['GET'])
def get_speakers():
    return jsonify(vv_client.get_speakers())

@web.route('/api/logs', methods=['GET'])
def get_logs():
    return jsonify(processor.get_logs())

@web.route('/api/control/state', methods=['GET', 'POST'])
def handle_control_state():
    try:
        if request.method == 'POST':
            data = request.json
            if data is None:
                return jsonify({"status": "error", "message": "Invalid JSON"}), 400

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
                
                 # Notify clients
                event_manager.publish("state_update", {"is_enabled": should_enable})
                
            return jsonify({"status": "ok", "enabled": config.get("system.is_synthesis_enabled")})
        else:
            status = audio_manager.get_playback_status()
            resolve_available = get_resolve_client().is_available()
            
            return jsonify({
                "enabled": config.get("system.is_synthesis_enabled"),
                "playback": status,
                "resolve_available": resolve_available
            })
    except Exception as e:
        print(f"[API] Error in handle_control_state: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@web.route('/api/control/resolve_insert', methods=['POST'])
def handle_resolve_insert():
    try:
        data = request.json
        filename = data.get('filename')
        
        if not filename:
             return jsonify({"status": "error", "message": "No filename provided"}), 400
             
        output_dir = audio_manager.get_output_dir()
        abs_path = os.path.join(output_dir, filename)
        abs_path = os.path.abspath(abs_path)
        
        client = get_resolve_client()
        if client.insert_file(abs_path):
             return jsonify({"status": "ok"})
        else:
             return jsonify({"status": "error", "message": "Failed to insert into Resolve timeline"}), 500
             
    except Exception as e:
        print(f"[API] Resolve Insert Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

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
        
        # Notify clients to refresh logs
        event_manager.publish("log_update", {})
                
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
