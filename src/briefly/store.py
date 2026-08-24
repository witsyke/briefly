import json
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Engine
from sqlmodel import Field, Session, SQLModel, create_engine, delete, select

from briefly.briefing import BriefConfig, BriefOutcome
from briefly.extraction import (
    ExtractionOutcome,
    ExtractionPayload,
    ImageExtractionOutcome,
)
from briefly.extraction.extraction import ImageReference


class ExtractionRow(SQLModel, table=True):
    __tablename__ = "extractions"

    path: str = Field(primary_key=True)
    title: str | None = None
    authors: str | None = None
    markdown: str | None = None
    image_json: str | None = None
    error: str | None = None
    retryable: bool = False


def connect(db_path: Path):
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)
    return engine


def save_extraction(engine: Engine, outcome: ExtractionOutcome) -> None:
    payload = outcome.payload
    row = ExtractionRow(
        path=str(outcome.path),
        title=payload.title if payload else None,
        authors=payload.authors if payload else None,
        markdown=payload.markdown if payload else None,
        image_json=(
            json.dumps([ref.model_dump() for ref in payload.images])
            if payload
            else None
        ),
        error=outcome.error,
        retryable=outcome.retryable,
    )
    with Session(engine) as session:
        session.merge(row)
        session.commit()


def pending_paths(engine: Engine, all_paths: list[Path]) -> list[Path]:
    with Session(engine) as session:
        completed = set(
            session.exec(
                select(ExtractionRow.path).where(
                    ExtractionRow.markdown.is_not(None)
                    | ExtractionRow.retryable.is_(False)
                ),
            ).all()
        )
    return [path for path in all_paths if str(path) not in completed]


def successful_outcomes(engine: Engine) -> list[ExtractionOutcome]:
    with Session(engine) as session:
        rows = session.exec(
            select(ExtractionRow).where(
                ExtractionRow.markdown.is_not(None)  # pyright: ignore
            )
        ).all()

    def make_payload(row: ExtractionRow) -> ExtractionPayload:
        images = [ImageReference(**item) for item in json.loads(row.image_json or "[]")]
        if row.markdown is None:
            raise ValueError(f"Missing markdown for {row.path}")
        if row.title is None:
            raise ValueError(f"Missing title for {row.path}")
        if row.authors is None:
            raise ValueError(f"Missing authors for {row.path}")
        return ExtractionPayload(
            markdown=row.markdown,
            title=row.title,
            authors=row.authors,
            images=images,
            error=row.error,
        )

    return [ExtractionOutcome.ok(Path(row.path), make_payload(row)) for row in rows]


def set_retryable(engine: Engine, path: Path, retryable: bool, error: str) -> None:
    with Session(engine) as session:
        row = session.get(ExtractionRow, str(path))
        if row is None:
            row = ExtractionRow(path=str(path), error=error, retryable=retryable)
        else:
            row.retryable = retryable
        session.add(row)
        session.commit()


class ImageRow(SQLModel, table=True):
    __tablename__ = "images"

    path: str = Field(primary_key=True)
    order: int = Field(primary_key=True)
    page: int
    file_path: str


def save_images(engine: Engine, outcome: ImageExtractionOutcome) -> None:
    if outcome.files is None:
        return

    with Session(engine) as session:
        session.exec(delete(ImageRow).where(ImageRow.path == str(outcome.path)))
        for file in outcome.files:
            session.add(
                ImageRow(
                    path=str(outcome.path),
                    order=file.order,
                    page=file.page,
                    file_path=str(file.file_path),
                )
            )
        session.commit()


def images_for(engine: Engine, path: Path) -> dict[int, Path]:
    with Session(engine) as session:
        rows = session.exec(
            select(ImageRow).where(ImageRow.path == str(path)).order_by(ImageRow.order)
        ).all()

    return {row.order: Path(row.file_path) for row in rows}


class BriefRow(SQLModel, table=True):
    __tablename__ = "briefs"
    path: str = Field(primary_key=True)
    fields_json: str | None = None
    error: str | None = None
    retryable: bool = False


def save_brief(engine: Engine, outcome: BriefOutcome) -> None:
    fields = outcome.fields
    row = BriefRow(
        path=str(outcome.path),
        fields_json=(json.dumps(fields) if fields else None),
        error=outcome.error,
        retryable=outcome.retryable,
    )
    with Session(engine) as session:
        session.merge(row)
        session.commit()


def pending_briefs(engine: Engine) -> list[ExtractionOutcome]:
    outcomes = successful_outcomes(engine)
    with Session(engine) as session:
        completed = set(
            session.exec(
                select(BriefRow.path).where(
                    BriefRow.fields_json.is_not(None) | BriefRow.retryable.is_(False)  # pyright: ignore
                ),
            ).all()
        )
    return [outcome for outcome in outcomes if str(outcome.path) not in completed]


def successful_briefs(engine: Engine, brief_config: BriefConfig) -> list[BriefOutcome]:
    with Session(engine) as session:
        rows = session.exec(
            select(BriefRow).where(
                BriefRow.fields_json.is_not(None)  # pyright: ignore
            )
        ).all()

    return [
        BriefOutcome.ok(Path(row.path), json.loads(row.fields_json or "{}"))
        for row in rows
    ]


@dataclass(frozen=True)
class BriefIndexRow:
    path: Path
    title: str
    authors: str
    fields: dict[str, str]


def brief_index_rows(engine: Engine) -> list[BriefIndexRow]:
    with Session(engine) as session:
        rows = session.exec(
            select(ExtractionRow, BriefRow)
            .join(BriefRow, BriefRow.path == ExtractionRow.path)
            .where(BriefRow.fields_json.is_not(None))  # pyright: ignore
        ).all()

    return [
        BriefIndexRow(
            path=Path(extraction.path),
            title=extraction.title or "",
            authors=extraction.authors or "",
            fields=json.loads(brief.fields_json or "{}"),
        )
        for extraction, brief in rows
    ]
