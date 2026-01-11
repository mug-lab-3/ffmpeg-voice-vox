"""
API Implementation for Config Domain.

IMPORTANT:
The implementation in this file must strictly follow the specifications 
documented in `doc/specification/api-server.md`.
Please ensure any changes here are synchronized with the specification.
"""
from flask import Blueprint, request, jsonify
from pydantic import ValidationError
from app.services.config_service import get_config_handler, update_config_handler
from app.api.schemas.config import SynthesisUpdate, ResolveUpdate, SystemUpdate, FfmpegUpdate
from app.api.schemas.base import BaseResponse
from app.config import config

config_bp = Blueprint('config_api', __name__)

def handle_validation_error(e: ValidationError):
    """Standardized validation error response including current config state."""
    response_data = get_config_handler().model_dump()
    response_data.update({
        "status": "error",
        "error_code": "INVALID_ARGUMENT",
        "message": f"{e.errors()[0]['loc'][0]}: {e.errors()[0]['msg']}"
    })
    return jsonify(response_data), 422

@config_bp.route('/api/config', methods=['GET'])
def get_config():
    result = get_config_handler()
    return jsonify(result.model_dump())

@config_bp.route('/api/config/synthesis', methods=['POST'])
def update_synthesis():
    try:
        data = SynthesisUpdate(**request.json)
        for k, v in data.model_dump(exclude_unset=True).items():
            config.update(f"synthesis.{k}", v)
        return jsonify({"status": "ok"})
    except ValidationError as e:
        return handle_validation_error(e)

@config_bp.route('/api/config/resolve', methods=['POST'])
def update_resolve():
    try:
        data = ResolveUpdate(**request.json)
        for k, v in data.model_dump(exclude_unset=True).items():
            config.update(f"resolve.{k}", v)
        return jsonify({"status": "ok"})
    except ValidationError as e:
        return handle_validation_error(e)

@config_bp.route('/api/config/system', methods=['POST'])
def update_system():
    try:
        data = SystemUpdate(**request.json)
        if data.output_dir is not None:
            config.update("system.output_dir", data.output_dir)
            from app.web.routes import processor
            processor.reload_history()
        return jsonify({"status": "ok"})
    except ValidationError as e:
        return handle_validation_error(e)

@config_bp.route('/api/config/ffmpeg', methods=['POST'])
def update_ffmpeg():
    try:
        data = FfmpegUpdate(**request.json)
        for k, v in data.model_dump(exclude_unset=True).items():
            config.update(f"ffmpeg.{k}", v)
        return jsonify({"status": "ok"})
    except ValidationError as e:
        return handle_validation_error(e)

# Compatibility route
@config_bp.route('/api/config', methods=['POST'])
def update_config_legacy():
    # This remains for backward compatibility but is no longer the preferred way
    data = request.json
    result = update_config_handler(data)
    if "outputDir" in data:
        from app.web.routes import processor
        processor.reload_history()
    return jsonify(result.model_dump())
