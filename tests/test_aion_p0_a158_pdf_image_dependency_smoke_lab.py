"""A158 compatible in-memory PDF and image roundtrips after pypdf upgrade.

Synthetic BytesIO only. No corpus ingestion, disk writes, network, service
activation, image decoder hardening claim or external custodian.
"""
from io import BytesIO
from importlib import metadata
import unittest

from pypdf import PdfReader, PdfWriter
from PIL import Image, UnidentifiedImageError


class A158PDFImageCompatibilityLAB(unittest.TestCase):
    def test_01_pypdf_version_is_security_patched_exactly(self):
        self.assertEqual(metadata.version("pypdf"),"6.21.1")

    def test_02_pypdf_writes_and_reads_one_blank_page(self):
        doc=PdfWriter()
        doc.add_blank_page(width=300,height=200)
        data=BytesIO()
        doc.write(data)
        data.seek(0)
        reader=PdfReader(data,strict=True)
        self.assertEqual(len(reader.pages),1)
        self.assertEqual(int(reader.pages[0].mediabox.width),300)

    def test_03_pypdf_multpage_roundtrip(self):
        doc=PdfWriter()
        for width in (120,200,350):
            doc.add_blank_page(width=width,height=440)
        data=BytesIO()
        doc.write(data)
        data.seek(0)
        reader=PdfReader(data)
        self.assertEqual(len(reader.pages),3)
        self.assertEqual([int(x.mediabox.width) for x in reader.pages],[120,200,350])

    def test_04_pypdf_metadata_roundtrip(self):
        doc=PdfWriter()
        doc.add_blank_page(width=210,height=297)
        doc.add_metadata({"/Title":"AION synthetic LAB","/Author":"synthetic"})
        output=BytesIO()
        doc.write(output)
        output.seek(0)
        self.assertEqual(PdfReader(output).metadata.title,"AION synthetic LAB")

    def test_05_pypdf_rejects_truncated_synthetic_payload(self):
        with self.assertRaises(Exception):
            PdfReader(BytesIO(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog"),strict=True)

    def test_06_pillow_png_rgb_bytes_roundtrip(self):
        img=Image.new("RGB",(8,4),(20,90,140))
        output=BytesIO()
        img.save(output,format="PNG")
        output.seek(0)
        with Image.open(output) as img2:
            img2.load()
            self.assertEqual(img2.size,(8,4))
            self.assertEqual(img2.getpixel((0,0)),(20,90,140))

    def test_07_pillow_png_rgba_alpha_roundtrip(self):
        img=Image.new("RGBA",(3,5),(200,20,70,128))
        output=BytesIO()
        img.save(output,format="PNG")
        output.seek(0)
        with Image.open(output) as img2:
            img2.load()
            self.assertEqual(img2.mode,"RGBA")
            self.assertEqual(img2.getpixel((1,1)),(200,20,70,128))

    def test_08_pillow_bad_bytes_rejected_without_claiming_rce_coverage(self):
        with self.assertRaises(UnidentifiedImageError):
            Image.open(BytesIO(b"not-image-synthetic"))


if __name__ == "__main__":
    unittest.main()
