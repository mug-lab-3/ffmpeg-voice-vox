from flask import Flask, request, render_template, jsonify
import json
import urllib.request
import urllib.parse
import winsound
import os
import re
from datetime import datetime
import webbrowser
import threading
import wave
import time
import platform
import subprocess
import signal

app = Flask(__name__)

HOST = '127.0.0.1'
PORT = 3000

# ログ保存用
received_logs = []

# ... (Existing code)

@app.route('/', methods=['POST'])
def whisper_receiver():
    print("--- データの受信を開始したよ！ ---")
    
    buffer = ""
    # 届いたデータを少しずつ読み込むよ
    for chunk in request.stream:
        if chunk:
            # 届いた分をバッファに追加
            buffer += chunk.decode('utf-8', errors='ignore')
            
            if '}' in buffer:
                try:
                    brace_index = buffer.find('}')
                    while brace_index != -1:
                        json_str = buffer[:brace_index+1]
                        buffer = buffer[brace_index+1:] # 残りをバッファに戻す
                        
                        try:
                            data = json.loads(json_str)
                            print(f"Received JSON: {json.dumps(data, ensure_ascii=False)}")
                            
                            if "text" in data and "start" in data and "end" in data:
                                text = data["text"]
                                start = data["start"]
                                end = data["end"]
                                
                                print(f"処理中: [{start}ms - {end}ms] {text}")
                                
                                generated_file = None
                                actual_duration = 0.0
                                
                                if is_synthesis_enabled:
                                    generated_file, actual_duration = generate_and_save_voice(text, start, end)
                                    
                                    # 構造化ログを作成
                                    log_entry = {
                                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                                        "text": text,
                                        "duration": f"{actual_duration:.2f}s", # Use actual WAV duration
                                        "config": current_config.copy(), 
                                        "filename": generated_file if generated_file else "Error"
                                    }
                                    
                                    # ログ保存
                                    if len(received_logs) > 50:
                                        received_logs.pop(0)
                                    received_logs.append(log_entry)
                                else:
                                    print("  -> Synthesis Skipped (Stopped) - Discarding data")
                            else:
                                print("Skipping: 必要なデータ(text, start, end)が不足しています")
                                
                        except json.JSONDecodeError:
                             print("JSON Decode Error (chunk)")

                        brace_index = buffer.find('}')
                        
                except Exception as e:
                    print(f"Stream Error: {e}")
                    continue
                    
    return "OK", 200



# Voicevoxの設定
VOICEVOX_HOST = "127.0.0.1"
VOICEVOX_PORT = 50021

# Voicevoxの設定 (デフォルト値)
DEFAULT_CONFIG = {
    "speaker": 1,      # ずんだもん (ノーマル)
    "speedScale": 1.0,
    "pitchScale": 0.0,
    "intonationScale": 1.0,
    "volumeScale": 1.0
}

# ID -> 名前マッピング
SPEAKER_NAMES = {
    1: "ずんだもん",
    2: "四国めたん",
    8: "春日部つむぎ",
    9: "波音リツ"
}

# 現在の設定
current_config = DEFAULT_CONFIG.copy()

# 合成機能の有効/無効状態 (デフォルトON)
is_synthesis_enabled = True

# ログ保存用
received_logs = []

OUTPUT_DIR = "output"

# 出力ディレクトリが存在しない場合は作成
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# 再生状態管理
playback_status = {
    "is_playing": False,
    "filename": None,
    "start_time": 0,
    "duration": 0
}
playback_lock = threading.Lock()

def get_wav_duration(filepath):
    """WAVファイルの正確な再生時間を取得する"""
    try:
        with wave.open(filepath, 'rb') as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return frames / float(rate)
    except Exception as e:
        print(f"Error getting wav duration: {e}")
        return 0.0

def format_srt_time(seconds):
    """秒数を SRT形式 (HH:MM:SS,mmm) に変換する"""
    millis = int((seconds - int(seconds)) * 1000)
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"

# --- Web UI Routes ---
@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    global current_config
    if request.method == 'POST':
        new_config = request.json
        print(f"[API] Config Update Request: {new_config}")
        
        # Validate and Update
        for key in current_config:
            if key in new_config:
                # Type safe update (simple version)
                if isinstance(current_config[key], (int, float)) and isinstance(new_config[key], (int, float)):
                    current_config[key] = new_config[key]
        
        print(f"  -> New Config: {current_config}")
        return jsonify({"status": "ok", "config": current_config})
    else:
        return jsonify(current_config)

@app.route('/api/speakers', methods=['GET'])
def get_speakers():
    return jsonify(SPEAKER_NAMES)

@app.route('/api/logs', methods=['GET'])
def get_logs():
    return jsonify(received_logs)

@app.route('/api/control/state', methods=['GET', 'POST'])
def handle_control_state():
    global is_synthesis_enabled
    if request.method == 'POST':
        data = request.json
        if 'enabled' in data:
            is_synthesis_enabled = bool(data['enabled'])
            print(f"[API] Synthesis State Updated: {is_synthesis_enabled}")
        return jsonify({"status": "ok", "enabled": is_synthesis_enabled})
        return jsonify({"status": "ok", "enabled": is_synthesis_enabled})
    else:
        # Calculate remaining playback time if any
        remaining = 0
        current_status = {}
        with playback_lock:
             current_status = playback_status.copy()
        
        if current_status["is_playing"]:
             elapsed = time.time() - current_status["start_time"]
             remaining = max(0, current_status["duration"] - elapsed)
             # Auto-reset if time passed (failsafe)
             if remaining == 0:
                 with playback_lock:
                     playback_status["is_playing"] = False
                     playback_status["filename"] = None
        
        return jsonify({
            "enabled": is_synthesis_enabled,
            "playback": {
                "is_playing": current_status["is_playing"] and remaining > 0,
                "filename": current_status["filename"],
                "remaining": remaining
            }
        })

@app.route('/api/control/play', methods=['POST'])
def handle_control_play():
    try:
        data = request.json
        filename = data.get('filename')
        
        if not filename:
             return jsonify({"status": "error", "message": "No filename provided"}), 400
             
        wav_path = os.path.join(OUTPUT_DIR, filename)
        
        if not os.path.exists(wav_path):
             return jsonify({"status": "error", "message": "File not found"}), 404
             
        # Get accurate duration
        duration = get_wav_duration(wav_path)
        start_time = time.time()
        
        with playback_lock:
            playback_status["is_playing"] = True
            playback_status["filename"] = filename
            playback_status["start_time"] = start_time
            playback_status["duration"] = duration

        def play_worker(path):
            try:
                print(f"[API] PlayingAsync: {path}")
                winsound.PlaySound(path, winsound.SND_FILENAME)
            except Exception as e:
                print(f"Play Worker Error: {e}")
            finally:
                # Reset status when done
                with playback_lock:
                    if playback_status["filename"] == filename: # Ensure we don't clear if another file started
                        playback_status["is_playing"] = False
        
        # Start playback in thread
        threading.Thread(target=play_worker, args=(wav_path,), daemon=True).start()
        
        return jsonify({
            "status": "ok", 
            "duration": duration,
            "start_time": start_time
        })

    except Exception as e:
        print(f"[API] Play Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/control/delete', methods=['POST'])
def handle_control_delete():
    global received_logs
    try:
        data = request.json
        filename = data.get('filename')
        
        if not filename:
             return jsonify({"status": "error", "message": "No filename provided"}), 400
        
        # Remove from logs first
        received_logs = [log for log in received_logs if log.get('filename') != filename]
        
        # Paths
        wav_path = os.path.join(OUTPUT_DIR, filename)
        srt_path = wav_path.replace(".wav", ".srt")
        
        deleted_files = []
        
        # Delete WAV
        if os.path.exists(wav_path):
            try:
                os.remove(wav_path)
                deleted_files.append(filename)
            except Exception as e:
                print(f"Error deleting WAV: {e}")
        
        # Delete SRT
        if os.path.exists(srt_path):
            try:
                os.remove(srt_path)
                deleted_files.append(os.path.basename(srt_path))
            except Exception as e:
                print(f"Error deleting SRT: {e}")
                
        print(f"[API] Deleted: {deleted_files}")
        return jsonify({"status": "ok", "deleted": deleted_files})
        
    except Exception as e:
        print(f"[API] Delete Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

def generate_and_save_voice(text, start_time, end_time):
    try:
        # 1. 音声合成用のクエリを作成 (Audio Query)
        # 現在の設定を使用
        speaker_id = current_config["speaker"]
        query_url = f"http://{VOICEVOX_HOST}:{VOICEVOX_PORT}/audio_query?text={urllib.parse.quote(text)}&speaker={speaker_id}"
        req = urllib.request.Request(query_url, method='POST')
        with urllib.request.urlopen(req) as res:
            query_data = json.load(res)

        # パラメータの適用
        query_data['speedScale'] = current_config['speedScale']
        query_data['pitchScale'] = current_config['pitchScale']
        query_data['intonationScale'] = current_config['intonationScale']
        query_data['volumeScale'] = current_config['volumeScale']

        # 2. 音声合成を実行 (Synthesis)
        synth_url = f"http://{VOICEVOX_HOST}:{VOICEVOX_PORT}/synthesis?speaker={speaker_id}"
        req = urllib.request.Request(synth_url, data=json.dumps(query_data).encode('utf-8'), method='POST')
        req.add_header('Content-Type', 'application/json')
        
        with urllib.request.urlopen(req) as res:
            audio_data = res.read()

        # 3. 音声をファイルに保存
        # フォーマット: {start時間}_{話者名}_{内容先頭8文字}.wav
        speaker_name = SPEAKER_NAMES.get(speaker_id, f"ID{speaker_id}")
        
        # ファイル名に使用できない文字を除去・置換
        # Windowsの禁止文字: \ / : * ? " < > |
        safe_text = re.sub(r'[\\/:*?"<>|]+', '', text)
        safe_text = safe_text.replace('\n', '').replace('\r', '') # 改行も削除
        
        prefix_text = safe_text[:8]
        
        filename_base = f"{int(start_time):06d}_{speaker_name}_{prefix_text}"
        wav_filename = f"{filename_base}.wav"
        srt_filename = f"{filename_base}.srt"
        
        wav_path = os.path.join(OUTPUT_DIR, wav_filename)
        srt_path = os.path.join(OUTPUT_DIR, srt_filename)
        
        with open(wav_path, "wb") as f:
            f.write(audio_data)
            
        # 4. SRTファイルの生成
        # ユーザー指定: JSONのEND-STARTをDurationとする
        # 入力がミリ秒(ms)であるため、秒に変換する
        raw_duration = end_time - start_time
        duration = raw_duration / 1000.0
        
        # もし負の値になったり極端におかしい場合は最低値を設定するなどのガードを入れるか？
        if duration < 0:
            duration = 0

        # 正確なWAVの長さを取得して上書き
        actual_duration = get_wav_duration(wav_path)
        if actual_duration > 0:
            duration = actual_duration

        srt_content = f"1\n00:00:00,000 --> {format_srt_time(duration)}\n{text}\n"
        
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)
        
        print(f"  -> Saved: {wav_path}")
        print(f"  -> Saved: {srt_path}")
        print(f"     [Info] Start: {start_time}ms / Text: {text}")
        print(f"     [Config] Speaker: {speaker_id} / Speed: {current_config['speedScale']:.2f}")
        print(f"     [Stats] JSON Duration: {(raw_duration/1000.0):.2f}s / WAV Duration: {duration:.2f}s")

        return wav_filename, duration


    except Exception as e:
        print(f"Voicevox Error: {e}")




# --- Auto-Shutdown & Logic ---

# Activity Monitoring
last_activity_time = time.time()
SHUTDOWN_TIMEOUT = 300  # 5 minutes in seconds

@app.before_request
def update_activity():
    global last_activity_time
    last_activity_time = time.time()

def monitor_activity():
    """Monitor activity and shut down if inactive for too long."""
    global last_activity_time
    print("[Monitor] Activity monitor started.")
    while True:
        time.sleep(10)
        elapsed = time.time() - last_activity_time
        if elapsed > SHUTDOWN_TIMEOUT:
            print(f"[Monitor] No activity for {elapsed:.0f}s. Shutting down...")
            os._exit(0)

@app.route('/api/heartbeat', methods=['GET'])
def handle_heartbeat():
    return jsonify({"status": "alive"})

def kill_existing_process(port):
    """
    Kills any process listening on the specified port.
    Cross-platform implementation.
    """
    print(f"[Startup] Checking for existing process on port {port}...")
    system = platform.system()
    
    try:
        if system == "Windows":
            # Find PID using netstat
            cmd_find = f"netstat -ano | findstr :{port}"
            # Note: This is a simple check, parsing might be needed for robustness but usually sufficient for dev
            result = subprocess.check_output(cmd_find, shell=True).decode()
            
            if result:
                lines = result.strip().split('\n')
                for line in lines:
                    parts = line.strip().split()
                    if len(parts) > 4:
                        pid = parts[-1]
                        if pid != "0": # Avoid System Idle Process
                            print(f"[Startup] Killing PID {pid} on port {port}...")
                            subprocess.run(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            
        else: # Linux / MacOS
            # Find PID using lsof
            cmd_find = f"lsof -t -i:{port}"
            try:
                pid = subprocess.check_output(cmd_find, shell=True).decode().strip()
                if pid:
                    print(f"[Startup] Killing PID {pid} on port {port}...")
                    subprocess.run(f"kill -9 {pid}", shell=True)
            except subprocess.CalledProcessError:
                pass # No process found
                
    except Exception as e:
        # Ignore errors if no process found or permission issues (usually fine in user dev env)
        pass

if __name__ == '__main__':
    # Define HOST and PORT for consistency and easier modification
    HOST = '127.0.0.1'
    PORT = 3000

    # Kill any existing process on the specified port
    kill_existing_process(PORT)
    
    # Start monitor thread
    threading.Thread(target=monitor_activity, daemon=True).start()
    
    # Open browser logic (delayed)
    def open_browser():
        time.sleep(1)
        webbrowser.open(f'http://{HOST}:{PORT}')

    threading.Thread(target=open_browser).start()
    app.run(host=HOST, port=PORT, debug=False)