"""
Fixes from the review of calls 83-100 (17-18 Nov) and the team's feedback. Each test uses what was really said
on those calls. Offline: no Sarvam, no phone.
"""

import pytest

from voice_agent.call_guard import caller_signals, is_closing_word, is_hold_request
from voice_agent.conclusion import guard_actions
from voice_agent.language import LanguageRouter, detect_explicit_language_request
from voice_agent.session import AGENT_GREETING, TTS_MAX_CHUNK_CHARS, VOICE_RULES


# --- the call must not hang up on a question, and a goodbye without the marker still ends it

def test_question_in_the_middle_keeps_the_call_open():
    # call 98 hung up before the customer could answer
    spoken = ("Wonderful sir! Our team will call you tomorrow at three in the afternoon. Just to confirm, may I have "
              "your name and WhatsApp number? Thank you for your time sir, see you tomorrow!")
    assert ("CALL_COMPLETED", "") not in guard_actions(spoken, [("CALL_COMPLETED", "")])


def test_goodbye_without_the_marker_ends_the_call():
    # call 97 said goodbye about six times and went on asking for a slot
    for spoken in ("Thank you for your valuable time sir, have a good day!",
                   "మీ valuable time ఇచ్చినందుకు thank you sir, have a nice day!",
                   "మీ విలువైన సమయానికి ధన్యవాదాలు అండి, మంచి రోజు!",
                   "आपके valuable time के लिए thank you sir, have a nice day!"):
        assert ("CALL_COMPLETED", "") in guard_actions(spoken, []), spoken


def test_a_question_is_not_a_goodbye():
    assert guard_actions("Have a nice day! ఇంకా ఏమైనా తెలుసుకోవాలా sir?", []) == []


def test_meeting_is_kept_when_the_reply_ends_with_a_statement():
    actions = guard_actions("Perfect sir, రేపు three PM కి మా team call చేస్తారు. Thank you sir, have a nice day!",
                            [("MEETING", "2026-11-19 15:00"), ("CALL_COMPLETED", "")])
    assert ("MEETING", "2026-11-19 15:00") in actions and ("CALL_COMPLETED", "") in actions


# --- "I need an app" is not "wait"

@pytest.mark.parametrize("text", ["అవునండి, మొబైల్ అప్లికేషన్ అవసరం ఉండండి.", "ఉందండి.", "అవసరం ఉండండి"])
def test_need_is_not_a_hold_request(text):
    # call 100: the agent answered "సరేనండి, తీసుకోండి" (take your time)
    assert not is_hold_request(text)


@pytest.mark.parametrize("text", ["ఉండండి ఉండండి", "ఉండండి.", "ఒక్క నిమిషం ఉండండి", "ఆగండి", "one minute", "एक मिनट रुकिए"])
def test_real_hold_requests_still_work(text):
    assert is_hold_request(text)


# --- an angry customer gets one calm close

@pytest.mark.parametrize("text", [
    "ఇందాక నేను మాట్లాడుతుంటే కూడా మీరు కాల్ కట్ చేశారు రూడ్ గా.",   # call 96
    "మళ్ళీ రిపీటెడ్ కాల్స్ చేస్తున్నారు నాకు.",
    "మీ బిహేవియర్ ఏం బాలేదు ఇలా అయితే.",
    "మీరు చాలా చీదరించుకుంటున్నారండి.",
    "Why are you calling again and again, it is so annoying",
    "बार बार कॉल क्यों कर रहे हो",
])
def test_upset_customer_is_recognised(text):
    assert "upset" in caller_signals(text)


def test_upset_hint_closes_the_call_politely():
    from voice_agent.call_guard import HINTS
    assert "don't ask anything" in HINTS["upset"] and "[CALL_COMPLETED]" in HINTS["upset"]
    assert "our team will call them later" in HINTS["upset"]


# --- language

def test_named_language_switches_at_once():
    # call 93: "Telugu or English?" and "...तेलुगु और इंग्लिश में बात करो" in a Hindi call
    assert detect_explicit_language_request("Telugu or English?", "hi-IN") == "te-IN"
    assert detect_explicit_language_request("बात कर रहे हो, तेलुगु और इंग्लिश में बात करो।", "hi-IN") == "te-IN"
    assert detect_explicit_language_request("నేను తెలుగులో మాట్లాడుతుంటే మీరు హిందీలో మాట్లాడుతున్నారు ఏందండి?", "hi-IN") == "te-IN"
    assert detect_explicit_language_request("Can you speak in English?", "te-IN") == "en-IN"
    # naming the language we already speak changes nothing
    assert detect_explicit_language_request("Telugu ok", "te-IN") is None


def test_named_language_switches_the_voice():
    router = LanguageRouter("hi-IN")
    _, frame = router.prepare("Telugu or English?")
    assert frame is not None and router.current_language == "te-IN"


def test_a_full_telugu_sentence_in_a_hindi_call_switches_at_once():
    # call 96: the greeting was Hindi, the customer spoke Telugu, the agent replied in Hindi first
    router = LanguageRouter("hi-IN")
    _, frame = router.prepare("మీరు ఇందాకనే కాల్ చేశారు కదండీ, చెప్తున్నా కూడా అట్లా కాల్ కట్ చేస్తారా?")
    assert frame is not None and router.current_language == "te-IN"


def test_short_hindi_noise_in_a_telugu_call_does_not_switch():
    # call 92: line noise came back as 2-3 Hindi-script words
    router = LanguageRouter("te-IN")
    for noise in ("फोन बच्चे से।", "फोनपे से।", "उनका प्रश्न है।"):
        _, frame = router.prepare(noise)
        assert frame is None and router.current_language == "te-IN"


# --- speech

def test_long_sentences_are_not_cut_mid_way():
    # 120 cut long Telugu sentences and stretched the last word ("గురించి" -> "gurinchiii")
    assert TTS_MAX_CHUNK_CHARS == 300


def test_tenglish_rules_and_examples():
    assert "English words in English letters" in VOICE_RULES
    assert "NUMBERS, ALWAYS IN WORDS" in VOICE_RULES and "eighteen percent GST" in VOICE_RULES
    assert "have a nice day" in VOICE_RULES and "WHY GO DIGITAL" in VOICE_RULES
    assert "CONTACT DETAILS" in VOICE_RULES and "never ask again" in VOICE_RULES
    assert "EARLIER CALLS" in VOICE_RULES and "Never state them as facts" in VOICE_RULES
    assert "When the customer talks over you or interrupts" in VOICE_RULES
    assert "website లేదా mobile app" in AGENT_GREETING["te-IN"]


@pytest.mark.parametrize("text", ["Have a nice day", "Same to you", "Thank you, have a great day", "ok thank you sir"])
def test_customer_goodbyes_are_closing_words(text):
    assert is_closing_word(text)
