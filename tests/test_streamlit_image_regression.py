import io
import unittest
from unittest.mock import patch

from test_streamlit_audio_regression import install_streamlit_stub

install_streamlit_stub()

from PIL import Image
import pillow_heif

from scripts.aggiungi_dedica_streamlit import (
    UploadedImageSnapshot,
    UPLOAD_IMAGE_MAX_SIDE,
    UPLOAD_IMAGE_HARD_MAX_BYTES,
    optimize_uploaded_image,
    stage_uploaded_image,
    decode_mobile_photo,
)
from scripts import aggiungi_dedica_streamlit as streamlit_app


class StreamlitImageRegressionTest(unittest.TestCase):
    def test_mobile_payload_rejects_partial_or_wrong_dedication_upload(self):
        for payload in (
            {"scope": "hist:other", "request_id": "12345678", "data": "YWJj", "size": 3},
            {"scope": "new", "request_id": "12345678", "data": "broken base64", "size": 3},
            {"scope": "new", "request_id": "12345678", "data": "", "size": 0},
            {"scope": "new", "request_id": "12345678", "data": "YWJj", "size": 4},
        ):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                decode_mobile_photo(payload, "new")
        snapshot = decode_mobile_photo({
            "scope": "new", "request_id": "12345678", "data": "YWJj",
            "size": 3, "name": "phone.jpg", "type": "image/jpeg",
        }, "new")
        self.assertEqual(snapshot.getvalue(), b"abc")

    def convert(self, data, name):
        result, info = optimize_uploaded_image(
            UploadedImageSnapshot(name, "application/octet-stream", data)
        )
        image = Image.open(io.BytesIO(result))
        image.load()
        self.assertEqual(image.format, "WEBP")
        self.assertLessEqual(len(result), UPLOAD_IMAGE_HARD_MAX_BYTES)
        return image, info

    def test_heic_detected_from_content_with_wrong_or_missing_extension(self):
        pillow_heif.register_heif_opener()
        output = io.BytesIO()
        Image.new("RGB", (80, 60), "red").save(output, format="HEIF")
        for name in ("photo.heic", "photo.jpg", "photo"):
            with self.subTest(name=name):
                image, _ = self.convert(output.getvalue(), name)
                self.assertEqual(image.size, (80, 60))

    def test_heif_keeps_primary_photo_instead_of_last_image(self):
        pillow_heif.register_heif_opener()
        output = io.BytesIO()
        Image.new("RGB", (80, 60), "red").save(
            output, format="HEIF", save_all=True,
            append_images=[Image.new("RGB", (80, 60), "blue")],
            primary_index=0,
        )
        image, info = self.convert(output.getvalue(), "photo.heic")
        self.assertEqual(info["frame_count"], 2)
        red, _, blue = image.getpixel((40, 30))
        self.assertGreater(red, blue + 100)

    def test_large_phone_jpeg_resized_and_orientation_preserved(self):
        output = io.BytesIO()
        exif = Image.Exif()
        exif[274] = 6
        Image.new("RGB", (4000, 3000), "green").save(
            output, format="JPEG", exif=exif
        )
        image, info = self.convert(output.getvalue(), "phone.jpg")
        self.assertEqual(info["original_size"], (3000, 4000))
        self.assertLessEqual(max(image.size), UPLOAD_IMAGE_MAX_SIDE)
        self.assertLess(image.width, image.height)

    def test_completed_mobile_upload_is_saved_immediately(self):
        uploaded = UploadedImageSnapshot("telefono.jpg", "image/jpeg", b"foto")
        original_session_state = getattr(streamlit_app.st, "session_state", None)
        streamlit_app.st.session_state = {"new_uploaded_file": uploaded}
        try:
            with patch.object(streamlit_app, "save_form_draft") as save_draft:
                stage_uploaded_image("new")

            snapshot = streamlit_app.st.session_state["new_uploaded_image_snapshot"]
            self.assertEqual(snapshot.getvalue(), b"foto")
            save_draft.assert_called_once_with("new", snapshot)
        finally:
            if original_session_state is None:
                del streamlit_app.st.session_state
            else:
                streamlit_app.st.session_state = original_session_state


if __name__ == "__main__":
    unittest.main()
