from flask import Blueprint, request, render_template, jsonify
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
        
        # We assume the frontend sends a flat key-value structure or matches our config structure
        # The original code filtered specifically. Let's adapt to our config structure.
        # Original keys were: speaker, speedScale, etc.
        # Our config keys in config.json are under 'synthesis'.
        
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
                config.update(config_key, new_config[client_key])
                
        print(f"  -> Config Updated")
        return jsonify({"status": "ok", "config": config.get("synthesis")})
    else:
        # Return flattened config for frontend compatibility
        syn_config = config.get("synthesis")
        # Flatten structure if needed, but original used keys like 'speaker' which match our keys if we just map them back
        return jsonify({
            "speaker": syn_config["speaker_id"],
            "speedScale": syn_config["speed_scale"],
            "pitchScale": syn_config["pitch_scale"],
            "intonationScale": syn_config["intonation_scale"],
            "volumeScale": syn_config["volume_scale"]
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
            config.update("system.is_synthesis_enabled", bool(data['enabled']))
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

@web.route('/api/heartbeat', methods=['GET'])
def handle_heartbeat():
    return jsonify({"status": "alive"})
