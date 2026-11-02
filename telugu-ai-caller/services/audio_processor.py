"""
Audio Processor utility for converting audio formats.
Handles Linear PCM, WAV header packaging, and Twilio mu-law encoding/decoding.
"""

import io
import wave
import audioop
from typing import Tuple


def pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 16000, channels: int = 1, sample_width: int = 2) -> bytes:
    """
    Wrap raw 16-bit PCM bytes with standard WAV headers.
    """
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_bytes)
    return buffer.getvalue()


def mulaw_to_wav(mulaw_bytes: bytes, in_rate: int = 8000, out_rate: int = 16000) -> bytes:
    """
    Convert Twilio mu-law (G.711 8kHz) audio bytes to 16kHz 16-bit PCM WAV.
    """
    # Convert mu-law to linear 16-bit PCM (sample width = 2)
    linear_pcm = audioop.ulaw2lin(mulaw_bytes, 2)

    # Resample 8000 Hz to 16000 Hz if needed
    if in_rate != out_rate:
        linear_pcm, _ = audioop.ratecv(linear_pcm, 2, 1, in_rate, out_rate, None)

    return pcm_to_wav(linear_pcm, sample_rate=out_rate, channels=1, sample_width=2)


def wav_to_mulaw(wav_bytes: bytes, target_rate: int = 8000) -> bytes:
    """
    Convert WAV audio (e.g. from Sarvam TTS) to Twilio 8kHz mu-law format.
    """
    buffer = io.BytesIO(wav_bytes)
    with wave.open(buffer, 'rb') as wf:
        num_channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        frame_rate = wf.getframerate()
        raw_frames = wf.readframes(wf.getnframes())

    # If stereo, convert to mono
    if num_channels == 2:
        raw_frames = audioop.tomono(raw_frames, sample_width, 1, 1)

    # Resample to target rate (8000 Hz)
    if frame_rate != target_rate:
        raw_frames, _ = audioop.ratecv(raw_frames, sample_width, 1, frame_rate, target_rate, None)

    # Convert linear PCM to mu-law
    mulaw_data = audioop.lin2ulaw(raw_frames, sample_width)
    return mulaw_data



def exotel_audio_to_wav(audio_chunk: bytes, encoding: str = "audio/x-mulaw", sample_rate: int = 8000) -> bytes:
    """
    Transcode Exotel AgentStream audio (mu-law or Linear PCM L16) into standard 16kHz WAV.
    """
    if "mulaw" in encoding.lower() or "ulaw" in encoding.lower():
        return mulaw_to_wav(audio_chunk, in_rate=sample_rate, out_rate=16000)
    else:
        # Linear PCM 16-bit
        if sample_rate != 16000:
            resampled, _ = audioop.ratecv(audio_chunk, 2, 1, sample_rate, 16000, None)
            return pcm_to_wav(resampled, sample_rate=16000, channels=1, sample_width=2)
        return pcm_to_wav(audio_chunk, sample_rate=16000, channels=1, sample_width=2)


def wav_to_exotel_audio(wav_bytes: bytes, encoding: str = "audio/x-mulaw", target_rate: int = 8000) -> bytes:
    """
    Transcode synthesized WAV response from Sarvam TTS into Exotel's requested format (mu-law or PCM L16).
    """
    if "mulaw" in encoding.lower() or "ulaw" in encoding.lower():
        return wav_to_mulaw(wav_bytes, target_rate=target_rate)
    else:
        # Linear PCM
        buffer = io.BytesIO(wav_bytes)
        with wave.open(buffer, 'rb') as wf:
            num_channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            frame_rate = wf.getframerate()
            raw_frames = wf.readframes(wf.getnframes())

        if num_channels == 2:
            raw_frames = audioop.tomono(raw_frames, sample_width, 1, 1)

        if frame_rate != target_rate:
            raw_frames, _ = audioop.ratecv(raw_frames, sample_width, 1, frame_rate, target_rate, None)

        return raw_frames


class VoiceActivityDetector:
    """
    Energy-based Voice Activity Detector (VAD) with Barge-In & End-of-Turn Detection.
    Optimizes turn-taking latency and prevents speaking over the caller.
    """
    def __init__(
        self,
        energy_threshold: int = 500,
        silence_duration_ms: int = 800,
        min_speech_duration_ms: int = 400,
        sample_rate: int = 8000,
        sample_width: int = 2
    ):
        self.energy_threshold = energy_threshold
        self.silence_duration_ms = silence_duration_ms
        self.min_speech_duration_ms = min_speech_duration_ms
        self.sample_rate = sample_rate
        self.sample_width = sample_width

        self.bytes_per_ms = (sample_rate * sample_width) // 1000
        self.silence_bytes_threshold = self.silence_duration_ms * self.bytes_per_ms
        self.min_speech_bytes = self.min_speech_duration_ms * self.bytes_per_ms

        self.is_user_speaking = False
        self.speech_buffer = bytearray()
        self.consecutive_silence_bytes = 0

    def process_frame(self, pcm_frame: bytes) -> dict:
        """
        Process a PCM frame and return real-time speech/silence state.
        """
        if len(pcm_frame) < 2:
            return {
                "is_speech": False,
                "end_of_turn": False,
                "barge_in": False,
                "accumulated_bytes": len(self.speech_buffer),
                "rms": 0
            }

        rms = audioop.rms(pcm_frame, self.sample_width)
        is_speech = rms >= self.energy_threshold

        barge_in = False
        end_of_turn = False

        if is_speech:
            if not self.is_user_speaking:
                self.is_user_speaking = True
                barge_in = True
            self.speech_buffer.extend(pcm_frame)
            self.consecutive_silence_bytes = 0
        else:
            if self.is_user_speaking:
                self.speech_buffer.extend(pcm_frame)
                self.consecutive_silence_bytes += len(pcm_frame)
                if self.consecutive_silence_bytes >= self.silence_bytes_threshold:
                    if len(self.speech_buffer) >= self.min_speech_bytes:
                        end_of_turn = True
                    self.is_user_speaking = False
                    self.consecutive_silence_bytes = 0

        return {
            "is_speech": is_speech,
            "end_of_turn": end_of_turn,
            "barge_in": barge_in,
            "accumulated_bytes": len(self.speech_buffer),
            "rms": rms
        }

    def get_speech_bytes(self) -> bytes:
        data = bytes(self.speech_buffer)
        self.speech_buffer.clear()
        self.is_user_speaking = False
        self.consecutive_silence_bytes = 0
        return data

    def reset(self):
        self.speech_buffer.clear()
        self.is_user_speaking = False
        self.consecutive_silence_bytes = 0
