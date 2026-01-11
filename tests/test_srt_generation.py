import os
import unittest
from unittest.mock import patch, MagicMock
from server import generate_and_save_voice, OUTPUT_DIR, format_srt_time


class TestSRTGeneration(unittest.TestCase):
    @patch("server.urllib.request.urlopen")
    def test_srt(self, mock_urlopen):
        # Mock responses
        # 1. audio_query response
        mock_res1 = MagicMock()
        mock_res1.read.return_value = b"{}"  # json.load reads from this, but wait, json.load takes a file-like object
        # server.py usage: json.load(res)
        # So mocks needs to be a file-like object or return a simple dict for json.load?
        # Actually server.py does `query_data = json.load(res)`.
        # Making mock_urlopen return a context manager that yields a file-like object.

        # Complex mocking for sequence of calls:
        # 1st call: audio_query -> returns JSON bytes
        # 2nd call: synthesis -> returns Audio bytes

        mock_response_query = MagicMock()
        mock_response_query.read.return_value = b'{"speedScale":1.0, "pitchScale":0.0, "intonationScale":1.0, "volumeScale":1.0}'
        # For json.load to work, we need something that behaves like a file with read() return bytes string?
        # json.load calls read().

        mock_response_synth = MagicMock()
        mock_response_synth.read.return_value = b"FAKE_AUDIO_DATA"

        # Configure the side_effect for urlopen
        # urlopen returns a context manager
        cm_query = MagicMock()
        cm_query.__enter__.return_value = mock_response_query

        cm_synth = MagicMock()
        cm_synth.__enter__.return_value = mock_response_synth

        mock_urlopen.side_effect = [cm_query, cm_synth]

        # Test Data
        text = "SRT_TEST"
        # Input: Milliseconds (e.g. start=1000ms, end=4500ms -> duration 3500ms = 3.5s)
        start_time = 1000
        end_time = 4500

        generate_and_save_voice(text, start_time, end_time)

        # Check files
        files = os.listdir(OUTPUT_DIR)
        srt_files = [f for f in files if f.endswith(".srt") and "SRT_TEST" in f]
        self.assertTrue(len(srt_files) > 0, "SRT file should be created")

        srt_path = os.path.join(OUTPUT_DIR, srt_files[0])
        with open(srt_path, "r", encoding="utf-8") as f:
            content = f.read()
            print(f"Generated SRT:\n{content}")

            # Duration should be 4500-1000 = 3500ms = 3.5s
            # 3.5s -> 00:00:03,500
            expected_time = "00:00:03,500"
            self.assertIn(expected_time, content)
            self.assertIn(text, content)


if __name__ == "__main__":
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    # Patching inside the test method doesn't work well with unittest main if not careful,
    # but unittest.main() runs the class.
    # We need to construct the json.load behavior correctly.
    # In python 3, json.load accepts bytes or str.

    # Actually, simpler: just mock json.load as well if needed, but patching urlopen is cleaner integration test.
    # However, json.load(res). res is the object returned by urlopen().
    # So res.read() is called? Or does json.load iterate?
    # Usually json.load(fp) calls fp.read().

    # Let's refine the mock setup in the class.
    pass

    # Manual run wrapper
    t = TestSRTGeneration()
    # We create a manual runner if we want or just unittest.main
    unittest.main()
