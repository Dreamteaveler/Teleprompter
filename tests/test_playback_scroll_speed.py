import unittest

from app.pages.playback_mixin import PlaybackMixin


class PlaybackScrollSpeedTest(unittest.TestCase):
    def setUp(self):
        self.mixin = PlaybackMixin()
        self.mixin._font_size = 24

    def test_scroll_speed_at_two_seconds_is_gently_accelerated(self):
        # 旧曲线（elapsed**2.5 * 0.012 * 字号）在 2 秒时约 2.205
        speed = self.mixin._compute_scroll_speed(2.0)

        self.assertLess(speed, 2.0)
        self.assertAlmostEqual(speed, 1.536, places=3)

    def test_scroll_speed_increases_monotonically(self):
        speeds = [
            self.mixin._compute_scroll_speed(0.5),
            self.mixin._compute_scroll_speed(1.0),
            self.mixin._compute_scroll_speed(2.0),
            self.mixin._compute_scroll_speed(3.0),
        ]

        self.assertEqual(speeds, sorted(speeds))
        self.assertGreater(speeds[-1], speeds[0])

    def test_scroll_speed_caps_at_max(self):
        speed = self.mixin._compute_scroll_speed(60.0)

        self.assertEqual(speed, 240)

    def test_scroll_speed_at_zero_is_base(self):
        speed = self.mixin._compute_scroll_speed(0.0)

        self.assertAlmostEqual(speed, 24 * 0.024, places=6)


if __name__ == "__main__":
    unittest.main()
