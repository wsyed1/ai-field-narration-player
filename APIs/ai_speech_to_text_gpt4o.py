from flask import Blueprint, request, jsonify
from openai import OpenAI
from dotenv import load_dotenv
import os
import uuid
load_dotenv()
client = OpenAI(api_key=os.getenv("openai_api_key"))
ai_speech_to_text_gpt4o_bp = Blueprint('ai_speech_to_text_gpt4o_bp', __name__)
# In-memory conversation storage for demo
conversation_store = {}
@ai_speech_to_text_gpt4o_bp.route('/voice-assist', methods=['POST'])
def voice_assist():
    data = request.get_json()
    audio_file_path = data.get("audio_file_path")
    conversation_id = data.get("conversation_id")
    if not audio_file_path or not conversation_id:
        return jsonify({"error": "Audio file path and conversation_id must be provided."}), 400
    try:
        with open(audio_file_path, 'rb') as audio_file:
            transcription_result = client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-1",
                response_format="text"
            )
        user_input_text = transcription_result
        print("Transcribed:", user_input_text)
    except Exception as e:
        return jsonify({"error": f"Transcription failed: {e}"}), 500
    # Step 2: Track conversation history
    if conversation_id not in conversation_store:
        # First message in the thread
        conversation_store[conversation_id] = [
            {"role": "system", "content": "You are a helpful assistant that creates invoices and asks follow-up questions when needed."}
        ]
    # Append user input
    conversation_store[conversation_id].append({"role": "user", "content": user_input_text})
    # Step 3: Send full conversation to GPT-4o
    try:
        gpt_response = client.chat.completions.create(
            model="gpt-4o",
            messages=conversation_store[conversation_id]
        )
        reply_text = gpt_response.choices[0].message.content
        print("GPT-4o reply:", reply_text)
        # Append assistant reply to history
        conversation_store[conversation_id].append({"role": "assistant", "content": reply_text})
    except Exception as e:
        return jsonify({"error": f"GPT-4o failed: {e}"}), 500
    # Step 4: Convert to speech
    try:
        tts_result = client.audio.speech.create(
            model="tts-1",
            voice="nova",
            input=reply_text
        )
        output_path = f"voice_reply_{uuid.uuid4().hex}.mp3"
        with open(output_path, "wb") as f:
            f.write(tts_result.content)
    except Exception as e:
        return jsonify({"error": f"TTS failed: {e}"}), 500
    return jsonify({
        "transcription": user_input_text,
        "reply_text": reply_text,
        "reply_audio_path": output_path,
        "conversation_id": conversation_id  # Return this in case client wants to keep it
    })