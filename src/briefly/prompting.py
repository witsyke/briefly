from pathlib import Path

from briefly.briefing import BriefConfig, FieldSpec

EXTRACTOR_FILE = Path(__file__).parent / "roles" / "extractor.md"
BRIEFER_FILE = Path(__file__).parent / "roles" / "briefer.md"


def _bullets(fields: list[FieldSpec]) -> str:
    return "\n".join(
        f"- {field.field}: {field.description}"
        + (f"Allowed values: {','.join(field.values)}" if field.values else "")
        for field in fields
    )


def build_extraction_prompt(path: Path) -> str:
    return EXTRACTOR_FILE.read_text().replace("{PDF}", str(path))


def build_briefing_prompt(markdown: str, config: BriefConfig) -> str:
    return (
        BRIEFER_FILE.read_text()
        .replace("{MARKDOWN}", markdown)
        .replace("{PROJECT_NAME}", config.project.name)
        .replace("{PROJECT_DESCRIPTION}", config.project.description)
        .replace("{FRONTMATTER_FIELDS}", _bullets(config.frontmatter))
        .replace("{SECTION_FIELDS}", _bullets(config.sections))
    )
