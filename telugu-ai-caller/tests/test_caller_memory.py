"""
Caller memory (services/followup_engine.py): follow-up calls may pick up where the last call
ended but must never invent what the customer said. 6 Nov: after a first call where the customer
only said "Hello" and "Hmm", the second call opened with "last time you showed interest in a website".
"""

import json

from core.db import SessionLocal
from database import get_last_call_facts
from models import Call
from services.followup_engine import build_caller_memory_context
from tests.test_dialer import make_lead

REAL = {"talk_seconds": 95, "substantive_turns": 4}
THIN = {"talk_seconds": 53, "substantive_turns": 0}  # a call of "Hello", "Hmm", "हाँ"


def lead(**extra):
    return {"name": "Ravi", "last_call_summary": "Client asked about an online store.", "service_needed": "website",
            "outcome_label": "interested_later", **extra}


def test_call_with_no_real_conversation_gives_no_facts():
    memory = build_caller_memory_context(lead(last_call_facts=THIN))
    assert "no real conversation" in memory and "first conversation" in memory
    assert "online store" not in memory and "website" not in memory  # nothing to repeat back


def test_short_call_gives_no_facts_even_if_the_customer_spoke():
    assert "no real conversation" in build_caller_memory_context(
        lead(last_call_facts={"talk_seconds": 12, "substantive_turns": 3}))


def test_real_conversation_is_offered_as_something_to_confirm():
    memory = build_caller_memory_context(lead(last_call_facts=REAL))
    assert "online store" in memory and "NOT confirmed by the customer" in memory
    assert "only as a question for the customer to confirm" in memory
    assert "Last time we spoke you mentioned" not in memory  # the old instruction that caused the invention


def test_unknown_history_keeps_the_notes_but_stays_cautious():
    memory = build_caller_memory_context(lead())  # no last_call_facts key (older callers)
    assert "online store" in memory and "never say 'you told me'" in memory.lower().replace("‘", "'") or "Never say 'you told me'" in memory


def test_never_called_lead_has_no_memory():
    assert build_caller_memory_context({"name": "New Nani"}) == ""


def test_last_call_facts_counts_only_real_sentences():
    lead_id = make_lead(name="Facts Fatima", phone="+919812300401")
    turns = [{"role": "assistant", "content": "Namaskaram"}, {"role": "user", "content": "Hello"},
             {"role": "user", "content": "हाँ।"}, {"role": "user", "content": "నాకు ఒక వెబ్‌సైట్ కావాలి అండి"},
             {"role": "user", "content": "I need it by next month"}]
    session = SessionLocal()
    session.query(Call).filter(Call.lead_id == lead_id).delete()  # ids can be reused across tests
    session.add(Call(account_id=1, lead_id=lead_id, talk_seconds=70, outcome="follow_up",
                     transcript=json.dumps(turns, ensure_ascii=False)))
    session.commit()
    session.close()
    facts = get_last_call_facts(lead_id)
    assert facts == {"talk_seconds": 70, "substantive_turns": 2, "outcome": "follow_up"}
    assert get_last_call_facts(make_lead(name="Never Nila", phone="+919812300402")) is None
