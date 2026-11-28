# AI-Powered Hands-Free Computer Interaction 🖱️🎙️

A contactless human-computer interaction system that replaces the traditional mouse and keyboard with **head movement, eye blinks, and voice commands** — enabling users to control a computer entirely hands-free.
---

## 📖 Table of Contents

- [Introduction](#introduction)
- [System Overview](#system-overview)
- [Features](#features)
- [Benefits](#benefits)
- [System Architecture](#system-architecture)
- [Head Movement + Blink Tracking Module](#head-movement--blink-tracking-module)
- [Voice Control Module](#voice-control-module)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Setup & Installation](#setup--installation)
- [Applications](#applications)
- [Future Scope](#future-scope)

---

## Introduction

Traditional input devices — the mouse and keyboard — require sustained physical effort and pose accessibility barriers for users with motor impairments, repetitive strain injuries, or situations where touching a device isn't practical (e.g. sterile environments).

**This project solves that problem** by enabling fully contactless computer interaction through a combination of:
- **Head movements** → cursor control
- **Eye blinks** → mouse clicks
- **Voice commands** → application control and dictation

The result is a touch-free alternative to conventional input devices, built using only a standard webcam and microphone — no specialized hardware required.

---

## System Overview

The system is composed of three core modules working together:

### 🎯 Head-Tracking Module
- Uses a webcam combined with **MediaPipe Face Landmarker** to track head movement
- Maps nose-tip movement relative to a neutral position to on-screen cursor coordinates
- Applies an adaptive **Kalman + One Euro filter** pipeline to reduce cursor jitter while keeping movement responsive
- Uses **CLAHE** to improve landmark detection in uneven lighting
- Detects blinks with normalized eye-aspect ratios, temporal debounce, and cooldowns
- Supports a sustained mouth-open gesture for right-click
- Optional dynamic dwell-click mode (press **D** to toggle)
- Press **C** in the camera window to re-center; press **Q** to stop tracking

### 🗣️ Speech-to-Text Module
- Uses **Vosk** for offline English speech recognition after its model is downloaded once
- Routes allow-listed voice commands locally and supports a start/stop dictation mode

### 🎤 Voice Command Module
- Captures microphone audio locally with SoundDevice
- Supports clicks, scrolling, dictation, and a small set of safe application launch commands
- Does not send microphone audio to a cloud recognition service

### 🔗 System Integration
- Combines blink/dwell gestures and voice commands through a shared intent router
- Voice phrases such as **“select with blink”** arm a short-lived intent that a blink confirms
- Offers local next-word suggestions learned from accepted text; only word-transition counts are stored

---

## Features

| Feature | Description |
|---|---|
| 🖱️ Real-time Head Tracking | Head-movement cursor control with Kalman and One Euro smoothing |
| 🎙️ Offline Voice Control | Local Vosk recognition for a small allow-listed command set |
| 📘 In-App User Guide | Quick-start instructions, supported voice commands, gestures, and troubleshooting |
| ⌨️ Predictive Text | Locally learned next-word suggestions in the desktop app |
| 🔗 Voice + Gesture Fusion | Voice-armed click intents can be confirmed with a blink |
| 👄 Mouth Gesture | Sustained mouth opening followed by closing triggers right-click |
| ⚙️ Customizable Sensitivity & Commands | Tunable tracking sensitivity and configurable voice commands |
| 🖥️ Cross-platform Compatibility | Designed to work across different operating environments |

---

## Benefits

- **Hands-free productivity boost** — interact with a computer without lifting a finger
- **Hygienic interaction** — zero physical contact, ideal for sterile or shared-device environments
- **User comfort** — reduces repetitive strain associated with traditional mouse/keyboard use
- **Wide adaptability** — applicable across healthcare, education, gaming, and industrial settings
- **Accessibility** — empowers users with motor impairments to use computers independently

---

## System Architecture

```
┌──────────────────────┐        HTTP Requests        ┌──────────────────────┐
│   Frontend            │ ───────────────────────────▶│   Backend             │
│   (Electron + React)   │                              │   (Flask – server.py) │
│   UI with control      │ ◀─────────────────────────── │   Handles requests,   │
│   buttons               │                              │   runs eye & voice    │
└──────────────────────┘                              │   modules              │
                                                        └───────────┬───────────┘
                                                                    │
                                  ┌─────────────────────────────────┼─────────────────────────────────┐
                                  ▼                                                                    ▼
                  ┌──────────────────────────────┐                                  ┌──────────────────────────────┐
                  │  Head-Tracking Module          │                                  │  Voice Module                  │
                  │  (eye1.py)                      │                                  │  Executes spoken commands,     │
                  │  Uses MediaPipe & OpenCV         │                                  │  converts speech to text        │
                  │  to control the cursor           │                                  │                                  │
                  └──────────────────────────────┘                                  └──────────────────────────────┘
```

| Layer | Component | Responsibility |
|---|---|---|
| **Frontend** | `desktop-app/` | Electron + React desktop interface |
| **Backend** | `server.py` (Flask) | Handles requests, orchestrates the eye-tracking and voice modules |
| **Head-Tracking** | `eye1.py` | Uses MediaPipe and OpenCV to control the cursor |
| **Voice Module** | `voice_service.py` | Runs local Vosk speech recognition and routes commands |

---

## Head Movement + Blink Tracking Module

This module is the core of the hands-free cursor experience:

1. Captures live video via **webcam**
2. Runs **MediaPipe Face Landmarker** to detect facial landmarks
3. Uses the first detected nose-tip position as the neutral head position
4. Maps movement around that neutral position to screen coordinates and smooths it with Kalman and One Euro filters
5. Press **C** in the camera preview to set a new neutral position
6. Press **D** to enable or disable dwell-click mode; keep the pointer over a target for five seconds to select once, then move away to re-arm it
7. Interprets specific facial actions as input events:

| Gesture | Action |
|---|---|
| Left-eye blink | Single click |
| Right-eye blink | Double click |
| Hold mouth open briefly, then close | Right click |
---

## Voice Control and Predictive Text

- Voice commands use the small Vosk English model with a constrained grammar; free-form dictation uses the more accurate Faster-Whisper `base.en` model. Both run locally after their one-time downloads.
- Vosk recognizes supported commands, while Whisper recognizes free-form text in the focused field or browser address bar until `stop dictating` or `enter`.
- Supported commands include `left click`, `double click`, `right click`, `scroll up`, `scroll down`, `start typing` (or `start dictating`), `stop dictating`, `open keyboard`, and opening Notepad, Calculator, Files, Chrome, or Edge.
- For a browser search, say `open chrome` or `open edge`, then `focus address bar` and speak the query; focusing the address bar switches directly to unrestricted speech recognition. Say `enter` to submit the search, or `stop dictating` to leave dictation mode.
- Address-bar dictation types recognized text as-is to avoid changing names, search terms, or URLs. General dictation started with `start typing` or `start dictating` applies conservative offline spelling correction.
- Say `open keyboard` to launch the operating system's keyboard for typing in any app. The Predictive text panel has its own keyboard; hold a key with the pointer for five seconds to activate it once.
- Spoken commands can include common polite framing, such as `please scroll up now` or `could you scroll down for me`; application commands also accept `open the calculator`.
- In general dictation mode, Whisper-recognized words are typed into the currently focused desktop application, with the existing local spelling and punctuation formatting.
- Say **“select with blink”** or **“confirm with blink”**, then blink within three seconds to fuse voice intent with a gesture. **“Right click with blink”** arms the right-click equivalent.
- Predictive text is a lightweight on-device next-word model, not an 8B SLM. It uses built-in common continuations plus word-transition counts learned locally. Counts are stored in `backend/data/autocomplete.json`; raw phrases are not persisted.
- The Electron renderer uses a restricted preload bridge to call the local Flask API; Node integration is disabled in the UI renderer.

---

## Tech Stack

### Programming Languages & Frameworks
- **Python** — core implementation
- **Flask** — backend server and API handling
- **Electron, React, Vite** — desktop interface

### Libraries for Head Tracking
- **OpenCV** — webcam input and image processing
- **MediaPipe Face Landmarker** — facial landmark detection
- **pynput** — programmatic mouse control

### Libraries for Voice Control
- **Vosk** — offline speech recognition
- **pyspellchecker** — local spelling correction during dictation
- **SoundDevice** — local microphone streaming
- **pynput** — allow-listed keyboard and mouse actions

---

## Project Structure

```
Hands-free-computer-interaction/
├── backend/
│   ├── server.py        # Flask API and service orchestration
│   ├── interaction_router.py
│   ├── voice_service.py # Local Vosk command and Whisper dictation service
│   ├── scripts/eye1.py # Head tracking, gestures, and cursor filtering
│   └── models/          # Face model; Vosk model downloaded during setup
├── desktop-app/         # Electron + React + Vite UI
├── frontend/            # Legacy browser UI
├── backend/requirements.txt
└── README.md
```

---

## Setup & Installation

### Prerequisites
- Python 3.10+
- Node.js 20+ and npm
- A working webcam
- A working microphone

### Installation

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
python backend\scripts\download_vosk_model.py
python backend\scripts\download_whisper_model.py
```

The Vosk and Whisper model downloads are one-time setup steps. The Whisper `base.en` model is about 145 MB; after setup, speech recognition and camera processing run locally without sending audio to a cloud service. The [MediaPipe Face Landmarker model](https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task) is bundled at `backend/models/face_landmarker.task`.

### Running the Application

```powershell
# From the repository root (the venv should be activated)
cd desktop-app
npm run dev
```

This single command starts the Flask backend, Vite, and the Electron desktop app in the same terminal. When the UI opens, it automatically starts head tracking (webcam/Face Landmarker) and offline voice recognition (microphone/Vosk); allow camera and microphone access when prompted. Use the **Stop** buttons in the app to stop either service. Press **Ctrl+C** to stop all three processes. If the project virtual environment exists, its Python is used automatically; otherwise, make sure Python is on `PATH` or set `PYTHON` to its executable.

The development UI uses port `5173`; if another app is already using it, stop that app and run `npm run dev` again. To open Chromium DevTools for renderer diagnostics, run `$env:MOTIONEASE_DEVTOOLS="1"; npm run dev` in PowerShell.

To build the React interface and launch it in Electron outside development mode, run `npm run build` and then `npm start` in `desktop-app`; start the Flask backend separately with `python backend\server.py`.

---

## Applications

- **Assistive technology** for differently-abled users
- **Sterile environments** (hospitals, laboratories) where touchless interaction is preferred
- **Hands-free computing** in industrial setups
- **Gaming and interactive learning** experiences

---

## Future Scope

- Improve head-tracking accuracy and reduce cursor jitter in varying lighting conditions
- Expand the voice command vocabulary for more complex, multi-step OS actions
- Add gesture customization through a settings UI rather than hardcoded thresholds
- Package as a standalone cross-platform desktop application for easier installation

---
