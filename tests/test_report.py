from pathlib import Path

from briefly.extraction import ExtractionOutcome, ExtractionPayload
from briefly.report import StageReport


def test_stage_report_sorts_outcomes_into_the_right_bucket():
    payload = ExtractionPayload(
        markdown="x", title="t", authors="a", images=[], error=None
    )
    report = StageReport(name="Test")

    report = StageReport(name="Test")

    report.record(ExtractionOutcome.ok(Path("a.pdf"), payload))
    report.record(
        ExtractionOutcome.failure(Path("b.pdf"), RuntimeError("x"), retryable=True)
    )
    report.record(
        ExtractionOutcome.failure(Path("c.pdf"), RuntimeError("y"), retryable=False)
    )
    report.record_crash(Path("d.pdf"), RuntimeError("z"))

    assert report.total == 4
    assert report.succeeded == 1
    assert [path for path, _ in report.retryable_failures] == [Path("b.pdf")]
    assert [path for path, _ in report.permanent_failures] == [Path("c.pdf")]
    assert [path for path, _ in report.crashed] == [Path("d.pdf")]
