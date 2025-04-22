from flask import Flask
from ai_speech_to_text_whisper import ai_speech_to_text_whisper_bp
# from ai_speech_to_text_gemini import ai_speech_to_text_gemini_bp
from ai_speech_to_text_gpt4o import ai_speech_to_text_gpt4o_bp
from dotenv import load_dotenv
import os

app = Flask(__name__)

# register blueprints for each API
app.register_blueprint(ai_speech_to_text_whisper_bp)
# app.register_blueprint(ai_speech_to_text_gemini_bp)
app.register_blueprint(ai_speech_to_text_gpt4o_bp)

if __name__ == '__main__':
    app.run(debug=True)