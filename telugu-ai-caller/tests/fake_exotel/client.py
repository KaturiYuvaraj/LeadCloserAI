"""
Fake telephony caller: tests the phone path without a provider account.

--provider exotel (default): behaves like Exotel's Voicebot applet. Sends the
  `connected` + `start` handshake, then 16-bit PCM 8 kHz `media` chunks, and
  reads `media` / `clear` back.
--provider vobiz: behaves like Vobiz (also numbers rented from Sarvam). Fetches
  our Answer URL like an incoming call, reads the <Stream> URL from the XML, sends
  `start` (streamId, mediaFormat) then 16 kHz Linear16 `media` chunks, and reads
  `playAudio` / `clearAudio` back.

Caller audio is streamed in real time in 100 ms chunks from any WAV file. The
client records the bot's audio, counts barge-in clears and measures the reply
gap: from the end of each caller utterance to the bot's first audio.

Usage (app running on port 8000):
  python tests/fake_exotel/client.py --wav tests/fake_exotel/samples/three_questions.wav
  python tests/fake_exotel/client.py --wav ... --lead-id 1 --out bot_reply.wav
  python tests/fake_exotel/client.py --wav ... --provider vobiz
  python tests/fake_exotel/client.py --wav ... --parallel 5      # load test
"""

import argparse
import asyncio
import audioop
import base64
import json
import re
import statistics
import time
import uuid
import wave
from dataclasses import dataclass, field
from typing import List, Optional

import httpx
import websockets

EXOTEL_RATE = 8000
VOBIZ_RATE = 16000
CHUNK_MS = 100
SPEECH_RMS = 300          # chunk energy above this counts as caller speech
UTTERANCE_END_MS = 500    # this much silence after speech ends an utterance
CALLEE = "+918040000000"


def load_pcm(path: str, target_rate: int = EXOTEL_RATE) -> bytes:
    """Read a WAV file and convert it to 16-bit mono PCM at target_rate."""
    with wave.open(path, "rb") as w:
        frames = w.readframes(w.getnframes())
        width, channels, rate = w.getsampwidth(), w.getnchannels(), w.getframerate()
    if channels == 2:
        frames = audioop.tomono(frames, width, 0.5, 0.5)
    if width != 2:
        frames = audioop.lin2lin(frames, width, 2)
    if rate != target_rate:
        frames, _ = audioop.ratecv(frames, 2, 1, rate, target_rate, None)
    return frames


def load_pcm8k(path: str) -> bytes:
    return load_pcm(path, EXOTEL_RATE)


def vobiz_stream_url(answer_url: str, lead_id: Optional[int], caller: str, call_id: str) -> str:
    """Fetch our Answer URL like Vobiz does and return the <Stream> WebSocket URL."""
    query = f"?lead_id={lead_id}" if lead_id else ""
    resp = httpx.post(answer_url + query, data={"From": caller, "To": CALLEE, "CallUUID": call_id}, timeout=10)
    resp.raise_for_status()
    match = re.search(r"<Stream[^>]*>([^<]+)</Stream>", resp.text)
    if not match:
        raise RuntimeError(f"No <Stream> in Answer URL response: {resp.text[:200]}")
    return match.group(1).replace("&amp;", "&")


@dataclass
class CallResult:
    name: str
    connected: bool = False
    reply_gaps: List[float] = field(default_factory=list)
    bot_audio_bytes: int = 0
    clear_events: int = 0
    error: Optional[str] = None
    bot_audio: bytearray = field(default_factory=bytearray)


def handshake_messages(provider: str, stream_id: str, call_id: str, caller: str,
                       lead_id: Optional[int]) -> List[dict]:
    if provider == "vobiz":
        return [{
            "event": "start",
            "sequenceNumber": 0,
            "streamId": stream_id,
            "start": {
                "streamId": stream_id,
                "callId": call_id,
                "tracks": ["inbound"],
                "mediaFormat": {"encoding": "audio/x-l16", "sampleRate": VOBIZ_RATE},
            },
        }]
    return [
        {"event": "connected"},
        {
            "event": "start",
            "sequence_number": 1,
            "stream_sid": stream_id,
            "start": {
                "stream_sid": stream_id,
                "call_sid": call_id,
                "account_sid": "fake_account",
                "from": caller,
                "to": CALLEE,
                "custom_parameters": {"lead_id": str(lead_id)} if lead_id else {},
                "media_format": {"encoding": "base64", "sample_rate": str(EXOTEL_RATE), "bit_rate": "128kbps"},
            },
        },
    ]


def media_message(provider: str, stream_id: str, seq: int, elapsed_ms: int, payload: str) -> dict:
    if provider == "vobiz":
        return {"event": "media", "sequenceNumber": seq, "streamId": stream_id,
                "media": {"track": "inbound", "timestamp": str(elapsed_ms), "chunk": seq, "payload": payload}}
    return {"event": "media", "sequence_number": seq, "stream_sid": stream_id,
            "media": {"chunk": seq, "timestamp": str(elapsed_ms), "payload": payload}}


def stop_message(provider: str, stream_id: str) -> dict:
    if provider == "vobiz":
        return {"event": "stop", "streamId": stream_id}
    return {"event": "stop", "stream_sid": stream_id, "stop": {"reason": "callended"}}


async def run_call(url: str, pcm: bytes, name: str, lead_id: Optional[int], caller: str,
                   tail_seconds: float, provider: str = "exotel", answer_url: str = "") -> CallResult:
    result = CallResult(name=name)
    stream_id, call_id = uuid.uuid4().hex, uuid.uuid4().hex
    rate = VOBIZ_RATE if provider == "vobiz" else EXOTEL_RATE
    chunk_bytes = rate * 2 * CHUNK_MS // 1000  # 16-bit mono

    if provider == "vobiz":
        try:
            url = await asyncio.to_thread(vobiz_stream_url, answer_url, lead_id, caller, call_id)
        except Exception as e:
            result.error = f"Answer URL failed: {e}"
            return result
    elif lead_id:
        url = f"{url}?lead_id={lead_id}"

    utterance_end: Optional[float] = None  # wall time when the caller's last utterance ended
    waiting_for_reply = False

    try:
        async with websockets.connect(url, max_size=None) as ws:
            for message in handshake_messages(provider, stream_id, call_id, caller, lead_id):
                await ws.send(json.dumps(message))
            result.connected = True

            async def receiver():
                nonlocal waiting_for_reply
                async for raw in ws:
                    try:
                        data = json.loads(raw)
                    except ValueError:
                        continue
                    event = data.get("event")
                    if event in ("media", "playAudio"):
                        audio = base64.b64decode(data.get("media", {}).get("payload", ""))
                        result.bot_audio_bytes += len(audio)
                        result.bot_audio.extend(audio)
                        if waiting_for_reply and utterance_end is not None:
                            result.reply_gaps.append(time.time() - utterance_end)
                            waiting_for_reply = False
                    elif event in ("clear", "clearAudio"):
                        result.clear_events += 1

            recv_task = asyncio.create_task(receiver())

            # Stream the caller audio in real time, tracking where utterances end
            in_speech, silence_ms, seq = False, 0, 1
            start = time.time()
            for i in range(0, len(pcm), chunk_bytes):
                chunk = pcm[i:i + chunk_bytes]
                if len(chunk) < chunk_bytes:
                    chunk += b"\x00" * (chunk_bytes - len(chunk))
                elapsed_ms = int((time.time() - start) * 1000)
                await ws.send(json.dumps(media_message(provider, stream_id, seq,
                                                       elapsed_ms, base64.b64encode(chunk).decode())))
                seq += 1

                if audioop.rms(chunk, 2) > SPEECH_RMS:
                    in_speech, silence_ms = True, 0
                elif in_speech:
                    silence_ms += CHUNK_MS
                    if silence_ms >= UTTERANCE_END_MS:
                        in_speech = False
                        utterance_end = time.time() - silence_ms / 1000
                        waiting_for_reply = True

                target = start + (i // chunk_bytes + 1) * CHUNK_MS / 1000  # real-time pacing
                await asyncio.sleep(max(0.0, target - time.time()))

            await asyncio.sleep(tail_seconds)  # let the last reply finish
            await ws.send(json.dumps(stop_message(provider, stream_id)))
            await asyncio.sleep(0.5)
            recv_task.cancel()
    except Exception as e:
        result.error = f"{type(e).__name__}: {e}"
    return result


async def main_async(args):
    rate = VOBIZ_RATE if args.provider == "vobiz" else EXOTEL_RATE
    url = args.url or ("ws://127.0.0.1:8000/api/voice/vobiz/stream" if args.provider == "vobiz"
                       else "ws://127.0.0.1:8000/api/voice/exotel/stream")
    pcm = load_pcm(args.wav, rate)
    target = args.answer_url if args.provider == "vobiz" else url
    print(f"[{args.provider}] caller audio: {len(pcm) / (rate * 2):.1f}s · {args.parallel} call(s) → {target}")
    started = time.time()
    results = await asyncio.gather(*[
        run_call(url, pcm, f"call{n + 1}", args.lead_id, args.caller, args.tail, args.provider, args.answer_url)
        for n in range(args.parallel)
    ])
    print(f"Finished in {time.time() - started:.1f}s\n")

    all_gaps = []
    for r in results:
        gaps = ", ".join(f"{g:.2f}s" for g in r.reply_gaps) or "none"
        status = "ERROR " + r.error if r.error else ("ok" if r.connected else "not connected")
        print(f"{r.name}: {status} · bot audio {r.bot_audio_bytes / (rate * 2):.1f}s · "
              f"clear events {r.clear_events} · reply gaps {gaps}")
        all_gaps.extend(r.reply_gaps)

    if all_gaps:
        print(f"\nReply gap: avg {statistics.mean(all_gaps):.2f}s · best {min(all_gaps):.2f}s · "
              f"worst {max(all_gaps):.2f}s over {len(all_gaps)} turns")

    if args.out and results and results[0].bot_audio:
        with wave.open(args.out, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(bytes(results[0].bot_audio))
        print(f"Bot audio of call1 saved to {args.out}")

    return 0 if all(r.connected and not r.error for r in results) else 1


def main():
    parser = argparse.ArgumentParser(description="Fake telephony caller (Exotel or Vobiz)")
    parser.add_argument("--provider", choices=["exotel", "vobiz"], default="exotel")
    parser.add_argument("--url", default=None, help="Exotel stream URL (default ws://127.0.0.1:8000/...)")
    parser.add_argument("--answer-url", default="http://127.0.0.1:8000/api/voice/vobiz/answer",
                        help="Vobiz Answer URL (the stream URL is read from its XML)")
    parser.add_argument("--wav", required=True, help="Caller audio (any WAV; converted automatically)")
    parser.add_argument("--lead-id", type=int, default=None, help="Outbound call for this lead")
    parser.add_argument("--caller", default="+919000000001", help="Caller number (inbound lookup)")
    parser.add_argument("--parallel", type=int, default=1, help="Simultaneous calls (load test)")
    parser.add_argument("--tail", type=float, default=8.0, help="Seconds to wait after the audio ends")
    parser.add_argument("--out", default=None, help="Save the bot's audio of the first call to this WAV")
    raise SystemExit(asyncio.run(main_async(parser.parse_args())))


if __name__ == "__main__":
    main()
