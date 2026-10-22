"""A159 isolated in-memory image decoding + Streamlit UI smoke checks.

Compatibility, NOT security penetration tests or a substitute for full
canonical Quality / UI browser suite. Never loads real user media, sends
HTTP, starts global worker, or accesses a production service.
"""
from io import BytesIO
from importlib import metadata
import unittest

from PIL import Image, ImageFile, ImageOps, ImageSequence, UnidentifiedImageError
import streamlit as st
from streamlit.testing.v1 import AppTest


def in_memory_image(fmt="PNG",mode="RGB",size=(14,9)):
    image=Image.new(mode,size,((30,50,80,255) if mode=="RGBA" else (30,50,80)))
    buf=BytesIO()
    image.save(buf,format=fmt)
    buf.seek(0)
    return buf


class A159Pillow13StreamlitRuntimeLAB(unittest.TestCase):
    def test_01_exact_installed_versions_before_imaging(self):
        self.assertEqual(metadata.version("streamlit"),"1.66.1")
        self.assertEqual(metadata.version("Pillow"),"13.0.0")

    def test_02_png_image_roundtrip(self):
        source=in_memory_image()
        with Image.open(source) as image:
            image.load()
            self.assertEqual(image.size,(14,9))
            self.assertEqual(image.mode,"RGB")
            self.assertEqual(image.getpixel((0,0)),(30,50,80))

    def test_03_jpeg_image_roundtrip(self):
        source=in_memory_image(fmt="JPEG")
        with Image.open(source) as image:
            image.load()
            self.assertEqual(image.size,(14,9))
            self.assertEqual(image.mode,"RGB")

    def test_04_png_alpha_roundtrip(self):
        source=in_memory_image(fmt="PNG",mode="RGBA")
        with Image.open(source) as image:
            image.load()
            self.assertEqual(image.getpixel((4,4)),(30,50,80,255))

    def test_05_image_resize_safe_synthetic(self):
        source=in_memory_image()
        with Image.open(source) as image:
            cropped=ImageOps.contain(image,(7,7))
            self.assertLessEqual(cropped.width,7)
            self.assertLessEqual(cropped.height,7)

    def test_06_reject_nonimage_bytes(self):
        with self.assertRaises(UnidentifiedImageError):
            Image.open(BytesIO(b"AION_synthetic_not_an_image"))

    def test_07_truncated_png_not_enabled_globally(self):
        self.assertIs(ImageFile.LOAD_TRUNCATED_IMAGES,False)

    def test_08_pillow_decompression_bomb_threshold_configured(self):
        self.assertIsNotNone(Image.MAX_IMAGE_PIXELS)
        self.assertGreater(Image.MAX_IMAGE_PIXELS,0)

    def test_09_streamlit_app_test_title_and_text(self):
        app=AppTest.from_string(
            "import streamlit as st\n"
            "st.title('AION synthetic smoke')\n"
            "st.write('Pillow 13 UI LAB')\n"
        ).run(timeout=20)
        self.assertEqual(len(app.exception),0,app.exception)
        self.assertEqual(app.title[0].value,"AION synthetic smoke")

    def test_10_streamlit_app_test_metric_and_dataframe(self):
        app=AppTest.from_string(
            "import streamlit as st\n"
            "st.metric('Synthetic count', 12)\n"
            "st.dataframe({'market': ['FOREX'], 'rows': [12]})\n"
        ).run(timeout=20)
        self.assertEqual(len(app.exception),0,app.exception)
        self.assertEqual(app.metric[0].label,"Synthetic count")

    def test_11_streamlit_app_test_button_with_state(self):
        app=AppTest.from_string(
            "import streamlit as st\n"
            "if st.button('Check synthetic gate'):\n"
            "    st.info('HARD NO-GO: not authorized')\n"
        ).run(timeout=20)
        self.assertEqual(len(app.exception),0,app.exception)
        app.button[0].click().run(timeout=20)
        self.assertEqual(len(app.exception),0,app.exception)
        self.assertEqual(len(app.info),1)

    def test_12_streamlit_app_test_synthetic_image_rendering(self):
        app=AppTest.from_string(
            "from io import BytesIO\n"
            "from PIL import Image\n"
            "import streamlit as st\n"
            "im=Image.new('RGB',(12,8),(20,30,40))\n"
            "buf=BytesIO()\n"
            "im.save(buf,format='PNG')\n"
            "st.image(buf.getvalue(),caption='Synthetic only')\n"
            "st.write('Image simulated safely')\n"
        ).run(timeout=20)
        self.assertEqual(len(app.exception),0,app.exception)


if __name__=="__main__":
    unittest.main()
