# AI Voice Kit

A collection of voice and speech AI projects. Expand a section below for that project's full documentation.

<details>
<summary><b>🎙️ Voice to Voice</b> — real-time conversational voice AI, two STT modes, iOS app</summary>

A voice AI pipeline that listens, thinks, and talks back — with two interchangeable speech-to-text front ends (cloud Whisper vs. on-device `SFSpeechRecognizer`), a streaming text-to-speech reply, and a native iOS client with a continuous conversation loop and barge-in.

**[Full documentation →](voice-to-voice/README.md)**

- Backend: `voice-to-voice/backend/`
- iOS app: `voice-to-voice/mobile/VoiceAssistant/`

</details>

<details>
<summary><b>🧭 AI Field Narrator</b> — speech transcription, field mapping, and audio playback</summary>

Transcribes audio files to text using OpenAI's Whisper model, synthesizes word-level timestamps, and maps derived fields to the audio segments where each was spoken — including inferred fields with context, and Google Vertex AI integration for enhanced speech-to-text.

**[Full documentation →](ai-field-narrator/README.md)**

- Backend: `ai-field-narrator/backend/`

</details>
