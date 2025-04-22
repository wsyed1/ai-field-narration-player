from flask import Blueprint, request, jsonify
from openai import OpenAI
from dotenv import load_dotenv
import os
import uuid
load_dotenv()
client = OpenAI(api_key=os.getenv("openai_api_key"))
ai_speech_to_text_gpt4o_bp = Blueprint('ai_speech_to_text_gpt4o_bp', __name__)
# In-memory conversation storage
conversation_store = {}
# Supported system prompts
system_prompts = {
    "en": "You are a helpful assistant that creates invoices and asks follow-up questions when needed.",
    "es": "Eres un asistente útil que crea facturas y hace preguntas de seguimiento cuando sea necesario."
}
# Voice mapping (OpenAI voices may support multiple languages soon)
voice_mapping = {
    "en": "shimmer",  # Or nova
    "es": "onyx"      # Adjust when OpenAI offers better Spanish voices
}
@ai_speech_to_text_gpt4o_bp.route('/voice-assist', methods=['POST'])
def voice_assist():
    data = request.get_json()
    audio_file_path = data.get("audio_file_path")
    conversation_id = data.get("conversation_id")
    language_code = data.get("language_code", "en")  # default to English
    if not audio_file_path or not conversation_id:
        return jsonify({"error": "Audio file path and conversation_id must be provided."}), 400
    # Step 1: Transcribe
    try:
        with open(audio_file_path, 'rb') as audio_file:
            transcription_result = client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-1",
                response_format="text",
                language=language_code
            )
        user_input_text = transcription_result
        print(f"[Transcribed ({language_code})] →", user_input_text)
    except Exception as e:
        return jsonify({"error": f"Transcription failed: {e}"}), 500
    # Step 2: Track conversation
    if conversation_id not in conversation_store:
        conversation_store[conversation_id] = [
            {"role": "system", "content": system_prompts.get(language_code, system_prompts["en"])}
        ]
    conversation_store[conversation_id].append({"role": "user", "content": user_input_text})
    # Step 3: GPT-4o response
    try:
        gpt_response = client.chat.completions.create(
            model="gpt-4o",
            messages=conversation_store[conversation_id]
        )
        reply_text = gpt_response.choices[0].message.content
        print(f"[GPT-4o reply ({language_code})] →", reply_text)
        conversation_store[conversation_id].append({"role": "assistant", "content": reply_text})
    except Exception as e:
        return jsonify({"error": f"GPT-4o failed: {e}"}), 500
    # Step 4: Text-to-speech
    try:
        selected_voice = voice_mapping.get(language_code, "nova")
        tts_result = client.audio.speech.create(
            model="tts-1",
            voice=selected_voice,
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
        "language_code": language_code,
        "conversation_id": conversation_id
    })

@ai_speech_to_text_gpt4o_bp.route('/text-assist', methods=['POST'])
def text_assist():
    data = request.get_json()
    user_input_text = data.get("user_input_text")
    conversation_id = data.get("conversation_id")
    language_code = data.get("language_code", "en")  # default to English

    if not user_input_text or not conversation_id:
        return jsonify({"error": "User input text and conversation_id must be provided."}), 400

    # Step 2: Track conversation (same as in voice_assist)
    if conversation_id not in conversation_store:
        conversation_store[conversation_id] = [
            {"role": "system", "content": system_prompts.get(language_code, system_prompts["en"])}
        ]
    conversation_store[conversation_id].append({"role": "user", "content": user_input_text})

    # Step 3: GPT-4o response
    try:
        gpt_response = client.chat.completions.create(
            model="gpt-4o",
            messages=conversation_store[conversation_id]
        )
        reply_text = gpt_response.choices[0].message.content
        print(f"[GPT-4o reply ({language_code})] →", reply_text)
        conversation_store[conversation_id].append({"role": "assistant", "content": reply_text})
    except Exception as e:
        return jsonify({"error": f"GPT-4o failed: {e}"}), 500

    # Step 4: Text-to-speech (same as in voice_assist)
    try:
        selected_voice = voice_mapping.get(language_code, "nova")
        tts_result = client.audio.speech.create(
            model="tts-1",
            voice=selected_voice,
            input=reply_text
        )
        output_path = f"voice_reply_{uuid.uuid4().hex}.mp3"
        with open(output_path, "wb") as f:
            f.write(tts_result.content)
    except Exception as e:
        return jsonify({"error": f"TTS failed: {e}"}), 500

    return jsonify({
        "user_input_text": user_input_text,
        "reply_text": reply_text,
        "reply_audio_path": output_path,
        "language_code": language_code,
        "conversation_id": conversation_id
    })