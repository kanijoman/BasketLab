"""Helpers of the tests of FIBA (#887): the real pages of ``tests/fixtures/fiba`` served the way the site serves them (as HTML with the data in Next chunks)."""
import gzip
import json
from pathlib import Path
from typing import Dict

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "fiba"


def flight(name: str) -> str:
    return gzip.decompress((FIXTURES / f"{name}.flight.gz").read_bytes()).decode("utf-8")


def html_of(text: str, chunk: int = 20000) -> str:
    """The page that carries ``text`` in its Next data chunks, as the real one does (several ``self.__next_f.push`` scripts)."""
    pieces = [text[i:i + chunk] for i in range(0, len(text), chunk)] or [""]
    return "<html><body>" + "".join(f"<script>self.__next_f.push([1,{json.dumps(piece)}])</script>" for piece in pieces) + "</body></html>"


class Site:
    """A fake FIBA site: ``pages`` maps the end of a URL to what it answers (an HTML text, an exception to raise, or a list of those, one per request); every request is recorded."""

    def __init__(self, pages: Dict[str, object], default: object = None) -> None:
        self.pages = {k: (list(v) if isinstance(v, list) else [v]) for k, v in pages.items()}
        self.default, self.requests = default, []

    def fetch(self, url: str, user_agent: str) -> str:
        self.requests.append((url, user_agent))
        for end, answers in self.pages.items():
            if url.endswith(end):
                answer = answers.pop(0) if len(answers) > 1 else answers[0]
                if isinstance(answer, BaseException):
                    raise answer
                return answer
        if self.default is not None:                                    # what every page that is not listed answers (a 404, usually)
            if isinstance(self.default, BaseException):
                raise self.default
            return self.default
        raise AssertionError(f"unexpected request {url}")


class Clock:
    """A clock and a sleep that go together, so that the pauses of the client can be seen without waiting."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.slept = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds
