import asyncio
from pathlib import Path

from pypdfium2_raw.version import json

from briefly.claude import ClaudeBackend
from briefly.prompting import BackendType


class _FakeProcess:
    def __init__(self, stdout: bytes) -> None:
        self.stdout = stdout

    async def communicate(self, _input: bytes) -> tuple[bytes, bytes]:
        return self.stdout, b""


def _envelope(result: dict, *, is_error: bool = False) -> bytes:
    return json.dumps({"is_error": is_error, "result": json.dumps(result)}).encode()


def test_extract_returns_ok_on_a_valid_envelope(monkeypatch):
    payload = {
        "markdown": "# Paper",
        "title": "T",
        "authors": "A",
        "images": [],
        "error": None,
    }

    async def fake_exec(*args, **kwargs):
        return _FakeProcess(_envelope(payload))

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    backend = ClaudeBackend(BackendType.EXTRACTION)

    outcome = asyncio.run(backend.extract(Path("paper.pdf")))

    assert outcome.succeeded
    assert outcome.payload.title == "T"


def test_extract_is_retryable_when_claude_reports_is_error(monkeypatch):
    async def fake_exec(*args, **kwargs):
        return _FakeProcess(_envelope({}, is_error=True))

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    backend = ClaudeBackend(BackendType.EXTRACTION)

    outcome = asyncio.run(backend.extract(Path("paper.pdf")))

    assert not outcome.succeeded
    assert outcome.retryable


def test_extract_is_permanent_when_llm_reports_error(monkeypatch):
    payload = {
        "markdown": "",
        "title": "",
        "authors": "",
        "images": [],
        "error": "bad pdf, cannot open",
    }

    async def fake_exec(*args, **kwargs):
        return _FakeProcess(_envelope(payload))

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    backend = ClaudeBackend(BackendType.EXTRACTION)

    outcome = asyncio.run(backend.extract(Path("paper.pdf")))

    assert not outcome.succeeded
    assert outcome.error == "bad pdf, cannot open"
    assert not outcome.retryable
