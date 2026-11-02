"""
Test Suite for Phase 5: Voice Activity Detection (VAD), Barge-In, and Turn-Taking Optimizations.
"""

import os
import sys
import json
import base64
import audioop
import unittest
from unittest.mock import patch, AsyncMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.audio_processor import VoiceActivityDetector, pcm_to_wav
from fastapi.testclient import TestClient
from main import app


class VoicePipelineEnhancementTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_vad_speech_and_silence_detection(self):
        """
        Verify VAD accurately distinguishes speech energy from background silence.
        """
        vad = VoiceActivityDetector(energy_threshold=400, silence_duration_ms=500, min_speech_duration_ms=200, sample_rate=8000)

        # 1. Feed pure silence (all zeroes)
        silence_frame = b"\x00\x00" * 160  # 20ms at 8kHz
        state = vad.process_frame(silence_frame)
        self.assertFalse(state["is_speech"])
        self.assertFalse(state["barge_in"])

        # 2. Feed high energy speech signal (RMS > 400)
        speech_frame = b"\x20\x10" * 160
        state = vad.process_frame(speech_frame)
        self.assertTrue(state["is_speech"])
        self.assertTrue(state["barge_in"])

    def test_vad_end_of_turn_detection(self):
        """
        Verify that after continuous speech, silence triggers end_of_turn within threshold.
        """
        vad = VoiceActivityDetector(energy_threshold=400, silence_duration_ms=400, min_speech_duration_ms=200, sample_rate=8000)

        # Feed 300ms of speech (15 frames of 20ms)
        speech_frame = b"\x30\x15" * 160
        for _ in range(15):
            vad.process_frame(speech_frame)

        self.assertTrue(vad.is_user_speaking)

        # Feed 350ms of silence (less than 400ms threshold)
        silence_frame = b"\x00\x00" * 160
        for _ in range(17):
            state = vad.process_frame(silence_frame)
            self.assertFalse(state["end_of_turn"])

        # Feed additional silence to cross 400ms threshold
        end_state = None
        for _ in range(6):
            end_state = vad.process_frame(silence_frame)
            if end_state["end_of_turn"]:
                break

        self.assertTrue(end_state["end_of_turn"])
        speech_bytes = vad.get_speech_bytes()
        self.assertTrue(len(speech_bytes) > 0)
        self.assertFalse(vad.is_user_speaking)

    def test_barge_in_clears_websocket_buffer(self):
        """
        Verify that an incoming user speech packet during AI speech emits a 'clear' event.
        """
        sample_wav = pcm_to_wav(b"\x00\x00" * 8000, sample_rate=16000)
        with patch("services.sarvam_service.sarvam_client.text_to_speech", new_callable=AsyncMock) as mock_tts:
            mock_tts.return_value = sample_wav

            with self.client.websocket_connect("/api/telephony/exotel/stream?lead_id=1") as ws:
                # 1. Connect and start
                ws.send_text(json.dumps({
                    "event": "connected",
                    "stream_id": "stream_bargein_01",
                    "call_id": "call_bargein_01",
                    "media_format": {"encoding": "audio/x-mulaw", "sample_rate": 8000}
                }))

                # 2. Receive initial greeting
                greeting_reply = json.loads(ws.receive_text())
                self.assertEqual(greeting_reply["event"], "media")

                # 3. Simulate high-energy user speech frame (Barge-in / interruption)
                high_energy_pcm = b"\x50\x20" * 160
                high_energy_mulaw = audioop.lin2ulaw(high_energy_pcm, 2)
                payload = base64.b64encode(high_energy_mulaw).decode("utf-8")
                ws.send_text(json.dumps({
                    "event": "media",
                    "stream_id": "stream_bargein_01",
                    "media": {"payload": payload}
                }))

                # 4. Should receive clear event from server
                clear_msg = json.loads(ws.receive_text())
                self.assertEqual(clear_msg["event"], "clear")
                self.assertEqual(clear_msg["stream_id"], "stream_bargein_01")

                # 5. Stop stream
                ws.send_text(json.dumps({
                    "event": "stop",
                    "stream_id": "stream_bargein_01"
                }))


if __name__ == "__main__":
    unittest.main()
