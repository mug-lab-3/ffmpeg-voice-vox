import json
import os
from typing import Dict, Any
from .schemas import ConfigSchema, BaseModel
from pydantic import ValidationError


class ConfigManager:

    def __init__(self, config_filename: str = "config.json"):
        # Relocate config to 'data' directory
        self.data_dir = os.path.join(os.getcwd(), "data")
        self.config_path = os.path.join(self.data_dir, config_filename)

        self._ensure_data_dir()
        self._migrate_old_config(config_filename)

        self.is_synthesis_enabled = False  # Runtime state
        self._config_obj = self.load_config()

    def _ensure_data_dir(self):
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)

    def _migrate_old_config(self, filename: str):
        """Migrate config.json from root to data/ if it exists."""
        old_path = os.path.join(os.getcwd(), filename)
        if os.path.exists(old_path) and not os.path.exists(self.config_path):
            try:
                print(f"[Config] Migrating {filename} to {self.config_path}")
                import shutil

                shutil.move(old_path, self.config_path)
            except Exception as e:
                print(f"[Config] Migration failed: {e}")

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
        load_failed = False
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded_data = json.load(f)
            except json.JSONDecodeError as e:
                # Corrupt file: Backup and start fresh
                import shutil
                import time

                timestamp = int(time.time())
                backup_path = f"{self.config_path}.corrupt.{timestamp}"
                print(f"[Config] Error reading JSON {self.config_path}: {e}")
                print(f"[Config] Backing up corrupt config to {backup_path}")
                try:
                    shutil.copy(self.config_path, backup_path)
                except Exception as be:
                    print(f"[Config] Failed to backup: {be}")

                # Treat as empty to trigger default creation
                loaded_data = {}
                load_failed = True
            except Exception as e:
                print(f"[Config] Error reading {self.config_path}: {e}")
                # For permission errors etc, maybe we shouldn't overwrite?
                # But to be safe and robust for "cannot read", we might default.
                pass

        try:
            # Validate and apply defaults
            config_obj = ConfigSchema(**loaded_data)
        except ValidationError as e:
            print(f"[Config] Validation errors found in {self.config_path}:")
            for error in e.errors():
                print(f"  - {'.'.join(str(i) for i in error['loc'])}: {error['msg']}")

            # Use partial data and fill rest with defaults
            config_obj = self._load_best_effort(loaded_data)
            # Only save if we corrected something OR if we failed to load (fresh start/corruption)
            # But don't overwrite if it was just a validation error on start?
            # Yes, we should probably save the corrected version to ensure consistency.
            self.save_config(config_obj)
        else:
            # Check if we need to save (e.g. if fields were missing and filled by defaults)
            if loaded_data != config_obj.model_dump() or load_failed:
                print(f"[Config] Synchronizing missing fields to {self.config_path}")
                self.save_config(config_obj)

        print(f"[Config] Configuration loaded and synchronized via Pydantic")
        return config_obj

    def _load_best_effort(self, data: Dict[str, Any]) -> ConfigSchema:
        """Attempt to load what's valid from data, fallback to defaults for invalid/missing parts."""
        default_obj = ConfigSchema()

        if not isinstance(data, dict):
            return default_obj

        for section_name in default_obj.__class__.model_fields:
            if section_name not in data:
                continue

            section_data = data[section_name]
            current_section_instance = getattr(default_obj, section_name)

            # Case 1: Simple field (not a nested BaseModel)
            if not isinstance(current_section_instance, BaseModel):
                try:
                    # Validate by creating a temporary schema with this field
                    # Note: ConfigSchema itself can be used for simple top-level fields
                    temp_data = default_obj.model_dump()
                    temp_data[section_name] = section_data
                    ConfigSchema(**temp_data)
                    setattr(default_obj, section_name, section_data)
                except ValidationError:
                    print(
                        f"[Config] Field '{section_name}' has invalid value. Using default."
                    )
                continue

            # Case 2: Nested BaseModel (the usual case like 'synthesis', 'ffmpeg')
            if not isinstance(section_data, dict):
                print(
                    f"[Config] Section '{section_name}' expects a dictionary. Using default."
                )
                continue

            section_model_class = current_section_instance.__class__
            valid_section_data = current_section_instance.model_dump()

            for field_name, field_value in section_data.items():
                if field_name not in section_model_class.model_fields:
                    continue

                test_data = valid_section_data.copy()
                test_data[field_name] = field_value

                try:
                    section_model_class(**test_data)
                    valid_section_data[field_name] = field_value
                except ValidationError:
                    print(
                        f"[Config] Field '{section_name}.{field_name}' has invalid value. Using default."
                    )

            setattr(
                default_obj, section_name, section_model_class(**valid_section_data)
            )

        return default_obj

    def save_config(self, config_to_save: Any = None):
        """Save current config to file."""
        obj = config_to_save if config_to_save is not None else self._config_obj
        # Propagate exceptions to caller so API can return error
        data = obj.model_dump() if hasattr(obj, "model_dump") else obj

        # Ensure directory exists
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass

    def get(self, key: str, default=None):
        """Get a value by dot notation (e.g. 'server.host')."""
        keys = key.split(".")
        value = self.config
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def update(self, key: str, value: Any) -> bool:
        """
        Update a value by dot notation and save.
        Returns True if successful, False if validation fails.
        """
        if key == "system.is_synthesis_enabled":
            self.is_synthesis_enabled = bool(value)
            return True

        # Create a copy of current data to test the update
        current_data = self._config_obj.model_dump()

        # Traverse and update the dict
        keys = key.split(".")
        target = current_data
        try:
            for k in keys[:-1]:
                target = target[k]

            # Type conversion attempt (handling strings from WebUI)
            print(f"[Config] Updating {key} to {value} (type: {type(value).__name__})")
            target[keys[-1]] = value

            # Re-validate the whole structure
            new_obj = ConfigSchema(**current_data)
            self._config_obj = new_obj
            self.save_config()
            return True
        except (ValidationError, KeyError, TypeError, ValueError) as e:
            if isinstance(e, ValidationError):
                print(f"[Config] Update rejected for '{key}': Validation failed.")
                for error in e.errors():
                    print(
                        f"  - {'.'.join(str(i) for i in error['loc'])}: {error['msg']}"
                    )
            else:
                print(f"[Config] Update rejected for '{key}': {e}")
            return False


# Global instance
config = ConfigManager()
