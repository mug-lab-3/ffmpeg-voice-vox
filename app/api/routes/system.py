from flask import Blueprint, jsonify
from app.services.system_service import get_audio_devices_handler, heartbeat_handler

system_bp = Blueprint('system_api', __name__)

@system_bp.route('/api/ffmpeg/devices', methods=['GET'])
def get_audio_devices():
    try:
        result = get_audio_devices_handler()
        return jsonify(result.model_dump())
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@system_bp.route('/api/heartbeat', methods=['GET'])
def heartbeat():
    return jsonify(heartbeat_handler())
