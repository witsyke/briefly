import asyncio
from pathlib import Path

from briefly.briefing import BriefConfig, BriefOutcome, FieldSpec, ProjectInfo
from briefly.cli import write_brief


def test_write_brief_orders_frontmatter_and_sections_by_config_order(tmp_path):
    config = BriefConfig(
        project=ProjectInfo(name="P", description="D"),
        frontmatter=[FieldSpec(field="tags", description="d")],
        sections=[FieldSpec(field="summary", description="d")],
    )

    outcome = BriefOutcome.ok(Path("a.pdf"), {"tags": "x", "summary": "a summary"})

    out_path = asyncio.run(write_brief(outcome, config, tmp_path))

    text = out_path.read_text()
    assert text.startswith("---\ntags: x\n---")
    assert "## Summary\n\na summary" in text
