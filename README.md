# 🌟 Multimodal Web-Based AI Companion

[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-646CFF?style=for-the-badge&logo=vite&logoColor=white)](https://vitejs.dev/)
[![Three.js](https://img.shields.io/badge/Three.js-black?style=for-the-badge&logo=three.js&logoColor=white)](https://threejs.org/)
[![Groq LPU](https://img.shields.io/badge/Groq-LPU%20Inference-F55036?style=for-the-badge)](https://groq.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

An interactive, real-time multimodal AI companion that **sees**, **listens**, **reasons**, and **speaks** with ultra-low latency directly in your web browser. Featuring live vision presence detection, real-time hand gesture interruption, streaming speech synthesis, a responsive 3D interactive hologram bust, and beautiful LaTeX mathematical typesetting.

---

## 🏗️ Architecture Overview

```
                          ┌──────────────────────────┐
                          │   React + Vite Client    │
                          │ (Three.js 3D Bust / UI)  │
                          └────────────┬─────────────┘
                                       │
                  WebRTC MediaStream   │  Full-Duplex WebSocket
                 (Video & Audio Feeds) │  (Control & Event Stream)
                                       ▼
                          ┌──────────────────────────┐
                          │     FastAPI Backend      │
                          │   (Async Event Router)   │
                          └────────────┬─────────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        ▼                              ▼                              ▼
┌───────────────┐              ┌───────────────┐              ┌───────────────┐
│  Perception   │              │   Cognition   │              │   Synthesis   │
│   Pipeline    │              │   Pipeline    │              │   Pipeline    │
├───────────────┤              ├───────────────┤              ├───────────────┤
│ • YOLOv8      │              │ • Groq LPU    │              │ • Edge-TTS    │
│   (Presence)  │              │ • Gemini 1.5  │              │   Streaming   │
│ • MediaPipe   │              │ • LangChain   │              │ • Base64      │
│   (Gestures)  │              │ • KaTeX Math  │              │   Audio Queue │
└───────────────┘              └───────────────┘              └───────────────┘
```

---

## ✨ Key Features

- **👁️ Real-Time Vision & Perception**:
  - Continuous user presence tracking powered by **YOLOv8**.
  - Real-time hand gesture recognition via **MediaPipe** (e.g., raise an open palm to instantly interrupt the AI).
- **⚡ Sub-Second Cognition via Groq LPU**:
  - Streaming token-level reasoning utilizing ultra-fast LPU inference (`openai/gpt-oss-120b`, `llama-3.3-70b-versatile`).
  - Seamless fallback to Google Gemini (`gemini-1.5-flash`), NVIDIA NIM, or OpenAI.
- **🗣️ Low-Latency Sentence-Boundary Audio Streaming**:
  - Asynchronous pipeline synthesizes speech per sentence boundary (`.`, `!`, `?`, `\n\n`) via **Edge-TTS**.
  - First audio chunk plays in under ~1.2 seconds while subsequent sentences buffer continuously.
- **📐 Rich Mathematical Typesetting**:
  - Deep mathematical reasoning with phonetic LaTeX normalization and step-by-step rendering via **KaTeX**.
- **🔮 Interactive 3D Holographic Avatar**:
  - Screen-anchored geometric humanoid bust built with **Three.js** / **React Three Fiber**.
  - Dynamic emissive pulsing reacting to companion states (`idle`, `listening`, `thinking`, `speaking`).
- **🎙️ Flexible Audio Input**:
  - Push-to-Talk (PTT), Voice Activity Detection (VAD), and Web Speech API integration.

---

## 📁 Repository Structure

```
multimodal-ai-companion/
├── backend/
│   ├── app/
│   │   ├── api/             # WebSocket and REST endpoints
│   │   ├── cognition/       # LLM streaming & phonetic math cleaner
│   │   ├── core/            # Pydantic configuration and environment loader
│   │   ├── perception/      # YOLOv8 & MediaPipe gesture detection
│   │   └── utils/           # Audio serializers and helper functions
│   ├── main.py              # FastAPI application entry point
│   ├── requirements.txt     # Python backend dependencies
│   └── .env.example         # Backend environment configuration template
├── frontend/
│   ├── public/              # Static assets and icons
│   ├── src/
│   │   ├── components/      # Hologram, VideoPreview, Controls, MathDisplay
│   │   ├── hooks/           # WebRTC and WebSocket streaming hooks
│   │   ├── App.jsx          # Primary UI container and state manager
│   │   ├── App.css          # Glassmorphic dark UI styling
│   │   └── main.jsx         # React DOM entry point
│   ├── package.json         # Node.js dependencies
│   └── vite.config.js       # Vite configuration with proxy settings
├── .env.example             # Root environment blueprint
├── .gitignore               # Multi-layer gitignore rules
├── LICENSE                  # MIT License
└── README.md                # Project documentation
```

---

## 🚀 Quick Start Guide

### Prerequisites

- **Python**: `3.10` or `3.11`
- **Node.js**: `18.x` or `20.x` (with `npm`)
- **Hardware**: Webcam and microphone enabled in your browser

---

### 1. Backend Setup

1. **Navigate to the backend directory**:
   ```bash
   cd backend
   ```

2. **Create and activate a virtual environment**:
   ```bash
   # On Windows (PowerShell):
   python -m venv venv
   .\venv\Scripts\Activate.ps1

   # On Linux / macOS:
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   ```bash
   cp .env.example .env
   ```
   Open `.env` and add your **Groq API key** ([Get free key](https://console.groq.com/keys)) or **Gemini API key** ([Get free key](https://aistudio.google.com/app/apikey)).

5. **Start the FastAPI server**:
   ```bash
   python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
   ```
   *The backend will be running at `http://127.0.0.1:8000` with WebSocket endpoint at `ws://127.0.0.1:8000/ws/companion`.*

---

### 2. Frontend Setup

1. **Navigate to the frontend directory**:
   ```bash
   cd frontend
   ```

2. **Install npm packages**:
   ```bash
   npm install
   ```

3. **Launch the development server**:
   ```bash
   npm run dev
   ```

4. **Open the application**:
   Visit [http://localhost:5173](http://localhost:5173) in your browser. Click **"Enable Camera & Mic"** to begin your real-time session!

---

## ⚙️ Environment Variables Reference

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `GROQ_API_KEY` | `""` | Groq API Key for ultra-low latency LLM inference. |
| `GROQ_MODEL_NAME` | `openai/gpt-oss-120b` | Model name on Groq (or `llama-3.3-70b-versatile`). |
| `GEMINI_API_KEY` | `""` | Google Gemini API Key. |
| `GEMINI_MODEL_NAME` | `gemini-1.5-flash` | Gemini model for conversational fallback. |
| `EDGE_TTS_VOICE` | `en-US-AriaNeural` | Microsoft Edge TTS voice persona. |
| `WHISPER_MODEL_SIZE` | `tiny.en` | Faster-Whisper local model size. |
| `PORT` | `8000` | FastAPI server port. |
| `HOST` | `0.0.0.0` | FastAPI host binding. |

---

## 🔗 Adding to an Existing GitHub Repository (`ai-ml-projects`)

If you maintain a centralized repository (e.g., `ai-ml-projects`) and want to include this project:

### Option A: As a Subfolder inside `ai-ml-projects`
```bash
# 1. In your ai-ml-projects repository root:
mkdir multimodal-ai-companion
# Copy the backend/, frontend/, .env.example, README.md, and .gitignore into this folder

# 2. Stage and commit:
git add multimodal-ai-companion/
git commit -m "feat: add multimodal-ai-companion project"
git push origin main
```

### Option B: As a Standalone Dedicated Repository
```bash
# 1. Initialize Git in this folder:
git init -b main

# 2. Stage and commit when ready:
git add .
git commit -m "feat: initial commit for multimodal-ai-companion"

# 3. Link to your GitHub remote and push:
git remote add origin https://github.com/<your-username>/multimodal-ai-companion.git
git push -u origin main
```

---

## 📡 WebSocket Event Protocol

| Event Direction | Event Type | Description |
| :--- | :--- | :--- |
| **Client ➔ Server** | `user_presence_frame` | Base64 JPEG frame for YOLOv8 & MediaPipe gesture recognition. |
| **Client ➔ Server** | `user_speech_transcription` | User spoken prompt text and audio metadata. |
| **Client ➔ Server** | `user_interrupt` | Immediate gesture or button signal to abort active speech. |
| **Server ➔ Client** | `ai_state` | State changes (`idle`, `listening`, `thinking`, `speaking`). |
| **Server ➔ Client** | `ai_audio_response` | Streamed sentence audio chunk (Base64 MP3) + accumulated subtitle text. |
| **Server ➔ Client** | `perception_results` | YOLOv8 bounding boxes and recognized hand gestures. |

---

## 🛡️ Security & Privacy Notice

- **API Keys**: Never commit your `.env` file to GitHub. The included `.gitignore` protects against accidental credential leaks.
- **Local Media Processing**: Video and audio frames are streamed directly to your local FastAPI backend instance and are not permanently saved to disk.

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more information.
