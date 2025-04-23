from flask import Blueprint, request, jsonify
from openai import OpenAI
from dotenv import load_dotenv
import os
import uuid
# Load environment variables
load_dotenv()
client = OpenAI(api_key=os.getenv("openai_api_key"))
# Do not change this name
ai_speech_to_text_gpt4o_bp = Blueprint('ai_speech_to_text_gpt4o_bp', __name__)
# Memory store
conversation_store = {}
conversation_state = {}
voice_mapping = {
    "en": "nova",  # expressive and natural
    "es": "onyx"
}
system_prompt = (
    "You are a helpful, human-like assistant that helps users complete tasks like creating emails, invoices, or reminders. "
    "Speak casually and naturally. Ask only one clear, specific follow-up question at a time. "
    "Do not use generic responses like 'please provide details'. If all needed info is available, complete the task concisely."
)
def initialize_conversation(conversation_id, language_code):
    if conversation_id not in conversation_store:
        conversation_store[conversation_id] = [
            {"role": "system", "content": system_prompt}
        ]
        conversation_state[conversation_id] = {
            "pending_questions": [],
            "last_prompted": None,
            "task_finalized": False
        }
def get_next_question(conversation_id):
    state = conversation_state[conversation_id]
    if state["pending_questions"]:
        next_q = state["pending_questions"].pop(0)
        state["last_prompted"] = next_q
        return next_q
    return None
def get_gpt_response(conversation_id):
    gpt_response = client.chat.completions.create(
        model="gpt-4o",
        messages=conversation_store[conversation_id]
    )
    content = gpt_response.choices[0].message.content.strip()
    return content.split("\n")[0], content
def filter_answered_questions(conversation_id, user_input_text):
    state = conversation_state[conversation_id]
    pending = state["pending_questions"]
    if not pending:
        return
    prompt = (
        "You are an assistant helping a user complete a task. Below is the latest user message and a list of pending questions. "
        "Return a Python list of only the unanswered questions based on whether the user’s message already answers them.\n\n"
        f"User message:\n{user_input_text}\n\n"
        f"Pending questions:\n{pending}\n\n"
        "Unanswered questions (in Python list format):"
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": prompt}]
        )
        cleaned = response.choices[0].message.content.strip()
        state["pending_questions"] = eval(cleaned) if cleaned.startswith("[") else pending
    except Exception as e:
        print("Question filtering failed:", e)
def process_user_input(conversation_id, user_input_text, language_code):
    conversation_store[conversation_id].append({"role": "user", "content": user_input_text})
    filter_answered_questions(conversation_id, user_input_text)
    state = conversation_state[conversation_id]
    if not state["pending_questions"] and not state["task_finalized"]:
        _, assistant_response = get_gpt_response(conversation_id)
        conversation_store[conversation_id].append({"role": "assistant", "content": assistant_response})
        # Extract specific questions only
        lines = assistant_response.split("\n")
        questions = [line.strip() for line in lines if line.strip().endswith("?")]
        if questions:
            state["pending_questions"] = questions[1:]
            return questions[0], questions[0]
        else:
            state["task_finalized"] = True
            return assistant_response.split("\n")[0], assistant_response
    elif state["pending_questions"]:
        next_question = get_next_question(conversation_id)
        return next_question, next_question
    else:
        high_level_reply, detailed_response = get_gpt_response(conversation_id)
        conversation_store[conversation_id].append({"role": "assistant", "content": detailed_response})
        state["task_finalized"] = True
        return high_level_reply, detailed_response
def generate_tts_response(text, language_code):
    selected_voice = voice_mapping.get(language_code, "nova")
    tts_result = client.audio.speech.create(
        model="tts-1",
        voice=selected_voice,
        input=text
    )
    output_path = f"voice_reply_{uuid.uuid4().hex}.mp3"
    with open(output_path, "wb") as f:
        f.write(tts_result.content)
    return output_path
# VOICE ENDPOINT
@ai_speech_to_text_gpt4o_bp.route('/voice-assist', methods=['POST'])
def voice_assist():
    data = request.get_json()
    audio_file_path = data.get("audio_file_path")
    conversation_id = data.get("conversation_id")
    language_code = data.get("language_code", "en")
    if not audio_file_path or not conversation_id:
        return jsonify({"error": "Audio file path and conversation_id must be provided."}), 400
    initialize_conversation(conversation_id, language_code)
    try:
        with open(audio_file_path, 'rb') as audio_file:
            transcription_result = client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-1",
                response_format="text",
                language=language_code
            )
        user_input_text = transcription_result
    except Exception as e:
        return jsonify({"error": f"Transcription failed: {e}"}), 500
    try:
        high_level_reply, detailed_response = process_user_input(conversation_id, user_input_text, language_code)
        output_path = generate_tts_response(high_level_reply, language_code)
    except Exception as e:
        return jsonify({"error": f"Processing failed: {e}"}), 500
    return jsonify({
        "user_input_text": user_input_text,
        "reply_text": high_level_reply,
        "detailed_response": detailed_response,
        "reply_audio_path": output_path,
        "language_code": language_code,
        "conversation_id": conversation_id
    })
# TEXT ENDPOINT
@ai_speech_to_text_gpt4o_bp.route('/text-assist', methods=['POST'])
def text_assist():
    data = request.get_json()
    user_input_text = data.get("user_input_text")
    conversation_id = data.get("conversation_id")
    language_code = data.get("language_code", "en")
    if not user_input_text or not conversation_id:
        return jsonify({"error": "User input text and conversation_id must be provided."}), 400
    initialize_conversation(conversation_id, language_code)
    try:
        high_level_reply, detailed_response = process_user_input(conversation_id, user_input_text, language_code)
        output_path = generate_tts_response(high_level_reply, language_code)
    except Exception as e:
        return jsonify({"error": f"Processing failed: {e}"}), 500
    return jsonify({
        "user_input_text": user_input_text,
        "reply_text": high_level_reply,
        "detailed_response": detailed_response,
        "reply_audio_path": output_path,
        "language_code": language_code,
        "conversation_id": conversation_id
    })