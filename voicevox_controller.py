import webbrowser
import threading
import time
import os
import platform
import subprocess
import socket
from app import create_app
from app.config import config
from app.core.events import event_manager


def kill_previous_instances():
    """
    Scans for other Python processes running 'voicevox_controller.py' and kills them.
    Uses psutil for cross-platform support.
    """
    print("[Startup] Scanning for existing instances...")
    try:
        import psutil

        current_pid = os.getpid()
        parent_pid = os.getppid()  # Get parent PID (e.g. uv.exe)
        killed_count = 0

        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                # Check if it's a python process
                if "python" in proc.info["name"].lower():
                    cmdline = proc.info["cmdline"]
                    if cmdline:
                        # Check if voicevox_controller.py is in the arguments
                        if any("voicevox_controller.py" in arg for arg in cmdline):
                            proc_pid = proc.info["pid"]
                            if proc_pid != current_pid and proc_pid != parent_pid:
                                print(
                                    f"[Startup] Found existing instance (PID: {proc.info['pid']}). Killing..."
                                )
                                proc.kill()
                                killed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                # Ignore processes that we cannot access or that disappear during scan
                pass

        if killed_count == 0:
            print("[Startup] No other instances found.")
        else:
            print(f"[Startup] Killed {killed_count} existing instance(s).")

    except ImportError:
        print("[Startup] psutil not installed. Skipping duplicate instance check.")
    except Exception as e:
        print(f"[Startup] Error in process scan: {e}")


def find_free_port(start_port):
    """
    Finds a free port starting from start_port.
    """
    port = start_port
    while port < 65535:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("0.0.0.0", port))
                return port
        except OSError:
            port += 1
    return start_port


# Activity Monitoring
last_activity_time = time.time()
SHUTDOWN_TIMEOUT = 900  # 15 minutes


def update_activity():
    global last_activity_time
    last_activity_time = time.time()


def monitor_activity():
    global last_activity_time
    print("[Monitor] Activity monitor started.")
    while True:
        time.sleep(10)
        elapsed = time.time() - last_activity_time
        if elapsed > SHUTDOWN_TIMEOUT:
            print(f"[Monitor] No activity for {elapsed:.0f}s. Shutting down...")
            from app.web.routes import cleanup_resources

            cleanup_resources()
            os._exit(0)


if __name__ == "__main__":
    # 0. Single Instance Check
    kill_previous_instances()

    # 1. Determine Port (Auto-select available)
    host = config.server.host
    # Start checking from configured port
    start_port = config.server.port

    port = find_free_port(start_port)

    # 2. Initialize App (Logging setup happens here)
    app = create_app()
    app.before_request(update_activity)

    # Start monitor thread
    threading.Thread(target=monitor_activity, daemon=True).start()

    # Open browser logic
    def open_browser():
        webbrowser.open(f"http://{host}:{port}")

    threading.Thread(target=open_browser).start()

    print(f"Starting server on {host}:{port}")
    try:
        app.run(host=host, port=port, debug=False, threaded=True)
    finally:
        # Cleanup on exit (whether checking, error, or clean return)
        print("[Startup] Server stopping...")
        try:
            from app.web.routes import cleanup_resources

            cleanup_resources()
        except KeyboardInterrupt:
            # Allow forced exit during cleanup without error message
            pass
        except Exception as e:
            print(f"[Startup] Error during cleanup: {e}")
