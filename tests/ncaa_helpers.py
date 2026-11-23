"""Helpers of the tests of the NCAA source (#888, D4): the real answers of ESPN of ``tests/fixtures/ncaa`` served as the site serves them."""
import gzip
import json
from pathlib import Path
from typing import Any, Dict, List

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "ncaa"


def fixture(name: str) -> Dict[str, Any]:
    return json.loads(gzip.decompress((FIXTURES / f"{name}.json.gz").read_bytes()))


def text(name: str) -> str:
    return json.dumps(fixture(name))


class Clock:
    """Time that only moves when someone sleeps: the pauses of a client are seen without waiting."""

    def __init__(self) -> None:
        self.now, self.sleeps = 1000.0, []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class Site:
    """A fake ESPN: ``answers`` maps a piece of a URL to what it answers (a text, an exception to raise, or a list of those, one per request); every request is kept with its user agent."""

    def __init__(self, answers: Dict[str, object]) -> None:
        self.answers = {k: (list(v) if isinstance(v, list) else [v]) for k, v in answers.items()}
        self.requests: List[tuple] = []

    def fetch(self, url: str, user_agent: str) -> str:
        self.requests.append((url, user_agent))
        for part, queue in self.answers.items():
            if part in url:
                answer = queue.pop(0) if len(queue) > 1 else queue[0]
                if isinstance(answer, BaseException):
                    raise answer
                return answer
        raise AssertionError(f"unexpected request {url}")
