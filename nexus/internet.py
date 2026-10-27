"""Small, explicit internet checks and user-initiated web research.

No request is made for a chat message unless the user presses the Web search
button.  This keeps the normal Ollama chat path local-first.
"""
from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote_plus, urlparse

import requests


CONNECTIVITY_CHECKS = (
    ("https://connectivitycheck.gstatic.com/generate_204", "gstatic"),
    ("https://www.cloudflare.com/cdn-cgi/trace", "cloudflare"),
)
SEARCH_URL = "https://html.duckduckgo.com/html/?q={query}"
USER_AGENT = "NEXUS-AI/1.0 (local desktop assistant)"


@dataclass(frozen=True)
class InternetStatus:
    online: bool
    detail: str


def check_internet(timeout: float = 3.0, request_get=requests.get) -> InternetStatus:
    """Verify DNS plus HTTPS access without treating an open socket as internet.

    A raw connection to a fixed IP can succeed on a captive portal or a network
    that blocks DNS/web traffic, so it is intentionally not used as the signal.
    """
    errors: list[Exception] = []
    intercepted = False
    for url, provider in CONNECTIVITY_CHECKS:
        try:
            response = request_get(
                url,
                timeout=timeout,
                allow_redirects=False,
                headers={"User-Agent": USER_AGENT},
            )
        except requests.exceptions.SSLError as exc:
            errors.append(exc)
            continue
        except requests.RequestException as exc:
            errors.append(exc)
            continue

        body = response.text.strip()
        if provider == "gstatic" and response.status_code == 204:
            return InternetStatus(True, "HTTPS and DNS verified")
        if provider == "cloudflare" and response.status_code == 200 and "fl=" in body and "ip=" in body:
            return InternetStatus(True, "HTTPS and DNS verified")
        intercepted = True

    if intercepted:
        return InternetStatus(False, "This network redirected or blocked the connectivity check. Open a browser and complete any sign-in page.")
    if any(isinstance(error, requests.exceptions.SSLError) for error in errors):
        return InternetStatus(False, "HTTPS certificate validation failed. Check your system clock or network security software.")
    if any("name resolution" in str(error).lower() or "getaddrinfo" in str(error).lower() for error in errors):
        return InternetStatus(False, "DNS could not resolve a public website. Connect to Wi-Fi/Ethernet or fix DNS settings.")
    return InternetStatus(False, "No HTTPS connection. Check Wi-Fi/Ethernet, airplane mode, proxy, or firewall settings.")


class _DuckDuckGoResultsParser(HTMLParser):
    """Extract result links and titles from DuckDuckGo's lightweight HTML page."""

    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._current: dict[str, str] | None = None
        self._collecting = ""

    def _finish_current(self) -> None:
        if not self._current:
            return
        title = " ".join(self._current.get("title", "").split())
        href = self._current.get("url", "")
        if title and href:
            parsed = urlparse(href if not href.startswith("//") else "https:" + href)
            redirect_target = parse_qs(parsed.query).get("uddg", [""])[0]
            self._current["url"] = redirect_target or href
            self._current["title"] = title
            self._current["snippet"] = " ".join(self._current.get("snippet", "").split())
            self.results.append(self._current)
        self._current = None
        self._collecting = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = values.get("class") or ""
        if tag == "a" and "result__a" in classes:
            self._finish_current()
            self._current = {"title": "", "url": values.get("href") or "", "snippet": ""}
            self._collecting = "title"
        elif self._current and "result__snippet" in classes:
            self._collecting = "snippet"

    def handle_data(self, data: str) -> None:
        if self._current and self._collecting:
            self._current[self._collecting] += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._collecting == "title":
            self._collecting = ""
        elif tag in {"div", "span"} and self._collecting == "snippet":
            self._collecting = ""

    def close(self) -> None:
        super().close()
        self._finish_current()


def search_web(query: str, limit: int = 5, timeout: float = 12.0, request_get=requests.get) -> list[dict[str, str]]:
    """Return a few links for a query the user explicitly requested."""
    query = " ".join(query.split())
    if not query:
        raise ValueError("Enter a web search query.")
    try:
        response = request_get(
            SEARCH_URL.format(query=quote_plus(query)),
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Web search could not connect: {exc}") from exc
    parser = _DuckDuckGoResultsParser()
    parser.feed(response.text)
    parser.close()
    return parser.results[:limit]
