from server import format_srt_time

def test_ms_input():
    # Simulate 1.5 second duration from Millisecond input
    start_ms = 1000
    end_ms = 2500
    duration_raw = end_ms - start_ms # 1500

    formatted = format_srt_time(duration_raw)
    print(f"Input diff: {duration_raw}")
    print(f"Formatted: {formatted}")

    if "00:25:00" in formatted:
         print("[CONFIRMED] 1500 input interpreted as 1500 seconds (25 mins)")
    else:
         print("[UNCLEAR] Result seems ok? " + formatted)

if __name__ == "__main__":
    test_ms_input()
