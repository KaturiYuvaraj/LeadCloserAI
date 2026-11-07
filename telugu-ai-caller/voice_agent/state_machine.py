"""
Real-Time Conversation State Machine (Phase 8).
Manages explicit conversational states, enforces valid lifecycle transitions,
tracks duration in each state, and records diagnostic audit events.
"""

from enum import Enum
import time
from typing import Callable, Dict, List, Optional, Set, Any
from loguru import logger


class ConversationState(str, Enum):
    INITIALIZING = "INITIALIZING"
    CALL_CONNECTING = "CALL_CONNECTING"
    CALL_CONNECTED = "CALL_CONNECTED"
    GREETING = "GREETING"
    LISTENING = "LISTENING"
    SPEECH_DETECTED = "SPEECH_DETECTED"
    PROCESSING = "PROCESSING"
    GENERATING_RESPONSE = "GENERATING_RESPONSE"
    SPEAKING = "SPEAKING"
    INTERRUPTED = "INTERRUPTED"
    RECOVERING = "RECOVERING"
    CALL_ENDING = "CALL_ENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


VALID_TRANSITIONS: Dict[ConversationState, Set[ConversationState]] = {
    ConversationState.INITIALIZING: {
        ConversationState.CALL_CONNECTING,
        ConversationState.CALL_CONNECTED,
        ConversationState.FAILED,
    },
    ConversationState.CALL_CONNECTING: {
        ConversationState.CALL_CONNECTED,
        ConversationState.CALL_ENDING,
        ConversationState.FAILED,
    },
    ConversationState.CALL_CONNECTED: {
        ConversationState.GREETING,
        ConversationState.LISTENING,
        ConversationState.CALL_ENDING,
        ConversationState.FAILED,
    },
    ConversationState.GREETING: {
        ConversationState.SPEAKING,
        ConversationState.LISTENING,
        ConversationState.INTERRUPTED,
        ConversationState.CALL_ENDING,
        ConversationState.FAILED,
    },
    ConversationState.LISTENING: {
        ConversationState.SPEECH_DETECTED,
        ConversationState.PROCESSING,
        ConversationState.INTERRUPTED,
        ConversationState.RECOVERING,
        ConversationState.CALL_ENDING,
        ConversationState.COMPLETED,
        ConversationState.FAILED,
    },
    ConversationState.SPEECH_DETECTED: {
        ConversationState.PROCESSING,
        ConversationState.LISTENING,
        ConversationState.INTERRUPTED,
        ConversationState.RECOVERING,
        ConversationState.CALL_ENDING,
        ConversationState.FAILED,
    },
    ConversationState.PROCESSING: {
        ConversationState.GENERATING_RESPONSE,
        ConversationState.LISTENING,
        ConversationState.SPEAKING,
        ConversationState.RECOVERING,
        ConversationState.CALL_ENDING,
        ConversationState.FAILED,
    },
    ConversationState.GENERATING_RESPONSE: {
        ConversationState.SPEAKING,
        ConversationState.INTERRUPTED,
        ConversationState.RECOVERING,
        ConversationState.LISTENING,
        ConversationState.CALL_ENDING,
        ConversationState.FAILED,
    },
    ConversationState.SPEAKING: {
        ConversationState.LISTENING,
        ConversationState.INTERRUPTED,
        ConversationState.RECOVERING,
        ConversationState.CALL_ENDING,
        ConversationState.COMPLETED,
        ConversationState.FAILED,
    },
    ConversationState.INTERRUPTED: {
        ConversationState.LISTENING,
        ConversationState.SPEECH_DETECTED,
        ConversationState.PROCESSING,
        ConversationState.RECOVERING,
        ConversationState.CALL_ENDING,
        ConversationState.FAILED,
    },
    ConversationState.RECOVERING: {
        ConversationState.LISTENING,
        ConversationState.SPEAKING,
        ConversationState.CALL_ENDING,
        ConversationState.FAILED,
    },
    ConversationState.CALL_ENDING: {
        ConversationState.COMPLETED,
        ConversationState.FAILED,
    },
    ConversationState.COMPLETED: set(),
    ConversationState.FAILED: set(),
}


class CallStateMachine:
    """Explicit state machine governing call lifecycles, timing, and transitions."""

    def __init__(self, session_id: str, on_state_change: Optional[Callable[[ConversationState, ConversationState, Dict[str, Any]], None]] = None):
        self.session_id = session_id
        self._state = ConversationState.INITIALIZING
        self._on_state_change = on_state_change
        self._history: List[Dict[str, Any]] = []
        self._last_transition_time = time.time()
        self.record_event("STATE_INITIALIZED", {"initial_state": self._state.value})

    @property
    def current_state(self) -> ConversationState:
        return self._state

    def is_active(self) -> bool:
        return self._state not in (ConversationState.COMPLETED, ConversationState.FAILED, ConversationState.CALL_ENDING)

    def is_speaking(self) -> bool:
        return self._state in (ConversationState.SPEAKING, ConversationState.GREETING)

    def is_listening(self) -> bool:
        return self._state in (ConversationState.LISTENING, ConversationState.SPEECH_DETECTED)

    def transition_to(self, new_state: ConversationState, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Attempt to transition to new_state. Returns True if transition was accepted, False otherwise."""
        if self._state == new_state:
            return True  # No-op re-entry

        allowed = VALID_TRANSITIONS.get(self._state, set())
        # Always allow transitioning to terminal failure/ending from any non-terminal state
        if new_state in (ConversationState.CALL_ENDING, ConversationState.FAILED) and self.is_active():
            pass
        elif new_state not in allowed:
            logger.warning(
                f"[StateMachine:{self.session_id[:8]}] Invalid transition attempted: {self._state.value} -> {new_state.value}. Allowed: {[s.value for s in allowed]}"
            )
            return False

        now = time.time()
        duration_in_prev = round(now - self._last_transition_time, 3)
        old_state = self._state
        self._state = new_state
        self._last_transition_time = now

        meta = metadata or {}
        event_record = {
            "timestamp": now,
            "session_id": self.session_id,
            "from_state": old_state.value,
            "to_state": new_state.value,
            "duration_in_previous_sec": duration_in_prev,
            "metadata": meta,
        }
        self._history.append(event_record)
        logger.debug(
            f"[StateMachine:{self.session_id[:8]}] {old_state.value} -> {new_state.value} (spent {duration_in_prev}s)"
        )

        if self._on_state_change:
            try:
                self._on_state_change(old_state, new_state, meta)
            except Exception as e:
                logger.error(f"[StateMachine:{self.session_id[:8]}] Error in on_state_change callback: {e}")

        return True

    def record_event(self, event_name: str, payload: Optional[Dict[str, Any]] = None):
        """Record diagnostic event in timeline."""
        record = {
            "timestamp": time.time(),
            "session_id": self.session_id,
            "event": event_name,
            "state": self._state.value,
            "data": payload or {},
        }
        self._history.append(record)

    def get_timeline(self) -> List[Dict[str, Any]]:
        return list(self._history)
