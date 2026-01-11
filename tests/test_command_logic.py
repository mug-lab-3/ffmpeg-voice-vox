from server import process_command, COMMANDS

def run_tests():
    test_cases = [
        ("ずんだもん", True, "Exact match"),
        ("ずんだもんにして", True, "Suffix 'にして'"),
        ("ずんだもんに変えて", True, "Suffix 'に変えて'"),
        ("ずんだもんに設定", True, "Suffix 'に設定'"),
        ("ずんだちゃん", True, "Suffix 'ちゃん'"),
        ("ねぇずんだもん", True, "Prefix 'ねぇ' (noise within threshold)"),
        ("ずんだもん！", True, "Suffix '！'"),
        ("ずんだもん、お願いします", True, "Suffix '、お願いします' (remainder 'します' <= 4)"),
        ("ずんだもん今日の天気は", False, "Long conversation text"),
        ("もっと速くして", True, "Command 'もっと速く' + suffix 'して'")
    ]

    print("Running command logic tests...")
    failures = 0
    for text, expected, desc in test_cases:
        # Reset printed output capture? We just care about return value
        result = process_command(text)
        status = "PASS" if result == expected else "FAIL"
        print(f"[{status}] '{text}': Expected {expected}, Got {result} ({desc})")
        if result != expected:
            failures += 1

    if failures == 0:
        print("\nAll tests passed!")
    else:
        print(f"\n{failures} tests failed.")

if __name__ == "__main__":
    run_tests()
