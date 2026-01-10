from flask import Blueprint, request, render_template, jsonify, Response
import os
from app.config import config
from app.core.voicevox import VoiceVoxClient
from app.core.audio import AudioManager
from app.core.processor import StreamProcessor
from app.core.events import event_manager

web = Blueprint('web', __name__)

from multiprocessing import current_process

# Initialize services (Simple Dependency Injection)
# In a larger app, we might use current_app or a proper DI framework
from app.core.resolve import ResolveClient
from app.core.ffmpeg import FFmpegClient

vv_client = VoiceVoxClient()
audio_manager = AudioManager()
processor = StreamProcessor(vv_client, audio_manager)
ffmpeg_client = FFmpegClient()

# Lazy initialization for ResolveClient to verify preventing multiprocessing recursion
_resolve_client = None

def get_resolve_client():
    global _resolve_client
    if _resolve_client is None:
        _resolve_client = ResolveClient()
    return _resolve_client

def cleanup_resources():
    """Cleanup resources like ResolveClient monitor process."""
    global _resolve_client
    if _resolve_client:
        print("[System] Shutting down Resolve Monitor...")
        _resolve_client.shutdown()
        
    global ffmpeg_client
    if ffmpeg_client:
        print("[System] Shutting down FFmpeg...")
        ffmpeg_client.stop_process()


# Background Thread to Poll Resolve Status (Running in Main Process)
# Checks the shared memory status of the child process
import threading
import time

def start_resolve_poller():
    def poll_loop():
        last_status = False
        while True:
            try:
                # Polling should only happen if we can safely access the client
                # Double check to avoid any edge cases
                if current_process().daemon:
                    return

                client = get_resolve_client()
                current_status = client.is_available()
                
                if current_status != last_status:
                    print(f"[System] Resolve Status Changed: {last_status} -> {current_status}")
                    event_manager.publish("resolve_status", {"available": current_status})
                    last_status = current_status
                    
            except Exception as e:
                # Suppress expected error if somehow we get here, but log others
                if "daemonic processes are not allowed" not in str(e):
                    print(f"[System] Resolve Poller Error: {e}")
            
            time.sleep(2) # Poll UI status every 2s

    t = threading.Thread(target=poll_loop, daemon=True)
    t.start()

# Only start the poller if we are NOT in a daemon process (like the Resolve monitor worker)
if not current_process().daemon:
    start_resolve_poller()

@web.route('/api/stream')
def stream():
    remote_addr = request.remote_addr
    def generator():
        print(f"[Stream] New connection from {remote_addr}")
        q = event_manager.subscribe()
        try:
            while True:
                data = q.get()
                # print(f"[Stream] Yielding data to {remote_addr}") # Too noisy for heartbeat
                yield data
        except GeneratorExit:
            print(f"[Stream] Client disconnected: {remote_addr}")
            event_manager.unsubscribe(q)
        except Exception as e:
            print(f"[Stream] Error: {e}")
            event_manager.unsubscribe(q)
            
    response = Response(generator(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    return response

@web.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@web.route('/', methods=['POST'])
def whisper_receiver():
    print("--- データの受信を開始したよ！ ---")
    try:
        processor.process_stream(request.stream)
        return "OK", 200
    except (ConnectionResetError, OSError) as e:
        # Expected when FFmpeg is killed/stopped
        print(f"[API] Stream connection closed: {e}")
        return "Stream Closed", 200
    except Exception as e:
        print(f"[API] Error processing stream: {e}")
        return "Error", 500

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
            
        # Handle FFmpeg config
        if "ffmpeg" in new_config:
            # We assume the frontend passes a dict for 'ffmpeg' key
            for k, v in new_config["ffmpeg"].items():
                config.update(f"ffmpeg.{k}", v)
                
        print(f"  -> Config Updated")
        
        # Publish event
        event_manager.publish("config_update", {})

        resolve_available = get_resolve_client().is_available()

        return jsonify({
            "status": "ok", 
            "config": config.get("synthesis"),
            "outputDir": config.get("system.output_dir"),
            "ffmpeg": config.get("ffmpeg"),
            "resolve_available": resolve_available
        })
    else:
        # Return full config structure for frontend compatibility
        resolve_available = get_resolve_client().is_available()

        return jsonify({
            "config": config.get("synthesis"),
            "outputDir": config.get("system.output_dir"),
            "ffmpeg": config.get("ffmpeg"),
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
                
                    # Start FFmpeg
                    # Automatically determine port from the request (the port this server is listening on)
                    current_port = None
                    if ':' in request.host:
                        current_port = request.host.split(':')[-1]
                    
                    success, msg = ffmpeg_client.start_process(config.get("ffmpeg"), port_override=current_port)
                    if not success:
                        print(f"[API] Enable Failed: FFmpeg start error: {msg}")
                        return jsonify({
                            "status": "error", 
                            "message": f"FFmpeg Start Error: {msg}"
                        }), 400

                else:
                    # Stop FFmpeg
                    ffmpeg_client.stop_process()
                
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

@web.route('/api/system/browse_file', methods=['POST'])
def browse_file():
    """
    Opens a native file selection dialog on the server machine.
    Returns the selected path.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
        import winsound
        import ctypes
        
        # 0. Enable High DPI Awareness (Windows)
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1) 
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass 

        # 1. Play a system sound
        winsound.MessageBeep(winsound.MB_ICONASTERISK)
        
        # 2. Create and force focus on the root window
        root = tk.Tk()
        root.withdraw() 
        root.attributes('-topmost', True) 
        root.lift()
        root.focus_force() 
        
        # 3. Open dialog
        # We can accept filters if needed, but generic for now
        file_types = [("All Files", "*.*"), ("Executables", "*.exe"), ("Models", "*.bin")]
        path = filedialog.askopenfilename(title="Select File", parent=root, filetypes=file_types)
        
        root.destroy() 
        
        if path:
            path = os.path.abspath(path)
            return jsonify({"status": "ok", "path": path})
        else:
            return jsonify({"status": "cancelled"})
            
    except Exception as e:
        print(f"[API] Browse File Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@web.route('/api/ffmpeg/devices', methods=['GET'])
def get_audio_devices():
    try:
        # User requirement: API should use server-side state (config)
        ffmpeg_path = config.get("ffmpeg.ffmpeg_path")
             
        if not ffmpeg_path:
            return jsonify({"status": "error", "message": "FFmpeg path not configured on server"}), 400
            
        devices = ffmpeg_client.list_audio_devices(ffmpeg_path)
        print(f"[API] Devices (repr): {repr(devices)}")
        return jsonify({"status": "ok", "devices": devices})
        
    except Exception as e:
        print(f"[API] Get Devices Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@web.route('/api/heartbeat', methods=['GET'])
def handle_heartbeat():
    return jsonify({"status": "alive"})
