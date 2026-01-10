import unittest
import os
import shutil
import tempfile
from datetime import datetime
from unittest.mock import MagicMock
from app.core.audio import AudioManager
from app.core.processor import StreamProcessor
from app.core.voicevox import VoiceVoxClient

class TestHistoryLoading(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        
        # Mock Config to return test_dir
        self.original_get_output_dir = AudioManager.get_output_dir
        AudioManager.get_output_dir = MagicMock(return_value=self.test_dir)
        
        self.audio_manager = AudioManager()
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)
        AudioManager.get_output_dir = self.original_get_output_dir

    def create_dummy_file(self, filename, content="test content"):
        path = os.path.join(self.test_dir, filename)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return path

    def test_scan_output_dir(self):
        # Create valid files
        # 123456_Speaker1_Hello.wav
        self.create_dummy_file("100000_Metan_Hello.wav", "RIFF....")
        self.create_dummy_file("100000_Metan_Hello.srt", "1\n00:00:00,000 --> 00:00:01,000\nHello World")
        
        # Create older file
        older_path = self.create_dummy_file("090000_Zundamon_Hi.wav", "RIFF....")
        os.utime(older_path, (10000, 10000)) # Set old time
        
        # Create invalid file
        self.create_dummy_file("invalid_file.wav", "RIFF....")
        
        files = self.audio_manager.scan_output_dir()
        
        self.assertEqual(len(files), 2)
        
        # First one should be the newer one (Metan)
        self.assertEqual(files[0]['speaker_name'], "Metan")
        self.assertEqual(files[0]['text'], "Hello World") # From SRT
        
        # Second one
        self.assertEqual(files[1]['speaker_name'], "Zundamon")
        self.assertEqual(files[1]['text'], "Hi") # From filename (fallback)

    def test_processor_loading(self):
        # Setup mocks
        mock_vv = MagicMock(spec=VoiceVoxClient)
        mock_vv.get_speakers.return_value = {1: "Metan", 3: "Zundamon"}
        
        # Create files
        self.create_dummy_file("100000_Metan_Hello.wav", "RIFF....")
        self.create_dummy_file("100000_Metan_Hello.srt", "1\n00:00:00,000 --> 00:00:01,000\nHello World")
        
        processor = StreamProcessor(mock_vv, self.audio_manager)
        
        logs = processor.get_logs()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]['text'], "Hello World")
        self.assertEqual(logs[0]['config']['speaker_id'], 1) # Should map "Metan" -> 1

if __name__ == '__main__':
    unittest.main()
