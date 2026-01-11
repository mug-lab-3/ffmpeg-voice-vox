import os
import json
import shutil
from app.config import ConfigManager
from app.schemas import ConfigSchema

def test_config_validation():
    test_config_path = "test_config.json"
    if os.path.exists(test_config_path):
        os.remove(test_config_path)

    print("--- Test 1: New config (defaults) ---")
    cm = ConfigManager(test_config_path)
    config = cm.config
    assert config["server"]["host"] == "127.0.0.1"
    assert config["system"]["is_synthesis_enabled"] is False
    print("Test 1 passed: Default config created.")

    print("\n--- Test 2: Missing fields ---")
    # Manually corrupt file by removing a section
    with open(test_config_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    del data["voicevox"]
    with open(test_config_path, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    
    cm2 = ConfigManager(test_config_path)
    assert "voicevox" in cm2.config
    assert cm2.config["voicevox"]["port"] == 50021
    print("Test 2 passed: Missing section restored from defaults.")

    print("\n--- Test 3: Invalid types ---")
    with open(test_config_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    data["synthesis"]["speaker_id"] = "invalid_int"
    with open(test_config_path, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    
    cm3 = ConfigManager(test_config_path)
    assert cm3.config["synthesis"]["speaker_id"] == 1
    print("Test 3 passed: Invalid type corrected to default.")

    print("\n--- Test 3a: Range validation (out of bounds) ---")
    with open(test_config_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    data["synthesis"]["speed_scale"] = 5.0  # Max is 2.0
    data["ffmpeg"]["queue_length"] = 500    # Max is 100
    with open(test_config_path, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    
    cm3a = ConfigManager(test_config_path)
    assert cm3a.config["synthesis"]["speed_scale"] == 1.0 # Section fallback to default
    assert cm3a.config["ffmpeg"]["queue_length"] == 10    # Section fallback to default
    print("Test 3a passed: Out of range values corrected to defaults.")

    print("\n--- Test 4: Custom validation (warning only) ---")
    cm3.update("system.output_dir", "non_existent_path_xyz")
    # This should trigger the warning in console but keep the value
    assert cm3.config["system"]["output_dir"] == "non_existent_path_xyz"
    print("Test 4 passed: Path existence warning triggered and value kept.")

    # Cleanup
    if os.path.exists(test_config_path):
        os.remove(test_config_path)
    print("\nAll tests passed!")

if __name__ == "__main__":
    test_config_validation()
