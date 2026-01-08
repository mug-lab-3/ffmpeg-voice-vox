import urllib.request
import json
import time

URL = "http://localhost:3000"

def send_test_message(json_data):
    data = json.dumps(json_data).encode('utf-8')
    print(f"Sending: {json_data}")
    try:
        req = urllib.request.Request(URL, data=data, method='POST')
        req.add_header('Content-Type', 'application/json')
        
        with urllib.request.urlopen(req) as response:
            print(f"Status Code: {response.getcode()}")
            print(f"Response: {response.read().decode('utf-8')}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("Testing Voicevox Integration with Commands...")
    
    # 1. デフォルト (ずんだもん)
    send_test_message({"start": 1000, "end": 3000, "text": "こんにちは、ずんだもんです。"})
    time.sleep(1)

    # 2. キャラクター変更コマンド (めたん: ID=2)
    # カタカナ "メタン" も認識することを確認
    send_test_message({"start": 0, "end": 0, "text": "メタンに変えて"}) 
    time.sleep(1)

    # 3. 変更後の確認
    send_test_message({"start": 1000, "end": 3000, "text": "こんにちは、四国めたんです。カタカナでも大丈夫ですか？"})
    time.sleep(1)

    # 3.5 誤検知テスト (会話の中にコマンドが含まれる場合 -> 無視されるべき)
    # "もっと速く" はコマンドだが、これは会話文なので無視して読み上げるはず
    send_test_message({"start": 4000, "end": 5000, "text": "もっと速く走るためにはどうすればいいですか"})
    time.sleep(1)

    # 4. 速度変更コマンド (速く)
    # これは短いのでコマンドとして認識されるはず
    send_test_message({"start": 0, "end": 0, "text": "もっと速く"})
    time.sleep(1)

    # 5. 変更後の確認 (速くなっているはず)
    send_test_message({"start": 1000, "end": 3000, "text": "早口言葉言えますか？"})
    time.sleep(1)

    # 6. リセット
    send_test_message({"start": 0, "end": 0, "text": "リセットして"})
    time.sleep(1)

    # 7. 元通り (ずんだもん)
    send_test_message({"start": 1000, "end": 3000, "text": "元に戻りました。"})

    print("Done.")
