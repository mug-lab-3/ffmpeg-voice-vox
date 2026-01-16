from flask import Blueprint, request, render_template, jsonify, Response
import os
from app.config import config
from app.core.voicevox import VoiceVoxClient
from app.core.audio import AudioManager
from app.services.processor import StreamProcessor
from app.core.events import event_manager
from app.core.resolve import ResolveClient
from app.core.capture import AudioCaptureService
from app.core.transcription import TranscriptionService
import threading
from multiprocessing import current_process

web = Blueprint("web", __name__)

# Initialize services
vv_client = VoiceVoxClient(config.voicevox)
audio_manager = AudioManager(config.system)
from app.core.database import db_manager

db_manager.set_config(config.system)
processor = StreamProcessor(vv_client, audio_manager, config.synthesis)
capture_service = AudioCaptureService()
transcription_service = TranscriptionService(config.transcription)

_resolve_client = None


def get_resolve_client():
    global _resolve_client
    if _resolve_client is None:
        _resolve_client = ResolveClient(config.resolve)
    return _resolve_client


def cleanup_resources():
    global _resolve_client
    if _resolve_client:
        _resolve_client.shutdown()
    if capture_service:
        capture_service.stop_capture()
    if transcription_service:
        transcription_service.stop()
    if audio_manager:
        audio_manager.shutdown()
    voicevox_stop_event.set()


# Status Pollers
voicevox_stop_event = threading.Event()


def start_resolve_poller():
    def poll_loop():
        last_status = False
        while True:
            try:
                if current_process().daemon:
                    return
                client = get_resolve_client()
                current_status = client.is_available()
                if current_status != last_status:
                    event_manager.publish(
                        "resolve_status", {"available": current_status}
                    )
                    last_status = current_status
            except:
                pass
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
                    event_manager.publish(
                        "voicevox_status", {"available": current_status}
                    )
                    if not current_status and config.is_synthesis_enabled:
                        capture_service.stop_capture()
                        transcription_service.stop()
                        config.is_synthesis_enabled = False
                        config.save_config_ex()
                        event_manager.publish("state_update", {"is_enabled": False})
                    last_status = current_status
            except:
                pass
            if voicevox_stop_event.wait(timeout=2):
                break

    threading.Thread(target=poll_loop, daemon=True).start()


if not current_process().daemon:
    start_resolve_poller()
    start_voicevox_poller()


@web.route("/api/stream")
def stream():
    def generator():
        q = event_manager.subscribe()
        try:
            while True:
                yield q.get()
        except GeneratorExit:
            event_manager.unsubscribe(q)

    response = Response(generator(), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response


@web.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@web.route("/", methods=["POST"])
def whisper_receiver():
    try:
        processor.process_stream(request.stream)
        return "OK", 200
    except:
        return "Error", 500


@web.route("/api/speakers", methods=["GET"])
def get_speakers():
    return jsonify([s.model_dump() for s in vv_client.get_speakers()])


@web.route("/api/logs", methods=["GET"])
def get_logs():
    return jsonify(processor.get_logs())
