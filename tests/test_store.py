from pathlib import Path

from briefly import store
from briefly.extraction import ExtractionOutcome, ExtractionPayload


def test_pending_path_excludes_succeeded_and_permanent_failures(tmp_path):
    engine = store.connect(tmp_path / "test.sqlite3")
    payload = ExtractionPayload(
        markdown="x", title="t", authors="a", images=[], error=None
    )
    store.save_extraction(engine, ExtractionOutcome.ok(Path("a.pdf"), payload))
    store.save_extraction(
        engine,
        ExtractionOutcome.failure(Path("b.pdf"), RuntimeError("bad"), retryable=False),
    )
    store.save_extraction(
        engine,
        ExtractionOutcome.failure(Path("c.pdf"), RuntimeError("flaky"), retryable=True),
    )

    pending = store.pending_paths(
        engine, [Path("a.pdf"), Path("b.pdf"), Path("c.pdf"), Path("d.pdf")]
    )

    assert pending == [Path("c.pdf"), Path("d.pdf")]


def test_set_retryable_creates_a_row_for_a_path_that_crashed(tmp_path):
    engine = store.connect(tmp_path / "test.sqlite3")

    store.set_retryable(engine, Path("crashed.pdf"), retryable=False, error="boom")

    assert store.pending_paths(engine, [Path("crashed.pdf")]) == []
