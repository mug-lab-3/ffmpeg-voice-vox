import json
import os
import copy
from typing import Dict, Any

class ConfigManager:
    DEFAULT_CONFIG = {
        "server": {
            "host": "127.0.0.1"
        },
        "voicevox": {
            "host": "127.0.0.1",
            "port": 50021
        },
        "synthesis": {
            "speaker_id": 1,
            "speed_scale": 1.0,
            "pitch_scale": 0.0,
            "intonation_scale": 1.0,
            "volume_scale": 1.0
        },
        "system": {
            "is_synthesis_enabled": False,
            "output_dir": ""
        },
        "ffmpeg": {
            "ffmpeg_path": "",
            "input_device": "",
            "model_path": "",
            "vad_model_path": "",
            "host": "localhost",
            "queue_length": ""
        },
        "resolve": {
            "enabled": False,
            "audio_track_index": 1,
            "subtitle_track_index": 2,
            "template_bin": "VoiceVox Captions",
            "template_name": "DefaultTemplate"
        }
    }

    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = self.load_config()

    def load_config(self) -> Dict[str, Any]:
        """Load config from file, or create with defaults if not exists."""
        if not os.path.exists(self.config_path):
            print(f"[Config] Creating new config file: {self.config_path}")
            self.save_config(self.DEFAULT_CONFIG)
            return copy.deepcopy(self.DEFAULT_CONFIG)
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                
            # Use deepcopy to ensure we don't modify the class constant
            final_config = copy.deepcopy(self.DEFAULT_CONFIG)
            self._merge_configs(final_config, loaded_config)
            
            # Force reset synthesis state to False on startup
            if "system" in final_config:
                final_config["system"]["is_synthesis_enabled"] = False
            
            # Validation and Correction logic
            is_corrected = False
            
            # Resolve Settings Correction
            if "resolve" in final_config:
                r = final_config["resolve"]
                defaults = self.DEFAULT_CONFIG["resolve"]
                
                # Check for empty strings or missing keys in critical fields
                for key in ["template_bin", "template_name"]:
                    if not r.get(key) or str(r.get(key)).strip() == "":
                        r[key] = defaults[key]
                        is_corrected = True
                
                # Check for numeric track indices
                for key in ["audio_track_index", "subtitle_track_index"]:
                    if not isinstance(r.get(key), int):
                        try:
                            # Try to convert if it's a string, else use default
                            r[key] = int(r.get(key))
                        except (ValueError, TypeError):
                            r[key] = defaults[key]
                        is_corrected = True

            if is_corrected:
                print(f"[Config] Corrections applied to {self.config_path}")
                # Save immediately to ensure file is in sync
                self.save_config(final_config)
            
            print(f"[Config] Loaded successfully")
            return final_config
        except Exception as e:
            print(f"Error loading config: {e}. Using defaults.")
            return copy.deepcopy(self.DEFAULT_CONFIG)

    def _merge_configs(self, base: Dict, other: Dict) -> Dict:
        """Recursive merge of dictionaries into base."""
        for key, value in other.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_configs(base[key], value)
            else:
                base[key] = value
        return base

    def save_config(self, config: Dict[str, Any] = None):
        """Save current config to file."""
        if config is None:
            config = self.config
        
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key: str, default=None):
        """Get a value by dot notation (e.g. 'server.port')."""
        keys = key.split('.')
        value = self.config
        try:
            for k in keys:
                value = value[k]
            return value
        except KeyError:
            return default

    def update(self, key: str, value: Any):
        """Update a value by dot notation and save."""
        keys = key.split('.')
        target = self.config
        for k in keys[:-1]:
            target = target.setdefault(k, {})
        target[keys[-1]] = value
        self.save_config()

# Global instance
config = ConfigManager()
