import json
import os
from typing import Dict, Any
from .schemas import ConfigSchema
from pydantic import ValidationError

class ConfigManager:
    DEFAULT_CONFIG_PATH = "default_config.json"
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.is_synthesis_enabled = False  # Runtime state
        self._config_obj = self.load_config()

    @property
    def config(self) -> Dict[str, Any]:
        """Return the configuration as a dictionary, including runtime state."""
        data = self._config_obj.model_dump()
        if "system" not in data:
            data["system"] = {}
        data["system"]["is_synthesis_enabled"] = self.is_synthesis_enabled
        return data

    def load_config(self) -> ConfigSchema:
        """Load user config, validate with Pydantic, and correct if needed."""
        loaded_data = {}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
            except Exception as e:
                print(f"[Config] Error reading {self.config_path}: {e}")

        try:
            # Validate and apply defaults
            config_obj = ConfigSchema(**loaded_data)
        except ValidationError as e:
            print(f"[Config] Validation errors found in {self.config_path}:")
            for error in e.errors():
                print(f"  - {'.'.join(str(i) for i in error['loc'])}: {error['msg']}")
            
            # Use partial data and fill rest with defaults
            config_obj = self._load_best_effort(loaded_data)
            self.save_config(config_obj)
        else:
            # Check if we need to save (e.g. if fields were missing and filled by defaults)
            if loaded_data != config_obj.model_dump():
                print(f"[Config] Synchronizing missing fields to {self.config_path}")
                self.save_config(config_obj)

        print(f"[Config] Configuration loaded and synchronized via Pydantic")
        return config_obj

    def _load_best_effort(self, data: Dict[str, Any]) -> ConfigSchema:
        """Attempt to load what's valid from data, fallback to defaults for invalid/missing parts."""
        default_obj = ConfigSchema()
        
        if not isinstance(data, dict):
            return default_obj

        for section_name in default_obj.model_fields:
            if section_name in data and isinstance(data[section_name], dict):
                section_data = data[section_name]
                section_model = getattr(default_obj, section_name).__class__
                try:
                    setattr(default_obj, section_name, section_model(**section_data))
                except ValidationError:
                    print(f"[Config] Section '{section_name}' has invalid values. Using defaults for this section.")
                    
        return default_obj

    def save_config(self, config_to_save: Any = None):
        """Save current config to file."""
        obj = config_to_save if config_to_save is not None else self._config_obj
        try:
            data = obj.model_dump() if hasattr(obj, 'model_dump') else obj
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
        if key == "system.is_synthesis_enabled":
            self.is_synthesis_enabled = bool(value)
            return

        keys = key.split('.')
        target = self._config_obj
        for k in keys[:-1]:
            target = getattr(target, k)
        
        setattr(target, keys[-1], value)
        
        try:
            # Re-validate locally
            validated_data = ConfigSchema(**self._config_obj.model_dump())
            self._config_obj = validated_data
        except ValidationError as e:
            print(f"[Config] Update failed validation: {e}")
            
        self.save_config()

# Global instance
config = ConfigManager()
