"""
Soft office sound under the agent's voice on phone calls, so pauses don't sound like a dead line
(Sarvam's agent does the same with "Quiet office").

  VOICE_BACKGROUND_SOUND   path to a WAV file; "off" turns it off (default: assets/office_ambience.wav)
  VOICE_BACKGROUND_VOLUME  0.0-1.0, default 0.12 (gentle; the voice must stay clearly on top)

Any WAV works: it is converted to mono at the phone line's sample rate when the call starts.
assets/office_ambience.wav is made by scripts/make_office_ambience.py (soft room tone and faint typing);
a real recorded office ambience (royalty-free) can replace it at the same path.
"""

import os
from pathlib import Path
from typing import Optional

import numpy as np
from loguru import logger
from pipecat.audio.mixers.soundfile_mixer import SoundfileMixer

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SOUND = BASE_DIR / "assets" / "office_ambience.wav"


class ResamplingSoundfileMixer(SoundfileMixer):
    """Pipecat's SoundfileMixer only accepts a file at exactly the line's rate; this converts it."""

    def _load_sound_file(self, sound_name: str, file_name: str):
        import soundfile as sf
        try:
            sound, rate = sf.read(file_name, dtype="float32", always_2d=True)
        except Exception as e:
            logger.warning(f"Background sound {file_name} could not be read: {e}")
            return
        mono = sound.mean(axis=1)
        if rate != self._sample_rate and len(mono):
            length = int(len(mono) * self._sample_rate / rate)
            mono = np.interp(np.linspace(0, len(mono) - 1, length), np.arange(len(mono)), mono)
        self._sounds[sound_name] = (np.clip(mono, -1, 1) * 32767).astype(np.int16)


def background_mixer() -> Optional[ResamplingSoundfileMixer]:
    choice = os.getenv("VOICE_BACKGROUND_SOUND", "").strip()
    if choice.lower() in ("off", "0", "false", "no"):
        return None
    path = Path(choice) if choice else DEFAULT_SOUND
    if not choice and not path.is_file():  # *.wav isn't in git: make the default one on first use
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("make_office_ambience", BASE_DIR / "scripts" / "make_office_ambience.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.main()
        except Exception as e:
            logger.warning(f"Could not make the office background sound: {e}")
    if not path.is_file():
        logger.info(f"No background sound at {path}; calls play without it")
        return None
    volume = float(os.getenv("VOICE_BACKGROUND_VOLUME", "0.12"))
    return ResamplingSoundfileMixer(sound_files={"office": str(path)}, default_sound="office", volume=volume)
