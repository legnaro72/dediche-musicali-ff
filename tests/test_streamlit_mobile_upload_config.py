import tomllib
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


class StreamlitMobileUploadConfigTest(unittest.TestCase):
    def test_disconnected_session_survives_a_minute_in_phone_gallery(self):
        with (ROOT_DIR / ".streamlit" / "config.toml").open("rb") as config_file:
            config = tomllib.load(config_file)

        self.assertGreaterEqual(config["server"]["disconnectedSessionTTL"], 60)


if __name__ == "__main__":
    unittest.main()
