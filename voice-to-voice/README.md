# Voice to Voice

A voice AI pipeline that listens, thinks, and talks back — with two interchangeable speech-to-text front ends, a streaming text-to-speech reply, and a native iOS client.

Demoed as a medical assistant (fictional patient data) to make the conversation feel real, but the architecture applies to any domain — customer support, field data collection, accessibility tools.

## Two speech-to-text modes

- **Precision Mode** — records audio on-device, uploads it, transcribes with OpenAI's Whisper API. Higher accuracy, especially on uncommon terms; audio leaves the device.
- **Live Mode** — transcribes entirely on-device with Apple's `SFSpeechRecognizer`, live-updating transcript as you speak. Nothing leaves the device; real-time, no upload latency.

Both modes feed the same backend, the same GPT-4o conversation, and the same OpenAI TTS voice on the way out.

## Architecture

```
iOS App → Flask Backend → GPT-4o (multi-turn) → OpenAI TTS (streamed) → iOS App plays it back
```

- Conversation history and identity-verification state are tracked independently per `session_id` — Live Mode and Precision Mode never share history.
- TTS responses stream back as raw PCM as OpenAI generates them, so playback starts before the full reply finishes synthesizing.
- The app runs as a continuous session: tap once, get an instant local greeting, and the app auto-resumes listening after every response — no re-tapping between turns.

## Backend

### Setup

```bash
cd voice-to-voice/backend
pip install flask openai python-dotenv
```

Create a `.env` file in `voice-to-voice/backend/`:

```bash
openai_api_key=your_openai_api_key_here
```

### Running

```bash
python3 main.py
```

Runs on `http://0.0.0.0:5000` so a physical iOS device on the same network can reach it.

### Endpoints

**`POST /voice/chat/text`**
```json
{ "text": "I have a headache", "session_id": "abc123" }
```
Streams back spoken audio (raw PCM, 24kHz mono) with `X-Response-Text` header.

**`POST /voice/chat/whisper`**
Multipart form upload: `audio_file` (the recording) + `session_id`. Streams back spoken audio with `X-User-Text` (transcript) and `X-Response-Text` headers.

**`POST /voice/interrupt`**
```json
{ "session_id": "abc123" }
```
Flags the current turn to stop generating/streaming.

There's also a lightweight browser test client at `GET /voice/test` for exercising the backend without the iOS app.

## iOS app

Located in `voice-to-voice/mobile/VoiceAssistant/`. Open `VoiceAssistant.xcodeproj` in Xcode.

- Update `BackendConfig.swift` with your Mac's LAN IP if running on a physical device (Simulator can use `127.0.0.1`).
- On-device speech recognition (Live Mode) requires a real iPhone — the iOS Simulator's on-device speech model is unreliable.
- Requires Microphone and Speech Recognition permissions (already configured in `Info.plist`).

## Out of scope

- No real patient database — one fictional mock patient, hardcoded.
- No authentication beyond a scripted identity check (name + a follow-up question) — not real security.
- No HIPAA/compliance handling, no production WSGI server, no clinical validation of the safety guardrails.
