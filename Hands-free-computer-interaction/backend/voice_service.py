import json
import logging
import queue
import threading
from pathlib import Path


logger = logging.getLogger(__name__)

COMMAND_PHRASES = (
    "left click",
    "click",
    "select",
    "confirm",
    "double click",
    "right click",
    "scroll up",
    "scroll down",
    "start dictating",
    "start typing",
    "stop dictating",
    "open notepad",
    "open calculator",
    "open files",
    "open chrome",
    "open edge",
    "open keyboard",
    "focus address bar",
    "select address bar",
    "select with blink",
    "confirm with blink",
    "use blink to select",
    "double click with blink",
    "right click with blink",
    "use blink for right click",
)

COMMAND_PREFIXES = (
    "could you ",
    "would you ",
    "can you ",
    "will you ",
    "please ",
    "okay ",
    "ok ",
    "hey ",
)
COMMAND_GRAMMAR_PREFIXES = (*COMMAND_PREFIXES, "could you please ")
COMMAND_SUFFIXES = (
    " thank you",
    " for me",
    " please",
    " thanks",
    " now",
)

COMMAND_GRAMMAR = sorted(
    {
        "[unk]",
        *COMMAND_PHRASES,
        *(
            f"{prefix}{phrase}"
            for prefix in COMMAND_GRAMMAR_PREFIXES
            for phrase in COMMAND_PHRASES
        ),
        *(
            f"{phrase}{suffix}"
            for phrase in COMMAND_PHRASES
            for suffix in COMMAND_SUFFIXES
        ),
        *(
            f"{prefix}{phrase}{suffix}"
            for prefix in COMMAND_GRAMMAR_PREFIXES
            for phrase in COMMAND_PHRASES
            for suffix in COMMAND_SUFFIXES
        ),
        "open the notepad",
        "open the calculator",
        "open the files",
        "open the chrome",
        "open the edge",
        "open the keyboard",
    }
)


class OfflineVoiceService:
    def __init__(self, model_path, on_transcript, is_dictation_enabled=None):
        self.model_path = Path(model_path)
        self.on_transcript = on_transcript
        self.is_dictation_enabled = is_dictation_enabled or (lambda: False)
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = None
        self._state = "stopped"
        self._error = None
        self._last_transcript = ""
        self._queue_error = None
        self._audio_queue = queue.Queue(maxsize=32)

    def start(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return False
            if not self.model_path.is_dir():
                raise FileNotFoundError(
                    f"Vosk model not found at {self.model_path}. "
                    "Run backend/scripts/download_vosk_model.py first."
                )
            self._stop_event.clear()
            self._error = None
            self._queue_error = None
            self._state = "starting"
            self._thread = threading.Thread(
                target=self._run, name="offline-voice", daemon=True
            )
            self._thread.start()
            return True

    def stop(self):
        self._stop_event.set()
        with self._lock:
            thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=3.0)
            if thread.is_alive():
                raise TimeoutError("Voice recognition did not stop within 3 seconds")
        return self.status()

    def status(self):
        with self._lock:
            return {
                "status": self._state,
                "model_ready": self.model_path.is_dir(),
                "model_path": str(self.model_path),
                "last_transcript": self._last_transcript,
                "error": self._error,
            }

    def _set_state(self, state, error=None):
        with self._lock:
            self._state = state
            self._error = error

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            logger.warning("Audio input status: %s", status)
        try:
            self._audio_queue.put_nowait(bytes(indata))
        except queue.Full:
            logger.error("Offline speech audio queue is full; stopping recognition")
            self._queue_error = "Audio processing could not keep up with microphone input"
            self._stop_event.set()

    @staticmethod
    def _create_recognizer(recognizer_type, model, dictation_enabled):
        if dictation_enabled:
            recognizer = recognizer_type(model, 16000)
        else:
            recognizer = recognizer_type(
                model, 16000, json.dumps(COMMAND_GRAMMAR)
            )
        recognizer.SetWords(True)
        return recognizer

    def _run(self):
        try:
            import sounddevice as sd
            from vosk import KaldiRecognizer, Model

            model = Model(str(self.model_path))
            dictation_enabled = self.is_dictation_enabled()
            recognizer = self._create_recognizer(
                KaldiRecognizer, model, dictation_enabled
            )
            with sd.RawInputStream(
                samplerate=16000,
                blocksize=8000,
                dtype="int16",
                channels=1,
                callback=self._audio_callback,
            ):
                self._set_state("running")
                while not self._stop_event.is_set():
                    try:
                        chunk = self._audio_queue.get(timeout=0.25)
                    except queue.Empty:
                        continue
                    current_dictation_mode = self.is_dictation_enabled()
                    if current_dictation_mode != dictation_enabled:
                        recognizer = self._create_recognizer(
                            KaldiRecognizer, model, current_dictation_mode
                        )
                        dictation_enabled = current_dictation_mode
                    if recognizer.AcceptWaveform(chunk):
                        result = json.loads(recognizer.Result())
                        text = result.get("text", "").strip()
                        if text and text != "[unk]":
                            with self._lock:
                                self._last_transcript = text
                            self.on_transcript(text)
                            current_dictation_mode = self.is_dictation_enabled()
                            if current_dictation_mode != dictation_enabled:
                                recognizer = self._create_recognizer(
                                    KaldiRecognizer, model, current_dictation_mode
                                )
                                dictation_enabled = current_dictation_mode
            if self._queue_error:
                self._set_state("error", self._queue_error)
            else:
                self._set_state("stopped")
        except Exception as error:
            logger.exception("Offline speech recognition failed")
            self._set_state("error", str(error))
