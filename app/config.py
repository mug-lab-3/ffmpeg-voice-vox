import json
import os
import copy
from typing import Dict, Any

class ConfigManager:
    DEFAULT_CONFIG_PATH = "default_config.json"
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        # Load default config first
        self.default_config = self._load_default_config()
        # Then load user config
        self.config = self.load_config()

    def _load_default_config(self) -> Dict[str, Any]:
        if os.path.exists(self.DEFAULT_CONFIG_PATH):
            try:
                with open(self.DEFAULT_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[Config] Error loading default_config.json: {e}")
        
        # Absolute fallback if file missing
        return {
            "server": {"host": "127.0.0.1"},
            "voicevox": {"host": "127.0.0.1", "port": 50021},
            "synthesis": {"speaker_id": 1, "speed_scale": 1.0, "pitch_scale": 0.0, "intonation_scale": 1.0, "volume_scale": 1.0},
            "system": {"is_synthesis_enabled": False, "output_dir": ""},
            "ffmpeg": {"ffmpeg_path": "", "input_device": "", "model_path": "", "vad_model_path": "", "host": "localhost", "queue_length": 10},
            "resolve": {"enabled": False, "audio_track_index": 1, "subtitle_track_index": 2, "template_bin": "VoiceVox Captions", "template_name": "DefaultTemplate"}
        }

    def load_config(self) -> Dict[str, Any]:
        """Load user config, validate against defaults, and correct if needed."""
        loaded_config = {}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
            except Exception as e:
                print(f"[Config] Error reading {self.config_path}: {e}")

        # Deep copy defaults as base
        final_config = copy.deepcopy(self.default_config)
        
        # Merge and Validate
        is_corrected = self._merge_and_validate(final_config, loaded_config, self.default_config)
        
        # Force reset synthesis state to False on startup
        if "system" in final_config:
            final_config["system"]["is_synthesis_enabled"] = False
        
        if is_corrected or not os.path.exists(self.config_path):
            print(f"[Config] Saving corrected configuration to {self.config_path}")
            self.save_config(final_config)
            
        print(f"[Config] Configuration loaded and synchronized")
        return final_config

    def _merge_and_validate(self, base: Dict, other: Dict, defaults: Dict) -> bool:
        """
        Recursively merge 'other' into 'base'. 
        If a value in 'other' is invalid (wrong type or empty for critical fields), 
        keep/use the value from 'defaults'.
        Returns True if any correction was made.
        """
        corrected = False
        for key, default_val in defaults.items():
            user_val = other.get(key)
            
            if isinstance(default_val, dict):
                # Ensure the section exists in base
                if key not in base:
                    base[key] = copy.deepcopy(default_val)
                    corrected = True
                
                # Recurse
                sub_corrected = self._merge_and_validate(base[key], other.get(key, {}), default_val)
                if sub_corrected:
                    corrected = True
            else:
                if user_val is None:
                    # Key missing in user config, already has default from deepcopy of base
                    # But we mark it as "needs saving" since it was missing
                    corrected = True
                    continue
                
                # Type Check
                if type(user_val) != type(default_val):
                    # Special case: try converting numeric strings
                    if isinstance(default_val, int) and isinstance(user_val, str):
                        try:
                            base[key] = int(user_val)
                            continue
                        except: pass
                    
                    print(f"[Config] Type mismatch for '{key}': expected {type(default_val)}, got {type(user_val)}. Using default.")
                    base[key] = default_val
                    corrected = True
                    continue
                
                # Empty Value Check for Strings (Optional: define which fields allow empty)
                # For now, if default is non-empty and user is empty, we consider it a correction needed for template fields
                if isinstance(default_val, str) and default_val != "" and str(user_val).strip() == "":
                    # Specifically for Resolve templates and critical paths
                    critical_fields = ["template_bin", "template_name", "host", "ffmpeg_path"]
                    if key in critical_fields:
                        base[key] = default_val
                        corrected = True
                        continue

                # Everything OK, use user value
                base[key] = user_val
                
        return corrected

    def save_config(self, config_to_save: Dict[str, Any] = None):
        """Save current config to file."""
        data = config_to_save if config_to_save is not None else self.config
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[Config] Error saving config: {e}")

    def get(self, key: str, default=None):
        """Get a value by dot notation (e.g. 'server.host')."""
        keys = key.split('.')
        value = self.config
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
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
