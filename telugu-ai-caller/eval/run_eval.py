"""
Shreya 2.0 evaluation runner: plays each scenario in eval/scenarios.py through our engine's real prompt,
language router, hints, call state and ending rules, with the real Sarvam LLM (text only, no phone call),
and scores every reply automatically.

USES SARVAM CREDITS (one LLM request per customer turn, about 6-7K input tokens each). It never runs
without --yes. Start small:

    venv/Scripts/python.exe -m eval.run_eval --limit 5            # shows what would run, spends nothing
    venv/Scripts/python.exe -m eval.run_eval --limit 5 --yes      # runs 5 scenarios
    venv/Scripts/python.exe -m eval.run_eval --group angry --yes  # one group

Report: eval/results/<timestamp>.json and a printed summary per check and per group.
"""

import argparse
import asyncio
import json
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.scenarios import SCENARIOS  # noqa: E402

DIGITS = re.compile(r"[0-9₹%]")
SCRIPT = {"te-IN": (0x0C00, 0x0C7F), "hi-IN": (0x0900, 0x097F)}
PRICE_WORDS = re.compile(r"లక్ష|వేల\s+రూపాయ|రూపాయలు|lakh|thousand\s+rupees|rupees|लाख|हज़ार\s+रुपये|रुपये", re.I)
AI_WORDS = re.compile(r"\bAI\b|virtual\s+assistant|artificial|ఏఐ|ఎఐ|रोबोट|robot", re.I)
FAMILIAR_BYE = re.compile(r"సెలవు|ఉంటాను|ఉంటానండి")
# only a question sentence that asks about budget ("the ad budget is separate. Is this your WhatsApp?" is fine)
BUDGET_Q = re.compile(r"(budget|బడ్జెట్|बजट)[^.!?।]*\?", re.I)
ASKS_AI = re.compile(r"robot|\bAI\b|machine|ఏఐ|మనిషా", re.I)
PRICE_ASK = re.compile(r"ఎంత|entha|price|cost|charges?|rates?|how\s+much|kitn|ధర|कीमत|कितन|discount|quotation|"
                       r"expensive|costly|ఎక్కువ|महंगा|budget|బడ్జెట్|बजट", re.I)


def in_language(text: str, lang: str) -> bool:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters or len(text.split()) <= 6:  # "Sure అండి, take your time." is natural in every language
        return True
    if lang in SCRIPT:
        lo, hi = SCRIPT[lang]
        return sum(lo <= ord(ch) <= hi for ch in letters) / len(letters) >= 0.15  # Tenglish keeps English words (and prices are spoken as English number words)
    return sum(ch.isascii() for ch in letters) / len(letters) >= 0.9


def check_reply(reply: str, ctx: Dict[str, Any]) -> Dict[str, bool]:
    words = len(reply.split())
    return {
        "numbers_in_words": not DIGITS.search(reply),
        "one_question": reply.count("?") + reply.count("？") <= 1,
        "short": words <= (60 if ctx["price_asked"] else 40),
        "call_language": in_language(reply, ctx["lang"]),
        "no_budget_question": not BUDGET_Q.search(reply),
        "price_only_when_asked": ctx["price_asked"] or not PRICE_WORDS.search(reply),
        "ai_only_when_asked": ctx["ai_asked"] or not AI_WORDS.search(reply),
        "formal_goodbye": not FAMILIAR_BYE.search(reply),
    }


def _in_office_hours(arg: str) -> bool:
    from voice_agent.actions import parse_when
    from voice_agent.rules import IST
    when = parse_when(arg)
    if not when:
        return True
    hour = when.astimezone(IST).hour + when.astimezone(IST).minute / 60
    return 9.5 <= hour <= 19


async def run_scenario(sc: Dict[str, Any], llm) -> Dict[str, Any]:
    from voice_agent.conclusion import guard_actions, split_actions
    from voice_agent.language import LanguageRouter
    from services.price_list import PRICE_LIST_FOR_AI
    from voice_agent.numbers import spoken_numbers
    from voice_agent.session import AGENT_GREETING, BaseCallSession

    lead = {"id": None, "name": "Ravi", "phone": "+919000000001", "preferred_language": sc["lang"]}
    session = BaseCallSession(lead=lead, language=sc["lang"])
    system_prompt, greeting = await session._build_prompt_and_greeting()
    router = LanguageRouter(sc["lang"], hint_provider=session.message_hints)
    messages = [{"role": "system", "content": system_prompt}, {"role": "assistant", "content": greeting}]
    turns, ended, ctx = [], False, {"lang": sc["lang"], "price_asked": False, "ai_asked": False}
    previous_topics = set(session.state.last_asked)
    for i, text in enumerate(sc["turns"]):
        if ended:
            break
        annotated, _ = router.prepare(text)
        ctx["lang"] = router.current_language
        ctx["price_asked"] = ctx["price_asked"] or bool(PRICE_ASK.search(text))
        ctx["ai_asked"] = ctx["ai_asked"] or bool(ASKS_AI.search(text))
        messages.append({"role": "user", "content": annotated})
        started = time.monotonic()
        raw = await llm(messages)
        seconds = round(time.monotonic() - started, 2)
        spoken, _, actions = split_actions(raw)
        model_text = spoken
        spoken = spoken_numbers(spoken).strip()  # as the live call does before the voice
        actions = guard_actions(spoken, actions)
        messages.append({"role": "assistant", "content": spoken})
        session.transcript += [{"role": "user", "content": text}, {"role": "assistant", "content": spoken}]
        session.state.on_reply(spoken)
        topics = set(session.state.last_asked)
        for tag, arg in actions:
            session.state.on_action(tag, arg)
        ended = any(tag == "CALL_COMPLETED" for tag, _ in actions)
        checks = check_reply(spoken, ctx)
        # the AI itself, before the safety net. Prices come as "₹66,500" copied from the guide, and must be real
        # (25 Nov: she wrote ₹66,500 in words herself as "one lakh sixty-six thousand five hundred")
        amounts = re.findall(r"₹\s?[\d,]+\d", model_text)
        checks["numbers_in_words"] = not DIGITS.search(re.sub(r"₹\s?[\d,]+\d", "", model_text))
        checks["price_from_guide"] = all(a.replace(" ", "") in PRICE_LIST_FOR_AI for a in amounts)
        # 25 Nov first run: "when do you want to start?" twice in a row; a 4 PM callback saved as 04:00
        checks["no_repeated_question"] = not (topics & previous_topics)
        previous_topics = topics
        checks["booking_in_office_hours"] = all(_in_office_hours(arg) for tag, arg in actions
                                                if tag in ("MEETING", "CALLBACK"))
        if sc.get("hold_turn") == i:
            checks["hold_is_short"] = len(spoken.split()) <= 10 and "?" not in spoken
        turns.append({"customer": text, "shreya": spoken, "actions": actions, "seconds": seconds, "checks": checks})
    final = {}
    if sc.get("ends"):
        final["call_ended"] = ended
    if sc.get("no_end"):
        final["call_kept_open"] = not ended
    return {"id": sc["id"], "group": sc["group"], "lang": sc["lang"], "turns": turns, "final": final}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--group")
    ap.add_argument("--ids", help="comma separated scenario ids")
    ap.add_argument("--yes", action="store_true", help="really run (uses Sarvam credits)")
    args = ap.parse_args()

    chosen = [s for s in SCENARIOS if (not args.group or s["group"] == args.group)
              and (not args.ids or str(s["id"]) in args.ids.split(","))][: args.limit]
    requests = sum(len(s["turns"]) for s in chosen)
    print(f"{len(chosen)} scenario(s), up to {requests} Sarvam LLM requests (about 6-7K input tokens each).")
    if not args.yes:
        print("Nothing was sent. Add --yes to run it.")
        return

    from services.sarvam_service import sarvam_client
    from voice_agent.session import LLM_MODEL

    async def llm(messages):
        # 25 Nov: Sarvam answered 429 "Rate limit exceeded" after about 100 quick requests; pace and retry
        for attempt in range(5):
            await asyncio.sleep(1.0)
            try:
                return await sarvam_client.chat_completion(messages, model=LLM_MODEL, temperature=0.5, max_tokens=240)
            except Exception as e:
                if "429" not in str(e) and "rate limit" not in str(e).lower() or attempt == 4:
                    raise
                await asyncio.sleep(10 * (attempt + 1))

    results = []
    for sc in chosen:
        try:
            results.append(await run_scenario(sc, llm))
        except Exception as e:  # a failed request counts as a failed scenario, the run goes on
            results.append({"id": sc["id"], "group": sc["group"], "error": str(e)[:300], "turns": [], "final": {}})
        r = results[-1]
        bad = [k for t in r["turns"] for k, ok in t["checks"].items() if not ok] + [k for k, ok in r["final"].items() if not ok]
        print(f"#{sc['id']:3} {sc['group']:13} {'ERROR ' + r['error'][:60] if r.get('error') else ('OK' if not bad else 'FAIL: ' + ', '.join(sorted(set(bad))))}")

    per_check, per_group = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    for r in results:
        passed = not r.get("error")
        for t in r["turns"]:
            for k, ok in t["checks"].items():
                per_check[k][0] += ok
                per_check[k][1] += 1
                passed = passed and ok
        for k, ok in r["final"].items():
            per_check[k][0] += ok
            per_check[k][1] += 1
            passed = passed and ok
        per_group[r["group"]][0] += passed
        per_group[r["group"]][1] += 1
    seconds = [t["seconds"] for r in results for t in r["turns"]]
    print("\nChecks (passed / total):")
    for k, (ok, n) in sorted(per_check.items()):
        print(f"  {k:24} {ok}/{n}")
    print("Scenarios fully passed, by group:")
    for g, (ok, n) in per_group.items():
        print(f"  {g:13} {ok}/{n}")
    if seconds:
        print(f"LLM reply time: average {sum(seconds) / len(seconds):.2f}s, slowest {max(seconds):.2f}s")
    out = Path(__file__).resolve().parent / "results"
    out.mkdir(exist_ok=True)
    label = args.group or ("ids" if args.ids else "first")
    path = out / f"{datetime.now():%Y%m%d-%H%M%S}-{label}.json"  # one file per run, never overwritten
    path.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Saved: {path}")


if __name__ == "__main__":
    asyncio.run(main())
