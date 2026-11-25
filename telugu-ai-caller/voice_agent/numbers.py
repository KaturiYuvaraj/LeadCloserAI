"""
Safety net: digits in a reply are spoken as words before they reach the voice.

The price guide writes amounts in digits (₹2,00,000) and the AI sometimes copies them into the reply
(25 Nov eval, scenario 31: "Basic plan ... ₹2,00,000 అవుతుంది"). The voice then reads digits badly. Here they
become English words in the Indian system ("two lakh rupees"), which is how people say them in Tenglish too.
"""

import re

_ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
         "sixteen seventeen eighteen nineteen").split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()

NUMBER = re.compile(r"(₹\s?)?(\d[\d,]*)(\.\d+)?(\s?%)?(\s*(?:/-|-/))?")
# a number still being streamed: hold it back until the next character shows it is complete
NUMBER_TAIL = re.compile(r"(₹\s?)?[\d][\d,.]*$|₹\s?$")


def _under_hundred(n: int) -> str:
    if n < 20:
        return _ONES[n]
    return _TENS[n // 10] + ("" if n % 10 == 0 else " " + _ONES[n % 10])


def _under_thousand(n: int) -> str:
    if n < 100:
        return _under_hundred(n)
    rest = n % 100
    return _ONES[n // 100] + " hundred" + (" " + _under_hundred(rest) if rest else "")


def in_words(n: int) -> str:
    """Indian system: 260000 -> 'two lakh sixty thousand', 15000000 -> 'one crore fifty lakh'."""
    if n == 0:
        return "zero"
    parts = []
    for size, name in ((10_000_000, "crore"), (100_000, "lakh"), (1000, "thousand")):
        if n >= size:
            parts.append(in_words(n // size) + " " + name)
            n %= size
    if n:
        parts.append(_under_thousand(n))
    return " ".join(parts)


def _say(m: re.Match) -> str:
    rupee, digits, decimals, percent, suffix = m.groups()
    try:
        value = int(digits.replace(",", ""))
    except ValueError:
        return m.group(0)
    if value >= 10**9 and "," not in digits:  # a phone number or an id: leave it alone
        return m.group(0)
    words = in_words(value)
    if decimals and decimals.strip(".").strip("0"):
        words += " point " + " ".join(_ONES[int(d)] for d in decimals[1:])
    if percent:
        words += " percent"
    after = m.string[m.end():m.end() + 12].lower()
    if (rupee or suffix) and not re.match(r"\s*(rupee|rs(?![a-z])|lakh|crore|thousand|రూపాయ|లక్ష|కోటి|వేల|रुपय|रुपये|लाख|करोड़|हज़ार)", after):
        words += " rupees"
    return words


def spoken_numbers(text: str) -> str:
    return NUMBER.sub(_say, text or "")
