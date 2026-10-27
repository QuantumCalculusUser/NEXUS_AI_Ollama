import tempfile
import unittest
from pathlib import Path

from nexus.voice import voice_diagnostics


class VoiceDiagnosticsTests(unittest.TestCase):
    def test_reports_missing_model_files_before_importing_audio_libraries(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "Vosk model is incomplete"):
                voice_diagnostics(Path(directory))


if __name__ == "__main__":
    unittest.main()
