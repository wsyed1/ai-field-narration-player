from flask import Flask, jsonify, request
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from google.auth import default
import json
import os


# Set up Google credentials and Flask app
credentials, project_id = default()
app = Flask(__name__)

# Replace with your project ID and location
project_id = "stately-arc-434002-q1"
location = "us-central1"

vertexai.init(project=project_id, location=location)

model = GenerativeModel("gemini-1.5-flash-001")

def serialize_response(response):
    try:
        response_dict = {
            "candidates": [
                {
                    "content": {
                        "role": candidate.content.role,
                        "parts": [{"text": part.text} for part in candidate.content.parts]
                    },
                    "finish_reason": candidate.finish_reason,
                    "safety_ratings": [
                        {
                            "category": rating.category,
                            "probability": rating.probability,
                            "probability_score": rating.probability_score,
                            "severity": rating.severity,
                            "severity_score": rating.severity_score
                        } for rating in candidate.safety_ratings
                    ],
                    "avg_logprobs": candidate.avg_logprobs
                } for candidate in response.candidates
            ],
            "usage_metadata": {
                "prompt_token_count": response.usage_metadata.prompt_token_count,
                "candidates_token_count": response.usage_metadata.candidates_token_count,
                "total_token_count": response.usage_metadata.total_token_count
            }
        }
        return response_dict
    except AttributeError as e:
        print(f"Error processing response: {e}")
        return None

def transcribe_with_keyword(audio_file_path, keyword):
    with open(audio_file_path, "rb") as f:
        audio_data = f.read()

    audio_file = Part.from_data(audio_data, mime_type="audio/mpeg")

    prompt = f"""
    Can you return start and end timestamps for each word?

    # **Keyword:** {keyword}
    """

    contents = [audio_file, prompt]
    response = model.generate_content(contents)

    print("****************")
    response_dict = serialize_response(response)
    if response_dict:
        print(json.dumps(response_dict, indent=2))

    try:
        # Get the first candidate's response
        json_str = response.candidates[0].content.parts[0].text
        
        # Clean the response (remove markdown formatting)
        json_str = json_str.replace("```json\n", "").replace("```", "").strip()
        
        # Load the JSON response
        json_response = json.loads(json_str)

        # Extracting word information
        extracted_data = []
        for item in json_response:
            word = item['word']
            start_time = item['start']
            end_time = item['end']
            extracted_data.append((word, start_time, end_time))

        return extracted_data

    except json.JSONDecodeError as e:
        print("Error decoding JSON:", e)
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None


@app.route('/transcribe', methods=['POST'])
def transcribe():
    audio_file_path = f"{os.getcwd()}/Sample Audios/SampleAudio2.m4a"
    print("Full Audio File Path:", audio_file_path)
    # keyword = request.form.get('keyword')
    keyword = "test"

    if not keyword:
        return "Missing keyword", 400

    transcription = transcribe_with_keyword(audio_file_path, keyword)

    print("############")
    print(transcription)
    print("############")
    return jsonify(transcription)


if __name__ == '__main__':
    app.run(debug=True)