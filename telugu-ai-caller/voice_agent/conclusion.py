"""
Detects the AI ending the conversation.

The sales prompt tells the LLM to finish its goodbye with the marker
[CALL_COMPLETED] (services/sales_agent.py). With streaming, the marker can arrive
split across tokens ("[CALL", "_COMPLETED]"), so this processor holds back any
text that could be the start of the marker, removes the marker so it is never
spoken or stored, and reports the conclusion when the reply ends.
"""

from typing import Awaitable, Callable

from pipecat.frames.frames import (
    Frame,
    InterruptionFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

CALL_COMPLETED_MARKER = "[CALL_COMPLETED]"


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


class CallConclusionFilter(FrameProcessor):
    """Strips [CALL_COMPLETED] from streamed replies and reports when it was said."""

    def __init__(self, on_concluded: Callable[[], Awaitable[None]], **kwargs):
        super().__init__(**kwargs)
        self._on_concluded = on_concluded
        self._held = ""
        self._found = False

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, LLMFullResponseStartFrame):
            self._held, self._found = "", False
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, LLMTextFrame):
            emit, self._held, found = split_marker(self._held + frame.text)
            self._found = self._found or found
            if emit:
                await self.push_frame(LLMTextFrame(emit), direction)
            return

        if isinstance(frame, LLMFullResponseEndFrame):
            leftover = self._held.replace(CALL_COMPLETED_MARKER, "")
            self._held = ""
            if leftover:
                await self.push_frame(LLMTextFrame(leftover), direction)
            await self.push_frame(frame, direction)
            if self._found:
                self._found = False
                await self._on_concluded()
            return

        if isinstance(frame, InterruptionFrame):
            self._held, self._found = "", False

        await self.push_frame(frame, direction)
