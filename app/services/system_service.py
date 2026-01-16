from app.api.schemas.system import DevicesResponse


def get_audio_devices_handler(capture_service) -> DevicesResponse:
    """Lists available audio devices."""
    devices = capture_service.list_devices()
    device_names = [d["name"] for d in devices]
    return DevicesResponse(devices=device_names)


def heartbeat_handler():
    """Simple alive check."""
    return {"status": "alive"}


def get_available_models_handler():
    """Checks which whisper models are downloaded."""
    import os
    model_dir = os.path.join("models", "whisper")
    if not os.path.exists(model_dir):
        return []

    downloaded = []
    sizes = [
        "tiny",
        "base",
        "small",
        "medium",
        "large-v1",
        "large-v2",
        "large-v3",
        "large-v3-turbo",
    ]

    try:
        entries = os.listdir(model_dir)
        for size in sizes:
            # Check for direct folder or HF hub cache style
            found = False
            for entry in entries:
                if size in entry and os.path.isdir(os.path.join(model_dir, entry)):
                    downloaded.append(size)
                    found = True
                    break
            if not found and os.path.exists(os.path.join(model_dir, size)):
                downloaded.append(size)
    except Exception:
        pass

    return downloaded
