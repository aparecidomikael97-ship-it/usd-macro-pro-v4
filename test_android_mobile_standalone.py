from pathlib import Path
import unittest


class AndroidMobileStandaloneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.activity = Path(
            "mobile/android/app/src/main/java/com/atlasquant/mobile/MainActivity.java"
        ).read_text(encoding="utf-8")
        cls.academy = Path(
            "mobile/android/app/src/main/assets/academy.html"
        ).read_text(encoding="utf-8")

    def test_academy_contains_all_22_lessons(self):
        expected = (
            {f"macro_{i:02d}" for i in range(1, 9)}
            | {f"ict_{i:02d}" for i in range(1, 8)}
            | {f"aq_{i:02d}" for i in range(1, 8)}
        )
        for lesson_id in expected:
            self.assertIn(f'id:"{lesson_id}"', self.academy)
        self.assertEqual(self.academy.count('id:"macro_'), 8)
        self.assertEqual(self.academy.count('id:"ict_'), 7)
        self.assertEqual(self.academy.count('id:"aq_'), 7)

    def test_offline_academy_is_default_home(self):
        self.assertIn('showAcademy();', self.activity)
        self.assertIn('file:///android_asset/academy.html', self.activity)
        self.assertIn('Academy Offline', self.activity)

    def test_desktop_connection_remains_optional(self):
        self.assertIn('Conectar ao Desktop', self.activity)
        self.assertIn('showDesktopConnection()', self.activity)
        self.assertIn('PREF_URL', self.activity)

    def test_mobile_progress_is_persistent(self):
        self.assertIn('localStorage', self.academy)
        self.assertIn('atlasquant_academy_mobile_done_v1', self.academy)


if __name__ == "__main__":
    unittest.main()
