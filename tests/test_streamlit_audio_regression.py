import sys
import types
import unittest


def install_streamlit_stub():
    streamlit = types.ModuleType("streamlit")
    streamlit.secrets = {}
    streamlit.cache_data = lambda *args, **kwargs: (lambda func: func)
    streamlit.cache_resource = lambda *args, **kwargs: (lambda func: func)

    components = types.ModuleType("streamlit.components")
    components_v1 = types.ModuleType("streamlit.components.v1")
    components.v1 = components_v1

    sys.modules.setdefault("streamlit", streamlit)
    sys.modules.setdefault("streamlit.components", components)
    sys.modules.setdefault("streamlit.components.v1", components_v1)


install_streamlit_stub()

from scripts.aggiungi_dedica_streamlit import default_form_values, prepare_values


class StreamlitAudioRegressionTest(unittest.TestCase):
    def test_spotify_url_wins_over_stale_uploaded_audio_state(self):
        values = default_form_values()
        values.update(
            {
                "date": "2026-09-14",
                "song_title": "Test Song",
                "artist": "Test Artist",
                "audio_url": "https://open.spotify.com/intl-it/track/0xYlLcTvwe9Odc2R7Ftdkk?si=abc",
                "source_type": "uploaded_audio",
                "mime_type": "audio/mpeg",
                "original_filename": "old-upload.mp3",
                "image_mode": "none",
            }
        )

        cleaned = prepare_values(values)

        self.assertEqual(cleaned["source_type"], "spotify")
        self.assertEqual(cleaned["audio_type"], "spotify")
        self.assertEqual(cleaned["audio_url"], "https://open.spotify.com/track/0xYlLcTvwe9Odc2R7Ftdkk")
        self.assertEqual(cleaned["mime_type"], "")
        self.assertEqual(cleaned["original_filename"], "")


if __name__ == "__main__":
    unittest.main()
