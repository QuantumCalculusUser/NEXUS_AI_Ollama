import json
import tempfile
import unittest
from pathlib import Path

from nexus.local_context import epic_games, steam_games


class LocalGameInventoryTests(unittest.TestCase):
    def test_reads_a_steam_app_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            steamapps = root / "steamapps"
            steamapps.mkdir()
            (steamapps / "appmanifest_123.acf").write_text(
                '"AppState" { "name" "Portal 2" "installdir" "Portal 2" }', encoding="utf-8"
            )
            games = steam_games([root])
            self.assertEqual(games[0]["name"], "Portal 2")
            self.assertEqual(games[0]["source"], "Steam")

    def test_reads_an_epic_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "game.item"
            manifest.write_text(json.dumps({"DisplayName": "Fortnite", "InstallLocation": "D:/Games/Fortnite"}), encoding="utf-8")
            games = epic_games(directory)
            self.assertEqual(games, [{"name": "Fortnite", "source": "Epic Games", "path": "D:/Games/Fortnite"}])


if __name__ == "__main__":
    unittest.main()
