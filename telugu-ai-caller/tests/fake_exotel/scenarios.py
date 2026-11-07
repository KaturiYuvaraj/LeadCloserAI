"""
Scenario caller: acts as the customer on the real-time engine, before anyone picks up a phone.

It speaks generated Telugu / Hindi / English audio into the Vobiz audio stream (the same path a phone
call uses), waits for the AI to finish, replies, interrupts, goes silent or changes language, and can
add traffic noise or a bad network. Afterwards it reads the call from the database and checks what
the AI heard, what it said and what it did.

    python tests/fake_exotel/scenarios.py --base http://127.0.0.1:8772 --db <path to the test database>
    python tests/fake_exotel/scenarios.py --base ... --db ... --only hold,vaddu

Run it against a test copy of the app with its own database. It places no phone calls, but each
call uses Sarvam (about Rs 2 per minute). Generated voices are cleaner than people on real phone
lines, so a pass here is necessary, not proof: real calls are still the final test.
"""

import argparse
import asyncio
import base64
import difflib
import hashlib
import io
import json
import os
import re
import sqlite3
import sys
import time
import uuid
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import httpx
import numpy as np
import websockets
from dotenv import dotenv_values

sys.path.insert(0, str(Path(__file__).resolve().parent))
from client import VOBIZ_RATE, handshake_messages, media_message, stop_message, vobiz_stream_url  # noqa: E402

FRAME_MS = 20
FRAME_SAMPLES = VOBIZ_RATE * FRAME_MS // 1000
VOICES = {"te-IN": "tarun_te_narration", "hi-IN": "aayan_hi_conversational", "en-IN": "dev_en_conversational"}
ROOT = Path(__file__).resolve().parents[2]
CACHE = Path(os.getenv("SCENARIO_AUDIO_CACHE") or (Path(__file__).parent / ".audio-cache"))
TE, HI, EN = "te-IN", "hi-IN", "en-IN"


# ------------------------------------------------------------------ customer audio
def speak(text: str, lang: str) -> np.ndarray:
    """Customer speech as 16 kHz float samples (cached, so reruns cost nothing)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / (hashlib.sha1(f"{lang}|{text}".encode()).hexdigest() + ".wav")
    if not path.exists():
        key = dotenv_values(ROOT / ".env")["SARVAM_API_KEY"].strip()
        r = httpx.post("https://api.sarvam.ai/text-to-speech", headers={"api-subscription-key": key}, timeout=60,
                       json={"text": text, "target_language_code": lang, "model": "bulbul:v4-flash",
                             "speaker": VOICES[lang]})
        r.raise_for_status()
        path.write_bytes(base64.b64decode(r.json()["audios"][0]))
    w = wave.open(str(path))
    rate = w.getframerate()
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
    if rate != VOBIZ_RATE:
        x = np.interp(np.arange(0, len(x), rate / VOBIZ_RATE), np.arange(len(x)), x)
    return phone_band(x)


def phone_band(x: np.ndarray) -> np.ndarray:
    """Keep 300-3400 Hz, like a phone line."""
    spectrum = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(len(x), 1 / VOBIZ_RATE)
    spectrum[(freqs < 300) | (freqs > 3400)] = 0
    return np.fft.irfft(spectrum, len(x))


def traffic(seconds: float, rng: np.random.Generator) -> np.ndarray:
    """Road rumble with engine hum and the odd horn."""
    n = int(seconds * VOBIZ_RATE)
    rumble = np.cumsum(rng.normal(0, 1, n))
    rumble -= np.convolve(rumble, np.ones(4000) / 4000, mode="same")
    rumble = rumble / (np.abs(rumble).max() + 1e-6) * 1800 + rng.normal(0, 260, n)
    t = np.arange(n) / VOBIZ_RATE
    for start in rng.uniform(0, max(seconds - 1, 1), int(seconds / 7) + 1):
        a, b = int(start * VOBIZ_RATE), int((start + 0.5) * VOBIZ_RATE)
        rumble[a:b] += 2600 * np.sign(np.sin(2 * np.pi * 440 * t[a:b]))
    return rumble


@dataclass
class Scenario:
    key: str
    title: str
    steps: List[Dict[str, Any]]
    check: Callable[["Result"], List[str]]
    noise: Optional[str] = None      # traffic
    lossy: bool = False              # bad network: bursts of lost audio


@dataclass
class Result:
    scenario: Scenario
    clears: int = 0
    gaps: List[float] = field(default_factory=list)
    said: List[str] = field(default_factory=list)
    transcript: List[Dict[str, Any]] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    end_reason: str = ""
    outcome: str = ""
    opt_out: bool = False
    jobs: List[Any] = field(default_factory=list)
    ended_by_server: bool = False
    bot_seconds: float = 0
    error: str = ""

    def ai(self) -> List[str]:
        return [m.get("content") or "" for m in self.transcript if m.get("role") == "assistant"]

    def heard(self) -> List[str]:
        return [m.get("content") or "" for m in self.transcript if m.get("role") == "user"]

    def hearing_score(self) -> float:
        """How much of what the customer said reached the AI (0-1), by characters in order."""
        said, heard = "".join(self.said), "".join(self.heard())
        clean = lambda s: re.sub(r"[\s.,?!।]", "", s).lower()  # noqa: E731
        if not said:
            return 1.0
        return difflib.SequenceMatcher(None, clean(said), clean(heard)).ratio()


# ------------------------------------------------------------------ the call
class Caller:
    def __init__(self, scenario: Scenario, stream_url: str, call_id: str, seed: int):
        self.s, self.url, self.call_id = scenario, stream_url, call_id
        self.rng = np.random.default_rng(seed)
        self.queue: List[np.ndarray] = []
        self.bot_until = 0.0
        self.bot_started_at: Optional[float] = None
        self.bot_ever = False
        self.spoke_end: Optional[float] = None
        self.closed = False
        self.result = Result(scenario)
        self.noise = traffic(240, self.rng) if scenario.noise == "traffic" else None
        self.noise_pos = 0

    def bot_talking(self) -> bool:
        return time.time() < self.bot_until

    def next_frame(self) -> bytes:
        frame = np.zeros(FRAME_SAMPLES, dtype=np.float32)
        if self.queue:
            chunk = self.queue[0][:FRAME_SAMPLES]
            frame[:len(chunk)] = chunk
            self.queue[0] = self.queue[0][FRAME_SAMPLES:]
            if len(self.queue[0]) == 0:
                self.queue.pop(0)
                if not self.queue:
                    self.spoke_end = time.time()
        if self.noise is not None:
            frame = frame + self.noise[self.noise_pos:self.noise_pos + FRAME_SAMPLES]
            self.noise_pos = (self.noise_pos + FRAME_SAMPLES) % (len(self.noise) - FRAME_SAMPLES)
        else:
            frame = frame + self.rng.normal(0, 12, FRAME_SAMPLES)  # a line is never digitally silent
        if self.s.lossy and self.rng.random() < 0.06:
            frame[:] = 0
        return np.clip(frame, -32000, 32000).astype(np.int16).tobytes()

    async def receive(self, ws):
        try:
            async for raw in ws:
                data = json.loads(raw)
                event = data.get("event")
                if event == "playAudio":
                    audio = base64.b64decode(data.get("media", {}).get("payload", ""))
                    seconds = len(audio) / 2 / VOBIZ_RATE
                    now = time.time()
                    if not self.bot_talking():
                        self.bot_started_at = now
                        if self.spoke_end:
                            self.result.gaps.append(round(now - self.spoke_end, 2))
                            self.spoke_end = None
                    self.bot_until = max(self.bot_until, now) + seconds
                    self.bot_ever = True
                    self.result.bot_seconds += seconds
                elif event == "clearAudio":
                    self.result.clears += 1
                    self.bot_until = time.time()
        except websockets.ConnectionClosed:
            pass
        self.closed = True

    async def send_audio(self, ws, stream_id):
        seq, start = 1, time.time()
        while not self.closed:
            payload = base64.b64encode(self.next_frame()).decode()
            try:
                await ws.send(json.dumps(media_message("vobiz", stream_id, seq, int((time.time() - start) * 1000), payload)))
            except websockets.ConnectionClosed:
                break
            seq += 1
            await asyncio.sleep(max(0.0, start + seq * FRAME_MS / 1000 - time.time()))
        self.closed = True

    async def wait_for_bot_to_finish(self, timeout: float = 30):
        """The AI has spoken and gone quiet for a moment."""
        end = time.time() + timeout
        spoken = self.result.bot_seconds
        while time.time() < end and not self.closed:
            if self.result.bot_seconds > spoken and not self.bot_talking():
                await asyncio.sleep(1.2)  # a short gap between two of the AI's sentences isn't the end
                if not self.bot_talking():
                    return
            await asyncio.sleep(0.05)

    async def wait_for_bot_to_start(self, timeout: float = 15):
        spoken = self.result.bot_seconds
        end = time.time() + timeout
        while time.time() < end and not self.closed and self.result.bot_seconds == spoken:
            await asyncio.sleep(0.05)

    async def say(self, text: str, lang: str):
        self.result.said.append(text)
        self.queue.append(await asyncio.to_thread(speak, text, lang))
        while self.queue and not self.closed:
            await asyncio.sleep(0.05)

    async def play(self, ws):
        await self.wait_for_bot_to_finish()  # the greeting
        for step in self.s.steps:
            if self.closed:
                break
            if "wait" in step:  # silence
                await asyncio.sleep(step["wait"])
                continue
            if step.get("barge"):  # talk over the AI, a moment after it starts
                await self.wait_for_bot_to_start()
                await asyncio.sleep(step["barge"])
                await self.say(step["say"], step.get("lang", TE))
                await self.wait_for_bot_to_finish()
                continue
            if isinstance(step["say"], list):  # one sentence with a pause in the middle
                for i, part in enumerate(step["say"]):
                    if i:
                        await asyncio.sleep(step.get("gap", 1.5))
                    await self.say(part, step.get("lang", TE))
            else:
                await self.say(step["say"], step.get("lang", TE))
            if step.get("reply", True):
                await self.wait_for_bot_to_finish()
            else:
                await asyncio.sleep(0.2)
        end = time.time() + 12  # let a last reply or hang-up happen
        while time.time() < end and not self.closed:
            await asyncio.sleep(0.1)
        self.result.ended_by_server = self.closed

    async def run(self):
        stream_id = uuid.uuid4().hex
        async with websockets.connect(self.url, max_size=None) as ws:
            for message in handshake_messages("vobiz", stream_id, self.call_id, "+919000000001", None):
                await ws.send(json.dumps(message))
            tasks = [asyncio.create_task(self.receive(ws)), asyncio.create_task(self.send_audio(ws, stream_id))]
            await self.play(ws)
            if not self.closed:
                await ws.send(json.dumps(stop_message("vobiz", stream_id)))
                await asyncio.sleep(0.5)
            self.closed = True
            for task in tasks:
                task.cancel()


# ------------------------------------------------------------------ checks
def has_action(r: Result, name: str) -> bool:
    return name in r.actions


def script_ok(text: str, lang: str) -> bool:
    ranges = {TE: (0x0C00, 0x0C7F), HI: (0x0900, 0x097F)}
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    if lang == EN:
        return sum(c.isascii() for c in letters) / len(letters) > 0.8
    lo, hi = ranges[lang]
    return sum(lo <= ord(c) <= hi for c in letters) / len(letters) > 0.6


def base_checks(r: Result, min_hearing: float = 0.6) -> List[str]:
    problems = []
    if r.bot_seconds < 3:
        problems.append("the AI was silent")
    if r.hearing_score() < min_hearing:
        problems.append(f"poor hearing ({r.hearing_score():.0%} of what was said)")
    replies = r.ai()[1:]
    for a, b in zip(replies, replies[1:]):
        if a and difflib.SequenceMatcher(None, a, b).ratio() > 0.75:
            problems.append("repeated itself almost word for word")
            break
    long_replies = [x for x in replies if len(x) > 240]
    if long_replies:
        problems.append(f"{len(long_replies)} very long repl{'y' if len(long_replies) == 1 else 'ies'}")
    return problems


def check_booked(r):
    p = base_checks(r)
    if not has_action(r, "meeting"):
        p.append("no meeting booked")
    return p


def check_noise(r):
    return base_checks(r, 0.45)


def check_hold(r):
    p = base_checks(r)
    if r.end_reason in ("silence", "no_response"):
        p.append("gave up during the hold")
    if len(r.ai()) > 1 and len(r.ai()[1]) > 90:
        p.append("kept talking instead of a short 'take your time'")
    return p


def check_vaddu(r):
    p = base_checks(r)
    if len(r.ai()) < 3:
        p.append("did not make one polite attempt")
    if not r.ended_by_server:
        p.append("did not end the call after the second no")
    if has_action(r, "meeting") or has_action(r, "callback"):
        p.append("booked something after a no")
    return p


def check_dnc(r):
    p = base_checks(r)
    if not r.opt_out:
        p.append("number NOT on the Do-Not-Call list")
    return p


def check_callback(r):
    p = base_checks(r)
    if not has_action(r, "callback"):
        p.append("no callback booked")
    return p


def check_barge(r):
    p = base_checks(r)
    if r.clears < 1:
        p.append("did not stop talking when interrupted")
    if not any(re.search(r"\d|వేల|రూపాయ|ప్రైస్", x) for x in r.ai()[1:]):
        p.append("did not answer the price question")
    return p


def lang_check(lang):
    def check(r):
        p = base_checks(r, 0.5)
        if not r.ai() or not script_ok(r.ai()[-1], lang):
            p.append(f"last reply was not in {lang}")
        return p
    return check


def check_mix(r):
    p = base_checks(r, 0.5)
    if not script_ok((r.ai() or [""])[-1], TE):
        p.append("left Telugu for a Telugu-English customer")
    return p


def check_pause(r):
    p = base_checks(r)
    if r.gaps and r.gaps[0] < 0:
        p.append("talked before the customer finished")
    heard_first = (r.heard() or [""])[0]
    if "యాప్" not in heard_first and len(r.heard()) > 1:
        p.append("cut the sentence in two at the pause")
    return p


def check_silence(r):
    p = []
    if r.bot_seconds < 3:
        p.append("the AI was silent")
    if not r.ended_by_server:
        p.append("did not end the call")
    if r.end_reason != "no_response":
        p.append(f"end reason {r.end_reason or 'missing'}, expected no_response")
    return p


def check_wrong_person(r):
    p = base_checks(r)
    if not has_action(r, "callback"):
        p.append("no callback booked for Ravi")
    return p


def check_angry(r):
    p = base_checks(r)
    if not r.opt_out and not r.ended_by_server:
        p.append("kept going with an angry customer")
    return p


SCENARIOS = [
    Scenario("happy", "Normal conversation to a demo", [
        {"say": "అవును అండి, మాకు ఒక వెబ్‌సైట్ కావాలి."},
        {"say": "ఈ కామర్స్ వెబ్‌సైట్ కావాలి, బట్టల షాప్ కోసం."},
        {"say": "ప్రైస్ ఎంత అవుతుంది?"},
        {"say": "రేపు ఉదయం పదకొండు గంటలకు డెమో పెట్టండి."},
    ], check_booked),
    Scenario("traffic", "Customer on a busy road", [
        {"say": "అవును అండి, మాకు ఒక మొబైల్ యాప్ కావాలి."},
        {"say": "ఆండ్రాయిడ్ యాప్ కావాలి, ప్రైస్ ఎంత?"},
    ], check_noise, noise="traffic"),
    Scenario("network", "Bad network, audio dropping", [
        {"say": "మాకు ఒక వెబ్‌సైట్ కావాలి, మా హోటల్ కోసం."},
        {"say": "ఎంత టైమ్ పడుతుంది?"},
    ], check_noise, lossy=True),
    Scenario("hold", "'One minute' then 15 s silence", [
        {"say": "ఒక్క నిమిషం ఆగండి."},
        {"wait": 15},
        {"say": "ఆ చెప్పండి, ఇప్పుడు వినిపిస్తోంది. వెబ్‌సైట్ గురించి చెప్పండి."},
    ], check_hold),
    Scenario("vaddu", "Says vaddu twice", [
        {"say": "వద్దు అండి, మాకు ఏమీ అవసరం లేదు."},
        {"say": "వద్దు అన్నాను కదా, ధన్యవాదాలు."},
    ], check_vaddu),
    Scenario("dnc", "Do not call again", [
        {"say": "మళ్ళీ నాకు కాల్ చేయకండి, నా నంబర్ తీసేయండి."},
    ], check_dnc),
    Scenario("busy", "Driving, call tomorrow 4 PM", [
        {"say": "నేను డ్రైవింగ్ లో ఉన్నాను, రేపు సాయంత్రం నాలుగు గంటలకు కాల్ చేయండి."},
    ], check_callback),
    Scenario("barge", "Interrupts the AI mid-sentence", [
        {"say": "మాకు ఒక వెబ్‌సైట్ కావాలి.", "reply": False},
        {"say": "ఆగండి ఆగండి, ముందు ప్రైస్ ఎంతో చెప్పండి.", "barge": 2.0},
    ], check_barge),
    Scenario("english", "Switches to English", [
        {"say": "Can you speak in English please? I need a mobile app for my shop.", "lang": EN},
        {"say": "How much will it cost and how long will it take?", "lang": EN},
    ], lang_check(EN)),
    Scenario("hindi", "Switches to Hindi", [
        {"say": "हिंदी में बात कीजिए, मुझे एक वेबसाइट चाहिए।", "lang": HI},
        {"say": "इसकी कीमत कितनी होगी?", "lang": HI},
    ], lang_check(HI)),
    Scenario("mixed", "Telugu-English mix", [
        {"say": "నాకు ఒక website కావాలి, but budget కొంచెం తక్కువ ఉంది."},
        {"say": "basic package లో ఏమేమి వస్తాయి, delivery ఎప్పుడు?"},
    ], check_mix),
    Scenario("pause", "Long pause inside a sentence", [
        {"say": ["నాకు ఒక వెబ్‌సైట్", "మరియు మొబైల్ యాప్ రెండూ కావాలి."], "gap": 1.5},
    ], check_pause),
    Scenario("silent", "Picks up and says nothing", [{"wait": 32}], check_silence),
    Scenario("wrongperson", "Someone else answers", [
        {"say": "ఆయన ఇంట్లో లేరు, నేను వాళ్ళ అమ్మని. సాయంత్రం ఆరు గంటలకు కాల్ చేయండి."},
    ], check_wrong_person),
    Scenario("angry", "Angry customer", [
        {"say": "ఎందుకు ఇలా మాటిమాటికీ కాల్ చేస్తారు? మీకు పనేమీ లేదా? నాకు చాలా కోపంగా ఉంది."},
        {"say": "ఫోన్ పెట్టేయండి, నాకు మాట్లాడటం ఇష్టం లేదు."},
    ], check_angry),
]


# ------------------------------------------------------------------ running
def collect(result: Result, db: str, lead_id: int):
    time.sleep(4)  # the engine saves the call after it ends
    con = sqlite3.connect(db)
    row = con.execute("select transcript, captured, outcome from calls where lead_id=? order by id desc limit 1",
                      (lead_id,)).fetchone()
    if row:
        result.transcript = json.loads(row[0]) if isinstance(row[0], str) else (row[0] or [])
        analytics = (json.loads(row[1] or "{}") if isinstance(row[1], str) else (row[1] or {})).get("analytics", {})
        result.actions = [a.get("action") for a in analytics.get("actions") or []]
        result.end_reason = analytics.get("end_reason") or ""
        result.outcome = row[2] or ""
    result.opt_out = bool(con.execute("select opt_out from leads where id=?", (lead_id,)).fetchone()[0])
    result.jobs = con.execute("select state, last_disposition from call_jobs where lead_id=?", (lead_id,)).fetchall()
    con.close()


async def run_one(scenario: Scenario, base: str, db: str, index: int) -> Result:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(f"{base}/api/leads", json={
            "name": f"Scenario {scenario.key}", "phone": f"+9198{int(time.time()) % 100000:05d}{index:03d}",
            "service_needed": "website", "preferred_language": TE, "source": "manual"})
        lead_id = resp.json()["lead_id"]
    call_id = uuid.uuid4().hex
    url = await asyncio.to_thread(vobiz_stream_url, f"{base}/api/voice/vobiz/answer", lead_id, "+919000000001", call_id)
    caller = Caller(scenario, url, call_id, seed=index)
    try:
        await caller.run()
    except Exception as e:
        caller.result.error = f"{type(e).__name__}: {e}"
    await asyncio.to_thread(collect, caller.result, db, lead_id)
    return caller.result


async def main_async(args):
    chosen = [s for s in SCENARIOS if not args.only or s.key in args.only.split(",")]
    semaphore = asyncio.Semaphore(args.parallel)

    async def guarded(s, i):
        async with semaphore:
            print(f"… {s.key}: {s.title}", flush=True)
            return await run_one(s, args.base, args.db, i)

    results = await asyncio.gather(*[guarded(s, i) for i, s in enumerate(chosen)])
    report, passed = [], 0
    for r in results:
        problems = ([r.error] if r.error else []) + r.scenario.check(r)
        passed += not problems
        gaps = [g for g in r.gaps if g >= 0]
        report.append(f"\n{'PASS' if not problems else 'FAIL'}  {r.scenario.key}: {r.scenario.title}")
        report.append(f"  hearing {r.hearing_score():.0%} · reply gap {np.mean(gaps) if gaps else 0:.2f}s · interrupted {r.clears}x · "
                      f"end {r.end_reason or '-'} · outcome {r.outcome or '-'} · actions {r.actions}")
        for problem in problems:
            report.append(f"  ✗ {problem}")
        for m in r.transcript:
            who = "AI " if m.get("role") == "assistant" else "CUSTOMER heard as"
            report.append(f"    {who}: {(m.get('content') or '')[:170]}")
    report.append(f"\n{passed}/{len(results)} scenarios passed")
    text = "\n".join(report)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", required=True, help="Test copy of the app, e.g. http://127.0.0.1:8772")
    parser.add_argument("--db", required=True, help="SQLite file of that test copy")
    parser.add_argument("--only", default="", help="Comma-separated scenario keys")
    parser.add_argument("--parallel", type=int, default=3)
    parser.add_argument("--out", default="", help="Also write the report to this file")
    args = parser.parse_args()
    if "127.0.0.1" not in args.base and "localhost" not in args.base:
        parser.error("Run this against a local test copy only.")
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
