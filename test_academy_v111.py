import ast
from pathlib import Path
import unittest


class AcademyVideoScriptsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path("academy_v111.py").read_text(encoding="utf-8")
        tree = ast.parse(cls.source)
        cls.scripts = None
        cls.ict_scripts = None
        cls.atlas_scripts = None
        for node in tree.body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.target.id == "MACRO_VIDEO_SCRIPTS":
                    cls.scripts = ast.literal_eval(node.value)
                elif node.target.id == "ICT_VIDEO_SCRIPTS":
                    cls.ict_scripts = ast.literal_eval(node.value)
                elif node.target.id == "ATLASQUANT_VIDEO_SCRIPTS":
                    cls.atlas_scripts = ast.literal_eval(node.value)
        if cls.scripts is None:
            raise AssertionError("MACRO_VIDEO_SCRIPTS não encontrado")
        if cls.ict_scripts is None:
            raise AssertionError("ICT_VIDEO_SCRIPTS não encontrado")
        if cls.atlas_scripts is None:
            raise AssertionError("ATLASQUANT_VIDEO_SCRIPTS não encontrado")

    def test_all_macro_lessons_have_complete_video_scripts(self):
        expected = {f"macro_{i:02d}" for i in range(1, 9)}
        self.assertEqual(set(self.scripts), expected)
        for lesson_id, segments in self.scripts.items():
            self.assertGreaterEqual(len(segments), 5, lesson_id)
            for segment in segments:
                self.assertTrue(segment.get("bloco"))
                self.assertTrue(segment.get("tela"))
                self.assertTrue(segment.get("narracao"))

    def test_all_ict_lessons_have_complete_video_scripts(self):
        expected = {f"ict_{i:02d}" for i in range(1, 8)}
        self.assertEqual(set(self.ict_scripts), expected)
        for lesson_id, segments in self.ict_scripts.items():
            self.assertGreaterEqual(len(segments), 5, lesson_id)
            for segment in segments:
                self.assertTrue(segment.get("bloco"))
                self.assertTrue(segment.get("tela"))
                self.assertTrue(segment.get("narracao"))

    def test_all_atlasquant_lessons_have_complete_video_scripts(self):
        expected = {f"aq_{i:02d}" for i in range(1, 8)}
        self.assertEqual(set(self.atlas_scripts), expected)
        for lesson_id, segments in self.atlas_scripts.items():
            self.assertGreaterEqual(len(segments), 5, lesson_id)
            for segment in segments:
                self.assertTrue(segment.get("bloco"))
                self.assertTrue(segment.get("tela"))
                self.assertTrue(segment.get("narracao"))

    def test_academy_renders_full_recording_script(self):
        self.assertIn('Roteiro completo de gravação', self.source)
        self.assertIn('def _video_script_for_lesson', self.source)
        self.assertIn('MACRO_VIDEO_SCRIPTS.get(lesson_id, [])', self.source)
        self.assertIn('ICT_VIDEO_SCRIPTS.get(lesson_id, [])', self.source)
        self.assertIn('ATLASQUANT_VIDEO_SCRIPTS.get(lesson_id, [])', self.source)

    def test_all_22_lessons_have_storyboard_support(self):
        all_ids = set(self.scripts) | set(self.ict_scripts) | set(self.atlas_scripts)
        self.assertEqual(len(all_ids), 22)
        self.assertIn('def build_storyboard', self.source)
        self.assertIn('Storyboard visual da aula', self.source)
        self.assertIn('"direcao_visual"', self.source)
        self.assertIn('Sequência pronta para gravação', self.source)


if __name__ == "__main__":
    unittest.main()
