"""A160 cross-OS, in-memory dependency and UI compatibility LAB smoke.

No untrusted corpus, network effects, real secrets, worker, or provider calls.
These checks do not substitute for the canonical Quality or Security suites.
"""
from importlib import metadata
from io import BytesIO
import unittest

from packaging.requirements import Requirement
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader, PdfWriter
from streamlit.testing.v1 import AppTest


class A160PatchedDependencyLAB(unittest.TestCase):
    def test_01_exact_streamlit_version(self):
        self.assertEqual(metadata.version("streamlit"), "1.66.1")

    def test_02_exact_pillow_version(self):
        self.assertEqual(metadata.version("Pillow"), "13.0.0")

    def test_03_exact_pypdf_version(self):
        self.assertEqual(metadata.version("pypdf"), "6.21.1")

    def test_04_pillow_13_is_allowed_by_installed_streamlit_metadata(self):
        requirements = [Requirement(item) for item in metadata.requires("streamlit")]
        pillow = [r for r in requirements if r.name.lower() == "pillow" and not r.marker]
        self.assertEqual(len(pillow), 1)
        self.assertTrue(pillow[0].specifier.contains("13.0.0"))
        
    def test_05_pypdf_one_page_roundtrip(self):
        writer = PdfWriter()
        writer.add_blank_page(width=300, height=200)
        data = BytesIO()
        writer.write(data)
        data.seek(0)
        reader = PdfReader(data, strict=True)
        self.assertEqual(len(reader.pages), 1)
        self.assertEqual(int(reader.pages[0].mediabox.width), 300)

    def test_06_pypdf_metadata_roundtrip(self):
        writer = PdfWriter()
        writer.add_blank_page(width=300, height=200)
        writer.add_metadata({"/Title": "synthetic A160"})
        data = BytesIO()
        writer.write(data)
        data.seek(0)
        self.assertEqual(PdfReader(data).metadata.title, "synthetic A160")

    def test_07_pypdf_three_page_roundtrip(self):
        writer = PdfWriter()
        for width in (100, 200, 300):
            writer.add_blank_page(width=width, height=420)
        data = BytesIO()
        writer.write(data)
        data.seek(0)
        self.assertEqual([int(p.mediabox.width) for p in PdfReader(data).pages],
                         [100, 200, 300])

    def test_08_pillow_png_rgb_roundtrip(self):
        data = BytesIO()
        Image.new("RGB", (3, 2), (20, 60, 100)).save(data, format="PNG")
        data.seek(0)
        with Image.open(data) as img:
            self.assertEqual(img.convert("RGB").getpixel((1, 1)), (20, 60, 100))

    def test_09_pillow_png_rgba_roundtrip(self):
        data = BytesIO()
        Image.new("RGBA", (2, 2), (10, 20, 30, 40)).save(data, format="PNG")
        data.seek(0)
        with Image.open(data) as img:
            self.assertEqual(img.convert("RGBA").getpixel((0, 0)), (10, 20, 30, 40))

    def test_10_pillow_invalid_bytes_rejected(self):
        with self.assertRaises((UnidentifiedImageError, OSError, ValueError)):
            Image.open(BytesIO(b"not an image")).load()

    def test_11_streamlit_apptest_title_and_button(self):
        at = AppTest.from_string(
            'import streamlit as st\nst.title("A160 LAB")\nst.button("GO")'
        ).run()
        self.assertFalse(at.exception)
        self.assertEqual(at.title[0].value, "A160 LAB")
        at.button[0].click().run()
        self.assertFalse(at.exception)

    def test_12_streamlit_apptest_slider_rerun(self):
        at = AppTest.from_string(
            'import streamlit as st\nst.slider("Risk", min_value=0, max_value=10, value=2)'
        ).run()
        self.assertFalse(at.exception)
        at.slider[0].set_value(7).run()
        self.assertFalse(at.exception)
        self.assertEqual(at.slider[0].value, 7)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(A160PatchedDependencyLAB)
    expected = 12
    if suite.countTestCases() != expected:
        raise SystemExit("A160 FAIL-CLOSED test count drift")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.testsRun != expected or result.skipped or not result.wasSuccessful():
        raise SystemExit("A160 FAIL-CLOSED smoke failed or skipped")
    print("PASS A160 12 in-memory LAB tests; NO CORE HOMOLOGATION")
