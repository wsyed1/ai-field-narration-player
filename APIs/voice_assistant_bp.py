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

MOCK_PATIENT = """
Patient: John Doe, Age 34
Allergies: Penicillin
Current medications: Metformin 500mg
Medical history: Type 2 diabetes, mild hypertension
"""

SYSTEM_PROMPT = f"""
You are a helpful voice AI assistant.
You have access to the following patient information:
{MOCK_PATIENT}
- Ask clarifying questions before recommending anything
- Never prescribe controlled substances
- Never make a definitive diagnosis
- Always recommend urgent care when symptoms are serious
- Keep responses concise — this is a voice interface
- End every response with: This is not a substitute for professional medical advice.
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


def stream_speech_pcm(text, session_id):
    """Yields raw 16-bit PCM bytes as OpenAI TTS generates them, so the client
    can start playback before the full response finishes synthesizing."""
    with client.audio.speech.with_streaming_response.create(
        model="tts-1",
        voice="nova",
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
        response_text = generate_reply(session_id, transcript)
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
        response_text = generate_reply(session_id, user_text)
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
