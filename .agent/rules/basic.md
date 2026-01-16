---
trigger: always_on
---

# AI Agent Instructions

## 1. Communication & Language
- **All interactions with the USER MUST be conducted in Japanese.** This includes explanations, planning, and status updates.
    - **Exception**: All source code (variable names, comments, etc.) and Web UI display labels MUST be in English.
- Internal thought processes and the content of basic.md are in English.
- Use UTF-8 encoding for all files.

## 2. Core Objectives
This application orchestrates voice recognition using **FFmpeg (v8.0+) with its built-in Whisper filter**. The workflow involves:
1.  Capturing user voice input via FFmpeg.
2.  Transcribing the audio using the integrated Whisper filter.
3.  Synthesizing response speech via **VOICEVOX**.
4.  Allowing the user to browse and **manually select items** for insertion as audio and subtitles (Text+) into the **DaVinci Resolve** timeline.
The goal is to provide a streamlined, high-quality audio synthesis and subtitling workflow with precise manual control.

## 3. Technical Requirements
- **Runtime**: Python 3.10+ (Managed via **uv**)
- **Framework**: Flask (Web UI & API)
- **Unit Testing**: 
    - Always use **pytest** for unit tests.
    - Run tests using `uv run pytest`.
    - Tests are located in the `tests/` directory.
- **Verification**: 
    - Perform final verification by running **`run_checks.bat`**. This script runs the auto-formatter (black) and the test suite via `scripts/run_tests.py`.
- **Documentation**: 
    - If any implementation or system behavior is changed, **ALWAYS update the corresponding specification files** in `docs/specification/`.

## 4. Key System Specifications
- **SSD Longevity**: SQLite optimization is active (Journal Mode = MEMORY, Synchronous = OFF, Temp Store = MEMORY). Minimize temporary file creation on disk.
- **File Naming**: Audio files MUST follow the pattern `{ID}_{SHA1}_{TextPrefix}.wav`. The SHA1 hash is derived from the text content to prevent caching issues.
- **Cross-Platform**: Support both Windows and macOS. Use cross-platform libraries and handle OS-specific behaviors (e.g., high DPI dialogs on Windows via `ctypes`) carefully.
- **Process Management**: Prevent multiple instances by killing old processes on startup. Auto-shutdown after 15 minutes of inactivity.

## 5. Project Structure
Follow the established layer separation:
- `app/api/`: Routing and input validation.
- `app/services/`: Business logic and service orchestration.
- `app/core/`: Infrastructure (FFmpeg, VoiceVox, Resolve Client).
- `static/` & `templates/`: Frontend WebUI.