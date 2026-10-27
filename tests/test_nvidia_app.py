import unittest
from unittest.mock import patch

from nexus.nvidia_app import games


class NvidiaAppTests(unittest.TestCase):
    def test_games_excludes_creative_applications(self):
        data = [
            {'displayName': 'Valorant', 'isCreativeApp': False},
            {'displayName': 'AutoCAD', 'isCreativeApp': True},
        ]
        with patch('nexus.nvidia_app.applications', return_value=data):
            self.assertEqual(games(), [{'displayName': 'Valorant', 'isCreativeApp': False}])


if __name__ == '__main__':
    unittest.main()
