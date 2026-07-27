import speech_recognition as sr
import pyttsx3
import requests
import json
import os
import datetime
import time
import subprocess
import base64 # For encoding images
import cv2 # For webcam access
import threading # For scheduling alarms/reminders
import re # For regular expressions to parse time
import fuzzywuzzy.fuzz as fuzz # Explicit import for fuzz
import fuzzywuzzy.process as process # Explicit import for process
import webbrowser # For opening web pages like YouTube

# New imports for Cohere DMM and googlesearch
import cohere
from googlesearch import search
from dotenv import dotenv_values

# --- Configuration ---
# IMPORTANT: Configure your API Keys and LLM providers here.
# Add more API keys to the lists for increased robustness (system will cycle through them).
#
# For Gemini: Ensure you use a SERVER-SIDE API KEY from Google Cloud Console
# or Google AI Studio, enabled for the "Generative Language API".
# Client-side keys (like those for Firebase Web SDK) will NOT work for direct API calls.

# Load environment variables
env_vars = dotenv_values(".env")
# Ensure these keys are present in your .env file
# CohereAPIKey = env_vars.get("CohereAPIKey") # Using a placeholder for now
# GroqAPIKey = env_vars.get("GroqAPIKey") # Using a placeholder for now
# Username = env_vars.get("Username", "Sir")
# Assistantname = env_vars.get("Assistantname", "AI Assistant")

# Placeholder for API keys if .env is not used or keys are missing
CohereAPIKey = env_vars.get("CohereAPIKey", "") # Fallback to user-provided key
GroqAPIKey = env_vars.get("GroqAPIKey", "") # Fallback to user-provided key

# User and Assistant names for system prompts
Username = env_vars.get("Username", "User")
Assistantname = env_vars.get("Assistantname", "AI Assistant")


LLM_CONFIG = {
    "gemini": {
        "api_keys": [
            "", # Replace with your actual, valid Gemini API Key
            # "YOUR_SECOND_VALID_GEMINI_API_KEY_HERE", # Add more Gemini keys if available
        ],
        "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
        "model": "gemini-2.0-flash"
    },
    "gemini-vision": { # New entry for Gemini Pro Vision model
        "api_keys": [
            "", # Use the same Gemini API Key, ensure it has vision permissions
            # "YOUR_SECOND_VALID_GEMINI_API_KEY_FOR_VISION", # Or a different key if preferred
        ],
        "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro-vision:generateContent",
        "model": "gemini-pro-vision"
    },
    "huggingface": {
        "api_keys": [""], # Your Hugging Face API Token
        "url": "https://api-inference.huggingface.co/models/",
        "model": "google/gemma-2b-it" # Changed to Gemma 2B Instruction-tuned model
        # You can change this to other Hugging Face models like:
        # "mistralai/Mistral-7B-Instruct-v0.2"
        # "google/gemma-7b-it"
        # "meta-llama/Llama-2-7b-chat-hf" (requires specific access on HF)
    },
    "groq": {
        "api_keys": [GroqAPIKey], # Use Groq API Key from .env
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "model": "llama3-70b-8192" # Updated to llama3-70b-8192 as per user's request
    }
}

DEFAULT_LLM_PROVIDER = "gemini" # Set your preferred default: "gemini", "huggingface", or "groq"

# File to store chat history
CHAT_HISTORY_FILE = "chat_history.json"
# Placeholder for app ID (not directly used for Firestore in this Python version, but kept for context)
APP_ID = "python-ai-assistant"

# Number of lines to speak before asking to continue
LINES_PER_CHUNK = 4

# --- Text-to-Speech Engine Initialization ---
engine = None
try:
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    male_voice = next((v for v in voices if 'male' in v.name.lower() or 'zira' in v.name.lower() or 'david' in v.name.lower() or 'en-us' in v.id.lower()), None)
    if male_voice:
        engine.setProperty('voice', male_voice.id)
    engine.setProperty('rate', 180)
except Exception as e:
    print(f"Error initializing text-to-speech engine: {e}. Speech output will be unavailable.")
    engine = None


# --- Global Application Commands ---
FUZZY_MATCH_THRESHOLD = 70

APP_COMMANDS = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "command prompt": "cmd.exe",
    "cmd": "cmd.exe",
    "paint": "mspaint.exe",
    "wordpad": "wordpad.exe",
    "browser": "start chrome" if os.name == 'nt' else "xdg-open https://www.google.com" if os.name == 'posix' else "open https://www.google.com",
    "chrome": "chrome" if os.name == 'posix' or os.name == 'darwin' else "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "firefox": "firefox",
    "vlc": "vlc",
    "code": "code",
    "excel": "excel.exe",
    "word": "winword.exe",
    "powerpoint": "powerpnt.exe",
    "settings": "ms-settings:" if os.name == 'nt' else None,
    "photos": "ms-photos:" if os.name == 'nt' else None,
    "mail": "outlook" if os.name == 'nt' else "thunderbird" if os.name == 'posix' else None,
    "calendar": "outlookcal:" if os.name == 'nt' else None,
    "spotify": "spotify",
    "discord": "discord",
    "steam": "steam",
    "file explorer": "explorer.exe" if os.name == 'nt' else None,
    "files": "explorer.exe" if os.name == 'nt' else "nautilus" if os.name == 'posix' else "open /System/Library/CoreServices/Finder.app",
    "task manager": "taskmgr.exe" if os.name == 'nt' else None,
    "control panel": "control.exe" if os.name == 'nt' else None,
    "device manager": "devmgmt.msc" if os.name == 'nt' else None,
    "notepad++": "notepad++.exe",
    "sublime text": "subl",
    "gimp": "gimp",
    "krita": "krita",
    "blender": "blender",
    "zoom": "zoom",
    "skype": "skype",
    "teams": "msteams",
    "slack": "slack",
    "obs": "obs",
    "obs studio": "obs",
    "photoshop": "photoshop.exe",
    "illustrator": "illustrator.exe",
    "premiere pro": "premiere.exe",
}

# --- Cohere DMM Setup ---
cohere_client = None
try:
    cohere_client = cohere.Client(api_key=CohereAPIKey)
except Exception as e:
    print(f"Error initializing Cohere client: {e}. Decision-Making Model will not function.")

# DMM functions list (from user's provided code)
DMM_FUNCS = [
    "exit", "general", "realtime", "open", "close", "play",
    "generate image", "system", "content", "google search",
    "youtube search", "reminder"
]

DMM_PREAMBLE = f"""
You are a very accurate Decision-Making Model, which decides what kind of a query is given to you.
You will decide whether a query is a 'general' query, a 'realtime' query, or is asking to perform any task or automation like 'open facebook, instagram', 'can you write a application and open it in notepad'
*** Do not answer any query, just decide what kind of query is given to you. ***
-> Respond with 'general ( query )' if a query can be answered by a llm model (conversational ai chatbot) and doesn't require any up to date information like if the query is 'who was akbar?' respond with 'general who was akbar?', if the query is 'how can i study more effectively?' respond with 'general how can i study more effectively?', if the query is 'can you help me with this math problem?' respond with 'general can you help me with this math problem?', if the query is 'Thanks, i really liked it.' respond with 'general thanks, i really liked it.' , if the query is 'what is python programming language?' respond with 'general what is python programming language?', etc. Respond with 'general (query)' if a query doesn't have a proper noun or is incomplete like if the query is 'who is he?' respond with 'general who is he?', if the query is 'what's his networth?' respond with 'general what's his networth?', if the query is 'tell me more about him.' respond with 'general tell me more about him.', and so on even if it require up-to-date information to answer. Respond with 'general (query)' if the query is asking about time, day, date, month, year, etc like if the query is 'what's the time?' respond with 'general what's the time?'.
-> Respond with 'realtime ( query )' if a query can not be answered by a llm model (because they don't have realtime data) and requires up to date information like if the query is 'who is indian prime minister' respond with 'realtime who is indian prime minister', if the query is 'tell me about facebook's recent update.' respond with 'realtime tell me about facebook's recent update.', if the query is 'tell me news about coronavirus.' respond with 'realtime tell me news about coronavirus.', etc and if the query is asking about any individual or thing like if the query is 'who is akshay kumar' respond with 'realtime who is akshay kumar', if the query is 'what is today's news?' respond with 'realtime what is today's headline?', if the query is 'what is today's headline?' respond with 'realtime what is today's headline?', etc.
-> Respond with 'open (application name or website name)' if a query is asking to open any application like 'open facebook', 'open telegram', etc. but if the query is asking to open multiple applications, respond with 'open 1st application name, open 2nd application name' and so on.
-> Respond with 'close (application name)' if a query is asking to close any application like 'close notepad', 'close facebook', etc. but if the query is asking to close multiple applications or websites, respond with 'close 1st application name, close 2nd application name' and so on.
-> Respond with 'play (song name)' if a query is asking to play a specific song directly, like 'play afsanay by ys', 'play let her go'. If the query is asking to play multiple songs, respond with 'play 1st song name, play 2nd song name' and so on.
-> Respond with 'generate image (image prompt)' if a query is requesting to generate a image with given prompt like 'generate image of a lion', 'generate image of a cat', etc. but if the query is asking to generate multiple images, respond with 'generate image 1st image prompt, generate image 2nd image prompt' and so on.
-> Respond with 'reminder (datetime with message)' if a query is requesting to set a reminder like 'set a reminder at 9:00pm on 25th june for my business meeting.' respond with 'reminder 9:00pm 25th june business meeting'.
-> Respond with 'system (task name)' if a query is asking to mute, unmute, volume up, volume down , etc. but if the query is asking to do multiple tasks, respond with 'system 1st task, system 2nd task', etc.
-> Respond with 'content (topic)' if a query is asking to write any type of content like application, codes, emails or anything else about a specific topic but if the query is asking to write multiple types of content, respond with 'content 1st topic, content 2nd topic' and so on.
-> Respond with 'google search (topic)' if a query is asking to search a specific topic on Google or the web, including phrases like 'search for [topic]', '[topic] in Chrome', 'search Google for [topic]', 'what is [topic] on the web'. If asking to search multiple topics, respond with 'google search 1st topic, google search 2nd topic' and so on.
-> Respond with 'youtube search (topic)' if a query is asking to search a specific topic on YouTube, including phrases like 'search YouTube for [topic]', 'find [video] on YouTube', 'play [music] in YouTube', 'search for [topic] in YouTube'. If asking to search multiple topics, respond with 'youtube search 1st topic, youtube search 2nd topic' and so on.
*** If the query is asking to perform multiple tasks like 'open facebook, telegram and close whatsapp' respond with 'open facebook, open telegram, close whatsapp' ***
*** If the user is saying goodbye or wants to end the conversation like 'bye jarvis.' respond with 'exit'.***
*** Respond with 'general (query)' if you can't decide the kind of query or if a query is asking to perform a task which is not mentioned above. ***
"""

# DMM's internal chat history for few-shot learning
DMM_CHAT_HISTORY = [
    {"role": "User", "message": "how are you ?"},
    {"role": "Chatbot", "message": "general how are you ?"},
    {"role": "User", "message": "do you like pizza ?"},
    {"role": "Chatbot", "message": "general do you like pizza ?"},
    {"role": "User", "message": "open chrome and tell me about mahatma gandhi."},
    {"role": "Chatbot", "message": "open chrome, general tell me about mahatma gandhi."},
    {"role": "User", "message": "open chrome and firefox"},
    {"role": "Chatbot", "message": "open chrome, open firefox"},
    {"role": "User", "message": "what is today's date and by the way remind me that i have a dancing performance on 5th at 11pm "},
    {"role": "Chatbot", "message": "general what is today's date, reminder 11:00pm 5th aug dancing performance"},
    {"role": "User", "message": "chat with me."},
    {"role": "Chatbot", "message": "general chat with me."}
]

def FirstLayerDMM(prompt: str = "test"):
    """
    Uses Cohere's Command-R-Plus to classify the user's prompt into a predefined function.
    """
    global DMM_CHAT_HISTORY # Declare global to modify it

    if cohere_client is None:
        print("Cohere client not initialized. Cannot use Decision-Making Model.")
        return ["general (Error: DMM not available)"]

    try:
        # Create a temporary chat history for the current request
        # This prevents polluting the global DMM_CHAT_HISTORY with failed or empty responses
        # until a successful response is received.
        # Ensure all messages in history have a non-empty 'message' field
        cleaned_dmm_history = []
        for entry in DMM_CHAT_HISTORY:
            if 'message' in entry and entry['message'].strip():
                cleaned_dmm_history.append(entry)
            else:
                print(f"Warning: Skipping DMM history entry with empty message: {entry}")

        # Add the current user prompt to the history for the API call
        current_dmm_history_for_api = list(cleaned_dmm_history) # Create a copy
        current_dmm_history_for_api.append({"role": "User", "message": prompt})

        stream = cohere_client.chat(
            model='command-r-plus',
            message=prompt,
            temperature=0.7,
            chat_history=current_dmm_history_for_api, # Use the temporary history
            prompt_truncation='OFF',
            connectors=[],
            preamble=DMM_PREAMBLE
        )

        response_text = ""
        for event in stream:
            if hasattr(event, 'event_type') and event.event_type == "text-generation":
                response_text += event.text
            elif isinstance(event, str): # Fallback for older cohere-api versions or different event types
                response_text += event

        response_text = response_text.replace("\n", "").strip()
        
        # Ensure response_text is not empty before updating DMM_CHAT_HISTORY
        if not response_text:
            response_text = f"general (DMM could not classify: {prompt})" # Fallback if DMM returns empty
            print(f"Warning: DMM returned empty response. Using fallback: {response_text}")

        # ONLY update global DMM_CHAT_HISTORY if the API call was successful and response_text is valid
        # The prompt was already added to `current_dmm_history_for_api`, so we just add the chatbot response
        DMM_CHAT_HISTORY.append({"role": "Chatbot", "message": response_text})
        
        # Parse multiple commands if present
        classified_commands = [i.strip() for i in response_text.split(",")]

        # Filter to ensure only valid DMM_FUNCS are returned
        filtered_commands = []
        for task in classified_commands:
            for func in DMM_FUNCS:
                if task.startswith(func):
                    filtered_commands.append(task)
                    break # Found a match, move to next task

        if not filtered_commands:
            # If nothing matched after filtering, default to general query
            return [f"general ({prompt})"]
        
        return filtered_commands

    except Exception as e:
        print(f"Error in FirstLayerDMM: {e}")
        # Do NOT append to DMM_CHAT_HISTORY if an exception occurred
        return [f"general (Error in DMM: {e}. Original query: {prompt})"]


# --- Helper Functions ---

def listen_for_yes_no():
    """
    Listens for a simple 'yes' or 'no' command for continuation.
    """
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("AI: (Waiting for 'yes' or 'no'...)")
        try:
            r.adjust_for_ambient_noise(source, duration=0.5) # Shorter adjustment
            audio = r.listen(source, timeout=3, phrase_time_limit=3) # Shorter timeout
            response = r.recognize_google(audio)
            print(f"You responded: {response}")
            return response
        except sr.WaitTimeoutError:
            print("No 'yes' or 'no' response detected.")
            return None # No speech
        except (sr.UnknownValueError, sr.RequestError) as e:
            print(f"Error understanding 'yes'/'no' response: {e}")
            return "" # Unclear or error, treat as unclear

def speak_response(text):
    """
    Converts text to speech and prints to console.
    Handles long texts by asking to continue after a few lines.
    """
    if engine is None:
        print(f"AI (Speech Disabled): {text}")
        return # Skip speech if engine not initialized

    lines = text.split('\n')
    current_line_index = 0
    total_lines = len(lines)

    while current_line_index < total_lines:
        chunk_to_speak = []
        for i in range(LINES_PER_CHUNK):
            if current_line_index < total_lines:
                chunk_to_speak.append(lines[current_line_index])
                current_line_index += 1
            else:
                break

        if chunk_to_speak:
            chunk_text = "\n".join(chunk_to_speak)
            print(f"AI: {chunk_text}")
            try:
                engine.say(chunk_text)
                engine.runAndWait()
                time.sleep(0.5) # Small pause after speaking a chunk
            except Exception as e:
                print(f"Error during speech output: {e}. Continuing without speech.")
                # If speech fails, just print and continue
                pass

        if current_line_index < total_lines:
            # If there are more lines, ask to continue
            try:
                engine.say("Would you like me to continue, sir?")
                engine.runAndWait()
                time.sleep(0.5) # Pause before listening
            except Exception as e:
                print(f"Error asking to continue: {e}. Skipping continuation prompt.")
                break # Break if continuation prompt fails

            response = listen_for_yes_no()
            if response is None: # No response within timeout
                speak_response("No response, sir. I will stop here.")
                break
            elif "no" in response.lower() or "stop" in response.lower() or "that's enough" in response.lower():
                speak_response("Very well, sir. I will stop here.")
                break
            elif "yes" in response.lower() or "continue" in response.lower() or "next" in response.lower():
                # Continue loop
                pass
            else:
                speak_response("I didn't quite catch that, sir. I will continue.")
                # Continue loop by default if unclear


def load_chat_history():
    """Loads chat history from a JSON file."""
    if os.path.exists(CHAT_HISTORY_FILE):
        try:
            with open(CHAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
                for msg in history:
                    if 'timestamp' in msg and isinstance(msg['timestamp'], str):
                        try:
                            msg['timestamp'] = datetime.datetime.fromisoformat(msg['timestamp'])
                        except ValueError:
                            # Handle cases where timestamp might be malformed
                            msg['timestamp'] = datetime.datetime.now() # Default to current time
                            print(f"Warning: Malformed timestamp in chat history. Corrected for entry: {msg['text']}")
                return history
        except json.JSONDecodeError:
            print(f"Warning: Could not decode JSON from {CHAT_HISTORY_FILE}. File might be corrupt. Starting with empty history.")
            # Optionally, back up the corrupt file before overwriting
            # os.rename(CHAT_HISTORY_FILE, CHAT_HISTORY_FILE + ".bak")
            return []
        except IOError as e:
            print(f"Error reading chat history file {CHAT_HISTORY_FILE}: {e}. Starting with empty history.")
            return []
    return []

def save_chat_history(history):
    """Saves chat history to a JSON file."""
    serializable_history = []
    for msg in history:
        temp_msg = msg.copy()
        if 'timestamp' in temp_msg and isinstance(temp_msg['timestamp'], datetime.datetime):
            temp_msg['timestamp'] = temp_msg['timestamp'].isoformat()
        serializable_history.append(temp_msg)

    try:
        with open(CHAT_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(serializable_history, f, indent=4)
    except IOError as e:
        print(f"Error saving chat history to {CHAT_HISTORY_FILE}: {e}. History might not be saved.")

def listen_for_command():
    """Listens for voice commands from the microphone."""
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("\nListening for command, sir...")
        try:
            r.adjust_for_ambient_noise(source, duration=1)
            audio = r.listen(source, timeout=5, phrase_time_limit=10)
            print("Processing command...")
            command = r.recognize_google(audio)
            print(f"You said: {command}")
            return command
        except sr.WaitTimeoutError:
            print("No speech detected, sir.")
            return None
        except sr.UnknownValueError:
            print("Could not understand audio, sir. Please try again.")
            speak_response("Sir, I could not understand the audio. Please try again.")
            return None
        except sr.RequestError as e:
            print(f"Could not request results from Google Speech Recognition service; {e}, sir. Please check your internet connection.")
            speak_response(f"Sir, I am having trouble connecting to the speech recognition service. Please check your internet connection.")
            return None
        except Exception as e:
            print(f"An unexpected error occurred during speech recognition: {e}")
            speak_response("Sir, an unexpected error occurred while listening. Please try again.")
            return None

def capture_image_from_webcam():
    """
    Captures a single image from the default webcam and returns its Base64 encoded string.
    Requires OpenCV (cv2) to be installed.
    """
    cap = None
    try:
        cap = cv2.VideoCapture(0) # 0 is typically the default webcam

        if not cap.isOpened():
            print("Error: Could not open webcam, sir.")
            return None, "Sir, I could not access the webcam. Please ensure it's connected and not in use by another application."

        ret, frame = cap.read() # Read a frame

        if not ret:
            print("Error: Could not read frame from webcam, sir.")
            return None, "Sir, I failed to capture an image from the webcam."

        # Encode the image to JPEG format
        _, buffer = cv2.imencode('.jpg', frame)
        # Convert to base64
        jpg_as_text = base64.b64encode(buffer).decode('utf-8')
        return jpg_as_text, None
    except Exception as e:
        print(f"An error occurred during webcam capture: {e}")
        return None, f"Sir, an error occurred while trying to use the webcam: {e}"
    finally:
        if cap:
            cap.release() # Ensure webcam is released


def call_llm_api(provider, chat_history_for_llm, user_query_for_llm, image_data_base64=None):
    """
    Calls the specified LLM API with the chat history and the current user query,
    trying multiple API keys if available for that provider.
    Can also send image data for vision models.
    """
    config = LLM_CONFIG.get(provider)
    if not config:
        return f"Sir, the LLM provider '{provider}' is not configured."

    api_keys = config["api_keys"]
    base_url = config["url"]
    model_name = config["model"]

    if not api_keys:
        return f"Sir, no API keys are configured for {provider}. Please add at least one key."

    headers = {'Content-Type': 'application/json'}

    # System instruction for LLM to control verbosity and maintain persona
    system_instruction = (
        f"You are a concise, helpful AI assistant named {Assistantname}. Always address the user as '{Username}'. "
        "Format your responses as natural, coherent paragraphs. Avoid overly long "
        "introductions, conclusions, or conversational filler. Get straight to the point."
    )

    payload = {}
    api_endpoint = base_url

    if provider == "gemini" or provider == "gemini-vision":
        gemini_contents = []
        # Add system instruction as the first user turn to guide Gemini's persona
        gemini_contents.append({"role": "user", "parts": [{"text": system_instruction}]})

        if image_data_base64 and provider == "gemini-vision":
            # For vision, the text prompt is directly related to the image
            # The user_query_for_llm will be the image description request.
            gemini_contents.append({
                "role": "user",
                "parts": [
                    {"text": user_query_for_llm}, # e.g., "Describe this image, sir."
                    {"inlineData": {"mimeType": "image/jpeg", "data": image_data_base64}}
                ]
            })
            payload = {"contents": gemini_contents}
            api_endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key=" # Specific endpoint for vision
        else:
            # Text-only Gemini request (or vision model called without image)
            for msg in chat_history_for_llm:
                role = "user" if msg['sender'] == 'user' else "model"
                gemini_contents.append({"role": role, "parts": [{"text": msg['text']}]})
            gemini_contents.append({"role": "user", "parts": [{"text": user_query_for_llm}]})
            payload = {"contents": gemini_contents}
            api_endpoint = f"{base_url}?key=" # API key appended later

    elif provider == "huggingface":
        hf_chat_string = system_instruction + "\n\n"
        for msg in chat_history_for_llm:
            hf_chat_string += f"{'User' if msg['sender'] == 'user' else 'AI'}: {msg['text']}\n"
        hf_chat_string += f"User: {user_query_for_llm}\nAI:"
        payload = {"inputs": hf_chat_string, "parameters": {"max_new_tokens": 250}}
        api_endpoint = f"{base_url}{model_name}"

    elif provider == "groq":
        # Groq client uses different message structure
        groq_messages = []
        groq_messages.append({"role": "system", "content": system_instruction})
        for msg in chat_history_for_llm:
            role = "user" if msg['sender'] == 'user' else "assistant"
            groq_messages.append({"role": role, "content": msg['text']})
        groq_messages.append({"role": "user", "content": user_query_for_llm})
        payload = {
            "model": model_name,
            "messages": groq_messages,
            "max_tokens": 2048 # Increased max_tokens for Groq as per user's example
        }
        api_endpoint = base_url

    else:
        return f"Sir, unsupported LLM provider: {provider}."

    for key in api_keys:
        # Basic check for empty API key
        if not key:
            print(f"Skipping {provider} due to empty API key configuration.")
            continue

        current_headers = headers.copy()
        if provider == "gemini" or provider == "gemini-vision":
            full_url = f"{api_endpoint}{key}"
        elif provider == "huggingface":
            current_headers["Authorization"] = f"Bearer {key}"
            full_url = api_endpoint
        elif provider == "groq":
            current_headers["Authorization"] = f"Bearer {key}"
            full_url = api_endpoint
        else:
            full_url = api_endpoint

        try:
            response = requests.post(full_url, headers=current_headers, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()

            if provider == "gemini" or provider == "gemini-vision":
                if result.get('candidates') and result['candidates'][0].get('content') and result['candidates'][0]['content'].get('parts'):
                    return result['candidates'][0]['content']['parts'][0].get('text', "No response text found.")
            elif provider == "huggingface":
                if isinstance(result, list) and result and result[0].get('generated_text'):
                    generated_text = result[0]['generated_text']
                    if generated_text.startswith(hf_chat_string):
                        return generated_text[len(hf_chat_string):].strip()
                    return generated_text.strip()
            elif provider == "groq":
                if result.get('choices') and result['choices'][0].get('message') and result['choices'][0]['message'].get('content'):
                    return result['choices'][0]['message']['content'].strip().replace("</s>", "") # Remove </s> token
            else:
                print(f"API Key {key[:5]}... for {provider}: Unexpected API response structure: {result}")
                continue

        except requests.exceptions.HTTPError as errh:
            status_code = errh.response.status_code
            error_message = f"API Key {key[:5]}... for {provider}: Http Error {status_code}: {errh}"
            print(error_message)
            if status_code in [401, 403, 429]:
                print(f"API Key {key[:5]}... for {provider} is invalid/forbidden/rate-limited. Trying next key.")
                continue
            # For other HTTP errors, we still want to try the next provider
            return f"ERROR_RESPONSE: {provider} service returned an error ({status_code})."
        except requests.exceptions.ConnectionError as errc:
            print(f"API Key {key[:5]}... for {provider}: Error Connecting: {errc}")
            return f"ERROR_RESPONSE: {provider} connection error." # Indicate failure to trigger switch
        except requests.exceptions.Timeout as errt:
            print(f"API Key {key[:5]}... for {errt}")
            return f"ERROR_RESPONSE: {provider} timeout error." # Indicate failure to trigger switch
        except requests.exceptions.RequestException as err:
            print(f"API Key {key[:5]}... for {provider}: Something went wrong: {err}")
            return f"ERROR_RESPONSE: {provider} unknown request error." # Indicate failure to trigger switch
        except json.JSONDecodeError as e:
            print(f"API Key {key[:5]}... for {provider}: JSON decoding error in response: {e}")
            return f"ERROR_RESPONSE: {provider} invalid JSON response."

    return f"ERROR_RESPONSE: All configured API keys for {provider} failed to provide a response."


def open_application(app_name_exact_match):
    """
    Attempts to open a specified application using its exact command.
    This function is called *after* fuzzy matching has identified the best app name.
    WARNING: This executes commands on your operating system. Use with EXTREME caution.
    """
    command_to_execute = APP_COMMANDS.get(app_name_exact_match.lower())

    if command_to_execute:
        try:
            if os.name == 'nt': # For Windows
                if isinstance(command_to_execute, str) and command_to_execute.startswith("start "):
                    subprocess.Popen(command_to_execute, shell=True)
                else:
                    os.startfile(command_to_execute)
            elif os.name == 'posix' or os.name == 'darwin': # For Linux/macOS
                if isinstance(command_to_execute, str) and (" " in command_to_execute and ("xdg-open" in command_to_execute or "open" in command_to_execute)):
                    subprocess.Popen(command_to_execute.split(), shell=False) # Use shell=False for security
                else:
                    subprocess.Popen(command_to_execute.split())
            else:
                speak_response(f"Apologies, sir. I do not recognize your operating system to open applications.")
                return False

            speak_response(f"Certainly, sir. Opening {app_name_exact_match.replace('_', ' ').title()}.") # Format for speaking
            return True
        except FileNotFoundError:
            speak_response(f"Apologies, sir. I could not find '{app_name_exact_match}'. Please ensure it's installed and accessible, or check its configured command.")
            return False
        except Exception as e:
            speak_response(f"An error occurred while trying to open {app_name_exact_match}, sir: {e}")
            return False
    else:
        speak_response(f"I'm sorry, sir, I encountered an internal issue trying to execute the command for '{app_name_exact_match}'.")
        return False

def handle_app_command(command_text):
    """
    Analyzes the command text to determine if it's an application opening request.
    If so, it attempts to open the application using fuzzy matching.
    Returns True if an app opening request was identified and handled (even if it failed to open),
    False otherwise.
    """
    lower_command = command_text.lower().strip()
    app_name_candidate = None

    # Check if command starts with "open "
    if lower_command.startswith("open "):
        app_name_candidate = lower_command[len("open "):].strip()
        if not app_name_candidate:
            speak_response("Sir, please specify which application you wish to open. For example, 'open Notepad'.")
            return True # Handled the empty "open" command
    else:
        # Check if the command itself is a potential app name (e.g., "notepad", "cmd")
        # This is for direct app name commands without "open" prefix
        app_name_candidate = lower_command

    if app_name_candidate:
        app_keys = list(APP_COMMANDS.keys())
        # Ensure fuzzywuzzy.process is available
        if 'process' not in globals() or not hasattr(process, 'extractOne'):
            print("Warning: fuzzywuzzy.process not fully imported. Skipping fuzzy matching for app commands.")
            return False

        best_match = process.extractOne(app_name_candidate, app_keys, scorer=fuzz.ratio)

        if best_match and best_match[1] >= FUZZY_MATCH_THRESHOLD:
            matched_app_name = best_match[0]
            if APP_COMMANDS.get(matched_app_name) is None:
                speak_response(f"Sir, I found '{matched_app_name}', but I don't have a command configured to open it on your system.")
                return True # Handled, but can't open
            return open_application(matched_app_name)
        else:
            # No sufficiently close match found, not an app command
            return False
    return False # No app name candidate found

# --- Date and Time Functions ---

def tell_current_time():
    """Tells the current date and time."""
    now = datetime.datetime.now()
    formatted_time = now.strftime("The current time is %I:%M %p on %A, %B %d, %Y, sir.")
    speak_response(formatted_time)

def set_alarm_or_reminder(command_text):
    """
    Sets an alarm or reminder based on the command text.
    Parses time and message from the command.
    Returns True if the command was recognized as an alarm/reminder request (even if parsing failed),
    False otherwise.
    """
    lower_command = command_text.lower()
    message = "your reminder"
    time_delta_seconds = 0
    alarm_set_successfully = False

    # Check if the command is even intended for alarm/reminder
    is_alarm_command = any(phrase in lower_command for phrase in [
        "set an alarm for", "remind me at", "remind me in",
        "set a reminder for", "set alarm in", "alarm for", "reminder for"
    ])

    if not is_alarm_command:
        return False # Not an alarm/reminder command

    # 1. Try to extract message first (e.g., "to take out the trash")
    message_match = re.search(r'to\s+(.+)', lower_command)
    if message_match:
        message = message_match.group(1).strip()
        # Remove message part from command for easier time parsing
        lower_command = lower_command.replace(message_match.group(0), "").strip()

    # 2. Try to parse relative time (e.g., "in 5 minutes", "5 minutes from now")
    # Pattern: (number) (minute/minutes/hour/hours/second/seconds) (optional "from now" / "in")
    match_relative = re.search(r'(\d+)\s+(minute|minutes|hour|hours|second|seconds)\s*(?:from\s+now|from|in)?', lower_command)
    if match_relative:
        try:
            value = int(match_relative.group(1))
            unit = match_relative.group(2)
            if unit.startswith("minute"):
                time_delta_seconds = value * 60
            elif unit.startswith("hour"):
                time_delta_seconds = value * 3600
            elif unit.startswith("second"):
                time_delta_seconds = value
            
            alarm_set_successfully = True
        except ValueError:
            print(f"Error parsing number for relative time: {match_relative.group(1)}")
            pass # Continue to absolute time parsing

    # 3. If not relative, try to parse absolute time (e.g., "at 7 PM", "for 14:30")
    if not alarm_set_successfully:
        time_str_match = re.search(r'(?:at|for)\s+([\d:apAP\s]+)', lower_command)
        if time_str_match:
            time_str = time_str_match.group(1).strip()
            now = datetime.datetime.now()
            alarm_datetime = None

            time_formats = [
                "%I:%M %p", "%I %p", # 7:30 PM, 7 PM
                "%H:%M",             # 19:00
                "%I%p",              # 7PM
                "%I",                # 7 (assume AM/PM based on current hour)
            ]

            for fmt in time_formats:
                try:
                    parsed_time = datetime.datetime.strptime(time_str, fmt).time()
                    alarm_datetime = now.replace(hour=parsed_time.hour, minute=parsed_time.minute, second=0, microsecond=0)

                    # Handle AM/PM ambiguity and past times
                    if "p" not in fmt.lower() and "a" not in fmt.lower() and parsed_time.hour < 12:
                        if alarm_datetime < now and (now - alarm_datetime).total_seconds() > 3600: # If more than an hour ago
                            alarm_datetime += datetime.timedelta(hours=12) # Assume PM

                    if alarm_datetime < now:
                        alarm_datetime += datetime.timedelta(days=1)
                    break
                except ValueError:
                    continue # Try next format
            
            if alarm_datetime:
                time_delta_seconds = (alarm_datetime - now).total_seconds()
                alarm_set_successfully = True

    if not alarm_set_successfully or time_delta_seconds <= 0:
        speak_response("Sir, I could not understand the time for your reminder. Please specify a future time, like 'in 5 minutes' or 'at 7 PM'.")
        return True # Indicate that it was an alarm command, but parsing failed

    speak_response(f"Certainly, sir. I will remind you at {datetime.datetime.now() + datetime.timedelta(seconds=time_delta_seconds):%I:%M %p} about {message}.")

    def alarm_function(msg):
        speak_response(f"Sir, this is your reminder: {msg}")

    # Ensure time_delta_seconds is positive before scheduling
    if time_delta_seconds > 0:
        timer = threading.Timer(time_delta_seconds, alarm_function, args=[message])
        timer.start()
        return True # Indicate successful handling of the alarm command
    else:
        speak_response("Sir, the reminder time calculated was not in the future. Please ensure the time is set correctly.")
        return True # Indicate it was an alarm command, but couldn't schedule


# --- New Features: YouTube Music and Take Picture ---

def handle_youtube_request(command_text):
    """
    Handles requests to play music or search YouTube.
    Returns True if the command was recognized as a YouTube request, False otherwise.
    """
    lower_command = command_text.lower()
    
    # Check if it's a YouTube-related command
    is_youtube_command = any(phrase in lower_command for phrase in [
        "play music", "play song", "play a music", "play a video", "play on youtube", "play youtube",
        "search youtube for", "search in youtube", "youtube search", "in youtube", "on youtube",
        "play me", "find on youtube" # Added more trigger phrases
    ])

    if not is_youtube_command:
        return False # Not a YouTube command

    music_query = None
    search_only = False

    # Determine if it's a search-only request
    search_phrases = ["search youtube for ", "search in youtube for ", "youtube search for ", "find on youtube for "]
    play_phrases = [
        "play music from youtube ", "play music on youtube ",
        "play youtube music ", "play youtube song ",
        "play a music in youtube ", "play a video in youtube ",
        "play me ", "play youtube ", "play song ", "play music ", "play "
    ]

    for phrase in search_phrases:
        if lower_command.startswith(phrase):
            music_query = lower_command[len(phrase):].strip()
            search_only = True
            break
    
    if not music_query: # If not a direct search phrase, check play phrases
        for phrase in play_phrases:
            if lower_command.startswith(phrase):
                music_query = lower_command[len(phrase):].strip()
                break
    
    # Fallback for patterns like "[query] in youtube" or "[query] on youtube"
    if not music_query:
        match_in_youtube = re.search(r'(.+?)\s+(?:in\s+youtube|on\s+youtube)', lower_command)
        if match_in_youtube:
            music_query = match_in_youtube.group(1).strip()
            # If the original command contained "search", then it's a search
            if "search" in lower_command or "find" in lower_command:
                search_only = True
        else:
            # Generic cleanup for commands like "play a music" or "search for elon"
            temp_query = lower_command.replace("play", "").replace("music", "").replace("song", "").replace("video", "").replace("youtube", "").replace("from", "").replace("on", "").replace("in", "").replace("search for", "").replace("find", "").strip()
            temp_query = re.sub(r'^(a|an|the)\s+', '', temp_query).strip() # Remove articles
            if temp_query and len(temp_query) > 1: # Ensure it's not just a single character left
                music_query = temp_query
                if "search" in lower_command or "find" in lower_command: # If generic, but "search" was in original command
                    search_only = True


    if not music_query:
        speak_response("Sir, please tell me what specific music or topic you would like to play or search on YouTube. For example, 'play Despacito' or 'search YouTube for science documentaries'.")
        return True # Recognized as YouTube command, but couldn't parse query

    if search_only:
        search_url = f"https://www.youtube.com/results?search_query={music_query.replace(' ', '+')}"
        speak_response(f"Certainly, sir. Searching YouTube for '{music_query}'.")
    else:
        # For play commands, still use search to find the video
        search_url = f"https://www.youtube.com/results?search_query={music_query.replace(' ', '+')}"
        speak_response(f"Certainly, sir. Opening YouTube to play '{music_query}'.")
    
    try:
        webbrowser.open(search_url)
        return True # Successfully handled
    except Exception as e:
        speak_response(f"Apologies, sir. I could not open YouTube. An error occurred: {e}")
        return True # Recognized as YouTube command, but failed to open

def take_and_save_photo(command_text):
    """
    Captures an image from the webcam and saves it to a file.
    Returns True if the command was recognized as a photo request, False otherwise.
    """
    lower_command = command_text.lower()
    is_photo_command = any(phrase in lower_command for phrase in ["take a picture", "take a photo", "capture image", "take photo"])

    if not is_photo_command:
        return False # Not a photo command

    speak_response("Certainly, sir. Preparing to take a picture.")
    cap = None
    try:
        cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            speak_response("Sir, I could not access the webcam to take a picture. Please ensure it's connected and not in use by another application.")
            return True # Indicate it was a photo command, but failed

        ret, frame = cap.read()
        cap.release() # Release immediately after reading

        if not ret:
            speak_response("Sir, I failed to capture an image from the webcam.")
            return True # Indicate it was a photo command, but failed

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"photo_{timestamp}.jpg"
        
        cv2.imwrite(filename, frame)
        speak_response(f"Picture taken, sir. It has been saved as {filename} in the current directory.")
        return True # Successfully handled
    except Exception as e:
        speak_response(f"Apologies, sir. I could not save the picture. An error occurred: {e}")
        return True # Indicate it was a photo command, but failed
    finally:
        if cap:
            cap.release()

def _perform_raw_google_search(query):
    """
    Performs a raw Google search using the googlesearch library and returns formatted results.
    """
    try:
        results = list(search(query, advanced=True, num_results=5, lang='en'))
        Answer = f"The search results for '{query}' are:\n"
        for i, res in enumerate(results):
            Answer += f"Title: {res.title}\nDescription: {res.description}\nURL: {res.url}\n\n"
        return Answer
    except Exception as e:
        print(f"Error during raw Google search: {e}")
        return f"Sir, I encountered an error while performing the Google search: {e}"

def perform_chrome_search(command_text, query_from_dmm=None):
    """
    Performs a Google search in the default browser for the given query,
    or synthesizes an answer if query_from_dmm is provided (from DMM's 'google search' intent).
    Returns True if the command was recognized as a Chrome search request, False otherwise.
    """
    lower_command = command_text.lower()
    
    search_query = None

    if query_from_dmm: # If DMM already extracted the query
        search_query = query_from_dmm
        speak_response(f"Certainly, sir. Searching the web for '{search_query}' and synthesizing a response.")
        
        # Perform the raw Google search
        search_results_text = _perform_raw_google_search(search_query)
        
        # Now, use the main LLM to synthesize an answer from the search results
        # We'll use the current_llm_provider for this, but could force Groq if desired for "realtime" answers
        llm_prompt = f"Based on the following search results for '{search_query}', please provide a concise and professional answer:\n\n{search_results_text}\n\n"
        
        # Pass current chat history to maintain context
        current_chat_history = load_chat_history() # Reload to ensure latest
        response_from_llm = call_llm_api(current_llm_provider[0], current_chat_history, llm_prompt)
        
        speak_response(response_from_llm)
        return True # Handled by synthesizing response

    # If not from DMM with extracted query, try to parse from raw command
    # Check if it's a Chrome/web search command
    is_search_command = any(phrase in lower_command for phrase in [
        "search chrome for", "search the web for", "search google for", "search for",
        "in chrome", "on google", "google search", "web search",
        "search on chrome for", "search in chrome for", "in chrome", "google"
    ])

    if not is_search_command:
        return False # Not a Chrome/web search command

    # Try to extract the query after common prefixes
    query_start_phrases = [
        "search chrome for ", "search the web for ", "search google for ", "search for ",
        "search on chrome for ", "search in chrome for "
    ]
    for phrase in query_start_phrases:
        if lower_command.startswith(phrase):
            search_query = lower_command[len(phrase):].strip()
            break
    
    # If not found by prefix, try to extract query from phrases like "[query] in chrome"
    if not search_query:
        match = re.search(r'(.+?)\s+(?:in\s+chrome|on\s+google|google\s+search|web\s+search)', lower_command)
        if match:
            search_query = match.group(1).strip()
        else:
            # Fallback: if the command is just the query followed by "chrome" or "google"
            if lower_command.endswith(" chrome") and len(lower_command.split()) > 1:
                search_query = lower_command.rsplit(" ", 1)[0].strip()
            elif lower_command.endswith(" google") and len(lower_command.split()) > 1:
                search_query = lower_command.rsplit(" ", 1)[0].strip()
            elif "chrome" in lower_command and lower_command != "chrome": # Handle "Tony Stark chrome"
                search_query = lower_command.replace("chrome", "").strip()
            elif "google" in lower_command and lower_command != "google": # Handle "Tony Stark google"
                search_query = lower_command.replace("google", "").strip()
            elif lower_command.startswith("search "): # Catch generic "search [query]"
                search_query = lower_command.split("search ", 1)[1].strip()
            elif lower_command.strip() == "google": # Handle just "google" command
                search_query = "" # Will prompt user for query
            elif lower_command.strip() == "chrome": # Handle just "chrome" command
                search_query = "" # Will prompt user for query


    if not search_query:
        speak_response("Sir, please tell me what you would like to search for. For example, 'search Chrome for today's weather' or 'Tony Stark in Chrome'.")
        return True # Recognized as search command, but couldn't parse query

    # If a query is parsed from raw command, open it in browser directly
    google_search_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
    
    try:
        webbrowser.open(google_search_url)
        speak_response(f"Certainly, sir. Opening the web browser to search for '{search_query}'.")
        return True # Successfully handled
    except Exception as e:
        speak_response(f"Apologies, sir. I could not perform the web search. An error occurred: {e}")
        return True # Recognized as search command, but failed to open

def Information():
    """
    Gathers real-time date and time information.
    """
    data = ""
    current_date_time = datetime.datetime.now()
    day = current_date_time.strftime("%A")
    date = current_date_time.strftime("%d")
    month = current_date_time.strftime("%B")
    year = current_date_time.strftime("%Y")
    hour = current_date_time.strftime("%H")
    minute = current_date_time.strftime("%M")
    second = current_date_time.strftime("%S")
    data += f"Use This Real-time Information if needed:\n"
    data += f"Day: {day}\n"
    data += f"Date: {date}\n"
    data += f"Month: {month}\n"
    data += f"Year: {year}\n"
    data += f"Time: {hour} hours: {minute} minutes: {second} seconds.\n"
    return data

def handle_realtime_query(prompt_from_dmm, chat_history_main):
    """
    Handles a 'realtime' query by performing a Google search and synthesizing an answer
    using the Groq LLM.
    """
    speak_response(f"Certainly, sir. Getting real-time information for '{prompt_from_dmm}'.")
    
    # Perform the raw Google search
    search_results_text = _perform_raw_google_search(prompt_from_dmm)
    
    # Get real-time date/time info
    realtime_info = Information()

    # Construct the prompt for the LLM
    llm_prompt = (
        f"Based on the following real-time information and search results for '{prompt_from_dmm}', "
        f"please provide a concise and professional answer. Prioritize the search results for factual data.\n\n"
        f"Real-time Info:\n{realtime_info}\n\n"
        f"Search Results:\n{search_results_text}\n\n"
    )
    
    # Use Groq for realtime queries as per user's original RealtimeSearchEngine
    response_from_llm = call_llm_api("groq", chat_history_main, llm_prompt)
    
    speak_response(response_from_llm)
    return response_from_llm # Return the response for logging


# --- Main Chatbot Logic ---

def main():
    """
    Main function to run the AI Assistant.
    """
    # Use a list to hold the current LLM provider, as it needs to be mutable across loop iterations
    current_llm_provider = [DEFAULT_LLM_PROVIDER] # Using a list to make it mutable

    print("Initializing AI Assistant, sir...")
    speak_response("Initializing AI Assistant, sir.")

    chat_history = load_chat_history()
    print(f"Loaded {len(chat_history)} messages from history.")

    if chat_history:
        print("\n--- Previous Conversation ---")
        for msg in chat_history:
            if isinstance(msg['timestamp'], datetime.datetime):
                timestamp_str = msg['timestamp'].strftime('%H:%M')
            else:
                timestamp_str = "Unknown Time"
            print(f"[{timestamp_str}] {'You' if msg['sender'] == 'user' else 'AI'}: {msg['text']}")
        print("-----------------------------\n")
    else:
        print("\nNo previous conversation found. Starting fresh, sir.")
        speak_response("No previous conversation found. Starting fresh, sir.")

    speak_response(f"Currently using {current_llm_provider[0]} as the AI model, sir.")

    while True:
        command = listen_for_command()

        if command:
            user_message = {"text": command, "sender": "user", "timestamp": datetime.datetime.now()}
            chat_history.append(user_message)
            save_chat_history(chat_history) # Pass the full chat_history list

            lower_command = command.lower().strip()
            response_text = None

            # --- Step 1: Use Decision-Making Model (DMM) to classify the command ---
            classified_commands = FirstLayerDMM(lower_command)
            print(f"DMM Classified: {classified_commands}")

            for classified_cmd in classified_commands:
                if classified_cmd.startswith("exit"):
                    speak_response("Goodbye, sir. It was a pleasure assisting you.")
                    return # Exit the main loop

                elif classified_cmd.startswith("open ("):
                    app_name = classified_cmd[len("open ("):].strip(")")
                    if handle_app_command(f"open {app_name}"): # Reuse existing app handler
                        response_text = f"Opened {app_name}."
                    else:
                        response_text = f"Failed to open {app_name}."

                elif classified_cmd.startswith("close ("):
                    app_name = classified_cmd[len("close ("):].strip(")")
                    speak_response(f"Sir, I am not yet equipped to close applications like {app_name}.")
                    response_text = f"Cannot close {app_name}."
                    # Placeholder for actual close functionality

                elif classified_cmd.startswith("play (") or classified_cmd.startswith("youtube search ("):
                    query = classified_cmd[classified_cmd.find("(")+1:-1].strip()
                    if handle_youtube_request(f"play {query}" if classified_cmd.startswith("play") else f"search youtube for {query}"):
                        response_text = f"Handled YouTube request for '{query}'."
                    else:
                        response_text = f"Failed to handle YouTube request for '{query}'."

                elif classified_cmd.startswith("generate image ("):
                    prompt = classified_cmd[len("generate image ("):].strip(")")
                    speak_response(f"Sir, I am not yet equipped to generate images for '{prompt}'.")
                    response_text = f"Cannot generate image for '{prompt}'."
                    # Placeholder for image generation

                elif classified_cmd.startswith("system ("):
                    task = classified_cmd[len("system ("):].strip(")")
                    speak_response(f"Sir, I am not yet equipped to perform system tasks like '{task}'.")
                    response_text = f"Cannot perform system task '{task}'."
                    # Placeholder for system commands

                elif classified_cmd.startswith("content ("):
                    topic = classified_cmd[len("content ("):].strip(")")
                    speak_response(f"Sir, I am not yet equipped to generate content on '{topic}'.")
                    response_text = f"Cannot generate content on '{topic}'."
                    # Placeholder for content generation

                elif classified_cmd.startswith("google search ("):
                    query = classified_cmd[len("google search ("):].strip(")")
                    # This will now use the _perform_raw_google_search and LLM synthesis
                    if perform_chrome_search(lower_command, query_from_dmm=query):
                        response_text = f"Handled Google search for '{query}'."
                    else:
                        response_text = f"Failed to handle Google search for '{query}'."

                elif classified_cmd.startswith("reminder ("):
                    reminder_details = classified_cmd[len("reminder ("):].strip(")")
                    if set_alarm_or_reminder(f"set a reminder {reminder_details}"):
                        response_text = f"Set reminder for '{reminder_details}'."
                    else:
                        response_text = f"Failed to set reminder for '{reminder_details}'."

                elif classified_cmd.startswith("realtime ("):
                    query = classified_cmd[len("realtime ("):].strip(")")
                    response_text = handle_realtime_query(query, chat_history) # Pass chat_history for context

                elif classified_cmd.startswith("general ("):
                    query_for_llm = classified_cmd[len("general ("):].strip(")")
                    # If it's a general query, send to the current LLM
                    response_text = call_llm_api(current_llm_provider[0], chat_history, query_for_llm)
                
                else:
                    # Fallback for unhandled classified commands
                    speak_response(f"Sir, I received an unhandled classified command: {classified_cmd}. I will treat it as a general query.")
                    response_text = call_llm_api(current_llm_provider[0], chat_history, command)
                
                # If a response_text was generated by a handler, speak and save it
                if response_text:
                    # The handlers already call speak_response, so just save here
                    # For DMM-dispatched commands, we only save the final response from the handler.
                    # The initial user command is already saved at the beginning of the loop.
                    if not response_text.startswith("Sir, I received an unhandled classified command:"): # Avoid double-speaking for unhandled cases
                        pass # Handlers already spoke
                    
                    # Update chat history with the assistant's response
                    bot_message = {"text": response_text, "sender": "bot", "timestamp": datetime.datetime.now()}
                    chat_history.append(bot_message)
                    save_chat_history(chat_history)

                # If multiple commands were classified, process them sequentially
                # The continue statement at the end of the main loop will get the next voice command.
                # If we want to process multiple DMM commands before listening again, we need to
                # remove the `continue` and ensure each handler returns a boolean indicating if it was fully handled.
                # For now, let's assume one DMM classification leads to one spoken response, then listen again.
                # If DMM returns multiple, we'll process them one by one.

            # --- Other direct commands (if DMM fails or for quick access) ---
            # These are now mostly handled by DMM, but keeping for robustness or direct access if DMM is off
            
            # Date and Time Feature Logic
            if any(phrase in lower_command for phrase in ["what time is it", "what is the time", "what's the time now", "current time"]):
                if not classified_commands or not any(cmd.startswith("general") for cmd in classified_commands): # Only if not already handled by DMM as general
                    tell_current_time()
                    # No need to save again, tell_current_time speaks directly
                    continue # Skip LLM

            # LLM Provider Switching Logic
            if lower_command.startswith("switch to ") or lower_command.startswith("change model to "):
                parts = lower_command.split(" to ", 1)
                if len(parts) > 1:
                    provider_name = parts[1].strip()
                    if provider_name in LLM_CONFIG:
                        if LLM_CONFIG[provider_name]["api_keys"]:
                            current_llm_provider[0] = provider_name # Update the mutable list
                            speak_response(f"Switched to {current_llm_provider[0]} as the AI model, sir.")
                        else:
                            speak_response(f"Sir, {provider_name} is configured but has no API keys. Please add keys to use it.")
                    else:
                        speak_response(f"Sir, '{provider_name}' is not a recognized AI model provider. Available options are: {', '.join(LLM_CONFIG.keys())}.")
                else:
                    speak_response("Sir, please specify which model to switch to. For example, 'switch to Groq'.")
                continue # Skip to next loop iteration after handling LLM switch

            # Cam Vision Logic
            if "what do you see" in lower_command or "analyze image" in lower_command or "look around" in lower_command:
                speak_response("Certainly, sir. Capturing image from webcam...")
                image_data_base64, error_message = capture_image_from_webcam()
                if image_data_base64:
                    speak_response("Image captured. Analyzing with Gemini Vision...")
                    vision_query = "Describe this image in detail, sir. What objects, people, or scenes are present? Provide a concise summary."
                    vision_response = call_llm_api("gemini-vision", [], vision_query, image_data_base64) 
                    speak_response(vision_response)
                else:
                    speak_response(error_message) # Speak the error if image capture failed
                continue # Skip to next loop iteration after handling vision command

        else:
            pass # No command was recognized, continue listening

if __name__ == "__main__":
    main()
