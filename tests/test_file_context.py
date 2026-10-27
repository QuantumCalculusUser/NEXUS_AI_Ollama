import tempfile, unittest
from pathlib import Path
from nexus.file_context import extract_file

class FileContextTests(unittest.TestCase):
    def test_text_file(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'notes.txt'; p.write_text('hello nexus',encoding='utf-8')
            text,images=extract_file(str(p))
            self.assertIn('hello nexus',text); self.assertEqual(images,[])
    def test_unsupported(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'thing.xyz'; p.write_text('x')
            with self.assertRaises(ValueError):extract_file(str(p))

if __name__=='__main__':unittest.main()
