from flask import Flask, jsonify, request
from openai import OpenAI
from dotenv import load_dotenv
import os
import json

app = Flask(__name__)
load_dotenv()
client = OpenAI(api_key=os.getenv('openai_api_key'))

@app.route('/transcribe', methods=['POST'])
def transcribe():
    # Get the audio file path from the request
    data = request.get_json()
    audio_file_path = data.get('audio_file_path')

    if not audio_file_path:
        return jsonify({"error": "Audio file path not provided."}), 400
    
    print("Full Audio File Path:", audio_file_path)

    # Open the audio file
    try:
        with open(audio_file_path, 'rb') as audio_file:
            # Call OpenAI API to create the transcription
            transcript = client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-1",
                response_format="verbose_json",
                timestamp_granularities=["word"]
            )
    except FileNotFoundError:
        return jsonify({"error": "Audio file not found."}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # Store transcription data directly
    transcription_data = {
        'text': transcript.text,
        'task': transcript.task,
        'language': transcript.language,
        'duration': transcript.duration,
        'words': transcript.words,
    }

    # Return the transcription as JSON
    return jsonify(transcription_data)

@app.route('/playback', methods=['POST'])
def playback():
    # Get the audio file path from the request
    data = request.get_json()
    audio_file_path = data.get('audio_file_path')

    if not audio_file_path:
        return jsonify({"error": "Audio file path not provided."}), 400
    
    # Call the transcribe API internally
    transcribe_response = transcribe_internal(audio_file_path)

    if 'error' in transcribe_response:
        return transcribe_response  # Pass through error from /transcribe

    transcription_data = transcribe_response

    print("**********")
    print(transcription_data)
    print("**********")

    prompt = f"""
    Analyze the transcription data JSON: {json.dumps(transcription_data)} 
    and return a JSON array with the following schema:
    [
    {{
        "first_name": {{
        "value": "Harry",
        "sentence_info": {{
            "sentence_spoken": {{
            "value": "Hello, I am Harry McGill",
            "start_time": 0.12,
            "end_time": 2.20
            }}
        }}
        }},
        "last_name": {{
        "value": "McGill",
        "sentence_info": {{
            "sentence_spoken": {{
            "value": "Hello, I am Harry McGill",
            "start_time": 0.12,
            "end_time": 2.20
            }}
        }}
        }},
        "no_of_dependents": {{
        "value": 2,
        "sentence_info": {{
            "sentence_spoken": {{
            "value": "I have a boy and a girl",
            "start_time": 7.06,
            "end_time": 9.14
            }}
        }}
        }}
    }}
    ]
    """

    # Make the API call to the OpenAI model to generate a response
    completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that infers personal data from transcriptions."},
            {"role": "user", "content": prompt},
        ],
        functions=[{
            "name": "fn_set_personal_info", 
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "first_name": {
                                    "type": "object",
                                    "properties": {
                                        "value": {"type": "string"},
                                        "sentence_info": {
                                            "type": "object",
                                            "properties": {
                                                "sentence_spoken": {
                                                    "type": "object",
                                                    "properties": {
                                                        "value": {"type": "string"},
                                                        "start_time": {"type": "number"},
                                                        "end_time": {"type": "number"}
                                                    }
                                                }
                                            }
                                        }
                                    }
                                },
                                "last_name": {
                                    "type": "object",
                                    "properties": {
                                        "value": {"type": "string"},
                                        "sentence_info": {
                                            "type": "object",
                                            "properties": {
                                                "sentence_spoken": {
                                                    "type": "object",
                                                    "properties": {
                                                        "value": {"type": "string"},
                                                        "start_time": {"type": "number"},
                                                        "end_time": {"type": "number"}
                                                    }
                                                }
                                            }
                                        }
                                    }
                                },
                                "no_of_dependents": {
                                    "type": "object",
                                    "properties": {
                                        "value": {"type": "integer"},
                                        "sentence_info": {
                                            "type": "object",
                                            "properties": {
                                                "sentence_spoken": {
                                                    "type": "object",
                                                    "properties": {
                                                        "value": {"type": "string"},
                                                        "start_time": {"type": "number"},
                                                        "end_time": {"type": "number"}
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }]
    )

    print("==============")
    print(completion)
    print("==============")

    # Handle the response
    try:
        generated_text = completion.choices[0].message.function_call.arguments
        return json.loads(generated_text)
    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify({"error": "Failed to process the request."}), 500

def transcribe_internal(audio_file_path):
    # Function to handle internal calls to the transcribe API
    data = {'audio_file_path': audio_file_path}
    response = transcribe()  # Call the transcribe function directly
    return response.get_json()  # Extract JSON data from the response

if __name__ == '__main__':
    app.run(debug=True)
