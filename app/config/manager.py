import json
import os
from typing import Dict, Any
from .schemas.config_schema import ConfigSchema
from .schemas import (
    BaseModel,
    ServerConfig,
    VoiceVoxConfig,
    SynthesisConfig,
    SystemConfig,
    FfmpegConfig,
    ResolveConfig,
)
from pydantic import ValidationError


class ConfigManager:

    def __init__(self, config_filename: str = "config.json", data_dir: str = None):
        # Relocate config to 'data' directory
        if data_dir:
            self.data_dir = data_dir
        else:
            self.data_dir = os.path.join(os.getcwd(), "data")

        self.config_path = os.path.join(self.data_dir, config_filename)

        self._ensure_data_dir()
        self._migrate_old_config(config_filename)

        self.is_synthesis_enabled = False  # Runtime state
        # Primary state object (Load using new robust logic)
        self._config_obj = self.load_config_ex()

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

    @property
    def server(self) -> ServerConfig:
        return self._config_obj.server

    @server.setter
    def server(self, value: ServerConfig):
        self._config_obj.server = value

    @server.deleter
    def server(self):
        pass

    @property
    def voicevox(self) -> VoiceVoxConfig:
        return self._config_obj.voicevox

    @voicevox.setter
    def voicevox(self, value: VoiceVoxConfig):
        self._config_obj.voicevox = value

    @voicevox.deleter
    def voicevox(self):
        pass

    @property
    def synthesis(self) -> SynthesisConfig:
        return self._config_obj.synthesis

    @synthesis.setter
    def synthesis(self, value: SynthesisConfig):
        self._config_obj.synthesis = value

    @synthesis.deleter
    def synthesis(self):
        pass

    @property
    def system(self) -> SystemConfig:
        return self._config_obj.system

    @system.setter
    def system(self, value: SystemConfig):
        self._config_obj.system = value

    @system.deleter
    def system(self):
        pass

    @property
    def ffmpeg(self) -> FfmpegConfig:
        return self._config_obj.ffmpeg

    @ffmpeg.setter
    def ffmpeg(self, value: FfmpegConfig):
        self._config_obj.ffmpeg = value

    @ffmpeg.deleter
    def ffmpeg(self):
        pass

    @property
    def resolve(self) -> ResolveConfig:
        return self._config_obj.resolve

    @resolve.setter
    def resolve(self, value: ResolveConfig):
        self._config_obj.resolve = value

    def load_config(self) -> ConfigSchema:
        """Legacy wrapper for backward compatibility in tests."""
        return self.load_config_ex()

    def load_config_ex(self) -> ConfigSchema:
        """
        New clean loading logic.
        Separates file I/O, validation, and repair.
        Saves to disk only once at the end if repairs or defaults were applied.
        """
        # 1. Read raw data
        raw_data = self._read_raw_json()

        # 2. Try strict validation
        try:
            config_obj = ConfigSchema.model_validate(raw_data)
        except ValidationError:
            print(
                f"[Config] Validation failed in {self.config_path}, attempting repair..."
            )
            # 3. Best-effort repair
            config_obj = self._repair_config(raw_data)

        # 4. Success or repaired, check if sync needed (missing default fields or repaired)
        # Compare current state with raw data to see if we need to write back
        if raw_data != config_obj.model_dump():
            print(
                f"[Config] Synchronizing changes (repairs or defaults) to {self.config_path}"
            )
            self.save_config_ex(config_obj)

        print(f"[Config] Configuration loaded (Clean)")
        return config_obj

    def _read_raw_json(self) -> Dict[str, Any]:
        """Read and decode JSON file, handling corruption."""
        if not os.path.exists(self.config_path):
            return {}

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception) as e:
            print(f"[Config] Critical error reading {self.config_path}: {e}")
            self._backup_corrupt_file()
            return {}

    def _backup_corrupt_file(self):
        """Move corrupt file to a backup path."""
        import shutil
        import time

        timestamp = int(time.time())
        backup_path = f"{self.config_path}.corrupt.{timestamp}"
        print(f"[Config] Backing up corrupt config to {backup_path}")
        try:
            shutil.copy(self.config_path, backup_path)
        except Exception as e:
            print(f"[Config] Backup failed: {e}")

    def _repair_config(self, data: Dict[str, Any]) -> ConfigSchema:
        """
        Repair configuration by delegating to each section's own load_best_effort.
        """
        repaired_data = {}
        defaults = ConfigSchema()

        if not isinstance(data, dict):
            return defaults

        # Get all top-level sections defined in ConfigSchema
        for section_name, field_info in ConfigSchema.model_fields.items():
            section_type = field_info.annotation
            section_input = data.get(section_name)

            # Delegate repair to the section class if it has load_best_effort
            if hasattr(section_type, "load_best_effort"):
                repaired_data[section_name] = section_type.load_best_effort(
                    section_input
                )
            else:
                # Fallback for non-delegated fields
                repaired_data[section_name] = getattr(defaults, section_name)

        return ConfigSchema(**repaired_data)

    def save_config(self, config_to_save: Any = None):
        """Save current config to file. (Legacy version, now uses save_config_ex)"""
        if config_to_save is not None:
            if isinstance(config_to_save, ConfigSchema):
                self.save_config_ex(config_to_save)
            else:
                # Fallback for dict-based or other objects (though not recommended)
                self.save_config_ex(ConfigSchema.model_validate(config_to_save))
        else:
            self.save_config_ex(self._config_obj)

    def save_config_ex(self, config_obj: ConfigSchema = None):
        """
        New clean save logic.
        Type-safe and uses ConfigSchema explicitly.
        """
        obj = config_obj if config_obj is not None else self._config_obj
        data = obj.model_dump()

        # Ensure directory exists
        path_dir = os.path.dirname(self.config_path)
        if path_dir:
            os.makedirs(path_dir, exist_ok=True)

        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
                f.flush()
                # Force write to physical disk
                try:
                    os.fsync(f.fileno())
                except OSError:
                    pass
        except Exception as e:
            print(f"[Config] Failed to save {self.config_path}: {e}")
            raise

    def update_server(self, update: ServerConfig) -> bool:
        self._config_obj.server = update
        self.save_config_ex(self._config_obj)
        return True

    def update_voicevox(self, update: VoiceVoxConfig) -> bool:
        self._config_obj.voicevox = update
        self.save_config_ex(self._config_obj)
        return True

    def update_synthesis(self, update: SynthesisConfig) -> bool:
        self._config_obj.synthesis = update
        self.save_config_ex(self._config_obj)
        return True

    def update_system(self, update: SystemConfig) -> bool:
        self._config_obj.system = update
        self.save_config_ex(self._config_obj)
        return True

    def update_ffmpeg(self, update: FfmpegConfig) -> bool:
        self._config_obj.ffmpeg = update
        self.save_config_ex(self._config_obj)
        return True

    def update_resolve(self, update: ResolveConfig) -> bool:
        self._config_obj.resolve = update
        self.save_config_ex(self._config_obj)
        return True


# Global instance
config = ConfigManager()
