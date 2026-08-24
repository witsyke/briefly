from pathlib import Path

from briefly.briefing import BriefConfig, FieldSpec, ProjectInfo
from briefly.prompting import build_briefing_prompt, build_extraction_prompt


def _config() -> BriefConfig:
    return BriefConfig(
        project=ProjectInfo(name="Project X", description="Evaluates Y"),
        frontmatter=[FieldSpec(field="tags", description="topical tags")],
        sections=[FieldSpec(field="summary", description="a briefing")],
    )


def test_build_prompt_extraction():
    prompt = build_extraction_prompt(Path("paper.pdf"))
    assert "paper.pdf" in prompt


def test_build_briefing_prompt_substitutes_project_info():
    prompt = build_briefing_prompt("# Paper body", _config())

    assert "Project X" in prompt
    assert "Evaluates Y" in prompt


def test_build_briefing_prompt_embeds_markdown_directly():
    prompt = build_briefing_prompt("# Paper body", _config())

    assert "# Paper body" in prompt


def test_build_briefing_prompt_lists_frontmatter_and_section_fields():
    prompt = build_briefing_prompt("# Paper body", _config())

    assert "tags" in prompt
    assert "topical tags" in prompt
    assert "summary" in prompt
    assert "a briefing" in prompt


def test_build_briefing_prompt_mentions_allowed_values_when_present():
    config = BriefConfig(
        project=ProjectInfo(name="P", description="D"),
        frontmatter=[
            FieldSpec(field="priority", description="d", values=["low", "high"])
        ],
        sections=[],
    )

    prompt = build_briefing_prompt("body", config)

    assert "low" in prompt
    assert "high" in prompt
