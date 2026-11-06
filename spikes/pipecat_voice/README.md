# T1 Spike: Pipecat + Sarvam Real-Time Voice

A standalone test of the real-time voice engine planned for Release 1 (tasks T1/T3). It is separate from the main app on purpose.

- **Streaming** Sarvam speech-to-text (`saaras:v3`), AI (`sarvam-105b-conversations`) and text-to-speech (`bulbul:v4-flash`)
- **Silero VAD** detects when the caller stops talking; the caller can **interrupt** the bot
- Logs the **reply gap** (caller stops → bot starts speaking) for every turn, with a per-service breakdown
- Same code runs in the **browser** now and on **Exotel phone calls** later

## Setup (Windows)

Pipecat needs Python 3.10–3.13 (not 3.14).

```bash
cd spikes/pipecat_voice
py -3.13 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

The Sarvam key is read from `telugu-ai-caller/.env` automatically. To override it, create `spikes/pipecat_voice/.env` (see `.env.example`).

## Try It in the Browser

```bash
python bot.py
```

Open **http://localhost:7860/client**, click **Connect**, allow the microphone, and talk. Use headphones.
Watch the terminal for lines like:

```
⏱  REPLY GAP 1.45s (pipeline 0.95s + silence wait 0.50s) · avg 1.52s over 4 turns
   breakdown (time to first byte): SarvamSTTService 180ms, SarvamLLMService 410ms, SarvamTTSService 290ms
```

Options (in `.env` or as environment variables):

| Variable | Default | Meaning |
|---|---|---|
| `BOT_LANGUAGE` | `te-IN` | Greeting and voice: `te-IN`, `hi-IN`, `en-IN` |
| `VAD_STOP_SECS` | `0.5` | Silence (seconds) that ends the caller's turn |
| `LLM_MODEL` | `sarvam-105b-conversations` | Sarvam chat model |

## Try It on a Real Phone Call (Once Exotel Is Ready)

1. Start a tunnel: `cloudflared tunnel --url http://localhost:7860` (or `ngrok http 7860`)
2. Exotel dashboard → **App Bazaar** → create a flow: **Call Start → Voicebot → Hangup**
3. Voicebot URL: `wss://<tunnel-host>/ws`
4. **ExoPhones** → your number → **Installed App** = this flow
5. Run `python bot.py --transport exotel`, then call the ExoPhone

Source: Sarvam's guide "Build Your First Voice Agent using Exotel" (docs.sarvam.ai).
