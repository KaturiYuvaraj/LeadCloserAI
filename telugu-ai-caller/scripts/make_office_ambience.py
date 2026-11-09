"""
Makes assets/office_ambience.wav: a gentle office background for phone calls (no download, no API).

  - soft room tone (deep, quiet noise, like air conditioning in a closed office)
  - faint, irregular keyboard typing from another desk, in short bursts with long pauses
  - nothing sharp or loud; 60 seconds, then it loops seamlessly

    python scripts/make_office_ambience.py
"""

import wave
from pathlib import Path

import numpy as np

RATE = 16000
SECONDS = 60
OUT = Path(__file__).resolve().parent.parent / "assets" / "office_ambience.wav"


def lowpass(x: np.ndarray, alpha: float) -> np.ndarray:
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc += alpha * (v - acc)
        y[i] = acc
    return y


def main():
    rng = np.random.default_rng(7)
    n = RATE * SECONDS
    room = lowpass(rng.normal(0, 1, n), 0.02)  # deep hum of a room
    room = room / np.abs(room).max() * 0.35

    typing = np.zeros(n)
    click = np.hanning(int(0.012 * RATE)) * rng.normal(0, 1, int(0.012 * RATE))
    click = lowpass(click, 0.35)  # soft key, not a sharp tick
    t = rng.uniform(1.0, 4.0)
    while t < SECONDS - 2:
        for _ in range(int(rng.integers(6, 20))):  # a short burst of typing
            start = int(t * RATE)
            typing[start:start + len(click)] += click * rng.uniform(0.25, 0.6)
            t += rng.uniform(0.08, 0.22)
        t += rng.uniform(3.0, 9.0)  # long pause before the next burst

    mix = room + typing * 0.5
    fade = int(0.5 * RATE)  # crossfade the ends so the loop has no click
    mix[:fade] = mix[:fade] * np.linspace(0, 1, fade) + mix[-fade:] * np.linspace(1, 0, fade)
    mix = mix[:-fade]
    mix = mix / np.abs(mix).max() * 0.5

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    print(f"Wrote {OUT} ({len(mix) / RATE:.0f} s)")


if __name__ == "__main__":
    main()
