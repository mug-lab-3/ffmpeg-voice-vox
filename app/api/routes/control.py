"""
API Implementation for Control Domain.

IMPORTANT:
The implementation in this file must strictly follow the specifications
documented in `docs/specification/api-server.md`.
Please ensure any changes here are synchronized with the specification.
"""

from flask import Blueprint, request, jsonify
from app.services.control_service import (
    browse_directory_handler,
    browse_file_handler,
    handle_control_state_logic,
    resolve_insert_handler,
    play_audio_handler,
    delete_audio_handler,
    update_text_handler,
)
from app.api.schemas.control import (
    ControlStateResponse,
    PlayResponse,
    DeleteResponse,
    ItemIdRequest,
)
from app.api.schemas.system import BrowseResponse
from app.web.routes import (
    vv_client,
    audio_manager,
    ffmpeg_client,
    processor,
    get_resolve_client,
)

control_bp = Blueprint("control_api", __name__)


@control_bp.route("/api/control/state", methods=["GET", "POST"])
def handle_control_state():
    if request.method == "POST":
        data = request.json
        if data is None or "enabled" not in data:
            return jsonify({"status": "error", "message": "Invalid request"}), 400

        try:
            enabled = handle_control_state_logic(
                data["enabled"], vv_client, audio_manager, ffmpeg_client, request.host
            )
            return jsonify({"status": "ok", "enabled": enabled})
        except ValueError as e:
            return jsonify({"status": "error", "message": str(e)}), 400
    else:
        status = audio_manager.get_playback_status()
        resolve_available = get_resolve_client().is_available()
        voicevox_available = vv_client.is_available()
        from app.config import config

        return jsonify(
            ControlStateResponse(
                enabled=config.is_synthesis_enabled,
                playback=status,
                resolve_available=resolve_available,
                voicevox_available=voicevox_available,
            ).model_dump()
        )


@control_bp.route("/api/control/resolve_insert", methods=["POST"])
def handle_resolve_insert():
    data = request.json
    try:
        req = ItemIdRequest(**data)
        db_id = req.id
    except Exception:
        return jsonify({"status": "error", "message": "Invalid or missing ID"}), 400

    try:
        from app.core.database import db_manager

        resolve_insert_handler(
            db_id, audio_manager, processor, get_resolve_client, db_manager
        )
        return jsonify({"status": "ok"})
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": f"Internal error: {str(e)}"}), 500


@control_bp.route("/api/control/play", methods=["POST"])
def handle_play():
    data = request.json
    try:
        req = ItemIdRequest(**data)
        db_id = req.id
    except Exception:
        return jsonify({"status": "error", "message": "Invalid or missing ID"}), 400

    try:
        request_id = data.get("request_id")
        duration, start_time = play_audio_handler(
            db_id, audio_manager, processor, request_id=request_id
        )
        return jsonify(
            PlayResponse(duration=duration, start_time=start_time).model_dump()
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@control_bp.route("/api/control/delete", methods=["POST"])
def handle_delete():
    data = request.json
    try:
        req = ItemIdRequest(**data)
        db_id = req.id
    except Exception:
        return jsonify({"status": "error", "message": "Invalid or missing ID"}), 400

    try:
        deleted_files = delete_audio_handler(db_id, audio_manager, processor)
        return jsonify(DeleteResponse(deleted=deleted_files).model_dump())
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@control_bp.route("/api/control/update_text", methods=["POST"])
def handle_update_text():
    data = request.json
    try:
        req = ItemIdRequest(**data)
        db_id = req.id
    except Exception:
        return jsonify({"status": "error", "message": "Invalid or missing ID"}), 400

    new_text = data.get("text")
    if new_text is None:
        return jsonify({"status": "error", "message": "Missing text"}), 400
    try:
        update_text_handler(db_id, new_text, processor)
        return jsonify({"status": "ok"})
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@control_bp.route("/api/system/browse", methods=["POST"])
def browse_directory():
    try:
        path = browse_directory_handler()
        if path:
            return jsonify(BrowseResponse(path=path).model_dump())
        return jsonify({"status": "cancelled"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@control_bp.route("/api/system/browse_file", methods=["POST"])
def browse_file():
    try:
        path = browse_file_handler()
        if path:
            return jsonify(BrowseResponse(path=path).model_dump())
        return jsonify({"status": "cancelled"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
