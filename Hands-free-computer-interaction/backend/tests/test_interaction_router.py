import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pynput.keyboard import Key

from interaction_router import IntentRouter, LocalAutocomplete
from voice_service import OfflineVoiceService


class FakeMouse:
    def __init__(self):
        self.clicks = []
        self.scrolls = []

    def click(self, button, count):
        self.clicks.append((button.name, count))

    def scroll(self, horizontal, vertical):
        self.scrolls.append((horizontal, vertical))


class FakeKeyboard:
    def __init__(self):
        self.typed = []
        self.pressed = []
        self.released = []

    def type(self, text):
        self.typed.append(text)

    def press(self, key):
        self.pressed.append(key)

    def release(self, key):
        self.released.append(key)


class IntentRouterTests(unittest.TestCase):
    def setUp(self):
        self.router = IntentRouter()
        self.router.mouse = FakeMouse()
        self.router.keyboard = FakeKeyboard()

    def test_voice_armed_blink_confirms_contextual_intent(self):
        armed = self.router.route_voice("select with blink")
        self.assertEqual(armed["action"], "waiting_for_blink")

        result = self.router.route_gesture("right_blink")

        self.assertTrue(result["fused"])
        self.assertEqual(self.router.mouse.clicks, [("left", 1)])

    def test_voice_armed_right_click_changes_gesture_action(self):
        self.router.route_voice("right click with blink")

        result = self.router.route_gesture("left_blink")

        self.assertTrue(result["fused"])
        self.assertEqual(self.router.mouse.clicks, [("right", 1)])

    def test_duplicate_blink_event_is_ignored(self):
        with patch("interaction_router.time.monotonic", side_effect=[10.0, 10.2]):
            first = self.router.route_gesture("left_blink")
            second = self.router.route_gesture("left_blink")

        self.assertEqual(first["action"], "left_click")
        self.assertTrue(second["duplicate"])
        self.assertEqual(self.router.mouse.clicks, [("left", 1)])

    def test_voice_blink_command_variants_arm_expected_action(self):
        expected = (
            ("select with blink", "left_click"),
            ("confirm with blink", "left_click"),
            ("use blink to select", "left_click"),
            ("double click with blink", "double_click"),
            ("double-click with blink", "double_click"),
            ("right click with blink", "right_click"),
            ("use blink for right click", "right_click"),
        )

        for phrase, action in expected:
            with self.subTest(phrase=phrase):
                result = self.router.route_voice(phrase)

                self.assertEqual(result["action"], "waiting_for_blink")
                self.assertEqual(self.router.pending_gesture_intent, action)
                self.router.pending_gesture_intent = None

    def test_unknown_gesture_does_not_consume_pending_intent(self):
        self.router.route_voice("select with blink")

        result = self.router.route_gesture("unknown")

        self.assertFalse(result["handled"])
        self.assertEqual(self.router.pending_gesture_intent, "left_click")
        self.assertEqual(self.router.mouse.clicks, [])

    def test_dictation_formats_punctuation_and_types_locally(self):
        self.router.route_voice("start dictating")

        result = self.router.route_voice("hello comma world")

        self.assertEqual(result["action"], "dictation_text")
        self.assertEqual(self.router.keyboard.typed, ["Hello, world "])

    def test_dictation_corrects_spelling_and_keeps_sentence_case(self):
        self.router.route_voice("start typing")

        result = self.router.route_voice("i am serching tomorow")

        self.assertEqual(result["text"], "I am searching tomorrow")
        self.assertEqual(self.router.keyboard.typed, ["I am searching tomorrow "])

    def test_dictation_preserves_ambiguous_search_spelling(self):
        self.router.route_voice("start typing")

        result = self.router.route_voice("search the interent")

        self.assertEqual(result["text"], "Search the interent")
        self.assertEqual(self.router.keyboard.typed, ["Search the interent "])

    def test_dictation_does_not_execute_desktop_commands(self):
        self.router.route_voice("start typing")

        result = self.router.route_voice("scroll up")

        self.assertEqual(result["action"], "dictation_text")
        self.assertEqual(self.router.keyboard.typed, ["Scroll up "])
        self.assertEqual(self.router.mouse.scrolls, [])

    def test_scroll_command_is_allow_listed(self):
        result = self.router.route_voice("scroll down.")

        self.assertTrue(result["handled"])
        self.assertEqual(self.router.mouse.scrolls, [(0, -3)])

    def test_voice_click_commands_and_aliases(self):
        expected = (
            ("left click", "left", 1),
            ("click", "left", 1),
            ("select", "left", 1),
            ("confirm", "left", 1),
            ("double-click", "left", 2),
            ("right-click", "right", 1),
        )

        for phrase, button, count in expected:
            with self.subTest(phrase=phrase):
                result = self.router.route_voice(phrase)

                self.assertTrue(result["handled"])
                self.assertEqual(self.router.mouse.clicks[-1], (button, count))

    def test_scroll_up_and_down_commands(self):
        for phrase, expected_scroll in (
            ("scroll up", (0, 3)),
            ("scroll down", (0, -3)),
        ):
            with self.subTest(phrase=phrase):
                result = self.router.route_voice(phrase)

                self.assertTrue(result["handled"])
                self.assertEqual(self.router.mouse.scrolls[-1], expected_scroll)

    def test_punctuation_is_ignored_for_command_matching(self):
        result = self.router.route_voice("  SCROLL, UP!  ")

        self.assertTrue(result["handled"])
        self.assertEqual(result["action"], "scroll_up")
        self.assertEqual(self.router.mouse.scrolls, [(0, 3)])

    def test_common_spoken_fillers_are_ignored_for_command_matching(self):
        expected = (
            ("scroll up now", "scroll_up", (0, 3)),
            ("could you please scroll down for me", "scroll_down", (0, -3)),
        )

        for phrase, action, scroll in expected:
            with self.subTest(phrase=phrase):
                result = self.router.route_voice(phrase)

                self.assertTrue(result["handled"])
                self.assertEqual(result["action"], action)
                self.assertEqual(self.router.mouse.scrolls[-1], scroll)

    def test_open_application_accepts_a_spoken_article(self):
        for phrase, action, application in (
            ("please open the calculator now", "open_calculator", "calculator"),
            ("open the edge", "open_edge", "edge"),
        ):
            with self.subTest(phrase=phrase):
                with patch.object(self.router, "_open_application") as open_application:
                    result = self.router.route_voice(phrase)

                self.assertTrue(result["handled"])
                self.assertEqual(result["action"], action)
                open_application.assert_called_once_with(application)

    def test_polite_blink_command_still_arms_fusion(self):
        result = self.router.route_voice("please select with blink now")

        self.assertEqual(result["action"], "waiting_for_blink")
        self.assertEqual(self.router.pending_gesture_intent, "left_click")
        self.assertEqual(self.router.mouse.clicks, [])

    def test_command_phrase_inside_a_sentence_remains_unrecognized(self):
        result = self.router.route_voice("I need to scroll up")

        self.assertFalse(result["handled"])
        self.assertEqual(self.router.mouse.scrolls, [])

    def test_dictation_commands_start_and_stop_mode(self):
        started = self.router.route_voice("start dictating.")
        self.assertEqual(started["action"], "dictation_started")
        self.assertTrue(self.router.dictation_enabled)
        self.assertTrue(self.router.is_dictation_enabled())

        stopped = self.router.route_voice("stop dictating.")
        self.assertEqual(stopped["action"], "dictation_stopped")
        self.assertFalse(self.router.dictation_enabled)
        self.assertFalse(self.router.is_dictation_enabled())

    def test_start_typing_enables_dictation_and_enter_submits(self):
        started = self.router.route_voice("start typing")
        typed = self.router.route_voice("search for cats")
        submitted = self.router.route_voice("enter")

        self.assertEqual(started["action"], "dictation_started")
        self.assertEqual(typed["action"], "dictation_text")
        self.assertEqual(self.router.keyboard.typed, ["Search for cats "])
        self.assertEqual(submitted["action"], "enter_pressed")
        self.assertEqual(self.router.keyboard.pressed[-1], Key.enter)
        self.assertEqual(self.router.keyboard.released[-1], Key.enter)

    def test_enter_is_not_pressed_outside_dictation(self):
        result = self.router.route_voice("enter")

        self.assertFalse(result["handled"])
        self.assertEqual(self.router.keyboard.pressed, [])

    def test_focus_address_bar_sends_platform_shortcut(self):
        with patch("interaction_router.platform.system", return_value="Windows"):
            result = self.router.route_voice("focus address bar")

        self.assertEqual(result["action"], "address_bar_focused")
        self.assertEqual(self.router.keyboard.pressed, [Key.ctrl, "l"])
        self.assertEqual(self.router.keyboard.released, ["l", Key.ctrl])

    def test_open_application_commands_are_allow_listed(self):
        for phrase, application in (
            ("open notepad", "notepad"),
            ("open calculator", "calculator"),
            ("open files", "files"),
            ("open chrome", "chrome"),
            ("open edge", "edge"),
        ):
            with self.subTest(phrase=phrase):
                with patch.object(self.router, "_open_application") as open_application:
                    result = self.router.route_voice(phrase)

                self.assertTrue(result["handled"])
                open_application.assert_called_once_with(application)

    def test_open_keyboard_is_an_allow_listed_command(self):
        with patch.object(self.router, "_open_application") as open_application:
            result = self.router.route_voice("open keyboard")

        self.assertEqual(result["action"], "open_keyboard")
        open_application.assert_called_once_with("keyboard")

    def test_opens_installed_windows_browsers_in_new_windows(self):
        for browser, executable_name in (
            ("chrome", "chrome.exe"),
            ("edge", "msedge.exe"),
        ):
            with self.subTest(browser=browser):
                with (
                    patch("interaction_router.platform.system", return_value="Windows"),
                    patch("interaction_router.Path.is_file", return_value=True),
                    patch("interaction_router.subprocess.Popen") as popen,
                ):
                    IntentRouter._open_application(browser)

                self.assertEqual(popen.call_count, 1)
                self.assertTrue(str(popen.call_args.args[0][0]).endswith(executable_name))
                self.assertEqual(popen.call_args.args[0][1], "--new-window")

    def test_opens_windows_on_screen_keyboard(self):
        with (
            patch("interaction_router.platform.system", return_value="Windows"),
            patch("interaction_router.Path.is_file", return_value=True),
            patch("interaction_router.subprocess.Popen") as popen,
        ):
            IntentRouter._open_application("keyboard")

        self.assertTrue(str(popen.call_args.args[0][0]).endswith("System32\\osk.exe"))


class LocalAutocompleteTests(unittest.TestCase):
    def test_learns_and_reloads_word_transitions_without_raw_phrases(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "autocomplete.json"
            autocomplete = LocalAutocomplete(path)
            autocomplete.learn("I need help")
            autocomplete.learn("I need to focus")

            saved_data = json.loads(path.read_text(encoding="utf-8"))
            self.assertNotIn("I need help", path.read_text(encoding="utf-8"))
            self.assertIn("need", saved_data)

            reloaded = LocalAutocomplete(path)
            words = {item["word"] for item in reloaded.suggest("I need ")}
            self.assertTrue({"help", "to"}.issubset(words))

    def test_returns_local_suggestions_for_prefix(self):
        autocomplete = LocalAutocomplete(Path(tempfile.gettempdir()) / "empty.json")
        self.assertEqual(autocomplete.suggest("I "), [
            {"completion": word, "word": word}
            for word in ("am", "can", "need")
        ])


class OfflineVoiceServiceTests(unittest.TestCase):
    def test_command_mode_uses_limited_grammar_but_dictation_does_not(self):
        class FakeRecognizer:
            def __init__(self, *arguments):
                self.arguments = arguments
                self.words_enabled = False

            def SetWords(self, enabled):
                self.words_enabled = enabled

        model = object()
        command_recognizer = OfflineVoiceService._create_recognizer(
            FakeRecognizer, model, False
        )
        dictation_recognizer = OfflineVoiceService._create_recognizer(
            FakeRecognizer, model, True
        )

        self.assertEqual(len(command_recognizer.arguments), 3)
        self.assertIn("scroll up", json.loads(command_recognizer.arguments[2]))
        self.assertIn("scroll down", json.loads(command_recognizer.arguments[2]))
        for phrase in (
            "start typing",
            "open chrome",
            "open edge",
            "open keyboard",
            "focus address bar",
        ):
            self.assertIn(phrase, json.loads(command_recognizer.arguments[2]))
        self.assertIn(
            "could you please scroll down for me",
            json.loads(command_recognizer.arguments[2]),
        )
        self.assertIn("[unk]", json.loads(command_recognizer.arguments[2]))
        self.assertEqual(dictation_recognizer.arguments, (model, 16000))
        self.assertTrue(command_recognizer.words_enabled)
        self.assertTrue(dictation_recognizer.words_enabled)

    def test_start_requires_local_vosk_model(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            service = OfflineVoiceService(
                Path(temporary_directory) / "missing-model",
                lambda text: None,
            )
            with self.assertRaises(FileNotFoundError):
                service.start()
            self.assertEqual(service.status()["status"], "stopped")


if __name__ == "__main__":
    unittest.main()
