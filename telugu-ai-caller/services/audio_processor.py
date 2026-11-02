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

