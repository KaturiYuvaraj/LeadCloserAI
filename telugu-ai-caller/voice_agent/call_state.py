"""
Shreya 2.0 context engine: a short, structured picture of the call so far, given to the AI with every
customer message ("CALL STATE"). It is built from what was said, with simple rules (no extra AI call, so no
added delay or cost):

  known      name, language, what they need, platform, business, when to start, WhatsApp confirmed
  asked      which of our questions were already asked, and how often (so she never asks a third time)
  decided    meeting or callback booked, Do-Not-Call, contact saved
  signals    price asked, said no, upset

18 Nov calls: name and WhatsApp were asked three times after "yes", and old details were stated as facts.
"""

import re
from typing import Dict, List, Optional

# (?![a-zA-Z0-9_]) instead of \b: Telugu and Hindi vowel signs are not "word" characters for \b
YES = re.compile(r"^\W*(yes|yeah|yep|ok(ay)?|sure|same|correct|haan|ha|అవునండి|అవును|హా|ఆ|ఉందండి|ఉంది|ఓకే|సరే|"
                 r"जी\s+हाँ|हाँ|हां|जी|वही|ठीक)(?![a-zA-Z0-9_])", re.IGNORECASE)

# what the customer says they need
NEEDS = {
    "website": r"website|వెబ్‌?సైట్|वेबसाइट|site\b",
    "mobile app": r"\bapp\b|application|యాప్|అప్లికేషన్|ऐप|एप्लीकेशन",
    "e-commerce": r"e-?\s?commerce|online\s+store|ఈ-?కామర్స్|ई-?कॉमर्स",
    "CRM": r"\bcrm\b",
    "ERP": r"\berp\b",
    "social media / ads": r"social\s+media|instagram|facebook|meta\s+ads|google\s+ads|marketing|మార్కెటింగ్|मार्केटिंग|ads?\b",
    "software": r"software|సాఫ్ట్‌?వేర్|सॉफ्टवेयर",
}
PLATFORM = {
    "Android + iPhone": r"(both|రెండు|రెండిటికీ|రెండింటికీ|दोनों|2\s*(కావాల|platforms?))|"
                        r"(android.*(ios|iphone))|((ios|iphone).*android)",
    "Android only": r"android\s+(only|మాత్రమే)|only\s+android",
}
TIMELINE = (r"immediate|urgent|asap|this\s+week|next\s+week|\d+\s*(day|week|month)s?|"
            r"తొందరగా|వెంటనే|వారం|నెల|ఇమీడియట్|తక్షణ|जल्दी|तुरंत|हफ्ते|महीने")

# our questions, by topic
ASKED = {
    "name": r"(your|మీ|आपका|आपकी)\s*(good\s+)?name|పేరు|नाम",
    "WhatsApp": r"whatsapp|వాట్సాప్|व्हाट्सऐप",
    "day and time": r"(what|which)\s+(day|time)|ఏ\s*(రోజు|టైమ్|time|day)|कौन\s*सा\s*(दिन|समय|time)|convenient|వీలవుతుంది",
    "what they need": r"(website|app).*(need|want|కావాలా|అవసరం)|ఏం\s+(కావాలి|అవసరం)|क्या\s+चाहिए",
    "platform": r"android.*(iphone|ios)|(iphone|ios).*android",
    # 25 Nov eval 35: "మీది ఏ business అండి?" three times in a row was not recognised
    "their business": r"(what|which)\s+(kind\s+of\s+)?business|business\s+do\s+you|your\s+business|"
                      r"(business|బిజినెస్)\s+(ఏంటి|ఏమిటి|ఎలాంటి|ఏంటో|ఏమిటో|దేని)|ఏ\s*(business|బిజినెస్)|"
                      r"कौन\s*सा\s*(बिज़?नेस|business)|(business|बिज़?नेस)\s+(किस|क्या)",
    "when to start": r"timeline|when.*(start|launch|ready)|ఎప్పటి(లోగా|కి)|ఎంత\s+(టైమ్|time)|कब\s+तक",
}


def _match(patterns: Dict[str, str], text: str) -> List[str]:
    return [k for k, p in patterns.items() if re.search(p, text or "", re.IGNORECASE)]


class CallState:
    def __init__(self, name: str = "", language: str = ""):
        self.name = name
        self.language = language
        self.needs: List[str] = []
        self.platform = ""
        self.timeline = ""
        self.whatsapp_confirmed = False
        self.asked: Dict[str, int] = {}
        self.last_asked: List[str] = []
        self.decided: List[str] = []
        self.price_asked = False
        self.said_no = 0
        self.upset = False

    # ------------------------------------------------------------------ updates
    def on_customer(self, text: str, language: str = "", signals: Optional[List[str]] = None):
        text = text or ""
        if language:
            self.language = language
        for need in _match(NEEDS, text):
            if need not in self.needs:
                self.needs.append(need)
        platform = _match(PLATFORM, text)
        if platform:
            self.platform = platform[0]
        m = re.search(TIMELINE, text, re.IGNORECASE)
        if m and not self.timeline:
            self.timeline = m.group(0)
        if "WhatsApp" in self.last_asked and YES.search(text):
            self.whatsapp_confirmed = True
        signals = signals or []
        if "not_interested" in signals:
            self.said_no += 1
        if "upset" in signals:
            self.upset = True

    def on_reply(self, text: str):
        """Our own reply: which questions did it ask? (only the question sentences count)"""
        questions = " ".join(re.findall(r"[^.!?।]*\?", text or ""))
        self.last_asked = _match(ASKED, questions)
        for topic in self.last_asked:
            self.asked[topic] = self.asked.get(topic, 0) + 1

    def on_action(self, tag: str, arg: str = ""):
        tag = (tag or "").upper()
        if tag == "CONTACT":
            self.whatsapp_confirmed = True
            name = (arg or "").split("|")[0].strip()
            if name and name.lower() != "same":
                self.name = name
            self.decided.append("contact saved")
        elif tag in ("MEETING", "CALLBACK"):
            self.decided.append(f"{tag.lower()} {arg}".strip())
        elif tag == "DO_NOT_CALL":
            self.decided.append("do not call again")

    # ------------------------------------------------------------------ for the AI
    def summary(self) -> str:
        known = []
        if self.name:
            known.append(f"name {self.name} (don't ask)")
        if self.needs:
            known.append("needs " + ", ".join(self.needs))
        if self.platform:
            known.append(self.platform)
        if self.timeline:
            known.append(f"start: {self.timeline}")
        if self.whatsapp_confirmed:
            known.append("WhatsApp confirmed (don't ask again)")
        parts = []
        if known:
            parts.append("Known: " + "; ".join(known) + ".")
        stop = [t for t, n in self.asked.items() if n >= 2 or (t == "WhatsApp" and self.whatsapp_confirmed)
                or (t == "name" and self.name)]
        if stop:
            parts.append("Don't ask again: " + ", ".join(stop) + ".")
        recent = [t for t in self.last_asked if t not in stop]
        if recent:
            parts.append("Your last reply asked about " + ", ".join(recent)
                         + ". Do NOT ask about " + ", ".join(recent) + " in this reply, in any words. If they didn't "
                         "answer it, answer what they said and ask about something else, or ask nothing.")
        if self.decided:
            parts.append("Decided: " + "; ".join(self.decided) + ".")
        flags = []
        if self.price_asked:
            flags.append("they asked about price")
        if self.said_no:
            flags.append(f"said no {self.said_no}x")
        if self.upset:
            flags.append("was upset")
        if flags:
            parts.append("Notes: " + ", ".join(flags) + ".")
        return ("CALL STATE: " + " ".join(parts)) if parts else ""
