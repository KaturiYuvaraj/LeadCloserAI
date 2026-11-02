"""
Test Suite for Phase 4: Exotel Telephony & AgentStream Integration.
"""

import os
import sys
import json
import base64
import unittest
from unittest.mock import patch, AsyncMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from main import app
from database import (
    create_lead,
    get_lead_by_id,
    save_call_record,
    get_call_by_id,
    get_connection
)
from services.audio_processor import exotel_audio_to_wav, wav_to_exotel_audio, pcm_to_wav


class ExotelTelephonyTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_audio_transcoding_exotel(self):
        """
        Verify bidirectional audio transcoding between 16kHz WAV and Exotel formats.
        """
        # Create 1 second of silence PCM 16-bit 8000Hz (16000 bytes)
        raw_pcm_8k = b"\x00\x00" * 8000
        wav_16k = pcm_to_wav(b"\x00\x00" * 16000, sample_rate=16000)

        # 1. Transcode WAV to Exotel mu-law 8kHz
        mulaw_out = wav_to_exotel_audio(wav_16k, encoding="audio/x-mulaw", target_rate=8000)
        self.assertEqual(len(mulaw_out), 8000)

        # 2. Transcode Exotel mu-law back to 16kHz WAV
        recovered_wav = exotel_audio_to_wav(mulaw_out, encoding="audio/x-mulaw", sample_rate=8000)
        self.assertTrue(recovered_wav.startswith(b"RIFF"))

        # 3. Transcode WAV to Exotel PCM L16 16kHz
        pcm_out = wav_to_exotel_audio(wav_16k, encoding="audio/x-l16", target_rate=16000)
        self.assertTrue(len(pcm_out) > 0)

    def test_exotel_status_callback_success(self):
        """
        Verify status callback captures call duration and recording URL.
        """
        # Create a test call record
        call_id = save_call_record({
            "call_sid": "exotel_call_test_101",
            "status": "in-progress",
            "duration_seconds": 0
        })

        resp = self.client.post("/api/telephony/exotel/status", data={
            "CallSid": "exotel_call_test_101",
            "Status": "completed",
            "Duration": "54",
            "RecordingUrl": "https://s3.exotel.com/recordings/test101.mp3"
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "received")
        self.assertEqual(data["disposition"], "completed")

        # Verify DB updated
        call = get_call_by_id(call_id)
        self.assertEqual(call["status"], "completed")
        self.assertEqual(call["duration_seconds"], 54)
        self.assertEqual(call["recording_url"], "https://s3.exotel.com/recordings/test101.mp3")

    def test_exotel_status_callback_busy_disposition(self):
        """
        Verify busy or no-answer disposition logs into lead notes.
        """
        lead_id = create_lead({
            "name": "Suresh Babu",
            "phone": "+91 9848077889",
            "company": "Babu Logistics",
            "notes": "Initial contact."
        })

        resp = self.client.post("/api/telephony/exotel/status", data={
            "CallSid": "exotel_call_busy_202",
            "Status": "busy",
            "CustomField": str(lead_id)
        })
        self.assertEqual(resp.status_code, 200)

        updated_lead = get_lead_by_id(lead_id)
        self.assertIn("PSTN Call attempt: BUSY", updated_lead["notes"])

    def test_exotel_recording_callback(self):
        """
        Verify recording webhook persists recording URL by CallSid.
        """
        call_id = save_call_record({
            "call_sid": "exotel_rec_303",
            "status": "completed"
        })

        resp = self.client.post("/api/telephony/exotel/recording", data={
            "CallSid": "exotel_rec_303",
            "RecordingUrl": "https://s3.exotel.com/recordings/rec_303.wav"
        })
        self.assertEqual(resp.status_code, 200)

        call = get_call_by_id(call_id)
        self.assertEqual(call["recording_url"], "https://s3.exotel.com/recordings/rec_303.wav")

    def test_exotel_agentstream_lifecycle(self):
        """
        Test Exotel AgentStream WebSocket protocol handshake, initial greeting, and stop event.
        """
        # Mock Sarvam TTS so this test doesn't require an external network call
        sample_wav = pcm_to_wav(b"\x00\x00" * 8000, sample_rate=16000)
        with patch("services.sarvam_service.sarvam_client.text_to_speech", new_callable=AsyncMock) as mock_tts:
            mock_tts.return_value = sample_wav

            with self.client.websocket_connect("/api/telephony/exotel/stream?lead_id=1") as ws:
                # 1. Send Exotel start / connected event
                ws.send_text(json.dumps({
                    "event": "connected",
                    "stream_id": "stream_exo_999",
                    "call_id": "call_exo_999",
                    "media_format": {
                        "encoding": "audio/x-mulaw",
                        "sample_rate": 8000
                    }
                }))

                # 2. Receive AI greeting media packet from server
                reply_text = ws.receive_text()
                reply_msg = json.loads(reply_text)
                self.assertEqual(reply_msg["event"], "media")
                self.assertEqual(reply_msg["stream_id"], "stream_exo_999")
                self.assertIn("payload", reply_msg["media"])

                # 3. Send stop event
                ws.send_text(json.dumps({
                    "event": "stop",
                    "stream_id": "stream_exo_999"
                }))


if __name__ == "__main__":
    unittest.main()
