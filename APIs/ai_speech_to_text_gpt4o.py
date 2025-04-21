from flask import Blueprint, request, jsonify
from openai import OpenAI
from dotenv import load_dotenv
import os
import uuid

# Load environment variables from .env file
load_dotenv()

# Initialize the OpenAI client with the API key
client = OpenAI(api_key=os.getenv("openai_api_key"))

# Initialize Flask Blueprint
ai_speech_to_text_gpt4o_bp = Blueprint('ai_speech_to_text_gpt4o_bp', __name__)

@ai_speech_to_text_gpt4o_bp.route('/voice-assist', methods=['POST'])
def voice_assist():
    data = request.get_json()
    audio_file_path = data.get("audio_file_path")

    # Check if audio file path is provided
    if not audio_file_path:
        return jsonify({"error": "Audio file path not provided."}), 400

    # Step 1: Transcribe using OpenAI Audio API (uses Whisper engine internally)
    try:
        with open(audio_file_path, 'rb') as audio_file:
            transcription_result = client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-1",  # Required as audio.transcriptions only supports whisper-* models
                response_format="text"
            )
        # Directly assign if transcription_result is a string
        user_input_text = transcription_result
        print("Transcribed:", user_input_text)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # Step 2: GPT-4o generates intelligent response
    try:
        gpt_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that communicates by voice. Respond with brief, clear follow-up."},
                {"role": "user", "content": user_input_text}
            ]
        )
        
        # Correctly accessing the response
        reply_text = gpt_response.choices[0].message.content
        print("Extracted Reply Text:", reply_text)
    except Exception as e:
        return jsonify({"error": f"GPT-4o failed: {e}"}), 500

    print("GPT-4o reply:", reply_text)

    # Step 3: Convert GPT reply to audio using OpenAI TTS
    try:
        print("***** Entered step3")
        tts_result = client.audio.speech.create(
            model="tts-1",
            voice="nova",  # shimmer, echo, fable, etc. are other choices
            input=reply_text
        )
        output_path = f"voice_reply_{uuid.uuid4().hex}.mp3"
        with open(output_path, "wb") as f:
            f.write(tts_result.content)
    except Exception as e:
        return jsonify({"error": f"TTS failed: {e}"}), 500

    # Final JSON Response
    return jsonify({
        "transcription": user_input_text,
        "reply_text": reply_text,
        "reply_audio_path": output_path
    })
