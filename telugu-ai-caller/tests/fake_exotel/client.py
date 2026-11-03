"""
Fake Exotel caller: tests the phone path without an Exotel account.

Behaves like Exotel's Voicebot applet: opens the WebSocket, sends the
`connected` and `start` handshake, then streams a WAV file as 16-bit PCM 8 kHz
mono in 100 ms base64 `media` chunks (in real time), and finally `stop`.
It records the bot's audio, counts `clear` (barge-in) events and measures the
reply gap: from the end of each caller utterance to the bot's first audio.

Usage (app running on port 8000):
  python tests/fake_exotel/client.py --wav tests/fake_exotel/samples/three_questions.wav
  python tests/fake_exotel/client.py --wav ... --lead-id 1 --out bot_reply.wav
  python tests/fake_exotel/client.py --wav ... --parallel 5      # load test
"""

import argparse
import asyncio
import audioop
import base64
import json
import statistics
import time
import uuid
import wave
from dataclasses import dataclass, field
from typing import List, Optional

import websockets

EXOTEL_RATE = 8000
CHUNK_MS = 100
CHUNK_BYTES = EXOTEL_RATE * 2 * CHUNK_MS // 1000  # 16-bit mono
SPEECH_RMS = 300          # chunk energy above this counts as caller speech
UTTERANCE_END_MS = 500    # this much silence after speech ends an utterance


def load_pcm8k(path: str) -> bytes:
    """Read a WAV file and convert it to 16-bit mono 8 kHz PCM."""
    with wave.open(path, "rb") as w:
        frames = w.readframes(w.getnframes())
        width, channels, rate = w.getsampwidth(), w.getnchannels(), w.getframerate()
    if channels == 2:
        frames = audioop.tomono(frames, width, 0.5, 0.5)
    if width != 2:
        frames = audioop.lin2lin(frames, width, 2)
    if rate != EXOTEL_RATE:
        frames, _ = audioop.ratecv(frames, 2, 1, rate, EXOTEL_RATE, None)
    return frames


@dataclass
class CallResult:
    name: str
    connected: bool = False
    reply_gaps: List[float] = field(default_factory=list)
    bot_audio_bytes: int = 0
    clear_events: int = 0
    error: Optional[str] = None
    bot_audio: bytearray = field(default_factory=bytearray)


async def run_call(url: str, pcm: bytes, name: str, lead_id: Optional[int], caller: str,
                   tail_seconds: float) -> CallResult:
    result = CallResult(name=name)
    stream_sid, call_sid = uuid.uuid4().hex, uuid.uuid4().hex
    query = f"?lead_id={lead_id}" if lead_id else ""
    utterance_end: Optional[float] = None  # wall time when the caller's last utterance ended
    waiting_for_reply = False

    try:
        async with websockets.connect(url + query, max_size=None) as ws:
            await ws.send(json.dumps({"event": "connected"}))
            await ws.send(json.dumps({
                "event": "start",
                "sequence_number": 1,
                "stream_sid": stream_sid,
                "start": {
                    "stream_sid": stream_sid,
                    "call_sid": call_sid,
                    "account_sid": "fake_account",
                    "from": caller,
                    "to": "+918040000000",
                    "custom_parameters": {"lead_id": str(lead_id)} if lead_id else {},
                    "media_format": {"encoding": "base64", "sample_rate": str(EXOTEL_RATE), "bit_rate": "128kbps"},
                },
            }))
            result.connected = True

            async def receiver():
                nonlocal waiting_for_reply
                async for message in ws:
                    try:
                        data = json.loads(message)
                    except ValueError:
                        continue
                    if data.get("event") == "media":
                        audio = base64.b64decode(data.get("media", {}).get("payload", ""))
                        result.bot_audio_bytes += len(audio)
                        result.bot_audio.extend(audio)
                        if waiting_for_reply and utterance_end is not None:
                            result.reply_gaps.append(time.time() - utterance_end)
                            waiting_for_reply = False
                    elif data.get("event") == "clear":
                        result.clear_events += 1

            recv_task = asyncio.create_task(receiver())

            # Stream the caller audio in real time, tracking where utterances end
            in_speech, silence_ms, seq = False, 0, 2
            start = time.time()
            for i in range(0, len(pcm), CHUNK_BYTES):
                chunk = pcm[i:i + CHUNK_BYTES]
                if len(chunk) < CHUNK_BYTES:
                    chunk += b"\x00" * (CHUNK_BYTES - len(chunk))
                await ws.send(json.dumps({
                    "event": "media",
                    "sequence_number": seq,
                    "stream_sid": stream_sid,
                    "media": {"chunk": seq, "timestamp": str(int((time.time() - start) * 1000)),
                              "payload": base64.b64encode(chunk).decode()},
                }))
                seq += 1

                loud = audioop.rms(chunk, 2) > SPEECH_RMS
                if loud:
                    in_speech, silence_ms = True, 0
                elif in_speech:
                    silence_ms += CHUNK_MS
                    if silence_ms >= UTTERANCE_END_MS:
                        in_speech = False
                        utterance_end = time.time() - silence_ms / 1000
                        waiting_for_reply = True

                # keep real-time pacing
                target = start + (i // CHUNK_BYTES + 1) * CHUNK_MS / 1000
                await asyncio.sleep(max(0.0, target - time.time()))

            await asyncio.sleep(tail_seconds)  # let the last reply finish
            await ws.send(json.dumps({"event": "stop", "stream_sid": stream_sid, "stop": {"reason": "callended"}}))
            await asyncio.sleep(0.5)
            recv_task.cancel()
    except Exception as e:
        result.error = f"{type(e).__name__}: {e}"
    return result


async def main_async(args):
    pcm = load_pcm8k(args.wav)
    print(f"Caller audio: {len(pcm) / (EXOTEL_RATE * 2):.1f}s · {args.parallel} call(s) → {args.url}")
    started = time.time()
    results = await asyncio.gather(*[
        run_call(args.url, pcm, f"call{n + 1}", args.lead_id, args.caller, args.tail)
        for n in range(args.parallel)
    ])
    print(f"Finished in {time.time() - started:.1f}s\n")

    all_gaps = []
    for r in results:
        gaps = ", ".join(f"{g:.2f}s" for g in r.reply_gaps) or "none"
        status = "ERROR " + r.error if r.error else ("ok" if r.connected else "not connected")
        print(f"{r.name}: {status} · bot audio {r.bot_audio_bytes / (EXOTEL_RATE * 2):.1f}s · "
              f"clear events {r.clear_events} · reply gaps {gaps}")
        all_gaps.extend(r.reply_gaps)

    if all_gaps:
        print(f"\nReply gap: avg {statistics.mean(all_gaps):.2f}s · best {min(all_gaps):.2f}s · "
              f"worst {max(all_gaps):.2f}s over {len(all_gaps)} turns")

    if args.out and results and results[0].bot_audio:
        with wave.open(args.out, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(EXOTEL_RATE)
            w.writeframes(bytes(results[0].bot_audio))
        print(f"Bot audio of call1 saved to {args.out}")

    return 0 if all(r.connected and not r.error for r in results) else 1


def main():
    parser = argparse.ArgumentParser(description="Fake Exotel Voicebot caller")
    parser.add_argument("--url", default="ws://127.0.0.1:8000/api/voice/exotel/stream")
    parser.add_argument("--wav", required=True, help="Caller audio (any WAV; converted to 8 kHz mono)")
    parser.add_argument("--lead-id", type=int, default=None, help="Outbound call for this lead")
    parser.add_argument("--caller", default="+919000000001", help="Caller number (inbound lookup)")
    parser.add_argument("--parallel", type=int, default=1, help="Simultaneous calls (load test)")
    parser.add_argument("--tail", type=float, default=8.0, help="Seconds to wait after the audio ends")
    parser.add_argument("--out", default=None, help="Save the bot's audio of the first call to this WAV")
    raise SystemExit(asyncio.run(main_async(parser.parse_args())))


if __name__ == "__main__":
    main()
