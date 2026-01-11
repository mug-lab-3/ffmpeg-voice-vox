import sys
import subprocess
import os


def main():
    # Ensure we run from the project root directory
    # This script is expected to be in scripts/run_tests.py, so root is two levels up
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    os.chdir(root_dir)

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "--ignore=tests/test_voicevox_integration.py",
        "--ignore=tests/test_command_logic.py",
        "--ignore=tests/test_history_loading.py",
        "--ignore=tests/test_log_consistency.py",
        "--ignore=tests/test_logs.py",
        "--ignore=tests/test_srt_generation.py",
    ]

    print(f"Running unit tests from {root_dir}...")
    # Flush stdout to ensure output is seen immediately
    sys.stdout.flush()

    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
