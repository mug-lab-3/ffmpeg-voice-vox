"""
API Implementation for Config Domain.

IMPORTANT:
The implementation in this file must strictly follow the specifications
documented in `docs/specification/api-server.md`.
Please ensure any changes here are synchronized with the specification.
"""

from flask import Blueprint, request, jsonify
from pydantic import ValidationError
from app.web.routes import vv_client, get_resolve_client, processor
from app.api.schemas.config import (
    ConfigResponse,
    APIConfigSchema,
    SynthesisUpdate,
    ResolveUpdate,
    SystemUpdate,
    FfmpegUpdate,
)
from app.api.schemas.base import BaseResponse
from app.config import config

config_bp = Blueprint("config_api", __name__)


def _save_and_notify(additional_data=None):
    """Internal helper to save config and publish update event."""
    config.save_config_ex()
    from app.core.events import event_manager

    event_manager.publish("config_update", additional_data or {})


def _get_config_state() -> ConfigResponse:
    """Internal helper to get current full config state."""
    resolve_available = get_resolve_client().is_available()
    voicevox_available = vv_client.is_available()

    full_cfg = APIConfigSchema(
        **config.synthesis.model_dump(),
        ffmpeg=config.ffmpeg.model_dump(),
        resolve=config.resolve.model_dump(),
    )

    return ConfigResponse(
        config=full_cfg,
        outputDir=config.system.output_dir,
        resolve_available=resolve_available,
        voicevox_available=voicevox_available,
    )


def handle_validation_error(e: ValidationError):
    """Standardized validation error response including current config state."""
    response_data = _get_config_state().model_dump()
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
    return jsonify(_get_config_state().model_dump())


@config_bp.route("/api/config/synthesis", methods=["POST"])
def update_synthesis():
    try:
        data = SynthesisUpdate(**request.json)
        for k, v in data.model_dump(exclude_unset=True).items():
            if hasattr(config.synthesis, k):
                setattr(config.synthesis, k, v)

        _save_and_notify()
        return jsonify(_get_config_state().model_dump())
    except ValidationError as e:
        return handle_validation_error(e)


@config_bp.route("/api/config/resolve", methods=["POST"])
def update_resolve():
    try:
        data = ResolveUpdate(**request.json)
        for k, v in data.model_dump(exclude_unset=True).items():
            if hasattr(config.resolve, k):
                setattr(config.resolve, k, v)

        _save_and_notify()
        return jsonify(_get_config_state().model_dump())
    except ValidationError as e:
        return handle_validation_error(e)


@config_bp.route("/api/config/system", methods=["POST"])
def update_system():
    try:
        data = SystemUpdate(**request.json)
        if data.output_dir is not None:
            config.system.output_dir = data.output_dir
            _save_and_notify({"outputDir": data.output_dir})
            processor.reload_history()
        return jsonify({"status": "ok"})
    except ValidationError as e:
        return handle_validation_error(e)


@config_bp.route("/api/config/ffmpeg", methods=["POST"])
def update_ffmpeg():
    try:
        data = FfmpegUpdate(**request.json)
        for k, v in data.model_dump(exclude_unset=True).items():
            if hasattr(config.ffmpeg, k):
                setattr(config.ffmpeg, k, v)

        _save_and_notify()
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

    bin_name = config.resolve.target_bin
    clips = client.get_text_plus_clips(bin_name)
    return jsonify({"status": "ok", "clips": clips})


