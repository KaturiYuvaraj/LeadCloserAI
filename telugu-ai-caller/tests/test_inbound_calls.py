"""
Inbound calls: a customer who calls our number is greeted as a caller (not pitched at), unknown
numbers become leads, and the lead belongs to the company that owns the number they called.
Offline: no call is placed and Sarvam is not contacted.
"""

import asyncio
from types import SimpleNamespace

from core.db import SessionLocal
from models import Account, Lead, Number
from tests.test_dialer import make_lead
from voice_agent.session import (
    INBOUND_GREETING, INBOUND_GREETING_KNOWN, INBOUND_NAME_PREFIX, VOICES, BaseCallSession,
    is_placeholder_name, lead_for_inbound_call, live_rules,
)


def lead_count(phone_digits):
    session = SessionLocal()
    try:
        return sum(1 for (p,) in session.query(Lead.phone_e164).all() if str(p).endswith(phone_digits))
    finally:
        session.close()


def test_unknown_caller_becomes_a_lead_once():
    lead, created = lead_for_inbound_call("+919812300501", "+917965482229")
    assert created and lead["name"] == f"{INBOUND_NAME_PREFIX}9812300501" and lead["phone"].endswith("9812300501")
    assert is_placeholder_name(lead["name"])
    again, created_again = lead_for_inbound_call("09812300501", "+917965482229")  # same number, other format
    assert not created_again and again["id"] == lead["id"] and lead_count("9812300501") == 1


def test_existing_lead_is_recognised():
    lead_id = make_lead(name="Known Kamal", phone="+919812300502")
    lead, created = lead_for_inbound_call("+919812300502", "+917965482229")
    assert not created and lead["id"] == lead_id and lead["name"] == "Known Kamal"


def test_hidden_or_invalid_numbers_create_nothing():
    assert lead_for_inbound_call("", "+917965482229") == (None, False)
    assert lead_for_inbound_call("anonymous", "+917965482229") == (None, False)
    assert lead_for_inbound_call("12345", "+917965482229") == (None, False)


def test_new_lead_is_filed_under_the_company_that_owns_the_called_number():
    session = SessionLocal()
    other = Account(name="Inbound Test Co", calling_approved=True)
    session.add(other)
    session.commit()
    session.add(Number(e164="+917965480099", provider="vobiz", account_id=other.id, status="active"))
    session.commit()
    other_id = other.id
    session.close()
    lead, created = lead_for_inbound_call("+919812300503", "917965480099")
    assert created
    session = SessionLocal()
    assert session.get(Lead, lead["id"]).account_id == other_id
    session.close()


def test_every_language_has_both_greetings_and_a_voice():
    for lang in VOICES:
        assert "{company}" in INBOUND_GREETING[lang] and "{name}" in INBOUND_GREETING_KNOWN[lang]
        assert "website" not in INBOUND_GREETING[lang].lower()  # a caller is not pitched at


def test_prompt_does_not_assume_what_an_unknown_caller_wants():
    rules = live_rules({"name": f"{INBOUND_NAME_PREFIX}9812300501"}, "in")
    assert "do not know their name" in rules and "Do not assume they want a website" in rules
    assert "Inbound caller" not in rules


def test_returning_lead_is_greeted_by_name_without_a_pitch():
    rules = live_rules({"name": "Known Kamal"}, "in")
    assert "Known Kamal called you back" in rules and "listen first" in rules


def _greeting(lead, language="te-IN", direction="in"):
    fake = SimpleNamespace(lead=lead, direction=direction, language=language, lead_id=(lead or {}).get("id"),
                           employee={"greeting": "OUTBOUND PITCH", "language": language},
                           knowledge=SimpleNamespace(prompt_section=lambda: ""))
    return asyncio.run(BaseCallSession._build_prompt_and_greeting(fake))


def test_inbound_greeting_replaces_the_outbound_pitch():
    prompt, greeting = _greeting({"id": 1, "name": f"{INBOUND_NAME_PREFIX}9812300501"}, "en-IN")
    assert "Thank you for calling" in greeting and "OUTBOUND PITCH" not in greeting
    assert "this call is recorded" in greeting.lower()  # the recording notice is still said once
    assert "CURRENT LEAD PROFILE" not in prompt  # no fake profile for a stranger
    _, known = _greeting({"id": 2, "name": "Known Kamal"}, "en-IN")
    assert known.startswith("Hello Known Kamal! Thanks for calling back")


def test_outbound_greeting_is_unchanged():
    _, greeting = _greeting({"id": 3, "name": "Out Omkar"}, "te-IN", direction="out")
    assert greeting.startswith("OUTBOUND PITCH")
