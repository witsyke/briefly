from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Protocol

from pydantic import BaseModel, ConfigDict


class ImageReference(BaseModel):
    model_config: ClassVar = ConfigDict(frozen=True, extra="forbid", strict=True)

    order: int
    page: int


class ExtractionPayload(BaseModel):
    """What a LLM or other extraction service must return of a PDF"""

    model_config: ClassVar = ConfigDict(frozen=True, extra="forbid", strict=True)

    markdown: str
    title: str
    authors: str
    images: list[ImageReference]
    error: str | None


@dataclass(frozen=True)
class ExtractionOutcome:
    path: Path
    payload: ExtractionPayload | None
    error: str | None = None
    retryable: bool = False

    @property
    def succeeded(self) -> bool:
        return self.payload is not None

    @classmethod
    def ok(cls, path: Path, payload: ExtractionPayload) -> "ExtractionOutcome":
        return cls(path=path, payload=payload)

    @classmethod
    def failure(
        cls, path: Path, error: BaseException, *, retryable: bool
    ) -> "ExtractionOutcome":
        return cls(path=path, payload=None, error=str(error), retryable=retryable)


class Backend(Protocol):
    async def extract(self, pdf_path: Path) -> ExtractionOutcome: ...
