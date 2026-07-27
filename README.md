# 🤖 Advanced AI Desktop Assistant (JARVIS-Style Voice Assistant)

An intelligent, feature-rich desktop voice assistant built in Python. It features a **Two-Layer Decision-Making Model (DMM)** using Cohere Command-R-Plus to classify user intent, supports multiple LLM providers (Google Gemini, Groq Llama 3, Hugging Face Gemma), executes system applications, handles real-time web scraping via Google search, manages alarms and reminders, interacts with web services like YouTube, and captures webcam images for vision-based analysis.

---

## 🚀 Key Features

* **Advanced Intent Classification (DMM):** Uses Cohere's `command-r-plus` as a first-layer Decision-Making Model to accurately route commands (general queries, real-time info, opening apps, media playback, web searches, reminders, etc.).
* **Multi-LLM Support & Fallback:** Seamlessly switch between **Google Gemini** (`gemini-2.0-flash`), **Groq** (`llama3-70b-8192`), and **Hugging Face** (`gemma-2b-it`). Automatically cycles through multiple API keys for robustness.
* **Vision Capabilities:** Captures images via OpenCV from your webcam and passes them to Gemini Vision for real-time visual analysis ("What do you see?").
* **Voice Recognition & Text-to-Speech:** Uses Google Speech Recognition (`speech_recognition`) for audio input and `pyttsx3` for local text-to-speech feedback. Includes a smart chunked-reading system with interactive "Would you like me to continue?" voice prompts.
* **System Automation:** Opens and controls local applications (Notepad, Chrome, VS Code, Task Manager, etc.) with fuzzy matching (`fuzzywuzzy`) for typo tolerance.
* **Real-Time Web Intelligence:** Integrates live Google Search scraping (`googlesearch-python`) combined with Groq/Gemini synthesis to provide up-to-date answers.
* **Task & Reminder Management:** Threaded timer system that parses natural language time offsets (`"in 5 minutes"`, `"at 7 PM"`) to set alarms and voice reminders.
* **Persistent Chat History:** Automatically saves conversation logs to `chat_history.json` with timestamp tracking.

---

## 🛠️ Prerequisites & System Requirements

* **Operating System:** Windows 10/11 (fully optimized for Windows system paths/commands), Linux, or macOS.
* **Python Version:** Python 3.8 or higher.
* **Hardware:** 
  * Working microphone for voice commands.
  * Webcam (optional, required for vision features).
  * Internet connection (for LLM API calls and web scraping).

---

## 📦 Required Python Packages (`pip`)

Run the following command to install all necessary dependencies:

```bash
pip install speechrecognition pyttsx3 requests python-dotenv cohere googlesearch-python fuzzywuzzy opencv-python
```

> **Note for Windows Users:** `pyttsx3` uses SAPI5 natively on Windows. If you encounter audio driver issues on Linux, you may need to install `espeak` and `libespeak1` via your package manager (e.g., `sudo apt install espeak libespeak1`).

---

## ⚙️ Configuration & Setup Guide

### Step 1: Clone or Save the Script
Save the main script file as `assistant.py` in your project directory.

### Step 2: Create a `.env` File
Create a file named `.env` in the same directory as `assistant.py` to securely store your API keys and custom names:

```env
# API Keys (Get your keys from respective developer consoles)
CohereAPIKey=your_cohere_api_key_here
GroqAPIKey=your_groq_api_key_here
GeminiAPIKey=your_gemini_api_key_here

# Assistant Personalization
Username=Sir
Assistantname=Jarvis
```

### Step 3: Configure API Keys in Code (Alternative)
If you prefer not to use a `.env` file, you can paste your API keys directly into the `LLM_CONFIG` dictionary inside `assistant.py`:

```python
LLM_CONFIG = {
    "gemini": {
        "api_keys": [
            "YOUR_GEMINI_API_KEY_HERE",
        ],
        ...
    },
    ...
}
```

---

## 🚀 How to Run the Assistant

Open your terminal or command prompt, navigate to the directory containing the script, and execute:

```bash
python assistant.py
```

---

## 💬 Voice & Text Command Examples

Once initialized, the assistant will listen to your microphone. You can speak commands like:

* **General Chat:** *"Who was Albert Einstein?"* or *"How can I study more effectively?"*
* **Real-time Info:** *"Who is the current Prime Minister of India?"* or *"What's today's headline news?"*
* **App Automation:** *"Open Chrome and Notepad"* or *"Open VS Code"*.
* **Web & YouTube Search:** *"Search YouTube for lofi hip hop"* or *"Search Chrome for quantum computing breakthroughs"*.
* **Reminders:** *"Set a reminder in 10 minutes to check the oven"* or *"Remind me at 8 PM for the meeting"*.
* **Vision Analysis:** *"What do you see?"* or *"Analyze image"* (captures webcam snapshot and describes it).
* **Model Switching:** *"Switch to Groq"* or *"Switch to Gemini"*.
* **Exit:** *"Bye Jarvis"* or *"Exit"*.

---

## 📂 Project Structure

```text
📂 AI-Desktop-Assistant/
├── assistant.py          # Main application script
├── .env                  # Environment variables (API keys & config)
├── chat_history.json     # Auto-generated persistent chat logs
└── README.md             # Project documentation (this file)
```

---

## 🛡️ Troubleshooting & Tips

1. **Microphone Errors:** Ensure your default recording device is correctly configured in your OS sound settings. If `speech_recognition` throws ambient noise errors, adjust the `duration` parameter in `r.adjust_for_ambient_noise()`.
2. **Webcam Access:** If using vision features, ensure no other application (like Zoom or Teams) is locking your webcam (`cv2.VideoCapture(0)`).
3. **API Rate Limits:** If you hit rate limits with Gemini or Groq, add secondary backup keys into the `api_keys` list inside `LLM_CONFIG` for automatic failover rotation.
