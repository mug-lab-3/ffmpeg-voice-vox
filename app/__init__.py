from flask import Flask
import logging
import os
from logging.handlers import RotatingFileHandler

def create_app():
    app = Flask(__name__, 
                static_folder="../static",
                template_folder="../templates")
    
    # Configure Logging
    if not os.path.exists('logs'):
        os.makedirs('logs')
        
    file_handler = RotatingFileHandler('logs/app.log', maxBytes=1048576, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Voicevox Integration Startup')
    
    # Register blueprints
    from app.web.routes import web
    from app.api.routes.config import config_bp
    from app.api.routes.control import control_bp
    from app.api.routes.system import system_bp

    app.register_blueprint(web)
    app.register_blueprint(config_bp)
    app.register_blueprint(control_bp)
    app.register_blueprint(system_bp)
    
    return app
