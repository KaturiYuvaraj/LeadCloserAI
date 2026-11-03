"""
Detects the AI ending the conversation and the actions it takes during the call.

The sales prompt tells the LLM to finish its goodbye with the marker
[CALL_COMPLETED] (services/sales_agent.py). The live-call rules add action markers
the LLM writes at the end of a reply when something must happen in the CRM:

  [CALLBACK: 2026-11-04 17:30]   call the lead again at that IST time
  [MEETING: 2026-11-05 11:00]    a meeting / demo was agreed
  [DO_NOT_CALL]                  the customer asked never to be called again
  [HUMAN_HANDOFF]                the customer wants a person from the team
  [WRONG_PERSON]                 someone other than the lead answered
  [SEND_WHATSAPP: quotation]     send details / a quotation on WhatsApp

With streaming, a marker can arrive split across tokens ("[CALL", "_COMPLETED]"),
so this processor holds back any text that could be the start of a marker,
removes markers so they are never spoken or stored, and reports them when the
reply ends: actions first, then the conclusion.
"""

import re
from typing import Awaitable, Callable, List, Optional, Tuple

from pipecat.frames.frames import (
    Frame,
    InterruptionFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

CALL_COMPLETED_MARKER = "[CALL_COMPLETED]"
ACTION_TAGS = ("CALL_COMPLETED", "CALLBACK", "MEETING", "DO_NOT_CALL", "HUMAN_HANDOFF",
               "WRONG_PERSON", "SEND_WHATSAPP")
_TAG_RE = re.compile(r"^\s*(" + "|".join(ACTION_TAGS) + r")\s*(?::\s*(.*?))?\s*$", re.IGNORECASE)
MAX_MARKER_CHARS = 80

Action = Tuple[str, str]  # (TAG, argument)


def split_marker(text: str, marker: str = CALL_COMPLETED_MARKER) -> tuple[str, str, bool]:
    """
    Remove complete markers from `text`.
    Returns (text_to_emit, text_to_hold, marker_found). `text_to_hold` is a trailing
    piece that could still become the marker once more tokens arrive.
    """
    found = marker in text
    text = text.replace(marker, "")
    for size in range(min(len(marker) - 1, len(text)), 0, -1):
        if marker.startswith(text[-size:]):
            return text[:-size], text[-size:], found
    return text, "", found


def _could_become_tag(partial: str) -> bool:
    """'[CALL' or '[CALLBACK: 2026-1' may still turn into a marker; '[about' cannot."""
    body = partial[1:].lstrip()
    if len(partial) > MAX_MARKER_CHARS:
        return False
    name = body.split(":", 1)[0].strip().upper()
    if ":" in body:
        return name in ACTION_TAGS
    return any(tag.startswith(name) for tag in ACTION_TAGS)


def split_actions(text: str) -> tuple[str, str, List[Action]]:
    """
    Remove complete action markers from `text`.
    Returns (text_to_emit, text_to_hold, actions) where `text_to_hold` is a trailing
    '[…' that could still become a marker.
    """
    out: List[str] = []
    actions: List[Action] = []
    pos = 0
    while True:
        start = text.find("[", pos)
        if start < 0:
            out.append(text[pos:])
            return "".join(out), "", actions
        out.append(text[pos:start])
        end = text.find("]", start)
        if end < 0:
            rest = text[start:]
            if _could_become_tag(rest):
                return "".join(out), rest, actions
            out.append("[")
            pos = start + 1
            continue
        match = _TAG_RE.match(text[start + 1:end])
        if match:
            actions.append((match.group(1).upper(), (match.group(2) or "").strip()))
        else:
            out.append(text[start:end + 1])
        pos = end + 1


# "We won't call you again" in the languages we speak: the promise must be kept even if the marker is missing
NO_MORE_CALLS = re.compile(
    r"(won'?t|will\s+not|never)\s+(call|contact|disturb)|not\s+be\s+(called|contacted)|"
    r"दोबारा\s+(कॉल|फोन)\s+नहीं|कॉल\s+नहीं\s+कर(ेंगे|ूँगा|ूंगा|ूँगी)|"
    r"మళ్ళీ\s+(కాల్|ఫోన్)\s+చేయ(ము|మం|బోము)",
    re.IGNORECASE,
)


def guard_actions(spoken: str, actions: List[Action]) -> List[Action]:
    """
    Safety rules on top of the LLM's markers:
      - a reply that ends with a question never hangs up (the customer must be able to answer),
        and books nothing: a callback or meeting it mentions is only a proposal so far;
      - a reply that promises no more calls always records Do-Not-Call.
    """
    tags = [tag for tag, _ in actions]
    if spoken.strip().endswith(("?", "？")):
        actions = [a for a in actions if a[0] not in ("CALL_COMPLETED", "CALLBACK", "MEETING")]
    if NO_MORE_CALLS.search(spoken) and "DO_NOT_CALL" not in tags:
        actions = [("DO_NOT_CALL", "")] + actions
    return actions


ActionCallback = Callable[[str, str], Awaitable[None]]


class CallConclusionFilter(FrameProcessor):
    """Strips action markers from streamed replies and reports them when the reply ends."""

    def __init__(self, on_concluded: Callable[[], Awaitable[None]],
                 on_action: Optional[ActionCallback] = None, **kwargs):
        super().__init__(**kwargs)
        self._on_concluded = on_concluded
        self._on_action = on_action
        self._held = ""
        self._spoken = ""
        self._actions: List[Action] = []

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, LLMFullResponseStartFrame):
            self._held, self._spoken, self._actions = "", "", []
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, LLMTextFrame):
            emit, self._held, actions = split_actions(self._held + frame.text)
            self._actions.extend(actions)
            self._spoken += emit
            if emit:
                await self.push_frame(LLMTextFrame(emit), direction)
            return

        if isinstance(frame, LLMFullResponseEndFrame):
            leftover, self._held = self._held, ""
            if leftover and not _could_become_tag(leftover):
                self._spoken += leftover
                await self.push_frame(LLMTextFrame(leftover), direction)
            await self.push_frame(frame, direction)
            actions, self._actions = self._actions, []
            spoken, self._spoken = self._spoken, ""
            actions = guard_actions(spoken, actions)
            concluded = False
            for tag, arg in actions:
                if tag == "CALL_COMPLETED":
                    concluded = True
                elif self._on_action:
                    await self._on_action(tag, arg)
            if concluded:
                await self._on_concluded()
            return

        if isinstance(frame, InterruptionFrame):
            self._held, self._spoken, self._actions = "", "", []

        await self.push_frame(frame, direction)
