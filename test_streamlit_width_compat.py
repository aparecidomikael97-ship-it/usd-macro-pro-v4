import pathlib
import unittest


ROOT=pathlib.Path(__file__).resolve().parent


class StreamlitWidthCompatibilityTests(unittest.TestCase):
    def test_application_sources_do_not_use_deprecated_container_width(self):
        offenders=[]
        for path in sorted(ROOT.glob("*.py")):
            if path.name.startswith("test_"):
                continue
            src=path.read_text(encoding="utf-8")
            if "use_container_width=" in src or "use_container_width =" in src:
                offenders.append(path.name)
        self.assertEqual(
            offenders,
            [],
            "Migrar use_container_width para width='stretch'/'content': "
            + ", ".join(offenders),
        )


if __name__=="__main__":
    unittest.main()
