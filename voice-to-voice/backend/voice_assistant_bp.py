from flask import Blueprint, request, jsonify, Response, send_from_directory
from openai import OpenAI
from dotenv import load_dotenv
from urllib.parse import quote
import os
import io

load_dotenv()
client = OpenAI(api_key=os.getenv('openai_api_key'))

voice_assistant_bp = Blueprint('voice_assistant_bp', __name__)

sessions = {}
interrupt_flags = {}
identity_verified = {}
identity_step = {}  # session_id -> "greeting" | "awaiting_name" | "awaiting_sport"
identity_name_answer = {}

EXPECTED_NAME = "John Appleseed"
GREETING_AND_NAME_PROMPT = "Hey there, how are you today? Can I please take a moment to verify your identity? Can you tell me your first and last name?"
SPORT_PROMPT = "Thanks! And one more quick question — what's your favorite sport?"
IDENTITY_REJECTED_MESSAGE = "Sorry, I couldn't verify your identity, so I can't continue. Let's try again — can you tell me your first and last name?"

MOCK_PATIENT = """
Patient: John Appleseed, Age 34
Allergies: Penicillin
Current medications: Metformin 500mg
Medical history: Type 2 diabetes, mild hypertension
"""

SYSTEM_PROMPT = f"""
You are a warm, friendly voice AI assistant with a caring, conversational tone — like a
supportive nurse checking in, not a clinical script.
You have access to the following patient information:
{MOCK_PATIENT}

Tone and pacing:
- Talk like a real person on a phone call, not a form. Be warm and natural.
- Keep every response short — 1 to 3 sentences. Never a long list or a wall of text.
- Never answer with just one word — always a brief, complete, human-sounding reply.
- Ask only ONE clarifying question per response. Never stack multiple questions
  together. Have a natural back-and-forth — it should take several turns to
  gather what you need, not one big interrogation.
- When bringing up the patient's history (allergies, medications, conditions),
  never recite it like a chart. Weave it in conversationally, e.g. "I see you're
  allergic to penicillin, so let's steer clear of that" — mention only what's
  actually relevant to the conversation at that moment, not the full record.
- If the user asks about or you recommend a specific medication, always check it
  against their current medications and conditions first, and say so directly if
  there's a relevant interaction or reason to avoid it (e.g. an NSAID like
  ibuprofen and Metformin/kidney considerations) — don't just give a generic
  "check with your doctor" answer when you already have the relevant info.

Rules:
- Ask clarifying questions before recommending anything
- Never prescribe controlled substances
- Never make a definitive diagnosis
- Always recommend urgent care when symptoms are serious
- Only when you recommend or suggest a specific medication, treatment, or course
  of action, end that response with: This is not a substitute for professional
  medical advice. Do NOT add this line to responses that are just asking a
  clarifying question or acknowledging what the user said — only when you're
  actually giving guidance.
"""


def get_history(session_id):
    return sessions.get(session_id, [])


def add_to_history(session_id, role, content):
    sessions.setdefault(session_id, []).append({
        "role": role,
        "content": content
    })


def generate_reply(session_id, user_text):
    completion = client.chat.completions.create(
        model="gpt-4o",
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            *get_history(session_id),
            {"role": "user", "content": user_text}
        ]
    )
    response_text = completion.choices[0].message.content
    add_to_history(session_id, "user", user_text)
    add_to_history(session_id, "assistant", response_text)
    return response_text


def check_name_answer(user_text):
    """Uses the LLM to judge whether the spoken answer plausibly gives the
    expected name, since a transcribed voice answer won't match a hardcoded
    string exactly."""
    prompt = f"""
A user was asked for their first and last name. They answered: "{user_text}"

Does their answer give the name "{EXPECTED_NAME}" (allow for minor
transcription differences in spelling/spacing)? Reply with exactly one
word: YES or NO.
"""
    completion = client.chat.completions.create(
        model="gpt-4o",
        temperature=0,
        messages=[{"role": "user", "content": prompt}]
    )
    return completion.choices[0].message.content.strip().upper().startswith("YES")


def handle_identity_gate(session_id, user_text):
    """Returns a response string to speak if identity verification isn't done
    yet, or None if the caller should proceed to the normal medical reply.

    Runs as two separate questions in sequence: first and last name, then
    favorite sport (asked once the name checks out; any sport answer is
    accepted, since it's an icebreaker rather than something to validate)."""
    if identity_verified.get(session_id, False):
        return None

    step = identity_step.get(session_id, "not_started")

    if step == "not_started":
        identity_step[session_id] = "awaiting_name"
        return GREETING_AND_NAME_PROMPT

    if step == "awaiting_name":
        if check_name_answer(user_text):
            identity_name_answer[session_id] = user_text
            identity_step[session_id] = "awaiting_sport"
            return SPORT_PROMPT
        return IDENTITY_REJECTED_MESSAGE

    if step == "awaiting_sport":
        identity_verified[session_id] = True
        return (
            "Nice, thanks for that! Let me just pull up your medical records... "
            "okay, got it. What can I help you with today?"
        )


def stream_speech_pcm(text, session_id):
    """Yields raw 16-bit PCM bytes as OpenAI TTS generates them, so the client
    can start playback before the full response finishes synthesizing."""
    with client.audio.speech.with_streaming_response.create(
        model="tts-1",
        voice="shimmer",
        input=text,
        response_format="pcm"
    ) as tts_response:
        for chunk in tts_response.iter_bytes(chunk_size=4096):
            if interrupt_flags.get(session_id):
                return
            yield chunk


@voice_assistant_bp.route('/voice/test', methods=['GET'])
def test_client():
    static_dir = os.path.join(os.path.dirname(__file__), 'static')
    return send_from_directory(static_dir, 'voice_test_client.html')


@voice_assistant_bp.route('/voice/chat/whisper', methods=['POST'])
def chat_whisper():
    audio_file = request.files.get('audio_file')
    session_id = request.form.get('session_id')

    if not audio_file or not session_id:
        return jsonify({"error": "audio_file and session_id are required."}), 400

    interrupt_flags[session_id] = False

    try:
        audio_buffer = io.BytesIO(audio_file.read())
        audio_buffer.name = audio_file.filename or "recording.m4a"
        transcript = client.audio.transcriptions.create(
            file=audio_buffer,
            model="whisper-1",
            response_format="text"
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    if interrupt_flags.get(session_id):
        return jsonify({"status": "interrupted"}), 200

    try:
        gate_response = handle_identity_gate(session_id, transcript)
        response_text = gate_response if gate_response is not None else generate_reply(session_id, transcript)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return Response(
        stream_speech_pcm(response_text, session_id),
        mimetype="audio/L16; rate=24000; channels=1",
        headers={
            "X-User-Text": quote(transcript),
            "X-Response-Text": quote(response_text)
        }
    )


@voice_assistant_bp.route('/voice/chat/text', methods=['POST'])
def chat_text():
    data = request.get_json()
    user_text = data.get('text')
    session_id = data.get('session_id')

    if not user_text or not session_id:
        return jsonify({"error": "text and session_id are required."}), 400

    interrupt_flags[session_id] = False

    try:
        gate_response = handle_identity_gate(session_id, user_text)
        response_text = gate_response if gate_response is not None else generate_reply(session_id, user_text)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    if interrupt_flags.get(session_id):
        return jsonify({"status": "interrupted"}), 200

    return Response(
        stream_speech_pcm(response_text, session_id),
        mimetype="audio/L16; rate=24000; channels=1",
        headers={
            "X-Response-Text": quote(response_text)
        }
    )


@voice_assistant_bp.route('/voice/interrupt', methods=['POST'])
def interrupt():
    data = request.get_json()
    session_id = data.get('session_id')

    if not session_id:
        return jsonify({"error": "session_id is required."}), 400

    interrupt_flags[session_id] = True
    return jsonify({"status": "interrupted"})
