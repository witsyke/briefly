import re
import shutil
from pathlib import Path

import markdown
import yaml

from briefly.briefing import BriefConfig, BriefOutcome, FieldSpec
from briefly.extraction import ExtractionOutcome
from briefly.store import BriefIndexRow

PLACEHOLDER_RE = re.compile(r"\{\{IMAGE:(\d+)\}\}")
_MD = markdown.Markdown(
    extensions=["extra", "pymdownx.arithmatex", "meta"],
    extension_configs={"pymdownx.arithmatex": {"generic": True}},
)
INDEX_TEMPLATE_FILE = Path(__file__).parent / "templates" / "index.html"
PAGE_TEMPLATE_FILE = Path(__file__).parent / "templates" / "page.html"
STYLE_CSS_FILE = Path(__file__).parent / "templates" / "style.css"


def render_page(markdown_text: str, title: str) -> str:
    _MD.reset()
    markdown_text = markdown_text.replace("](images/", "](../images/")
    body = _MD.convert(markdown_text)
    frontmatter = _render_frontmatter(_MD.Meta)
    return (
        PAGE_TEMPLATE_FILE.read_text()
        .replace("{TITLE}", title)
        .replace("{FRONTMATTER}", frontmatter)
        .replace("{BODY}", body)
    )


def _render_frontmatter(meta: dict[str, list[str]]) -> str:
    if not meta:
        return ""
    items = "".join(
        f"""<div class="meta-item"><span class="meta-key">{key}</span>"""
        f"""<span class="meta-value">{" ".join(values)}</span></div>"""
        for key, values in meta.items()
    )
    return f"""<div class="frontmatter">{items}</div>"""


def render_paper_page(
    extraction_dir: Path, site_dir: Path, path: Path, title: str
) -> None:
    text = (extraction_dir / f"{path.stem}.md").read_text()
    (site_dir / "papers" / f"{path.stem}.html").write_text(render_page(text, title))


def render_brief_page(
    briefing_dir: Path, site_dir: Path, path: Path, title: str
) -> None:
    text = (briefing_dir / f"{path.stem}.md").read_text()
    (site_dir / "briefs" / f"{path.stem}.html").write_text(render_page(text, title))


async def write_markdown(
    outcome: ExtractionOutcome, images: dict[int, Path], output_dir: Path
) -> Path:
    assert outcome.payload is not None
    out_path = output_dir / f"{outcome.path.stem}.md"

    def substitute(match: re.Match[str]) -> str:
        image_path = images.get(int(match.group(1)))
        if image_path is None:
            return match.group(0)
        else:
            relative = image_path.relative_to(output_dir)
            return f"![]({relative})"

    markdown = PLACEHOLDER_RE.sub(substitute, outcome.payload.markdown)
    out_path.write_text(markdown)
    return out_path


async def write_brief(outcome: BriefOutcome, config: BriefConfig, output_dir: Path):
    assert outcome.fields is not None
    out_path = output_dir / f"{outcome.path.stem}.md"
    frontmatter = {
        spec.field: outcome.fields[spec.field] for spec in config.frontmatter
    }
    body = "\n\n".join(
        f"## {spec.field.replace('_', ' ').title()}\n\n{outcome.fields[spec.field]}"
        for spec in config.sections
    )
    out_path.write_text(
        f"""---\n{yaml.safe_dump(frontmatter, width=float("inf"))}---\n\n{body}\n"""
    )
    return out_path


def _field_cell(spec: FieldSpec, value: str) -> str:
    if not spec.values or value not in spec.values:
        return value
    index = spec.values.index(value)
    return f"""<span class="pill pill-{min(index, 4)}">{value}</span>"""


def _index_row(row: BriefIndexRow, frontmatter: list[FieldSpec]) -> str:
    cells = "".join(
        f"""<td class="field-{spec.field}">"""
        f"""{_field_cell(spec, row.fields.get(spec.field, ""))}</td>"""
        for spec in frontmatter
    )

    return f"""
    <tr>
        <td class="title">
        {row.title}
        <a class="link" href="papers/{row.path.stem}.html">[paper]</a>
        <a class="link" href="briefs/{row.path.stem}.html">[brief]</a>
        </td>
        <td class="authors">{row.authors}</td>
        {cells}
    </tr>
    """


def build_index_html(rows: list[BriefIndexRow], frontmatter: list[FieldSpec]) -> str:
    header = "".join(f"<th>{spec.field}</th>" for spec in frontmatter)
    body = "\n".join(_index_row(row, frontmatter) for row in rows)

    return (
        INDEX_TEMPLATE_FILE.read_text()
        .replace("{FRONTMATTER_HEADERS}", header)
        .replace("{ROWS}", body)
    )


def sync_images(extraction_dir: Path, site_dir: Path) -> None:
    images_dir = extraction_dir / "images"
    if images_dir.exists():
        shutil.copytree(images_dir, site_dir / "images", dirs_exist_ok=True)


def sync_css(site_dir: Path) -> None:
    (site_dir / "style.css").write_text(STYLE_CSS_FILE.read_text())
