import asyncio
from pathlib import Path

import pytest
from pypdfium2_raw.version import json

from briefly.briefing import BriefConfig, FieldSpec, ProjectInfo
from briefly.claude import ClaudeBackend, ClaudeCallError
from briefly.extraction import ExtractionOutcome, ExtractionPayload
from briefly.payload import PayloadModel


class _Payload(PayloadModel):
    value: str


class _FakeProcess:
    def __init__(self, stdout: bytes) -> None:
        self.stdout = stdout

    async def communicate(self, _input: bytes) -> tuple[bytes, bytes]:
        return self.stdout, b""


def _envelope(result: dict, *, is_error: bool = False) -> bytes:
    return json.dumps({"is_error": is_error, "result": json.dumps(result)}).encode()


def _extraction_payload() -> ExtractionPayload:
    return ExtractionPayload(
        markdown="x", title="t", authors="a", images=[], error=None
    )


def _brief_config() -> BriefConfig:
    return BriefConfig(
        project=ProjectInfo(name="P", description="D"),
        frontmatter=[FieldSpec(field="tags", description="tags")],
        sections=[FieldSpec(field="summary", description="summary")],
    )


def test_run_returns_the_validated_payload_on_success(monkeypatch):
    async def fake_exec(*args, **kwargs):
        return _FakeProcess(_envelope({"value": "test", "error": None}))

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    backend = ClaudeBackend()

    payload = asyncio.run(backend._run("prompt", _Payload))

    assert payload.value == "test"


def test_run_is_retryable_on_malformed_json_envelope(monkeypatch):
    async def fake_exec(*args, **kwargs):
        return _FakeProcess(b"not json")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    backend = ClaudeBackend()

    with pytest.raises(ClaudeCallError) as exc_info:
        asyncio.run(backend._run("prompt", _Payload))

    assert exc_info.value.retryable


def test_run_is_retryable_when_claude_reports_is_error(monkeypatch):
    async def fake_exec(*args, **kwargs):
        return _FakeProcess(_envelope({}, is_error=True))

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    backend = ClaudeBackend()

    with pytest.raises(ClaudeCallError) as exc_info:
        asyncio.run(backend._run("prompt", _Payload))
    assert exc_info.value.retryable


def test_run_is_permanent_on_schema_validation_failure(monkeypatch):
    async def fake_exec(*args, **kwargs):
        return _FakeProcess(_envelope({"error": None}))

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    backend = ClaudeBackend()

    with pytest.raises(ClaudeCallError) as exc_info:
        asyncio.run(backend._run("prompt", _Payload))

    assert not exc_info.value.retryable


def test_run_is_permanent_when_payload_reports_its_own_error(monkeypatch):
    async def fake_exec(*args, **kwargs):
        return _FakeProcess(_envelope({"value": "", "error": "did not work"}))

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    backend = ClaudeBackend()

    with pytest.raises(ClaudeCallError) as exc_info:
        asyncio.run(backend._run("prompt", _Payload))
    assert not exc_info.value.retryable
    assert "did not work" in str(exc_info.value)


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
    backend = ClaudeBackend()

    outcome = asyncio.run(backend.extract(Path("paper.pdf")))

    assert outcome.succeeded
    assert outcome.payload.title == "T"


def test_extract_is_retryable_when_claude_reports_is_error(monkeypatch):
    async def fake_exec(*args, **kwargs):
        return _FakeProcess(_envelope({}, is_error=True))

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    backend = ClaudeBackend()

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
    backend = ClaudeBackend()

    outcome = asyncio.run(backend.extract(Path("paper.pdf")))

    assert not outcome.succeeded
    assert outcome.error == "bad pdf, cannot open"
    assert not outcome.retryable


def test_brief_returns_ok_on_valid_envelope(monkeypatch):
    payload = {"tags": "x", "summary": "y", "error": None}

    async def fake_exec(*args, **kwargs):
        return _FakeProcess(_envelope(payload))

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    backend = ClaudeBackend(_brief_config())
    outcome = ExtractionOutcome.ok(Path("paper.pdf"), _extraction_payload())

    result = asyncio.run(backend.brief(outcome))

    assert result.succeeded
    assert result.fields == {"tags": "x", "summary": "y"}


def test_brief_is_permanent_when_a_values_field_is_out_of_range(monkeypatch):
    config = BriefConfig(
        project=ProjectInfo(name="P", description="D"),
        frontmatter=[
            FieldSpec(field="priority", description="p", values=["low", "high"])
        ],
        sections=[],
    )

    payload = {"priority": "urgent", "error": None}

    async def fake_exec(*args, **kwargs):
        return _FakeProcess(_envelope(payload))

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    backend = ClaudeBackend(config)
    outcome = ExtractionOutcome.ok(Path("paper.pdf"), _extraction_payload())

    result = asyncio.run(backend.brief(outcome))

    assert not result.succeeded
    assert not result.retryable
