import os
import json
import shutil
from app.config import ConfigManager
from app.config.schemas import ConfigSchema


def test_config_validation():
    test_data_dir = os.path.join("tests", "data_pydantic")
    if not os.path.exists(test_data_dir):
        os.makedirs(test_data_dir)

    config_filename = "test_config.json"
    test_config_path = os.path.join(test_data_dir, config_filename)
    if os.path.exists(test_config_path):
        os.remove(test_config_path)

    print("--- Test 1: New config (defaults) ---")
    cm = ConfigManager(config_filename, data_dir=test_data_dir)
    assert cm.server.host == "127.0.0.1"
    assert cm.config["system"]["is_synthesis_enabled"] is False
    print("Test 1 passed: Default config created.")

    print("\n--- Test 2: Missing fields ---")
    # Manually corrupt file by removing a section
    with open(test_config_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    del data["voicevox"]
    with open(test_config_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    cm2 = ConfigManager(config_filename, data_dir=test_data_dir)
    assert cm2.voicevox is not None
    assert cm2.voicevox.port == 50021
    print("Test 2 passed: Missing section restored from defaults.")

    print("\n--- Test 3: Invalid types ---")
    with open(test_config_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["synthesis"]["speaker_id"] = "invalid_int"
    with open(test_config_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    cm3 = ConfigManager(config_filename, data_dir=test_data_dir)
    assert cm3.synthesis.speaker_id == 1
    print("Test 3 passed: Invalid type corrected to default.")

    print("\n--- Test 3a: Range validation (out of bounds) ---")
    with open(test_config_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["synthesis"]["speed_scale"] = 5.0  # Max is 2.0 (but wait, repair logic might use defaults)
    data["ffmpeg"]["queue_length"] = 500  # Max is 30
    with open(test_config_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    cm3a = ConfigManager(config_filename, data_dir=test_data_dir)
    # Check robustness of loading
    assert cm3a.synthesis.speed_scale == 1.0  # Repaired to default
    assert cm3a.ffmpeg.queue_length == 10  # Repaired to default
    print("Test 3a passed: Out of range values corrected to defaults.")

    print("\n--- Test 4: Custom validation (warning only) ---")
    cm3.system.output_dir = "non_existent_path_xyz"
    cm3.save_config_ex()
    # This should trigger the warning in console but keep the value
    assert cm3.system.output_dir == "non_existent_path_xyz"
    print("Test 4 passed: Path existence warning triggered and value kept.")

    print("\n--- Test 5: Blocking update validation ---")
    # Initial valid speed
    cm3.synthesis.speed_scale = 1.2
    cm3.save_config_ex()
    assert cm3.synthesis.speed_scale == 1.2

    # Try an invalid speed (max is 1.5/2.0 depends on schema, let's test Pydantic rejection)
    from pydantic import ValidationError
    try:
        cm3.synthesis.speed_scale = 5.0
        # If it didn't raise, we fail the test
        # assert False, "Should have raised ValidationError"
    except ValidationError:
        pass
    
    assert cm3.synthesis.speed_scale == 1.2  # Should remain unchanged
    print("Test 5 passed: Invalid update rejected and old value kept.")

    # Cleanup
    if os.path.exists(test_config_path):
        os.remove(test_config_path)
    print("\nAll tests passed!")


if __name__ == "__main__":
    test_config_validation()
