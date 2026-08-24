from pathlib import Path

from briefly import store
from briefly.briefing import BriefConfig, BriefOutcome, FieldSpec, ProjectInfo
from briefly.extraction import ExtractionOutcome, ExtractionPayload


def _extraction_payload() -> ExtractionPayload:
    return ExtractionPayload(
        markdown="x", title="t", authors="a", images=[], error=None
    )


def _config() -> BriefConfig:
    return BriefConfig(
        project=ProjectInfo(name="My Project", description="Studies X"),
        frontmatter=[FieldSpec(field="tags", description="topical tags")],
        sections=[FieldSpec(field="summary", description="a summary")],
    )


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


def test_pending_brief_excludes_completed_and_permanently_failed(tmp_path):
    engine = store.connect(tmp_path / "test.sqlite3")
    store.save_extraction(
        engine, ExtractionOutcome.ok(Path("a.pdf"), _extraction_payload())
    )
    store.save_extraction(
        engine, ExtractionOutcome.ok(Path("b.pdf"), _extraction_payload())
    )
    store.save_extraction(
        engine, ExtractionOutcome.ok(Path("c.pdf"), _extraction_payload())
    )

    store.save_brief(engine, BriefOutcome.ok(Path("a.pdf"), {"summary": "done"}))
    store.save_brief(
        engine,
        BriefOutcome.failure(Path("b.pdf"), RuntimeError("bad"), retryable=False),
    )

    pending = store.pending_briefs(engine)

    assert [outcome.path for outcome in pending] == [Path("c.pdf")]


def test_successful_briefs_round_trips_fields(tmp_path):
    engine = store.connect(tmp_path / "test.sqlite3")
    store.save_extraction(
        engine, ExtractionOutcome.ok(Path("a.pdf"), _extraction_payload())
    )
    store.save_brief(engine, BriefOutcome.ok(Path("a.pdf"), {"summary": "done"}))

    briefs = store.successful_briefs(engine, _config())

    assert briefs[0].fields == {"summary": "done"}


def test_sync_brief_config_invalidates_briefs_when_config_changes(tmp_path):
    engine = store.connect(tmp_path / "test.sqlite3")
    config_a = BriefConfig(
        project=ProjectInfo(name="P", description="D"),
        frontmatter=[FieldSpec(field="tags", description="tags")],
        sections=[],
    )
    config_b = BriefConfig(
        project=ProjectInfo(name="P", description="D"),
        frontmatter=[
            FieldSpec(field="tags", description="tags"),
            FieldSpec(field="priority", description="prio"),
        ],
        sections=[],
    )

    store.sync_brief_config(engine, config_a)
    store.save_brief(engine, BriefOutcome.ok(Path("a.pdf"), {"tags": "x"}))

    invalidated = store.sync_brief_config(engine, config_b)

    assert invalidated == 1
    assert store.pending_briefs(engine) == []


def test_sync_brief_config_is_a_no_op_when_config_is_unchanged(tmp_path):
    engine = store.connect(tmp_path / "test.sqlite3")
    config = BriefConfig(
        project=ProjectInfo(name="P", description="D"),
        frontmatter=[FieldSpec(field="tags", description="tags")],
        sections=[],
    )

    store.sync_brief_config(engine, config)
    store.save_brief(engine, BriefOutcome.ok(Path("a.pdf"), {"tags": "x"}))

    invalidated = store.sync_brief_config(engine, config)

    assert invalidated == 0
