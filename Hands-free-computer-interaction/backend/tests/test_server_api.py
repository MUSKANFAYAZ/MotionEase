import sys
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import server


class FakeMouse:
    def __init__(self):
        self.clicks = []
        self.scrolls = []

    def click(self, button, count):
        self.clicks.append((button.name, count))

    def scroll(self, horizontal, vertical):
        self.scrolls.append((horizontal, vertical))


class FakeProcess:
    def poll(self):
        return None


class ServerApiTests(unittest.TestCase):
    def setUp(self):
        self.client = server.app.test_client()
        self.original_mouse = server.intent_router.mouse
        server.intent_router.mouse = FakeMouse()

    def tearDown(self):
        server.intent_router.mouse = self.original_mouse

    def test_suggestions_and_voice_status_are_available(self):
        self.assertEqual(self.client.get("/api/state").status_code, 200)
        self.assertTrue(self.client.get("/api/voice/status").json["model_ready"])
        response = self.client.post("/api/suggestions", json={"text": "I "})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["suggestions"])

    def test_invalid_gesture_is_rejected_without_clicking(self):
        response = self.client.post(
            "/api/interaction/events", json={"gesture": "unknown"}
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(server.intent_router.mouse.clicks, [])

    def test_gesture_api_dispatches_fused_voice_intent(self):
        server.intent_router.route_voice("select with blink")

        response = self.client.post(
            "/api/interaction/events", json={"gesture": "left_blink"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["fused"])
        self.assertEqual(server.intent_router.mouse.clicks, [("left", 1)])

    def test_missing_vosk_model_is_reported_without_opening_microphone(self):
        missing_model = server.voice_service.model_path.parent / "missing-test-model"
        with patch.object(server.voice_service, "model_path", missing_model):
            response = self.client.post("/api/voice/start")

        self.assertEqual(response.status_code, 409)
        self.assertIn("download_vosk_model.py", response.json["error"])

    def test_start_eye_tracking_is_success_when_already_running(self):
        with patch.object(server, "eye_tracking_process", FakeProcess()):
            response = self.client.post("/start-eye-tracking")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["message"], "Eye tracking is already running")

    def test_spoken_command_with_filler_is_routed_and_exposed_in_state(self):
        with (
            patch.object(server.autocomplete, "learn"),
            patch.dict(server.last_interaction, clear=True),
        ):
            server.handle_transcript("scroll up now")
            response = self.client.get("/api/state")

        self.assertEqual(response.json["last_interaction"]["transcript"], "scroll up now")
        self.assertEqual(
            response.json["last_interaction"]["action"],
            {"handled": True, "action": "scroll_up"},
        )
        self.assertEqual(server.intent_router.mouse.scrolls, [(0, 3)])


if __name__ == "__main__":
    unittest.main()
