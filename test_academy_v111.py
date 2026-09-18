import ast
from pathlib import Path
import unittest


class AcademyVideoScriptsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path("academy_v111.py").read_text(encoding="utf-8")
        tree = ast.parse(cls.source)
        cls.scripts = None
        for node in tree.body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.target.id == "MACRO_VIDEO_SCRIPTS":
                    cls.scripts = ast.literal_eval(node.value)
                    break
        if cls.scripts is None:
            raise AssertionError("MACRO_VIDEO_SCRIPTS não encontrado")

    def test_all_macro_lessons_have_complete_video_scripts(self):
        expected = {f"macro_{i:02d}" for i in range(1, 9)}
        self.assertEqual(set(self.scripts), expected)
        for lesson_id, segments in self.scripts.items():
            self.assertGreaterEqual(len(segments), 5, lesson_id)
            for segment in segments:
                self.assertTrue(segment.get("bloco"))
                self.assertTrue(segment.get("tela"))
                self.assertTrue(segment.get("narracao"))

    def test_academy_renders_full_recording_script(self):
        self.assertIn('Roteiro completo de gravação', self.source)
        self.assertIn('MACRO_VIDEO_SCRIPTS.get(lesson["id"], [])', self.source)


if __name__ == "__main__":
    unittest.main()
