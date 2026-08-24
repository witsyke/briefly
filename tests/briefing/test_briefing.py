import pytest
from pydantic import ValidationError

from briefly.briefing import BriefConfig, FieldSpec, ProjectInfo, build_brief_model


def test_brief_config_rejects_duplicate_field_names_across_frontmatter_and_sections():
    with pytest.raises(ValidationError):
        BriefConfig(
            project=ProjectInfo(name="P", description="D"),
            frontmatter=[FieldSpec(field="tags", description="d")],
            sections=[FieldSpec(field="tags", description="d")],
        )


def test_build_brief_model_accepts_a_listed_value():
    config = BriefConfig(
        project=ProjectInfo(name="P", description="D"),
        frontmatter=[
            FieldSpec(field="priority", description="d", values=["low", "high"])
        ],
        sections=[],
    )

    model = build_brief_model(config)

    instance = model(priority="low", error=None)

    assert instance.priority == "low"


def test_build_brief_model_rejects_a_value_outside_the_list():
    config = BriefConfig(
        project=ProjectInfo(name="P", description="D"),
        frontmatter=[
            FieldSpec(field="priority", description="d", values=["low", "high"])
        ],
        sections=[],
    )
    model = build_brief_model(config)

    with pytest.raises(ValidationError):
        model(priority="medium", error=None)


def test_build_brief_model_defaults_error_to_none():
    config = BriefConfig(
        project=ProjectInfo(name="P", description="D"),
        frontmatter=[FieldSpec(field="tags", description="d")],
        sections=[],
    )
    model = build_brief_model(config)

    instance = model(tags="x")

    assert instance.error is None
