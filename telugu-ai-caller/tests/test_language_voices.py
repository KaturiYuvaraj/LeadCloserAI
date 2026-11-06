"""
Voices and language switching on real calls.
Offline: the speaker list is Sarvam's bulbul:v4-flash list as of 6 Nov 2026 (an unknown
speaker makes TTS fail mid-call and the AI goes silent).
"""

from voice_agent.language import VOICES, LanguageRouter

# Sarvam bulbul:v4-flash speakers for the languages we route (from Sarvam's error listing)
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
    for word in ("Hello", "हाँ।", "Hmm", "ನಮ್ಮ"):  # what the recogniser heard on the 6 Nov test call
        _, frame = router.prepare(word)
        assert frame is None and router.current_language == "te-IN"


def test_a_real_sentence_switches_language():
    router = LanguageRouter("te-IN")
    text, frame = router.prepare("Yes I need a website for my shop")
    assert frame is not None and router.current_language == "en-IN"
    assert "(Reply only in English." in text


def test_fillers_never_switch_even_when_repeated():
    # 6 Nov second call: "Hello" then "Sorry" switched the voice to English
    router = LanguageRouter("te-IN")
    for word in ("Hello", "Sorry", "Okay", "हाँ", "हाँ"):
        assert router.prepare(word)[1] is None
    assert router.current_language == "te-IN"


def test_two_word_sentence_in_another_language_switches():
    router = LanguageRouter("te-IN")
    assert router.prepare("नहीं चाहिए")[1] is not None and router.current_language == "hi-IN"
