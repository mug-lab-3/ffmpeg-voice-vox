from flask import Blueprint, request, jsonify
from app.services.config_service import get_config_handler, update_config_handler

config_bp = Blueprint('config_api', __name__)

@config_bp.route('/api/config', methods=['GET'])
def get_config():
    result = get_config_handler()
    return jsonify(result.model_dump())

@config_bp.route('/api/config', methods=['POST'])
def update_config():
    data = request.json
    result = update_config_handler(data)
    
    # Reload logic (if outputDir changed, we might need a way to trigger processor.reload_history())
    # For now, let's keep it simple or use events.
    if "outputDir" in data:
        from app.web.routes import processor
        processor.reload_history()
        
    return jsonify(result.model_dump())
