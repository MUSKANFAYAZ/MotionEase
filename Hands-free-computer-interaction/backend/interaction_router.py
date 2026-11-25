import logging
import json
import os
import platform
import re
import shutil
import subprocess
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

from pynput.keyboard import Controller as KeyboardController, Key
from pynput.mouse import Button, Controller as MouseController
from spellchecker import SpellChecker


logger = logging.getLogger(__name__)


class IntentRouter:
    """Routes allow-listed voice and gesture inputs to desktop actions."""

    def __init__(self):
        self.mouse = MouseController()
        self.keyboard = KeyboardController()
        self.spell_checker = SpellChecker(distance=1)
        self.lock = threading.RLock()
        self.dictation_enabled = False
        self.pending_gesture_intent = None
        self.pending_gesture_expires = 0.0
        self._last_blink_at = {}
        self.recent_signals = deque(maxlen=32)

    def is_dictation_enabled(self):
        with self.lock:
            return self.dictation_enabled

    def _record(self, modality, name, now):
        self.recent_signals.append(
            {"modality": modality, "name": name, "timestamp": now}
        )

    def route_gesture(self, name):
        now = time.monotonic()
        with self.lock:
            if name not in {"left_blink", "right_blink", "mouth_open", "dwell"}:
                return {"handled": False, "error": f"Unknown gesture: {name}"}
            if name in {"left_blink", "right_blink"}:
                previous = self._last_blink_at.get(name)
                if previous is not None and now - previous < 1.2:
                    return {
                        "handled": True,
                        "action": "duplicate_gesture_ignored",
                        "duplicate": True,
                    }
                self._last_blink_at[name] = now
            self._record("gesture", name, now)
            pending = self.pending_gesture_intent
            if pending and now <= self.pending_gesture_expires:
                self.pending_gesture_intent = None
                self._perform_click(pending)
                return {"handled": True, "action": pending, "fused": True}
            self.pending_gesture_intent = None

            if name == "left_blink":
                self.mouse.click(Button.left, 1)
                action = "left_click"
            elif name == "right_blink":
                self.mouse.click(Button.left, 2)
                action = "double_click"
            elif name == "mouth_open":
                self.mouse.click(Button.right, 1)
                action = "right_click"
            elif name == "dwell":
                self.mouse.click(Button.left, 1)
                action = "left_click"
            return {"handled": True, "action": action, "fused": False}

    def _perform_click(self, action):
        if action == "right_click":
            self.mouse.click(Button.right, 1)
        else:
            self.mouse.click(Button.left, 2 if action == "double_click" else 1)

    def route_voice(self, text):
        spoken_text = " ".join(text.strip().split())
        normalized = spoken_text.lower()
        if not normalized:
            return {"handled": False, "message": "No speech recognized"}
        command = " ".join(
            re.sub(r"[^\w\s]", " ", normalized).split()
        )
        command = self._normalize_command(command)

        with self.lock:
            now = time.monotonic()
            self._record("voice", normalized, now)

            if self.dictation_enabled:
                if command == "stop dictating":
                    self.dictation_enabled = False
                    return {"handled": True, "action": "dictation_stopped"}
                if command == "enter":
                    self.keyboard.press(Key.enter)
                    self.keyboard.release(Key.enter)
                    return {"handled": True, "action": "enter_pressed"}
                corrected = self._format_dictation(
                    self._spell_check(spoken_text)
                )
                self.keyboard.type(corrected)
                return {
                    "handled": True,
                    "action": "dictation_text",
                    "text": corrected.strip(),
                }

            if command in {
                "select with blink",
                "confirm with blink",
                "use blink to select",
            }:
                self.pending_gesture_intent = "left_click"
                self.pending_gesture_expires = now + 3.0
                return {
                    "handled": True,
                    "action": "waiting_for_blink",
                    "message": "Blink within 3 seconds to confirm the click",
                }

            if command == "double click with blink":
                self.pending_gesture_intent = "double_click"
                self.pending_gesture_expires = now + 3.0
                return {
                    "handled": True,
                    "action": "waiting_for_blink",
                    "message": "Blink within 3 seconds to confirm the double click",
                }

            if command in {"right click with blink", "use blink for right click"}:
                self.pending_gesture_intent = "right_click"
                self.pending_gesture_expires = now + 3.0
                return {
                    "handled": True,
                    "action": "waiting_for_blink",
                    "message": "Blink within 3 seconds to confirm the right click",
                }

            if command in {"left click", "click", "select", "confirm"}:
                self.mouse.click(Button.left, 1)
                return {"handled": True, "action": "left_click", "fused": False}
            if command == "double click":
                self.mouse.click(Button.left, 2)
                return {"handled": True, "action": "double_click", "fused": False}
            if command == "right click":
                self.mouse.click(Button.right, 1)
                return {"handled": True, "action": "right_click", "fused": False}
            if command in {"scroll up", "scroll down"}:
                self.mouse.scroll(0, 3 if command == "scroll up" else -3)
                return {"handled": True, "action": command.replace(" ", "_")}
            if command in {"start dictating", "start typing"}:
                self.dictation_enabled = True
                return {"handled": True, "action": "dictation_started"}
            if command == "stop dictating":
                self.dictation_enabled = False
                return {"handled": True, "action": "dictation_stopped"}
            if command in {"focus address bar", "select address bar"}:
                modifier = Key.cmd if platform.system() == "Darwin" else Key.ctrl
                self.keyboard.press(modifier)
                self.keyboard.press("l")
                self.keyboard.release("l")
                self.keyboard.release(modifier)
                return {"handled": True, "action": "address_bar_focused"}
            if command in {
                "open notepad",
                "open calculator",
                "open files",
                "open chrome",
                "open edge",
                "open keyboard",
            }:
                application = command.removeprefix("open ").strip()
                try:
                    self._open_application(application)
                except OSError as error:
                    logger.exception("Could not open %s", application)
                    return {
                        "handled": False,
                        "message": f"Could not open {application}: {error}",
                    }
                return {"handled": True, "action": command.replace(" ", "_")}

            return {"handled": False, "message": f"Unrecognized command: {normalized}"}

    def _spell_check(self, text):
        words = re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)?|[^A-Za-z]+", text)
        corrected = []
        for word in words:
            if not word.isalpha() or len(word) < 4:
                corrected.append(word)
                continue
            lower_word = word.lower()
            candidates = self.spell_checker.candidates(lower_word)
            frequency = self.spell_checker.word_frequency.dictionary.get
            ranked_candidates = sorted(
                candidates,
                key=frequency,
                reverse=True,
            )
            candidate = ranked_candidates[0] if ranked_candidates else lower_word
            second_frequency = (
                frequency(ranked_candidates[1])
                if len(ranked_candidates) > 1
                else 0
            )
            best_frequency = (
                frequency(candidate)
                if ranked_candidates
                else 0
            )
            if best_frequency < second_frequency * 20:
                candidate = lower_word
            if candidate and candidate != lower_word:
                if word.isupper():
                    candidate = candidate.upper()
                elif word[0].isupper():
                    candidate = candidate.capitalize()
                corrected.append(candidate)
            else:
                corrected.append(word)
        return "".join(corrected)

    @staticmethod
    def _normalize_command(command):
        leading_phrases = (
            "could you ",
            "would you ",
            "can you ",
            "will you ",
            "please ",
            "okay ",
            "ok ",
            "hey ",
        )
        trailing_phrases = (
            " thank you",
            " for me",
            " please",
            " thanks",
            " now",
        )

        changed = True
        while changed:
            changed = False
            for phrase in leading_phrases:
                if command.startswith(phrase):
                    command = command[len(phrase):]
                    changed = True
                    break
            for phrase in trailing_phrases:
                if command.endswith(phrase):
                    command = command[:-len(phrase)]
                    changed = True
                    break

        if command.startswith("open the "):
            command = "open " + command[len("open the "):]
        return command.strip()

    @staticmethod
    def _format_dictation(text):
        replacements = {
            "comma": ",",
            "period": ".",
            "full stop": ".",
            "question mark": "?",
            "exclamation mark": "!",
            "new line": "\n",
        }
        for phrase, replacement in sorted(
            replacements.items(), key=lambda item: len(item[0]), reverse=True
        ):
            text = re.sub(
                rf"\b{re.escape(phrase)}\b",
                replacement,
                text,
                flags=re.IGNORECASE,
            )
        text = re.sub(r"\s+([,?.!])", r"\1", text)
        text = re.sub(r"\bi\b", "I", text)
        text = re.sub(
            r"(^|[.!?]\s+)([a-z])",
            lambda match: match.group(1) + match.group(2).upper(),
            text,
        )
        return text + (" " if not text.endswith("\n") else "")

    @staticmethod
    def _open_application(name):
        if platform.system() == "Windows":
            applications = {
                "notepad": ["notepad.exe"],
                "calculator": ["calc.exe"],
                "files": ["explorer.exe"],
            }
            if name == "keyboard":
                executable = (
                    Path(os.environ.get("WINDIR", r"C:\Windows"))
                    / "System32"
                    / "osk.exe"
                )
                if not executable.is_file():
                    located = shutil.which("osk.exe")
                    if located is None:
                        raise FileNotFoundError(
                            "Windows On-Screen Keyboard (osk.exe) was not found."
                        )
                    executable = Path(located)
                subprocess.Popen([str(executable)])
                return
            if name in {"chrome", "edge"}:
                program_files = Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
                program_files_x86 = Path(
                    os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
                )
                local_app_data = Path(
                    os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
                )
                browser_paths = {
                    "chrome": (
                        program_files / "Google" / "Chrome" / "Application" / "chrome.exe",
                        program_files_x86 / "Google" / "Chrome" / "Application" / "chrome.exe",
                        local_app_data / "Google" / "Chrome" / "Application" / "chrome.exe",
                    ),
                    "edge": (
                        program_files_x86 / "Microsoft" / "Edge" / "Application" / "msedge.exe",
                        program_files / "Microsoft" / "Edge" / "Application" / "msedge.exe",
                    ),
                }
                executable = next(
                    (path for path in browser_paths[name] if path.is_file()),
                    None,
                )
                if executable is None:
                    executable_name = "chrome.exe" if name == "chrome" else "msedge.exe"
                    executable = shutil.which(executable_name)
                if executable is None:
                    raise FileNotFoundError(
                        f"{name.title()} was not found. Install it or add it to PATH."
                    )
                subprocess.Popen([str(executable), "--new-window"])
                return
            subprocess.Popen(applications[name])
            return
        if platform.system() == "Darwin":
            applications = {
                "notepad": ["open", "-a", "TextEdit"],
                "calculator": ["open", "-a", "Calculator"],
                "files": ["open", os.path.expanduser("~")],
                "chrome": ["open", "-a", "Google Chrome"],
                "edge": ["open", "-a", "Microsoft Edge"],
                "keyboard": ["open", "-a", "KeyboardViewer"],
            }
            subprocess.Popen(applications[name])
            return
        applications = {
            "notepad": ["gedit"],
            "calculator": ["gnome-calculator"],
            "files": ["xdg-open", os.path.expanduser("~")],
            "chrome": ["google-chrome", "google-chrome-stable", "chromium"],
            "edge": ["microsoft-edge", "microsoft-edge-stable"],
            "keyboard": ["onboard"],
        }
        if name in {"chrome", "edge", "keyboard"}:
            executable = None
            for candidate in applications[name]:
                executable = shutil.which(candidate)
                if executable:
                    break
            if executable is None:
                raise FileNotFoundError(
                    f"{name.title()} was not found. Install it or add it to PATH."
                )
            subprocess.Popen(
                [executable] if name == "keyboard" else [executable, "--new-window"]
            )
            return
        subprocess.Popen(applications[name])


class LocalAutocomplete:
    """Small private next-word model learned only from locally accepted text."""

    def __init__(self, history_path=None):
        self.lock = threading.Lock()
        self.transitions = defaultdict(lambda: defaultdict(int))
        self.history_path = (
            Path(history_path)
            if history_path
            else Path(__file__).resolve().parent / "data" / "autocomplete.json"
        )
        self.seed = {
            "i": ("am", "need", "would", "want", "can"),
            "i am": ("looking", "working", "going"),
            "i need": ("help", "to", "a"),
            "please": ("help", "open", "show"),
            "open": ("the", "settings", "browser"),
            "turn": ("on", "off"),
            "go": ("back", "forward", "to"),
            "how": ("do", "can", "to"),
            "how do": ("i", "we", "you"),
            "thank": ("you", "you very"),
            "thank you": ("for", "so", "very"),
        }
        self._load()

    def _load(self):
        if not self.history_path.is_file():
            return
        with self.history_path.open("r", encoding="utf-8") as history:
            data = json.load(history)
        if not isinstance(data, dict):
            raise ValueError(f"Invalid autocomplete history: {self.history_path}")
        for previous, words in data.items():
            if not isinstance(previous, str) or not isinstance(words, dict):
                raise ValueError(f"Invalid autocomplete history: {self.history_path}")
            for word, count in words.items():
                if (
                    not isinstance(word, str)
                    or not isinstance(count, int)
                    or count < 0
                ):
                    raise ValueError(f"Invalid autocomplete history: {self.history_path}")
                self.transitions[previous][word] = count

    def _save(self):
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.history_path.with_suffix(".tmp")
        serialized = {
            previous: dict(words)
            for previous, words in self.transitions.items()
        }
        with temporary_path.open("w", encoding="utf-8") as history:
            json.dump(serialized, history, ensure_ascii=False)
        temporary_path.replace(self.history_path)

    def learn(self, text):
        words = [word.lower() for word in text.split() if word.strip()]
        with self.lock:
            for index in range(len(words) - 1):
                previous = words[index - 1] if index > 0 else ""
                self.transitions[previous][words[index]] += 1
                self.transitions[words[index]][words[index + 1]] += 1
            self._save()

    def suggest(self, text, limit=3):
        if not text.strip() or text[-1:].isspace():
            context = text.lower().split()
            prefix = ""
        else:
            parts = text.lower().split()
            context = parts[:-1]
            prefix = parts[-1] if parts else ""

        previous = context[-1] if context else ""
        with self.lock:
            candidates = dict(self.transitions.get(previous, {}))
            if len(context) >= 2:
                phrase = " ".join(context[-2:])
                for word in self.seed.get(phrase, ()):
                    candidates[word] = candidates.get(word, 0) + 2
            if not candidates:
                for word in self.seed.get(previous, ()):
                    candidates[word] = candidates.get(word, 0) + 1
            ranked = sorted(
                (
                    (word, count)
                    for word, count in candidates.items()
                    if word.startswith(prefix) and word != prefix
                ),
                key=lambda item: (-item[1], item[0]),
            )
        return [
            {"completion": word[len(prefix) :], "word": word}
            for word, _ in ranked[:limit]
        ]
