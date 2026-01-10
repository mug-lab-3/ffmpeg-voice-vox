import webbrowser
import threading
import time
import os
import platform
import subprocess
import socket
from app import create_app
from app.config import config

def kill_previous_instances():
    """
    Scans for other Python processes running 'voicevox_controller.py' and kills them.
    More reliable than PID file as it checks identifying command line info.
    """
    print("[Startup] Scanning for existing instances...")
    try:
        # PowerShell command to find PIDs of python processes running voicevox_controller.py
        ps_cmd = "Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*voicevox_controller.py*' } | Select-Object -ExpandProperty ProcessId"
        
        # Run PowerShell command
        result = subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, text=True)
        
        if result.returncode != 0:
             print(f"[Startup] Warning: Process scan failed: {result.stderr}")
             return

        pids = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.isdigit():
                pids.append(int(line))
        
        my_pid = os.getpid()
        killed_count = 0
        
        for pid in pids:
            if pid != my_pid and pid != 0: # PID 0 checks just in case
                print(f"[Startup] Found existing instance (PID: {pid}). Killing...")
                subprocess.run(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                killed_count += 1
                
        if killed_count == 0:
            print("[Startup] No other instances found.")
        else:
            print(f"[Startup] Killed {killed_count} existing instance(s).")

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
                s.bind(('0.0.0.0', port))
                return port
        except OSError:
            port += 1
    return start_port

# Activity Monitoring
last_activity_time = time.time()
SHUTDOWN_TIMEOUT = 300  # 5 minutes

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

if __name__ == '__main__':
    # 0. Single Instance Check
    kill_previous_instances()
    
    # 1. Determine Port (Auto-select available)
    host = config.get("server.host", "127.0.0.1")
    # Start checking from configured port or default 3000
    start_port = config.get("server.port") or 3000
    if isinstance(start_port, str) and start_port.isdigit():
        start_port = int(start_port)
    elif not isinstance(start_port, int):
        start_port = 3000
        
    port = find_free_port(start_port)
    
    # 2. Initialize App (Logging setup happens here)
    app = create_app()
    app.before_request(update_activity)
    
    # Start monitor thread
    threading.Thread(target=monitor_activity, daemon=True).start()
    
    # Open browser logic
    def open_browser():
        print("[Startup] Browser thread started", flush=True)
        time.sleep(2)
        url = f'http://{host}:{port}'
        print(f"[Startup] Opening browser at {url}", flush=True)
        webbrowser.open(url)

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
            # Allow forced exit during cleanup
            pass
        except Exception as e:
            print(f"[Startup] Error during cleanup: {e}")

