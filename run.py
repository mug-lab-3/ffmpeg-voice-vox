import webbrowser
import threading
import time
import os
import platform
import subprocess
from app import create_app
from app.config import config

app = create_app()

def kill_existing_process(port):
    """
    Kills any process listening on the specified port.
    Cross-platform implementation.
    """
    print(f"[Startup] Checking for existing process on port {port}...")
    system = platform.system()
    
    try:
        if system == "Windows":
            cmd_find = f"netstat -ano | findstr :{port}"
            try:
                result = subprocess.check_output(cmd_find, shell=True).decode()
                if result:
                    lines = result.strip().split('\n')
                    for line in lines:
                        parts = line.strip().split()
                        if len(parts) > 4:
                            pid = parts[-1]
                            if pid != "0":
                                print(f"[Startup] Killing PID {pid} on port {port}...")
                                subprocess.run(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except subprocess.CalledProcessError:
                pass 
        else: 
            cmd_find = f"lsof -t -i:{port}"
            try:
                pid = subprocess.check_output(cmd_find, shell=True).decode().strip()
                if pid:
                    print(f"[Startup] Killing PID {pid} on port {port}...")
                    subprocess.run(f"kill -9 {pid}", shell=True)
            except subprocess.CalledProcessError:
                pass 
    except Exception as e:
        print(f"[Startup] Warning during port cleanup: {e}")

# Activity Monitoring
last_activity_time = time.time()
SHUTDOWN_TIMEOUT = 300  # 5 minutes

@app.before_request
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
            os._exit(0)

if __name__ == '__main__':
    host = config.get("server.host", "127.0.0.1")
    port = config.get("server.port", 3000)
    
    kill_existing_process(port)
    
    # Start monitor thread
    threading.Thread(target=monitor_activity, daemon=True).start()
    
    # Open browser logic
    def open_browser():
        time.sleep(1)
        webbrowser.open(f'http://{host}:{port}')

    threading.Thread(target=open_browser).start()
    
    print(f"Starting server on {host}:{port}")
    app.run(host=host, port=port, debug=False)
