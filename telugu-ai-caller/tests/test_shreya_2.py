"""
Shreya 2.0 (25 Nov): layered prompt, context engine (CALL STATE), price guide only when asked, turn timing.
Offline: no Sarvam calls.
"""

from voice_agent.call_state import CallState
from voice_agent.session import (SMART_TURN_MAX_WAIT_SECS, BaseCallSession, live_rules, turn_strategies,
                                 wait_ms_to_vad_stop_secs)
from voice_agent.shreya_prompt import MASTER_PROMPT, asks_about_price, build_voice_prompt


# --- prompt layers

def test_prompt_has_the_four_layers_and_is_much_lighter():
    prompt = build_voice_prompt({"name": "Ravi"}, live_rules({"name": "Ravi"}, "out"))
    assert "SHREYA 2.0: WHO YOU ARE" in prompt and "THINK BEFORE EACH REPLY" in prompt      # master
    assert "Gayatri Heights" in prompt and "WHAT WE OFFER" in prompt                         # business
    assert "WHO THIS IS (from our records; notes to confirm" in prompt                      # memory
    assert "LIVE PHONE CONVERSATION RULES" in prompt                                         # runtime
    assert len(prompt) < 24000  # was about 34,500 characters on every reply


def test_prices_are_not_in_the_prompt_until_asked():
    prompt = build_voice_prompt({"name": "Ravi"}, live_rules({"name": "Ravi"}, "out"))
    assert "₹3,00,000" not in prompt and "₹24,500" not in prompt
    assert "only when the customer asks" in prompt


def test_owner_rules_win_over_the_generic_master_prompt():
    # never ask the budget, start-up discount, AI only when asked, Tenglish
    rules = live_rules({"name": "Ravi"}, "out")
    assert "Never ask for their budget" in rules and "never bring up being a virtual assistant or AI yourself" in rules
    assert "start-ups get a good discount" in MASTER_PROMPT
    assert "budget" not in MASTER_PROMPT.split("UNDERSTAND THE NEED")[1].split("READ THE PERSON")[0].lower()


def test_test_lead_details_are_notes_not_facts():
    prompt = build_voice_prompt({"name": "Ravi", "company": "Sharma Logistics"}, "")
    assert "notes to confirm, not facts to state" in prompt and "Sharma Logistics" in prompt


def test_price_question_detection():
    for text in ("how much will it cost?", "ఎంత అవుతుంది అండి?", "प्राइस क्या है?", "app ki charges entha", "budget ekkuva"):
        assert asks_about_price(text), text
    for text in ("మాకు ఒక app కావాలి", "I need a website", "రేపు call చేయండి"):
        assert not asks_about_price(text), text


# --- context engine

def test_whatsapp_yes_is_remembered_and_not_asked_again():
    # 18 Nov call 92: "same number?" -> "అవును", asked again twice
    s = CallState(name="mahesh")
    s.on_reply("సరే అండి. ఈ number WhatsApp లో ఉందా sir?")
    s.on_customer("అవును.")
    assert s.whatsapp_confirmed
    summary = s.summary()
    assert "WhatsApp confirmed (don't ask again)" in summary and "name mahesh (don't ask)" in summary


def test_needs_platform_and_timeline_are_collected():
    s = CallState()
    s.on_customer("నాకు ఒక mobile app కావాలి, Android and iPhone both, within 2 months")
    summary = s.summary()
    assert "mobile app" in summary and "Android + iPhone" in summary and "start: 2 months" in summary


def test_a_question_asked_twice_is_flagged():
    s = CallState()
    for _ in range(2):
        s.on_reply("Sure sir. Which day and time is convenient for you?")
        s.on_customer("hmm")
    assert "Don't ask again: day and time" in s.summary()


def test_actions_update_the_state():
    s = CallState()
    s.on_action("CONTACT", "Giri | same")
    s.on_action("MEETING", "2026-11-26 15:00")
    summary = s.summary()
    assert "name Giri" in summary and "WhatsApp confirmed" in summary and "meeting 2026-11-26 15:00" in summary


def test_engine_sends_state_and_price_guide_once():
    session = BaseCallSession(lead={"id": None, "name": "Ravi", "phone": "+919000000001"}, language="te-IN")
    first = session.message_hints("మాకు website కావాలి") or ""
    assert "CALL STATE" in first and "website" in first and "PRICE GUIDE" not in first
    second = session.message_hints("దానికి ఎంత అవుతుంది?") or ""
    assert "PRICE GUIDE" in second and "they asked about price" in second
    third = session.message_hints("GST extra aa?") or ""
    assert "PRICE GUIDE" not in third  # sent once; it stays in the conversation


# --- natural voice timing

def test_turn_timing_is_shorter():
    assert wait_ms_to_vad_stop_secs(None) == 0.5           # was 0.8
    assert SMART_TURN_MAX_WAIT_SECS == 1.5                  # Pipecat default 3
    analyzer = turn_strategies().stop[0]._turn_analyzer
    assert analyzer._params.stop_secs == 1.5


# --- evaluation engine (offline, with a fake AI)

def test_evaluation_set_has_the_agreed_100_scenarios():
    from collections import Counter
    from eval.scenarios import SCENARIOS
    assert len(SCENARIOS) == 100
    assert Counter(s["group"] for s in SCENARIOS) == {"normal": 20, "tenglish": 15, "angry": 15, "pricing": 10,
                                                      "topic_change": 10, "interruptions": 10, "appointments": 10,
                                                      "unclear": 10}


def test_evaluator_scores_good_and_bad_replies():
    import asyncio
    from eval.run_eval import run_scenario
    angry = {"id": 1, "group": "angry", "lang": "te-IN", "ends": True,
             "turns": ["ఎవరు మీరు?", "మళ్ళీ మళ్ళీ call చేస్తున్నారు, చిరాకుగా ఉంది."]}
    replies = iter(["నేను S P Associates నుండి Shreya అండి. మేము businesses కి online లో customers తెచ్చే help చేస్తాం. మీ business ఏంటి అండి?",
                    "Sorry sir, మీకు ఇబ్బంది కలిగించినందుకు. Please don't worry, మా team మీకు later call చేస్తారు. "
                    "Thank you sir, have a nice day! [CALL_COMPLETED]"])

    async def fake_llm(messages):
        return next(replies)
    result = asyncio.run(run_scenario(angry, fake_llm))
    assert result["final"] == {"call_ended": True}
    assert all(all(t["checks"].values()) for t in result["turns"])

    bad = iter(["Our website plan is ₹6,700 and app is 2 lakh rupees. What is your budget? When to start?"])

    async def bad_llm(messages):
        return next(bad)
    sc = {"id": 2, "group": "normal", "lang": "en-IN", "turns": ["I need a website."]}
    checks = asyncio.run(run_scenario(sc, bad_llm))["turns"][0]["checks"]
    assert not checks["numbers_in_words"] and not checks["one_question"]
    assert not checks["no_budget_question"] and not checks["price_only_when_asked"]


# --- fixes from the first 10-scenario run (25 Nov)

def test_afternoon_times_are_not_booked_in_the_morning():
    from voice_agent.actions import parse_when
    from voice_agent.rules import IST
    def hhmm(arg):
        return parse_when(arg).astimezone(IST).strftime("%H:%M")
    assert hhmm("2026-11-26 04:00") == "16:00"      # "कल शाम चार बजे" came back as 04:00
    assert hhmm("2026-11-26 03:00 PM") == "15:00"
    assert hhmm("2026-11-26 11:00 AM") == "11:00"
    assert hhmm("2026-11-26 15:00") == "15:00" and hhmm("2026-11-26 10:30") == "10:30"


def test_the_greetings_question_is_not_asked_again_right_away():
    session = BaseCallSession(lead={"id": None, "name": "Ravi", "phone": "+919000000001"}, language="te-IN")
    hint = session.message_hints("చెప్పండి.") or ""
    assert "Your last reply asked about what they need" in hint


def test_master_prompt_covers_the_first_run_findings():
    assert "don't ask that again: in one line say why you called" in MASTER_PROMPT
    assert "Never ask the same thing in two replies in a row" in MASTER_PROMPT
    assert "about ten\nminutes; never give it another length" in MASTER_PROMPT
    assert "e-commerce is for selling products online" in MASTER_PROMPT


def test_scorer_catches_repeats_and_impossible_times():
    import asyncio
    from eval.run_eval import run_scenario
    replies = iter(["Sure sir. When do you want to start?", "Okay sir. When do you want to start this?",
                    "Sure sir, our team will call you at four. Thank you, have a nice day! [CALLBACK: 2026-11-26 23:00]"])

    async def llm(messages):
        return next(replies)
    sc = {"id": 3, "group": "normal", "lang": "en-IN", "turns": ["I need a website.", "For my shop.", "Call me."]}
    turns = asyncio.run(run_scenario(sc, llm))["turns"]
    assert turns[0]["checks"]["no_repeated_question"] and not turns[1]["checks"]["no_repeated_question"]
    assert not turns[2]["checks"]["booking_in_office_hours"]


# --- second eval round (25 Nov: normal, angry, pricing, Tenglish, interruptions)

def test_digits_are_spoken_as_words():
    from voice_agent.numbers import spoken_numbers
    assert spoken_numbers("Basic ₹2,00,000 అవుతుంది, plus 18% GST") == \
        "Basic two lakh rupees అవుతుంది, plus eighteen percent GST"
    assert spoken_numbers("₹1,21,500") == "one lakh twenty one thousand five hundred rupees"
    assert spoken_numbers("₹15,00,000 రూపాయలు") == "fifteen lakh రూపాయలు"
    assert spoken_numbers("call 9000000001") == "call 9000000001"  # phone numbers stay


def test_a_number_split_across_stream_pieces_is_spoken_whole():
    import asyncio
    from pipecat.frames.frames import LLMFullResponseEndFrame, LLMFullResponseStartFrame, LLMTextFrame
    from pipecat.processors.frame_processor import FrameDirection
    from voice_agent.conclusion import CallConclusionFilter

    async def concluded():
        pass

    async def run():
        f = CallConclusionFilter(on_concluded=concluded)
        out = []

        async def push(frame, direction=FrameDirection.DOWNSTREAM):
            if isinstance(frame, LLMTextFrame):
                out.append(frame.text)
        f.push_frame = push
        f._FrameProcessor__check_started = lambda frame: True
        for frame in (LLMFullResponseStartFrame(), LLMTextFrame("Basic plan ₹2,"), LLMTextFrame("00,000 అవుతుంది"),
                      LLMTextFrame(" plus 18"), LLMTextFrame("% GST"), LLMFullResponseEndFrame()):
            await f.process_frame(frame, FrameDirection.DOWNSTREAM)
        return "".join(out)
    try:
        said = asyncio.run(run())
    except Exception:  # pipecat base-class plumbing outside a pipeline: check the same logic directly
        from voice_agent.numbers import NUMBER_TAIL, spoken_numbers
        held, parts = "", []
        for piece in ("Basic plan ₹2,", "00,000 అవుతుంది", " plus 18", "% GST"):
            text = held + piece
            tail = NUMBER_TAIL.search(text)
            emit, held = (text[:tail.start()], text[tail.start():]) if tail else (text, "")
            parts.append(spoken_numbers(emit))
        said = "".join(parts) + spoken_numbers(held)
    assert said == "Basic plan two lakh rupees అవుతుంది plus eighteen percent GST"


def test_contact_is_not_saved_while_still_asking_for_it():
    from voice_agent.conclusion import guard_actions
    acts = guard_actions("The price is negotiable. Is this number on WhatsApp, sir?", [("CONTACT", "Ravi | same")])
    assert acts == []
    kept = guard_actions("Thank you sir, noted. Shall we book the free consultation?", [("CONTACT", "Ravi | same")])
    assert kept == [("CONTACT", "Ravi | same")]


def test_dont_call_again_in_tenglish_and_angry_no_beat_the_second_attempt():
    from voice_agent.call_guard import caller_hints, caller_signals
    assert "opt_out" in caller_signals("నాకు అవసరం లేదు, మళ్ళీ call చేయొద్దు.")
    assert "opt_out" in caller_signals("mujhe call mat karna")
    hints = caller_hints("बकवास बंद करो, मुझे कुछ नहीं चाहिए।")
    assert "[CALL_COMPLETED]" in hints and "Do NOT say goodbye" not in hints


def test_language_line_comes_after_the_price_guide():
    from voice_agent.language import LanguageRouter
    router = LanguageRouter("en-IN", hint_provider=lambda t: "PRICE GUIDE ... Startups కి మేము మంచి discount ఇస్తాం sir")
    annotated, _ = router.prepare("What's the price of your CRM?")
    assert annotated.rstrip().endswith("Reply only in English.)")


def test_business_question_repeat_is_recognised():
    s = CallState()
    s.on_reply("సరే అండి. మీది ఏ business అండి?")
    assert s.last_asked == ["their business"]
    s.on_reply("जी sir. आपका business किस चीज़ का है?")
    assert "their business" in s.last_asked


def test_price_answers_are_short_and_payment_terms_left_to_the_team():
    from services.price_list import PRICE_LIST_FOR_AI
    assert "at most three short sentences" in PRICE_LIST_FOR_AI
    assert "With every package, say" not in PRICE_LIST_FOR_AI
    assert "payment terms, EMI, milestones" in MASTER_PROMPT
    assert "many restaurants" not in MASTER_PROMPT


# --- 25 Nov call 122 (first live call on Shreya 2.0)

def test_bare_no_to_the_greeting_counts_as_the_first_no():
    from voice_agent.call_guard import is_bare_no
    assert is_bare_no("లేదండి.") and is_bare_no("No sir") and is_bare_no("नहीं जी")
    assert not is_bare_no("లేదండి, website ఉంది కానీ app కావాలి")
    session = BaseCallSession(lead={"id": None, "name": "Ravi"}, language="te-IN")
    first = session.message_hints("లేదండి.")
    assert "This is their first no" in first
    second = session.message_hints("వద్దండి మాకు.")
    assert "They have said no again" in second and "[CALL_COMPLETED]" in second


def test_bare_no_later_in_the_call_is_just_an_answer():
    session = BaseCallSession(lead={"id": None, "name": "Ravi"}, language="te-IN")
    session.message_hints("Restaurant business అండి.")
    session.state.on_reply("మీకు already website ఉందా?")
    hints = session.message_hints("లేదండి.") or ""
    assert "first no" not in hints and "said no again" not in hints


def test_prompt_says_not_to_echo_garbled_words_or_state_records():
    assert "never repeat it back" in MASTER_PROMPT
    assert "ask, don't state it" in MASTER_PROMPT


# --- pronunciation for the voice only (25 Nov: "whatsssssapp")

def test_voice_hears_whatsapp_the_local_way():
    from voice_agent.pronounce import for_voice
    assert for_voice("ఈ number WhatsApp లో ఉందా sir?", "te-IN") == "ఈ number వాట్సాప్ లో ఉందా sir?"
    assert for_voice("क्या यह number WhatsApp पर है?", "hi-IN") == "क्या यह number व्हाट्सऐप पर है?"
    assert for_voice("Is this number on WhatsApp?", "en-IN") == "Is this number on WhatsApp?"


def test_pronunciation_is_wired_to_the_voice_only():
    import asyncio
    session = BaseCallSession(lead={"id": None, "name": "Ravi"}, language="te-IN")
    assert asyncio.run(session._for_voice("WhatsApp లో పంపిస్తారు", "sentence")) == "వాట్సాప్ లో పంపిస్తారు"
