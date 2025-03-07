# ai-field-narration-player

## Features

- Transcription of audio files to text using OpenAI's Whisper model.
- Synthesizes audio and returns word-level timestamps, temporarily storing the audio in memory.
- Provides a mapping of derived fields along with the corresponding audio segments where each field is spoken. For cases where the mapping is inferred, context is provided to aid understanding. Additionally, timestamps for significant sentences or meaningful parts of the audio help listeners identify which portions correspond to each derived field.
- Integration with Google Vertex AI for enhanced speech-to-text capabilities.


## Prerequisites

- Python 3.7 or higher
- Flask
- OpenAI Python client
- Google Vertex AI SDK
- Python Dotenv

## Setup Instructions

### 1. Clone the repository:

   ```bash
   git clone https://github.com/your_username/your_repository.git
   cd your_repository
   ```

### 2. Install the required packages:
    ```bash
    pip install flask openai python-dotenv google-cloud-vertex-ai

    ```

### 3. Set up environment variables:

Create a `.env` file at the project root and add your OpenAI API key and Google Cloud Vertex configuration:
```bash
openai_api_key=your_openai_api_key_here
GOOGLE_APPLICATION_CREDENTIALS=path_to_your_google_service_account_key.json
```

## Usage

### 1. Running the Application:

Run `main.py` on your terminal. Make sure you are in the path where the file is present

## APIs

### 1. Open AI Whisper

#### 1. Transcribe
Synthesizes the audio and returns a word level timestamp and stores the audio in the memory

##### cURL

```bash
curl --location 'http://localhost:5000/transcribe' \
--header 'Content-Type: application/json' \
--data '{"audio_file_path": "YOUR_AUDIO_FILE_PATH.m4a"}'
```


##### Sample Response

 ``` json
{
    "duration": 9.789999961853027,
    "language": "english",
    "task": "transcribe",
    "text": "My name is John Parker. I live in New York. I work in California. I have two kids, a boy and a girl.",
    "words": [
        {
            "end": 0.7200000286102295,
            "start": 0.11999999731779099,
            "word": "My"
        },
        {
            "end": 1.0199999809265137,
            "start": 0.7200000286102295,
            "word": "name"
        },
        {
            "end": 1.3200000524520874,
            "start": 1.0199999809265137,
            "word": "is"
        },
        {
            "end": 1.7400000095367432,
            "start": 1.3200000524520874,
            "word": "John"
        },
        {
            "end": 2.200000047683716,
            "start": 1.7400000095367432,
            "word": "Parker"
        },
        {
            "end": 3.059999942779541,
            "start": 3.059999942779541,
            "word": "I"
        },
        {
            "end": 3.059999942779541,
            "start": 3.059999942779541,
            "word": "live"
        },
        {
            "end": 3.359999895095825,
            "start": 3.059999942779541,
            "word": "in"
        },
        {
            "end": 3.5,
            "start": 3.359999895095825,
            "word": "New"
        },
        {
            "end": 3.740000009536743,
            "start": 3.5,
            "word": "York"
        },
        {
            "end": 4.900000095367432,
            "start": 4.699999809265137,
            "word": "I"
        },
        {
            "end": 5.179999828338623,
            "start": 4.900000095367432,
            "word": "work"
        },
        {
            "end": 5.679999828338623,
            "start": 5.179999828338623,
            "word": "in"
        },
        {
            "end": 6.099999904632568,
            "start": 5.679999828338623,
            "word": "California"
        },
        {
            "end": 7.059999942779541,
            "start": 7.059999942779541,
            "word": "I"
        },
        {
            "end": 7.21999979019165,
            "start": 7.059999942779541,
            "word": "have"
        },
        {
            "end": 7.440000057220459,
            "start": 7.21999979019165,
            "word": "two"
        },
        {
            "end": 7.800000190734863,
            "start": 7.440000057220459,
            "word": "kids"
        },
        {
            "end": 8.4399995803833,
            "start": 8.100000381469727,
            "word": "a"
        },
        {
            "end": 8.4399995803833,
            "start": 8.4399995803833,
            "word": "boy"
        },
        {
            "end": 8.720000267028809,
            "start": 8.4399995803833,
            "word": "and"
        },
        {
            "end": 9.140000343322754,
            "start": 8.720000267028809,
            "word": "a"
        },
        {
            "end": 9.140000343322754,
            "start": 9.140000343322754,
            "word": "girl"
        }
    ]
}
```


#### 2. Playback
This feature provides a mapping of fields along with the corresponding segments of audio where each field is spoken. When the mapping is not direct but inferred, it offers context to aid understanding. Additionally, it includes timestamps for significant sentences or meaningful parts of the audio, helping listeners identify which portions of the audio correspond to each derived field.


**Note**  Playback after the transcribe is called so that you have a recorded audio to playback and map fields

##### cURL

```bash
curl --location 'http://localhost:5000/playback' \
--header 'Content-Type: application/json' \
--data '{"audio_file_path": "YOUR_AUDIO_FILE_PATH.m4a"}'
```


##### Sample Response

``` json
{
    "data": [
        {
            "first_name": {
                "sentence_info": {
                    "sentence_spoken": {
                        "end_time": 2.2,
                        "start_time": 1.32,
                        "value": "My name is John Parker"
                    }
                },
                "value": "John"
            },
            "last_name": {
                "sentence_info": {
                    "sentence_spoken": {
                        "end_time": 2.2,
                        "start_time": 1.32,
                        "value": "My name is John Parker"
                    }
                },
                "value": "Parker"
            },
            "no_of_dependents": {
                "sentence_info": {
                    "sentence_spoken": {
                        "end_time": 9.14,
                        "start_time": 7.06,
                        "value": "I have two kids, a boy and a girl"
                    }
                },
                "value": 2
            }
        }
    ]
}
```

### 2. Google Vertex AI

#### 1. Transcribe
Synthesizes the audio and returns a word level timestamp and stores the audio in the memory

##### cURL

```bash
curl --location 'http://localhost:5000/transcribe' \
--header 'Content-Type: application/json' \
--data '{
           "audio_file_path": "YOUR_AUDIO_FILE_PATH.m4a",
           "keyword": "test"
         }'
```


##### Sample Response

 ``` json
[
    [
        "My",
        0.0,
        0.1
    ],
    [
        "name",
        0.1,
        0.4
    ],
    [
        "is",
        0.4,
        0.5
    ],
    [
        "John",
        0.5,
        0.9
    ],
    [
        "Parker",
        0.9,
        1.4
    ],
    [
        "I",
        1.5,
        1.6
    ],
    [
        "live",
        1.6,
        1.9
    ],
    [
        "in",
        1.9,
        2.1
    ],
    [
        "New",
        2.1,
        2.4
    ],
    [
        "York",
        2.4,
        2.8
    ],
    [
        "I",
        2.9,
        3.0
    ],
    [
        "work",
        3.0,
        3.3
    ],
    [
        "in",
        3.3,
        3.5
    ],
    [
        "California",
        3.5,
        4.3
    ],
    [
        "I",
        4.4,
        4.5
    ],
    [
        "have",
        4.5,
        4.8
    ],
    [
        "two",
        4.8,
        5.1
    ],
    [
        "kids",
        5.1,
        5.5
    ],
    [
        "a",
        5.6,
        5.7
    ],
    [
        "boy",
        5.7,
        6.0
    ],
    [
        "and",
        6.0,
        6.2
    ],
    [
        "a",
        6.2,
        6.3
    ],
    [
        "girl",
        6.3,
        6.7
    ]
]
```


#### 2. Playback
TBD