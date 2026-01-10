import json
import os
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
            "track_index": 1
        }
    }

    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = self.load_config()

    def load_config(self) -> Dict[str, Any]:
        """Load config from file, or create with defaults if not exists."""
        if not os.path.exists(self.config_path):
            self.save_config(self.DEFAULT_CONFIG)
            return self.DEFAULT_CONFIG.copy()
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                # Merge with defaults to ensure all keys exist
                final_config = self._merge_configs(self.DEFAULT_CONFIG.copy(), loaded_config)
                # Force reset synthesis state to False on startup
                if "system" in final_config:
                    final_config["system"]["is_synthesis_enabled"] = False
                return final_config
        except Exception as e:
            print(f"Error loading config: {e}. Using defaults.")
            return self.DEFAULT_CONFIG.copy()

    def _merge_configs(self, default: Dict, other: Dict) -> Dict:
        """Recursive merge of dictionaries."""
        for key, value in other.items():
            if key in default and isinstance(default[key], dict) and isinstance(value, dict):
                self._merge_configs(default[key], value)
            else:
                default[key] = value
        return default

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
