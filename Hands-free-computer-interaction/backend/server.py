import os
import subprocess
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
import sys
import time

from interaction_router import IntentRouter, LocalAutocomplete
from voice_service import OfflineVoiceService

app = Flask(__name__)

CORS(app, resources={
    r"/*": {
        "origins": [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
}) 

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Dynamic path handling
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")

# Add directories to Python path
sys.path.extend([BASE_DIR, PARENT_DIR, SCRIPTS_DIR])

# Define script paths
EYE_TRACKING_SCRIPT = os.path.join(SCRIPTS_DIR, "eye1.py")
VOSK_MODEL_DIR = os.path.join(BASE_DIR, "models", "vosk-model-small-en-us-0.15")
WHISPER_MODEL_DIR = os.path.join(BASE_DIR, "models", "faster-whisper-base.en")

# Create scripts directory if it doesn't exist
os.makedirs(SCRIPTS_DIR, exist_ok=True)

# Store process instances
eye_tracking_process = None
intent_router = IntentRouter()
autocomplete = LocalAutocomplete()
last_interaction = {"transcript": "", "action": None}


def handle_transcript(text):
    autocomplete.learn(text)
    result = intent_router.route_voice(text)
    last_interaction["transcript"] = text
    last_interaction["action"] = result
    logger.info(
        "Offline speech routed as %s",
        result.get("action") or result.get("message", "unhandled"),
    )


voice_service = OfflineVoiceService(
    VOSK_MODEL_DIR,
    handle_transcript,
    is_dictation_enabled=intent_router.is_dictation_enabled,
    dictation_model_path=WHISPER_MODEL_DIR,
)

# Log directory structure
logger.info(f"Base Directory: {BASE_DIR}")
logger.info(f"Parent Directory: {PARENT_DIR}")
logger.info(f"Scripts Directory: {SCRIPTS_DIR}")
logger.info(f"Eye Tracking Script Path: {EYE_TRACKING_SCRIPT}")

@app.route("/")
def home():
    return jsonify({"message": "Hands-Free Interaction API is Running!"})

@app.errorhandler(500)
def handle_500_error(e):
    logger.error(f"Internal server error: {str(e)}")
    return jsonify({"error": "Internal server error", "details": str(e)}), 500

def start_process(script_path, script_name):
    try:
        logger.info(f"Attempting to start {script_name} from {script_path}")
        
        # Detailed file existence check
        if not os.path.exists(script_path):
            error_msg = f"Script not found: {script_path}"
            logger.error(error_msg)
            return None, error_msg

        # Check if script is readable
        try:
            with open(script_path, 'r') as f:
                pass
        except Exception as e:
            error_msg = f"Cannot read script {script_path}: {str(e)}"
            logger.error(error_msg)
            return None, error_msg

        # Add detailed environment setup logging
        env = os.environ.copy()
        python_path_entries = [PARENT_DIR, BASE_DIR, SCRIPTS_DIR]
        if env.get("PYTHONPATH"):
            python_path_entries.append(env["PYTHONPATH"])
        env["PYTHONPATH"] = os.pathsep.join(python_path_entries)
        logger.info(f"PYTHONPATH set to: {env['PYTHONPATH']}")
        
        # Start process with more detailed error capture
        try:
            process = subprocess.Popen(
                [sys.executable, script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                cwd=SCRIPTS_DIR
            )
            
            # Check for immediate startup errors
            time.sleep(1)  # Give the process a moment to start
            returncode = process.poll()
            if returncode is not None:
                stdout, stderr = process.communicate()
                error_msg = f"Process failed to start. Return code: {returncode}\nStdout: {stdout}\nStderr: {stderr}"
                logger.error(error_msg)
                return None, error_msg

            # Log successful start
            logger.info(f"Successfully started {script_name}")
            return process, "Success"
            
        except Exception as e:
            error_msg = f"Failed to start process: {str(e)}"
            logger.error(error_msg)
            return None, error_msg
            
    except Exception as e:
        error_msg = f"Error in start_process: {str(e)}"
        logger.error(error_msg)
        return None, error_msg

@app.route("/start-eye-tracking", methods=["POST"])
def start_eye_tracking():
    global eye_tracking_process
    
    try:
        if eye_tracking_process:
            if eye_tracking_process.poll() is None:
                return jsonify({"message": "Eye tracking is already running"}), 200
            eye_tracking_process = None

        logger.info("Starting eye tracking process")
        eye_tracking_process, msg = start_process(EYE_TRACKING_SCRIPT, "eye tracking")
        
        if eye_tracking_process:
            return jsonify({"message": "Head tracking started"}), 200
        return jsonify({"error": msg}), 500
        
    except Exception as e:
        error_msg = f"Error in start_eye_tracking: {str(e)}"
        logger.error(error_msg)
        return jsonify({"error": error_msg}), 500

@app.route("/stop-eye-tracking", methods=["POST"])
def stop_eye_tracking():
    global eye_tracking_process
    if eye_tracking_process:
        try:
            logger.info("Stopping eye tracking process")
            eye_tracking_process.terminate()
            eye_tracking_process.wait(timeout=5)
            eye_tracking_process = None
            return jsonify({"message": "Head tracking stopped"}), 200
        except subprocess.TimeoutExpired:
            logger.error("Force killing eye tracking process")
            eye_tracking_process.kill()
            eye_tracking_process = None
            return jsonify({"message": "Head tracking force stopped"}), 200
        except Exception as e:
            logger.error(f"Error stopping eye tracking: {str(e)}")
            return jsonify({"error": str(e)}), 500
    return jsonify({"message": "Head tracking is not running"}), 400

@app.route("/start-voice-control", methods=["POST"])
@app.route("/api/voice/start", methods=["POST"])
def start_voice_control():
    try:
        started = voice_service.start()
        return jsonify({
            "message": "Offline voice control starting" if started else "Offline voice control is already running",
            **voice_service.status(),
        }), 200
    except FileNotFoundError as error:
        return jsonify({**voice_service.status(), "error": str(error)}), 409
    except Exception as error:
        logger.exception("Could not start offline voice control")
        return jsonify({"error": str(error)}), 500

@app.route("/stop-voice-control", methods=["POST"])
@app.route("/api/voice/stop", methods=["POST"])
def stop_voice_control():
    try:
        status = voice_service.stop()
        return jsonify({"message": "Offline voice control stopped", **status}), 200
    except Exception as error:
        logger.exception("Could not stop offline voice control")
        return jsonify({"error": str(error)}), 500


@app.route("/api/voice/status", methods=["GET"])
def get_voice_status():
    return jsonify(voice_service.status())


@app.route("/api/interaction/events", methods=["POST"])
def interaction_event():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("gesture"), str):
        return jsonify({"error": "A gesture name is required"}), 400
    try:
        result = intent_router.route_gesture(payload["gesture"])
        if result.get("handled"):
            last_interaction["action"] = result
            return jsonify(result), 200
        return jsonify(result), 400
    except Exception as error:
        logger.exception("Could not route gesture event")
        return jsonify({"error": str(error)}), 500


@app.route("/api/suggestions", methods=["POST"])
def get_suggestions():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("text"), str):
        return jsonify({"error": "Text must be a string"}), 400
    text = payload["text"]
    if len(text) > 2000:
        return jsonify({"error": "Text must be 2000 characters or fewer"}), 413
    return jsonify({"suggestions": autocomplete.suggest(text)})


@app.route("/api/autocomplete/learn", methods=["POST"])
def learn_autocomplete():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("text"), str):
        return jsonify({"error": "Text must be a string"}), 400
    text = payload["text"].strip()
    if len(text) > 2000:
        return jsonify({"error": "Text must be 2000 characters or fewer"}), 413
    if text:
        autocomplete.learn(text)
    return jsonify({"learned": bool(text)})


@app.route("/api/state", methods=["GET"])
def get_interaction_state():
    return jsonify({
        "eye_tracking": {
            "status": "running" if eye_tracking_process and eye_tracking_process.poll() is None else "stopped",
        },
        "voice": voice_service.status(),
        "last_interaction": last_interaction,
        "dictation_enabled": intent_router.dictation_enabled,
        "pending_gesture_intent": intent_router.pending_gesture_intent,
    })

@app.route("/status", methods=["GET"])
def get_status():
    return jsonify({
        "eye_tracking": {
            "status": "running" if eye_tracking_process and eye_tracking_process.poll() is None else "stopped",
            "script_exists": os.path.exists(EYE_TRACKING_SCRIPT),
            "script_path": EYE_TRACKING_SCRIPT
        },
        "voice_control": {
            "status": voice_service.status()["status"],
            "model_ready": voice_service.status()["model_ready"],
        },
        "offline_voice": voice_service.status(),
        "directories": {
            "base_dir": BASE_DIR,
            "parent_dir": PARENT_DIR,
            "scripts_dir": SCRIPTS_DIR
        },
        "python_path": sys.path
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting server on port {port}")
    app.run(host="127.0.0.1", port=port)