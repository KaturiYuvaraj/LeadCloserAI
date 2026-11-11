"""
Voices and language switching on real calls with robust multi-turn verification.
Tests the 2-3 check verification rule, explicit switch requests, and loanword protection.
"""

from voice_agent.language import VOICES, LanguageRouter

# Sarvam bulbul:v4-flash speakers for the languages we route
V4_FLASH_SPEAKERS = {
    "kavitha_te_conversation", "pooja_te_conversation", "kavitha_te_narration", "tarun_te_narration",
    "aditya_hi_sales", "aayan_hi_conversational", "amit_hi_conversational", "kavya_hi_conversational",
    "simran_en_sales", "simran_en_conversation", "neha_en_customer",
    "chaitra_kn_conversation", "chetan_kn_conversation",
    "aravind_ta_ads", "gokul_ta_narration", "vijay_ta_narration",
}


def test_every_voice_exists_on_sarvam():
    unknown = {lang: voice for lang, voice in VOICES.items() if voice not in V4_FLASH_SPEAKERS}
    assert unknown == {}


def test_one_word_replies_do_not_switch_language():
    router = LanguageRouter("te-IN")
    for word in ("Hello", "हाँ।", "Hmm", "ನಮ್ಮ"):
        _, frame = router.prepare(word)
        assert frame is None and router.current_language == "te-IN"


def test_single_sentence_does_not_switch_without_verification():
    """Rule: Check twice or thrice to change language; don't just switch on first sentence."""
    router = LanguageRouter("te-IN")
    text, frame = router.prepare("Yes I need a website for my business")
    # First check: does NOT switch immediately
    assert frame is None and router.current_language == "te-IN"
    assert "(Reply only in Telugu." in text


def test_two_substantive_sentences_verify_and_switch_language():
    """Rule: 2 substantive sentences in the new language verify and confirm the switch."""
    router = LanguageRouter("te-IN")
    # Check 1:
    _, frame1 = router.prepare("Yes I need a website for my business")
    assert frame1 is None and router.current_language == "te-IN"
    # Check 2 (substantive >= 6 words):
    text2, frame2 = router.prepare("Can you tell me the pricing and timeline please")
    assert frame2 is not None and router.current_language == "en-IN"
    assert "(Reply only in English." in text2


def test_three_short_turns_verify_and_switch_language():
    """Rule: 3 consecutive short turns in new language verify and confirm the switch."""
    router = LanguageRouter("te-IN")
    # Check 1:
    assert router.prepare("हाँ जी")[1] is None and router.current_language == "te-IN"
    # Check 2:
    assert router.prepare("बात सुनो")[1] is None and router.current_language == "te-IN"
    # Check 3 (verified):
    text3, frame3 = router.prepare("क्या प्राइस है")
    assert frame3 is not None and router.current_language == "hi-IN"


def test_explicit_language_change_request_switches_immediately():
    """Direct user request (e.g. 'Can you speak in English?') switches immediately."""
    router = LanguageRouter("te-IN")
    text, frame = router.prepare("Can you please speak in English?")
    assert frame is not None and router.current_language == "en-IN"
    assert "(Reply only in English." in text


def test_short_reply_in_current_language_resets_the_pending_switch():
    router = LanguageRouter("te-IN")
    router.prepare("Hello there friend")
    router.prepare("అవునండీ బాగుంది")  # current language reply resets pending counter
    assert router.prepare("Okay sure")[1] is None and router.current_language == "te-IN"


def test_telugu_calls_use_shriyas_voice_pooja():
    from voice_agent.language import VOICES
    assert VOICES["te-IN"] == "pooja_te_conversation"
