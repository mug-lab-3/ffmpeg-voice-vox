"""
API Implementation for Config Domain.

IMPORTANT:
The implementation in this file must strictly follow the specifications
documented in `docs/specification/api-server.md`.
Please ensure any changes here are synchronized with the specification.
"""

from flask import Blueprint, request, jsonify
from pydantic import ValidationError
from app.services.config_service import get_config_handler, update_config_handler
from app.api.schemas.config import (
    SynthesisUpdate,
    ResolveUpdate,
    SystemUpdate,
    FfmpegUpdate,
)
from app.api.schemas.base import BaseResponse
from app.config import config

config_bp = Blueprint("config_api", __name__)


def handle_validation_error(e: ValidationError):
    """Standardized validation error response including current config state."""
    response_data = get_config_handler().model_dump()
    response_data.update(
        {
            "status": "error",
            "error_code": "INVALID_ARGUMENT",
            "message": f"{e.errors()[0]['loc'][0]}: {e.errors()[0]['msg']}",
        }
    )
    return jsonify(response_data), 422


@config_bp.route("/api/config", methods=["GET"])
def get_config():
    result = get_config_handler()
    return jsonify(result.model_dump())


@config_bp.route("/api/config/synthesis", methods=["POST"])
def update_synthesis():
    try:
        data = SynthesisUpdate(**request.json)
        for k, v in data.model_dump(exclude_unset=True).items():
            if not config.update(f"synthesis.{k}", v):
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": f"Failed to update synthesis.{k}",
                        }
                    ),
                    500,
                )
        from app.core.events import event_manager
        event_manager.publish("config_update", {})
        return jsonify({"status": "ok"})
    except ValidationError as e:
        return handle_validation_error(e)


@config_bp.route("/api/config/resolve", methods=["POST"])
def update_resolve():
    try:
        data = ResolveUpdate(**request.json)
        for k, v in data.model_dump(exclude_unset=True).items():
            if not config.update(f"resolve.{k}", v):
                return (
                    jsonify(
                        {"status": "error", "message": f"Failed to update resolve.{k}"}
                    ),
                    500,
                )
        from app.core.events import event_manager
        event_manager.publish("config_update", {})
        return jsonify({"status": "ok"})
    except ValidationError as e:
        return handle_validation_error(e)


@config_bp.route("/api/config/system", methods=["POST"])
def update_system():
    try:
        data = SystemUpdate(**request.json)
        if data.output_dir is not None:
            if not config.update("system.output_dir", data.output_dir):
                return (
                    jsonify(
                        {"status": "error", "message": "Failed to update output_dir"}
                    ),
                    500,
                )

            from app.core.events import event_manager

            event_manager.publish("config_update", {"outputDir": data.output_dir})

            from app.web.routes import processor

            processor.reload_history()
        return jsonify({"status": "ok"})
    except ValidationError as e:
        return handle_validation_error(e)


@config_bp.route("/api/config/ffmpeg", methods=["POST"])
def update_ffmpeg():
    try:
        data = FfmpegUpdate(**request.json)
        for k, v in data.model_dump(exclude_unset=True).items():
            if not config.update(f"ffmpeg.{k}", v):
                return (
                    jsonify(
                        {"status": "error", "message": f"Failed to update ffmpeg.{k}"}
                    ),
                    500,
                )
        from app.core.events import event_manager
        event_manager.publish("config_update", {})
        return jsonify({"status": "ok"})
    except ValidationError as e:
        return handle_validation_error(e)


@config_bp.route("/api/resolve/bins", methods=["GET"])
def get_resolve_bins():
    """Returns a list of bins in the root folder."""
    from app.web.routes import get_resolve_client

    client = get_resolve_client()
    if not client.is_available():
        return (
            jsonify({"status": "error", "message": "DaVinci Resolve is not connected"}),
            503,
        )

    bins = client.get_bins()
    return jsonify({"status": "ok", "bins": bins})


@config_bp.route("/api/resolve/clips", methods=["GET"])
def get_resolve_clips():
    """Returns a list of Text+ clips in the configured target bin."""
    from app.web.routes import get_resolve_client

    client = get_resolve_client()
    if not client.is_available():
        return (
            jsonify({"status": "error", "message": "DaVinci Resolve is not connected"}),
            503,
        )

    bin_name = config.get("resolve.target_bin", "VoiceVox Captions")
    clips = client.get_text_plus_clips(bin_name)
    return jsonify({"status": "ok", "clips": clips})


# Compatibility route
@config_bp.route("/api/config", methods=["POST"])
def update_config_legacy():
    # This remains for backward compatibility but is no longer the preferred way
    data = request.json
    result = update_config_handler(data)
    if "outputDir" in data:
        from app.web.routes import processor

        processor.reload_history()
    return jsonify(result.model_dump())
