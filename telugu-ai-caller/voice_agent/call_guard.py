"""
Call handling for real phone conditions: who (or what) answered, and how the
caller is behaving.

1. Machines. Right after an outbound call connects, the other side may be a
   voicemail greeting, an IVR menu ("press 1 for…") or a carrier message
   ("the number you are calling is switched off"). `classify_automated` spots
   these in English, Hindi, Telugu, Tamil, Kannada and Malayalam; `CallGuard`
   (placed right after STT) checks the first transcripts, keeps them away from
   the LLM, and ends the call so the dialer can retry later.

2. People. `caller_hints` looks at each caller message and returns a short
   instruction that travels with it to the LLM:
     - "one minute / hold on / ఒక్క నిమిషం / एक मिनट" → wait patiently
     - "don't call me again"                         → confirm and mark Do-Not-Call
     - "let me talk to a person"                     → offer a team callback
     - upset or abusive words                        → stay calm, don't argue
     - broken / noisy transcript ("the ... kh ...")  → ask to repeat, never guess
   The LLM still decides; the hints only make the right reaction very likely.
"""

import asyncio
import os
import re
import time
from typing import Awaitable, Callable, List, Optional

from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

# ----------------------------------------------------------------------------- machines

AUTOMATED_PATTERNS = {
    # Carrier messages: switched off, unreachable, invalid, busy on another call
    "unreachable": [
        r"switch(ed)?\s*off", r"not\s+reachable", r"out\s+of\s+(coverage|network|service)",
        r"(number|subscriber)\s+you\s+(are|have)\s+(calling|called|dialled|dialed)",
        r"does\s+not\s+exist", r"not\s+in\s+service", r"is\s+busy\s+(on|with)\s+another\s+call",
        r"please\s+try\s+(again\s+)?later", r"temporarily\s+(unavailable|out\s+of)",
        r"स्विच\s*ऑफ", r"पहुं?च\s+से\s+बाहर", r"आप\s+जिस\s+नं?ब", r"नंबर\s+मौजूद\s+नहीं",
        r"दूसरी\s+कॉल\s+पर\s+व्यस्त", r"कृपया\s+(थोड़ी\s+देर\s+)?बाद\s+में",
        r"స్విచ్\s*ఆఫ్", r"మీరు\s+(కాల్|డయల్)\s+చేస్తున్న", r"పరిధి\s+(వెలుపల|బయట)", r"నెట్‌?వర్క్\s+పరిధి",
        r"சுவிட்ச்\s*ஆஃப்",r"நீங்கள்\s+அழைக்கும்", r"ಸ್ವಿಚ್\s*ಆಫ್", r"ನೀವು\s+ಕರೆ\s+ಮಾಡುತ್ತಿರುವ",
        r"സ്വിച്ച്\s*ഓഫ്", r"നിങ്ങൾ\s+വിളിക്കുന്ന",
    ],
    "voicemail": [
        r"leave\s+(a|your)\s+message", r"after\s+the\s+(beep|tone)", r"voice\s*-?\s*mail", r"mail\s*box",
        r"not\s+available\s+to\s+take\s+your\s+call", r"record\s+your\s+message", r"can'?t\s+take\s+your\s+call",
        r"बीप\s+के\s+बाद", r"(अपना\s+)?संदेश\s+छोड़", r"బీప్", r"సందేశాన్ని\s+(వదిలి|రికార్డ్)",
    ],
    "ivr": [
        r"\bpress\s+(\d|one|two|three|star|hash|zero)\b", r"\bdial\s+\d\b", r"for\s+\w+\s*,?\s*press",
        r"main\s+menu", r"दबाएं|दबाइए|दबाये", r"నొక్కండి", r"அழுத்தவும்", r"ಒತ್ತಿ(ರಿ)?", r"അമർത്തുക",
    ],
}
_AUTOMATED = {kind: [re.compile(p, re.IGNORECASE) for p in pats] for kind, pats in AUTOMATED_PATTERNS.items()}

# The network's recording while the customer has put us on hold (they took another call).
# On 9 Nov this played for 5 minutes and the agent kept answering it as if the customer spoke.
CARRIER_HOLD_PATTERNS = [
    r"put\s+(your|the)\s+call\s+on\s+hold", r"call\s+(has\s+been\s+|is\s+)?(put\s+)?on\s+hold",
    r"(please\s+)?stay\s+on\s+the\s+line", r"please\s+hold\s+the\s+line",
    r"hold\s+par\s+rakha", r"line\s+par\s+bane", r"होल्ड\s+पर", r"लाइन\s+पर\s+बने",
    r"హోల్డ్‌?\s*లో\s+(పెట్ట|ఉంచ)", r"లైన్‌?\s*లో\s+(ఉండండి|వేచి)",
]
_CARRIER_HOLD = [re.compile(p, re.IGNORECASE) for p in CARRIER_HOLD_PATTERNS]
CARRIER_HOLD_SECS = float(os.getenv("VOICE_CARRIER_HOLD_SECS", "45"))


def is_carrier_hold(text: str) -> bool:
    return any(p.search(text or "") for p in _CARRIER_HOLD)


def classify_automated(text: str) -> Optional[str]:
    """'unreachable' | 'voicemail' | 'ivr' when the text is a recording or menu, else None."""
    for kind in ("unreachable", "voicemail", "ivr"):
        if any(p.search(text or "") for p in _AUTOMATED[kind]):
            return kind
    return None


# ----------------------------------------------------------------------------- people

HOLD_PATTERNS = [
    r"\b(one|1|a)\s+(minute|min|sec|second|moment)\b", r"\bjust\s+a\s+(sec|second|minute|moment)\b",
    r"\bhold\s+on\b", r"^\s*wait\b", r"\bwait\s+wait\b", r"\bgive\s+me\s+a\s+(minute|second|moment)\b", r"\blet\s+me\s+check\b",
    r"एक\s+(मिनट|सेकंड|सेकेंड)", r"रुकि?ए|रुको|ज़?रा\s+रुक", r"\bek\s+(minute|min|second)\b", r"\bruk(o|iye|na)\b",
    r"ఒక్?క?\s*(నిమిషం|సెకన్|సెకండ్)", r"ఆగండి|ఉండండి|ఆగు|ఉండు", r"\bok+a\s+nimisham\b", r"\baa?gandi\b|\bundandi\b|\baa?gu\b|\bundu\b",
    r"ஒரு\s+(நிமிஷம்|நிமிடம்)", r"இருங்க", r"ಒಂದು\s+ನಿಮಿಷ", r"ഒരു\s+മിനിറ്റ്",
]
OPT_OUT_PATTERNS = [
    r"\b(don'?t|do\s+not|never|stop)\s+(call|calling|phone)", r"remove\s+my\s+number", r"\bunsubscribe\b",
    r"(कॉल|फो?न)\s+मत\s+(करना|करो|कीजिए|करें)", r"\b(call|phone)\s+mat\s+kar", r"दोबारा\s+मत",
    r"(కాల్|ఫోన్)\s+చేయ(కండి|వద్దు)", r"\b(call|phone)\s+chey+(akandi|avaddu)\b",
    r"(கால்|போன்)\s+பண்ணாதீங்க", r"ಕರೆ\s+ಮಾಡಬೇಡಿ", r"വിളിക്കരുത്",
]
HUMAN_PATTERNS = [
    r"\b(talk|speak)\s+to\s+(a\s+|the\s+|your\s+)?(human|person|manager|someone|real\s+person|executive)\b",
    r"\bare\s+you\s+a\s+(robot|machine|bot)\b", r"इंसान\s+से|मैनेजर\s+से|किसी\s+व्यक्ति",
    r"మనిషితో|మేనేజర్‌?తో", r"\b(manager|executive)\s+(ki|ko|tho)\b",
]
UPSET_PATTERNS = [
    r"\b(fraud|scam|cheat(er|ing)?|nonsense|stupid|idiot|irritat\w*|harass\w*|waste\s+of\s+time)\b",
    r"बकवास|धोखा|फ्रॉड|परेशान", r"మోసం|విసిగి|చిరాకు|ఫ్రాడ్", r"\b(bakwas|dhokha|pareshan)\b",
]
# Signs that STT heard noise or a broken line rather than clear speech
UNCLEAR_PATTERNS = [r"(\.\.\.|…).*(\.\.\.|…)", r"\[(noise|inaudible|unclear|music)\]", r"<unk>", r"\binaudible\b"]
_UNCLEAR = [re.compile(p, re.IGNORECASE) for p in UNCLEAR_PATTERNS]
_HOLD = [re.compile(p, re.IGNORECASE) for p in HOLD_PATTERNS]
_OPT_OUT = [re.compile(p, re.IGNORECASE) for p in OPT_OUT_PATTERNS]
_HUMAN = [re.compile(p, re.IGNORECASE) for p in HUMAN_PATTERNS]
_UPSET = [re.compile(p, re.IGNORECASE) for p in UPSET_PATTERNS]

NOT_INTERESTED_PATTERNS = [
    r"\bnot\s+interested\b", r"\bno\s+need\b", r"\bdon'?t\s+(need|want)\b",
    r"नहीं\s+चाहिए", r"ज़?रूरत\s+नहीं", r"दिलचस्पी\s+नहीं",
    r"వద్దు", r"అవసరం\s+లేదు", r"ఆసక్తి\s+లేదు", r"ఇంట్రెస్ట్\s+లేదు", r"కావాల్సిన\s+అవసరం\s+లేదు",
]
ASKS_SOMETHING = r"ఎంత|ఎప్పుడు|ఏంటి|ఎలా|ఎందుకు|చెప్పండి|ప్రైస్|how|what|when|why|price|tell|कितन|क्या|कब|बताइए"
NOT_INTERESTED_FIRST = ("This is their first no. Do NOT say goodbye yet. Respect it in a few words, then ask one short "
                        "question: why, or what they use today, or if details on WhatsApp or a later call would help.")
NOT_INTERESTED_AGAIN = "They have said no again. Thank them, say goodbye and add [CALL_COMPLETED]. Do not try again."
_NOT_INTERESTED = [re.compile(p, re.IGNORECASE) for p in NOT_INTERESTED_PATTERNS]
_ASKS_SOMETHING = re.compile(ASKS_SOMETHING, re.IGNORECASE)
# "call me tomorrow at 4": a time word and a call-me-back request together
CALLBACK_PATTERNS = [
    r"call\s*(me|back).*(tomorrow|evening|morning|today|\d)",
    r"(రేపు|సాయంత్రం|ఉదయం|మధ్యాహ్నం|రాత్రి|గంటలకు|గంటలకి|ఈవినింగ్|సోమవారం|tomorrow|evening|morning|\d\s*(pm|am|o'?clock)).*"
    r"(కాల్\s*చే|ఫోన్\s*చే|call\s*(me|back|cheyy?andi)|कॉल\s*कर|फोन\s*कर)",
]
_CALLBACK = [re.compile(p, re.IGNORECASE) for p in CALLBACK_PATTERNS]

HINTS = {
    "callback": ("The customer asked to be called back at a time. If they gave a time, confirm it in one short "
                 "sentence with NO question after it, say goodbye, and add [CALLBACK: YYYY-MM-DD HH:MM] "
                 "[CALL_COMPLETED]. If they gave no exact time, ask only for the time."),
    "hold": "The customer asked you to wait. Say only a very short 'sure, take your time' and wait silently.",
    "opt_out": ("The customer may be asking not to be called again. If so, apologise once, confirm their number "
                "will not be called again, say goodbye and add [DO_NOT_CALL] [CALL_COMPLETED]."),
    "human": ("The customer wants a human. Say a team member will call them back soon, ask the best time "
              "if they haven't said it, and add [HUMAN_HANDOFF]."),
    "unclear": ("The audio was broken or noisy. Do not guess what they meant: say you couldn't hear clearly "
                "and ask them to repeat."),
    "upset": ("The customer sounds upset. Stay calm and respectful, apologise briefly, do not argue or "
              "push the sale; offer to call later or stop calling."),
}


def is_hold_request(text: str) -> bool:
    """
    A short 'one minute / hold on'. Longer sentences that merely contain 'wait' are real requests:
    "ఆగండి ఆగండి, ముందు ప్రైస్ ఎంతో చెప్పండి" asks for the price, and must not get "take your time".
    """
    words = (text or "").split()
    if not 0 < len(words) <= 5 or _ASKS_SOMETHING.search(text):
        return False
    return any(p.search(text) for p in _HOLD)


def caller_signals(text: str) -> List[str]:
    """Which behaviours this message shows: hold, opt_out, human, upset, unclear, not_interested, callback."""
    found = []
    if is_hold_request(text):
        found.append("hold")
    for name, patterns in (("opt_out", _OPT_OUT), ("human", _HUMAN), ("upset", _UPSET), ("unclear", _UNCLEAR),
                           ("not_interested", _NOT_INTERESTED), ("callback", _CALLBACK)):
        if any(p.search(text or "") for p in patterns):
            found.append(name)
    return found


def caller_hints(text: str, not_interested_before: bool = False) -> Optional[str]:
    signals = caller_signals(text)
    if "opt_out" in signals and "not_interested" in signals:
        signals.remove("not_interested")  # "don't call me" is stronger: no second attempt
    parts = [HINTS[s] for s in signals if s != "not_interested"]
    if "not_interested" in signals:
        parts.append(NOT_INTERESTED_AGAIN if not_interested_before else NOT_INTERESTED_FIRST)
    return " ".join(parts) or None


# ----------------------------------------------------------------------------- processor

AutomatedCallback = Callable[[str, str], Awaitable[None]]


class CallGuard(FrameProcessor):
    """
    Watches the first caller transcripts of an outbound call for voicemail, IVR menus
    and carrier messages. A match is swallowed (the LLM never answers a machine) and
    reported once through `on_automated(kind, text)`; the session then ends the call.

    At any time in the call, the network's "your call is on hold" recording is swallowed too.
    If the customer doesn't come back within hold_secs, it is reported as "customer_hold".
    """

    def __init__(self, on_automated: AutomatedCallback, window_secs: float = 30.0,
                 max_transcripts: int = 3, enabled: bool = True, hold_secs: Optional[float] = None, **kwargs):
        super().__init__(**kwargs)
        self._on_automated = on_automated
        self._window_secs = window_secs
        self._max_transcripts = max_transcripts
        self._enabled = enabled
        self._hold_secs = CARRIER_HOLD_SECS if hold_secs is None else hold_secs
        self._hold_timer: Optional[asyncio.Task] = None
        self._started = time.monotonic()
        self._seen = 0
        self.detected: Optional[str] = None

    async def _end_after_hold(self, text: str):
        await asyncio.sleep(self._hold_secs)
        if not self.detected:
            self.detected = "customer_hold"
            await self._on_automated("customer_hold", text)

    def _customer_back(self):
        if self._hold_timer:
            self._hold_timer.cancel()
            self._hold_timer = None

    def restart_window(self):
        """Start the detection window when the call is answered (not when the pipeline is built)."""
        self._started = time.monotonic()
        self._seen = 0

    def _watching(self) -> bool:
        return (self._enabled and self._seen < self._max_transcripts
                and time.monotonic() - self._started <= self._window_secs)

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame) and frame.text.strip():
            if self.detected:
                return  # call is ending; nothing more goes to the LLM
            if self._hold_secs > 0 and is_carrier_hold(frame.text):
                if not self._hold_timer:
                    self._hold_timer = asyncio.create_task(self._end_after_hold(frame.text.strip()))
                return
            self._customer_back()
            if self._watching():
                self._seen += 1
                kind = classify_automated(frame.text)
                if kind:
                    self.detected = kind
                    await self._on_automated(kind, frame.text.strip())
                    return

        await self.push_frame(frame, direction)
