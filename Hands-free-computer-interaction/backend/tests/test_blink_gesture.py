import unittest
from urllib.error import URLError
from unittest.mock import Mock, patch

from pynput.mouse import Button

from scripts.eye1 import (
    CURSOR_SPEED,
    AdaptiveKalmanFilter,
    DwellClickController,
    OneEuroFilter,
    dispatch_gesture,
    map_head_position,
    stabilize_cursor_position,
)


class CursorMappingTests(unittest.TestCase):
    def test_head_motion_maps_to_a_slightly_slower_cursor(self):
        self.assertEqual(CURSOR_SPEED, 0.55)
        mapped = map_head_position(0.6, 0.5, 0.18)
        self.assertAlmostEqual(mapped, 0.5 + 0.55 * (0.1 / 0.18))

    def test_cursor_filter_settles_after_head_movement_stops(self):
        kalman = AdaptiveKalmanFilter()
        smooth = OneEuroFilter()
        outputs = []

        for frame in range(75):
            timestamp = frame / 30
            measurement = 0.5 + 0.2 * min(timestamp, 1.0)
            filtered = kalman(measurement, timestamp)
            outputs.append(smooth(filtered, timestamp))

        self.assertLess(abs(outputs[-1] - 0.7), 0.003)
        self.assertEqual(kalman.velocity, 0.0)

    def test_cursor_deadband_rejects_small_jitter_and_allows_intentional_motion(self):
        anchor = (500, 300)

        for jitter in ((504, 303), (497, 298), (505, 300), (500, 306)):
            with self.subTest(jitter=jitter):
                self.assertEqual(stabilize_cursor_position(jitter, anchor), anchor)

        self.assertEqual(stabilize_cursor_position((512, 300), anchor), (512, 300))


class FakeMouse:
    def __init__(self):
        self.clicks = []

    def click(self, button, count):
        self.clicks.append((button, count))


class DwellClickControllerTests(unittest.TestCase):
    def test_selects_after_five_seconds_and_only_once_until_moving_away(self):
        controller = DwellClickController()

        self.assertEqual(controller.update((100, 100), 0.0), (None, 0.0))
        click, progress = controller.update((100, 100), 4.99)
        self.assertIsNone(click)
        self.assertAlmostEqual(progress, 0.998)

        self.assertEqual(controller.update((100, 100), 5.0), ((100, 100), 1.0))
        self.assertEqual(controller.update((100, 100), 5.2), (None, 1.0))
        self.assertEqual(controller.update((150, 100), 5.3), (None, 0.0))
        self.assertEqual(controller.update((150, 100), 10.3), ((150, 100), 1.0))


class GestureDispatchTests(unittest.TestCase):
    def test_timeout_does_not_repeat_a_gesture_locally(self):
        mouse = FakeMouse()
        with patch("scripts.eye1.urlopen", side_effect=TimeoutError("timed out")):
            dispatch_gesture("left_blink", mouse, Button.left)

        self.assertEqual(mouse.clicks, [])

    def test_connection_refused_uses_local_fallback(self):
        mouse = FakeMouse()
        error = URLError(ConnectionRefusedError("backend is not running"))
        with patch("scripts.eye1.urlopen", side_effect=error):
            dispatch_gesture("left_blink", mouse, Button.left)

        self.assertEqual(mouse.clicks, [(Button.left, 1)])

    def test_backend_response_does_not_trigger_a_second_local_click(self):
        mouse = FakeMouse()
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b'{"handled": true}'
        with patch("scripts.eye1.urlopen", return_value=response):
            dispatch_gesture("left_blink", mouse, Button.left)

        self.assertEqual(mouse.clicks, [])


if __name__ == "__main__":
    unittest.main()