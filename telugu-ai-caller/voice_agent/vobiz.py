"""
Vobiz telephony support (also behind Sarvam's "Rent from Sarvam" numbers).

How a Vobiz call reaches the engine:
  1. Vobiz fetches our Answer URL (POST /api/voice/vobiz/answer) and runs the XML we return:
     <Stream bidirectional="true" ...>wss://<host>/api/voice/vobiz/stream?...</Stream><Hangup/>
  2. Vobiz opens the WebSocket and sends `start` (streamId, callId, mediaFormat) then `media`
     events with base64 audio. We send `playAudio` (raw Linear16, no WAV header) and
     `clearAudio` for barge-in, following Sarvam's "Build voice agent with Vobiz" guide.
  3. When our side closes the stream, Vobiz continues to <Hangup/>.

The message names match Plivo's streaming protocol, but Vobiz expects Linear16
output, so this serializer replaces Pipecat's PlivoFrameSerializer (which sends
μ-law and hangs up through Plivo's REST API).
"""

import base64
import json
from typing import Any, Dict, Optional
from xml.sax.saxutils import escape

from loguru import logger

from pipecat.audio.utils import create_stream_resampler, ulaw_to_pcm
from pipecat.frames.frames import (
    AudioRawFrame,
    Frame,
    InputAudioRawFrame,
    InputDTMFFrame,
    InterruptionFrame,
)
from pipecat.audio.dtmf.types import KeypadEntry
from pipecat.processors.frame_processor import FrameProcessorSetup
from pipecat.serializers.base_serializer import FrameSerializer

# 16 kHz Linear16 both ways: better speech recognition than 8 kHz μ-law
VOBIZ_SAMPLE_RATE = 16000
VOBIZ_STREAM_CONTENT_TYPE = f"audio/x-l16;rate={VOBIZ_SAMPLE_RATE}"


def build_answer_xml(stream_url: str, status_callback_url: Optional[str] = None) -> str:
    """XML returned to Vobiz's Answer URL: stream the call to our engine, then hang up."""
    callback = (
        f' statusCallbackUrl="{escape(status_callback_url)}" statusCallbackMethod="POST"'
        if status_callback_url else ""
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<Response>\n"
        f'  <Stream bidirectional="true" audioTrack="inbound" keepCallAlive="true" '
        f'contentType="{VOBIZ_STREAM_CONTENT_TYPE}"{callback}>{escape(stream_url)}</Stream>\n'
        "  <Hangup/>\n"
        "</Response>\n"
    )


def parse_start_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract call details from Vobiz's `start` event. streamId may be top-level or
    under `start`; the audio format is in start.mediaFormat.
    """
    start = message.get("start") or {}
    media_format = start.get("mediaFormat") or message.get("mediaFormat") or {}
    encoding = str(media_format.get("encoding") or "audio/x-l16").lower()
    try:
        sample_rate = int(media_format.get("sampleRate") or VOBIZ_SAMPLE_RATE)
    except (TypeError, ValueError):
        sample_rate = VOBIZ_SAMPLE_RATE
    return {
        "stream_id": message.get("streamId") or start.get("streamId") or "",
        "call_id": start.get("callId") or message.get("callId") or start.get("callUUID") or "",
        "from": start.get("from") or "",
        "to": start.get("to") or "",
        "encoding": "mulaw" if "mulaw" in encoding or "ulaw" in encoding else "l16",
        "sample_rate": sample_rate,
        "custom_parameters": start.get("extraHeaders") or start.get("customParameters") or {},
    }


class VobizFrameSerializer(FrameSerializer):
    """Converts between Pipecat frames and Vobiz's bidirectional stream messages."""

    def __init__(self, stream_id: str, inbound_encoding: str = "l16",
                 inbound_sample_rate: int = VOBIZ_SAMPLE_RATE,
                 outbound_sample_rate: int = VOBIZ_SAMPLE_RATE, **kwargs):
        super().__init__(**kwargs)
        self._stream_id = stream_id
        self._inbound_encoding = inbound_encoding
        self._inbound_rate = inbound_sample_rate
        self._outbound_rate = outbound_sample_rate
        self._sample_rate = 0  # pipeline input rate, set in setup()
        self._input_resampler = create_stream_resampler()
        self._output_resampler = create_stream_resampler()

    async def setup(self, setup: FrameProcessorSetup):
        self._sample_rate = setup.audio_in_sample_rate

    async def serialize(self, frame: Frame) -> str | bytes | None:
        if isinstance(frame, InterruptionFrame):
            return json.dumps({"event": "clearAudio", "streamId": self._stream_id})
        if isinstance(frame, AudioRawFrame):
            pcm = frame.audio
            if frame.sample_rate != self._outbound_rate:
                pcm = await self._output_resampler.resample(pcm, frame.sample_rate, self._outbound_rate)
            if not pcm:
                return None
            return json.dumps({
                "event": "playAudio",
                "streamId": self._stream_id,
                "media": {
                    "contentType": "audio/x-l16",
                    "sampleRate": self._outbound_rate,
                    "payload": base64.b64encode(pcm).decode("utf-8"),
                },
            })
        return None

    async def deserialize(self, data: str | bytes) -> Frame | None:
        try:
            message = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Vobiz: ignoring non-JSON message: {str(data)[:80]}")
            return None

        event = message.get("event")
        if event == "media":
            payload = (message.get("media") or {}).get("payload")
            if not payload:
                return None
            raw = base64.b64decode(payload)
            if self._inbound_encoding == "mulaw":
                pcm = await ulaw_to_pcm(raw, self._inbound_rate, self._sample_rate, self._input_resampler)
            elif self._inbound_rate != self._sample_rate:
                pcm = await self._input_resampler.resample(raw, self._inbound_rate, self._sample_rate)
            else:
                pcm = raw
            if not pcm:
                return None
            return InputAudioRawFrame(audio=pcm, num_channels=1, sample_rate=self._sample_rate)

        if event == "dtmf":
            digit = (message.get("dtmf") or {}).get("digit")
            try:
                return InputDTMFFrame(KeypadEntry(digit)) if digit else None
            except ValueError:
                return None

        # start / playedStream / clearedAudio / checkpoint acknowledgements need no frame
        return None
