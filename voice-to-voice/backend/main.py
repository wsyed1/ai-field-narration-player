from flask import Flask
from voice_assistant_bp import voice_assistant_bp
from dotenv import load_dotenv
import os

app = Flask(__name__)

app.register_blueprint(voice_assistant_bp)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
