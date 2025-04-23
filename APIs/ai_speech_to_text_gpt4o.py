
from flask import Blueprint, request, jsonify
from openai import OpenAI
from dotenv import load_dotenv
import os
import uuid
import base64

load_dotenv()
client = OpenAI(api_key=os.getenv("openai_api_key"))

ai_speech_to_text_gpt4o_bp = Blueprint('ai_speech_to_text_gpt4o_bp', __name__)
conversation_store = {}
conversation_state = {}
voice_mapping = {"en": "nova", "es": "onyx"}

os.makedirs("conversations", exist_ok=True)

system_prompt = (
    "You are a friendly, natural-sounding assistant that helps users complete tasks like creating emails, invoices, or reminders. "
    "Ask only one clear, specific follow-up question at a time. Be concise, casual, and warm in tone. "
    "Extract multiple answers if the user provides more than one. If all info is available, generate the final response."
)

def initialize_conversation(conversation_id):
    if conversation_id not in conversation_store:
        conversation_store[conversation_id] = [{"role": "system", "content": system_prompt}]
        conversation_state[conversation_id] = {
            "last_intent": None,
            "pending_questions": [],
            "last_prompted": None,
            "task_finalized": False
        }

def save_conversation_to_file(conversation_id):
    path = f"conversations/{conversation_id}.txt"
    with open(path, "a", encoding="utf-8") as f:
        for msg in conversation_store[conversation_id]:
            f.write(f"{msg['role'].upper()}: {msg['content']}\n")
        f.write("\n--- END OF TURN ---\n\n")

def detect_task_type(user_input_text):
    prompt = f"What task is the user trying to do in this message? Just return one word like 'invoice', 'email', 'reminder'.\n\n{user_input_text}"
    try:
        res = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": prompt}])
        return res.choices[0].message.content.strip().lower()
    except:
        return "unknown"

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
        "You're a task assistant. Given the user message and pending questions, return only unanswered questions.\n"
        f"User: {user_input_text}\nPending: {pending}\n\nReturn a Python list:"
    )
    try:
        result = client.chat.completions.create(
            model="gpt-4o", messages=[{"role": "system", "content": prompt}]
        )
        cleaned = result.choices[0].message.content.strip()
        state["pending_questions"] = eval(cleaned) if cleaned.startswith("[") else pending
    except:
        pass

def reset_if_new_task(conversation_id, user_input_text):
    state = conversation_state[conversation_id]
    new_intent = detect_task_type(user_input_text)
    if new_intent and new_intent != state["last_intent"] and state["last_intent"] is not None:
        conversation_store[conversation_id] = [{"role": "system", "content": system_prompt}]
        conversation_state[conversation_id] = {
            "last_intent": new_intent,
            "pending_questions": [],
            "last_prompted": None,
            "task_finalized": False
        }
    else:
        state["last_intent"] = new_intent

def process_user_input(conversation_id, user_input_text, language_code):
    initialize_conversation(conversation_id)
    reset_if_new_task(conversation_id, user_input_text)
    state = conversation_state[conversation_id]
    conversation_store[conversation_id].append({"role": "user", "content": user_input_text})
    filter_answered_questions(conversation_id, user_input_text)

    if not state["pending_questions"] and not state["task_finalized"]:
        _, assistant_response = get_gpt_response(conversation_id)
        conversation_store[conversation_id].append({"role": "assistant", "content": assistant_response})
        questions = [line.strip() for line in assistant_response.split("\n") if line.strip().endswith("?")]
        if questions:
            state["pending_questions"] = questions[1:]
            save_conversation_to_file(conversation_id)
            return questions[0], questions[0]
        else:
            state["task_finalized"] = True
            save_conversation_to_file(conversation_id)
            return assistant_response.split("\n")[0], assistant_response
    elif state["pending_questions"]:
        next_question = get_next_question(conversation_id)
        save_conversation_to_file(conversation_id)
        return next_question, next_question
    else:
        high_level_reply, detailed_response = get_gpt_response(conversation_id)
        conversation_store[conversation_id].append({"role": "assistant", "content": detailed_response})
        state["task_finalized"] = True
        save_conversation_to_file(conversation_id)
        return high_level_reply, detailed_response

def generate_tts_response(text, language_code):
    voice = voice_mapping.get(language_code, "nova")
    tts_result = client.audio.speech.create(
        model="tts-1", voice=voice, input=text
    )
    output_path = f"voice_reply_{uuid.uuid4().hex}.mp3"
    with open(output_path, "wb") as f:
        f.write(tts_result.content)
    return output_path

@ai_speech_to_text_gpt4o_bp.route('/text-assist', methods=['POST'])
def text_assist():
    data = request.get_json()
    user_input_text = data.get("user_input_text")
    conversation_id = data.get("conversation_id")
    language_code = data.get("language_code", "en")
    if not user_input_text or not conversation_id:
        return jsonify({"error": "Missing user_input_text or conversation_id"}), 400

    initialize_conversation(conversation_id)

    try:
        reply, detail = process_user_input(conversation_id, user_input_text, language_code)
        audio_path = generate_tts_response(reply, language_code)
        with open(audio_path, "rb") as f:
            base64_audio = base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        return jsonify({"error": f"Processing failed: {e}"}), 500

    return jsonify({
        "user_input_text": user_input_text,
        "reply_text": reply,
        "detailed_response": detail,
        "reply_audio_path": audio_path,
        "reply_audio_base64": base64_audio,
        "language_code": language_code,
        "conversation_id": conversation_id
    })