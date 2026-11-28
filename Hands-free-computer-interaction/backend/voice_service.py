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

WHISPER_MODEL_FILES = (
    "config.json",
    "model.bin",
    "tokenizer.json",
    "vocabulary.txt",
)


class OfflineVoiceService:
    def __init__(
        self,
        model_path,
        on_transcript,
        is_dictation_enabled=None,
        dictation_model_path=None,
    ):
        self.model_path = Path(model_path)
        self.dictation_model_path = (
            Path(dictation_model_path) if dictation_model_path else None
        )
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
        self._transcription_queue = queue.Queue(maxsize=8)
        self._transcription_thread = None
        self._transcription_error = None

    def start(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return False
            if not self.model_path.is_dir():
                raise FileNotFoundError(
                    f"Vosk model not found at {self.model_path}. "
                    "Run backend/scripts/download_vosk_model.py first."
                )
            if not self._dictation_model_ready():
                raise FileNotFoundError(
                    f"Whisper dictation model not found at "
                    f"{self.dictation_model_path}. "
                    "Run backend/scripts/download_whisper_model.py first."
                )
            self._stop_event.clear()
            self._error = None
            self._queue_error = None
            self._transcription_error = None
            self._audio_queue = queue.Queue(maxsize=32)
            self._transcription_queue = queue.Queue(maxsize=8)
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
            thread.join(timeout=15.0)
            if thread.is_alive():
                raise TimeoutError("Voice recognition did not stop within 15 seconds")
        return self.status()

    def status(self):
        with self._lock:
            return {
                "status": self._state,
                "model_ready": self.model_path.is_dir(),
                "model_path": str(self.model_path),
                "dictation_model_ready": self._dictation_model_ready(),
                "dictation_model_path": (
                    str(self.dictation_model_path)
                    if self.dictation_model_path is not None
                    else None
                ),
                "last_transcript": self._last_transcript,
                "error": self._error,
            }

    def _dictation_model_ready(self):
        return (
            self.dictation_model_path is not None
            and all(
                (self.dictation_model_path / filename).is_file()
                for filename in WHISPER_MODEL_FILES
            )
        )

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

    def _enqueue_transcription(self, item):
        try:
            self._transcription_queue.put_nowait(item)
        except queue.Full:
            logger.error("Whisper transcription queue is full; stopping recognition")
            self._queue_error = "Speech transcription could not keep up with microphone input"
            self._stop_event.set()

    def _emit_transcript(self, text):
        with self._lock:
            self._last_transcript = text
        self.on_transcript(text)

    @staticmethod
    def _is_dictation_control(text):
        normalized = "".join(
            character.lower() if character.isalnum() else " " for character in text
        )
        return " ".join(normalized.split()) in {"enter", "stop dictating"}

    @classmethod
    def _dictation_item(cls, text, audio):
        if not audio:
            return None
        if text and text != "[unk]" and cls._is_dictation_control(text):
            return "command", text
        return "audio", audio

    @staticmethod
    def _transcribe_audio(model, audio):
        import numpy as np

        samples = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
        segments, _ = model.transcribe(
            samples,
            language="en",
            beam_size=5,
            condition_on_previous_text=False,
        )
        return " ".join(segment.text.strip() for segment in segments).strip()

    def _transcribe_queued_audio(self, model):
        while True:
            item = self._transcription_queue.get()
            if item is None:
                return
            item_type, value = item
            try:
                if item_type == "command":
                    text = value
                else:
                    text = self._transcribe_audio(model, value)
                if text:
                    self._emit_transcript(text)
            except Exception as error:
                logger.exception("Whisper dictation transcription failed")
                self._transcription_error = str(error)
                self._stop_event.set()
                return

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
            from faster_whisper import WhisperModel
            from vosk import KaldiRecognizer, Model

            model = Model(str(self.model_path))
            dictation_model = WhisperModel(
                str(self.dictation_model_path),
                device="cpu",
                compute_type="int8",
            )
            self._transcription_thread = threading.Thread(
                target=self._transcribe_queued_audio,
                args=(dictation_model,),
                name="whisper-dictation",
                daemon=True,
            )
            self._transcription_thread.start()
            dictation_enabled = self.is_dictation_enabled()
            recognizer = self._create_recognizer(
                KaldiRecognizer, model, dictation_enabled
            )
            utterance_audio = bytearray()
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
                        utterance_audio.clear()
                    if dictation_enabled:
                        utterance_audio.extend(chunk)
                    if recognizer.AcceptWaveform(chunk):
                        result = json.loads(recognizer.Result())
                        text = result.get("text", "").strip()
                        if dictation_enabled:
                            item = self._dictation_item(
                                text, bytes(utterance_audio)
                            )
                            if item is not None:
                                self._enqueue_transcription(item)
                            utterance_audio.clear()
                        elif text and text != "[unk]":
                            self._emit_transcript(text)
                        if text and text != "[unk]":
                            current_dictation_mode = self.is_dictation_enabled()
                            if current_dictation_mode != dictation_enabled:
                                recognizer = self._create_recognizer(
                                    KaldiRecognizer, model, current_dictation_mode
                                )
                                dictation_enabled = current_dictation_mode
                                utterance_audio.clear()
        except Exception as error:
            logger.exception("Offline speech recognition failed")
            self._set_state("error", str(error))
        finally:
            transcription_thread = self._transcription_thread
            if transcription_thread and transcription_thread.is_alive():
                try:
                    self._transcription_queue.put(None, timeout=3.0)
                    transcription_thread.join(timeout=15.0)
                    if transcription_thread.is_alive():
                        self._transcription_error = (
                            "Whisper transcription did not stop within 15 seconds"
                        )
                except queue.Full:
                    self._transcription_error = (
                        "Could not stop the Whisper transcription worker"
                    )

            with self._lock:
                state = self._state
            if state != "error":
                if self._queue_error:
                    self._set_state("error", self._queue_error)
                elif self._transcription_error:
                    self._set_state("error", self._transcription_error)
                else:
                    self._set_state("stopped")
