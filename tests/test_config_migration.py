import os
import json
import pytest
from app.config import ConfigManager
from app.config.schemas import ConfigSchema


@pytest.fixture
def test_data_dir(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    return d


def test_migration_complex_scenarios(test_data_dir):
    config_file = test_data_dir / "config.json"

    # 複雑な異常系データ
    # 1. systemセクションが完全に欠落
    # 2. synthesisセクションに有効な値と、バリデーションエラーになる値が混在
    # 3. transcriptionセクションが辞書ではなく文字列になっている
    # 4. resolveセクションに未知のキーが含まれている
    initial_data = {
        "synthesis": {
            "speaker_id": 99,  # 有効
            "speed_scale": 5.0,  # 異常 (max 1.5) -> デフォルトに戻るべき
            "pitch_scale": 0.1,  # 有効
            "pre_phoneme_length": "invalid",  # 型異常 -> デフォルトに戻るべき
        },
        "transcription": "should_be_dict_but_is_string",
        "resolve": {
            "enabled": True,
            "audio_track_index": 5,
            "unknown_feature_key": "ignore_me",
        },
        # "system" is missing completely
    }

    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(initial_data, f)

    manager = ConfigManager("config.json", data_dir=str(test_data_dir))

    config_obj = manager.load_config()

    # 検証: system (欠落していたがデフォルト値が設定されていること)
    assert config_obj.system.output_dir == ""

    # 検証: synthesis (有効なものは保持、異常なものはデフォルト)
    assert config_obj.synthesis.speaker_id == 99
    assert config_obj.synthesis.speed_scale == 1.0  # 5.0 -> 1.0 (default)
    assert config_obj.synthesis.pitch_scale == 0.1
    assert config_obj.synthesis.pre_phoneme_length == 0.1  # "invalid" -> 0.1 (default)

    # 検証: transcription (構造破壊 -> セクションごとデフォルト)
    assert config_obj.transcription.beam_size == 5
    assert config_obj.transcription.device == "cpu"

    # 検証: resolve (有効なものは保持、未知のキーは無視)
    assert config_obj.resolve.enabled is True
    assert config_obj.resolve.audio_track_index == 5


def test_migration_preserves_custom_output_dir_even_on_other_errors(test_data_dir):
    config_file = test_data_dir / "config.json"

    # system.output_dir は設定されているが、他のセクションがメチャクチャな場合
    initial_data = {
        "system": {"output_dir": "D:/MyRecordings"},
        "synthesis": {"speed_scale": "very fast"},  # Error
        "transcription": None,  # Error
        "extra_top_level_junk": 123,
    }

    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(initial_data, f)

    manager = ConfigManager("config.json", data_dir=str(test_data_dir))

    config_obj = manager.load_config()

    # output_dir が死守されていること
    assert config_obj.system.output_dir == "D:/MyRecordings"

    # 他は最善を尽くして初期化されていること
    assert config_obj.synthesis.speed_scale == 1.0


def test_migration_empty_config(test_data_dir):
    config_file = test_data_dir / "config.json"

    with open(config_file, "w", encoding="utf-8") as f:
        f.write("{}")

    manager = ConfigManager("config.json", data_dir=str(test_data_dir))

    config_obj = manager.load_config()

    # 全てデフォルト
    assert config_obj.synthesis.speaker_id == 1
    assert config_obj.system.output_dir == ""


def test_migration_completely_broken_json(test_data_dir):
    config_file = test_data_dir / "config.json"

    with open(config_file, "w", encoding="utf-8") as f:
        f.write("this is not { json ] at all")

    manager = ConfigManager("config.json", data_dir=str(test_data_dir))

    # 以前のテストと同様、破損時は古いファイルをバックアップしてデフォルトで起動するはず
    config_obj = manager.load_config()

    assert config_obj.synthesis.speaker_id == 1

    # バックアップが作成されていることの確認
    backups = [f for f in os.listdir(test_data_dir) if "config.json.corrupt" in f]
    assert len(backups) > 0


if __name__ == "__main__":
    pytest.main([__file__])
