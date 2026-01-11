from flask import Blueprint, request, render_template, jsonify, Response
import os
from app.config import config
from app.core.voicevox import VoiceVoxClient
from app.core.audio import AudioManager
from app.services.processor import StreamProcessor
from app.core.events import event_manager
from app.core.resolve import ResolveClient
from app.core.ffmpeg import FFmpegClient
import threading
from multiprocessing import current_process

web = Blueprint('web', __name__)

# Initialize services
vv_client = VoiceVoxClient()
audio_manager = AudioManager()
processor = StreamProcessor(vv_client, audio_manager)
ffmpeg_client = FFmpegClient()

_resolve_client = None

def get_resolve_client():
    global _resolve_client
    if _resolve_client is None:
        _resolve_client = ResolveClient()
    return _resolve_client

def cleanup_resources():
    global _resolve_client
    if _resolve_client:
        _resolve_client.shutdown()
    global ffmpeg_client
    if ffmpeg_client:
        ffmpeg_client.stop_process()
    voicevox_stop_event.set()

# Status Pollers
voicevox_stop_event = threading.Event()

def start_resolve_poller():
    def poll_loop():
        last_status = False
        while True:
            try:
                if current_process().daemon: return
                client = get_resolve_client()
                current_status = client.is_available()
                if current_status != last_status:
                    event_manager.publish("resolve_status", {"available": current_status})
                    last_status = current_status
            except: pass
            import time
            time.sleep(2)
    threading.Thread(target=poll_loop, daemon=True).start()

def start_voicevox_poller():
    def poll_loop():
        last_status = False
        while not voicevox_stop_event.is_set():
            try:
                current_status = vv_client.is_available()
                if current_status != last_status:
                    event_manager.publish("voicevox_status", {"available": current_status})
                    if not current_status and config.get("system.is_synthesis_enabled"):
                        ffmpeg_client.stop_process()
                        config.update("system.is_synthesis_enabled", False)
                        event_manager.publish("state_update", {"is_enabled": False})
                    last_status = current_status
            except: pass
            if voicevox_stop_event.wait(timeout=2): break
    threading.Thread(target=poll_loop, daemon=True).start()

if not current_process().daemon:
    start_resolve_poller()
    start_voicevox_poller()

@web.route('/api/stream')
def stream():
    def generator():
        q = event_manager.subscribe()
        try:
            while True:
                yield q.get()
        except GeneratorExit:
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
    try:
        processor.process_stream(request.stream)
        return "OK", 200
    except:
        return "Error", 500

@web.route('/api/speakers', methods=['GET'])
def get_speakers():
    return jsonify(vv_client.get_speakers())

@web.route('/api/logs', methods=['GET'])
def get_logs():
    return jsonify(processor.get_logs())
