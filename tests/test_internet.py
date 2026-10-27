import unittest

from nexus.internet import _DuckDuckGoResultsParser, check_internet


class FakeResponse:
    def __init__(self, status_code=204, text="", is_redirect=False):
        self.status_code = status_code
        self.text = text
        self.is_redirect = is_redirect


class InternetCheckTests(unittest.TestCase):
    def test_verified_connection(self):
        status = check_internet(request_get=lambda *args, **kwargs: FakeResponse())
        self.assertTrue(status.online)

    def test_captive_portal_is_not_reported_as_online(self):
        status = check_internet(request_get=lambda *args, **kwargs: FakeResponse(status_code=200, text="sign in here"))
        self.assertFalse(status.online)
        self.assertIn("sign-in", status.detail)

    def test_parser_extracts_a_result_and_its_snippet(self):
        parser = _DuckDuckGoResultsParser()
        parser.feed('<a class="result__a" href="https://example.com">Example</a><a class="result__snippet">Useful summary</a>')
        parser.close()
        self.assertEqual(parser.results, [{"title": "Example", "url": "https://example.com", "snippet": "Useful summary"}])


if __name__ == "__main__":
    unittest.main()
