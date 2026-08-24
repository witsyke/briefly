import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, create_model
from pydantic.functional_validators import model_validator

from briefly.payload import PayloadModel


class ProjectInfo(BaseModel):
    name: str
    description: str


class FieldSpec(BaseModel):
    field: str
    description: str
    values: list[str] | None = None


class BriefConfig(BaseModel):
    project: ProjectInfo
    frontmatter: list[FieldSpec]
    sections: list[FieldSpec]

    @model_validator(mode="after")
    def _unique_field_names(self) -> "BriefConfig":
        names = [spec.field for spec in [*self.frontmatter, *self.sections]]
        if len(names) != len(set(names)):
            raise ValueError("'field' must be unique across frontmattter and sections")
        return self


def _field_type(spec: FieldSpec) -> Any:
    return Literal[tuple(spec.values)] if spec.values else str


def build_brief_model(config: BriefConfig) -> type[PayloadModel]:
    fields: dict[str, Any] = {
        spec.field: (_field_type(spec), Field(description=spec.description))
        for spec in [*config.frontmatter, *config.sections]
    }
    fields["error"] = (str | None, None)

    return create_model(
        "BriefPayload",
        __base__=PayloadModel,
        **fields,
    )


@dataclass(frozen=True)
class BriefOutcome:
    path: Path
    fields: dict[str, str] | None
    error: str | None = None
    retryable: bool = False

    @property
    def succeeded(self):
        return self.fields is not None

    @classmethod
    def ok(cls, path: Path, fields: dict[str, str]) -> "BriefOutcome":
        return cls(path=path, fields=fields)

    @classmethod
    def failure(
        cls, path: Path, error: BaseException, retryable: bool
    ) -> "BriefOutcome":
        return cls(path=path, fields=None, error=str(error), retryable=retryable)


def config_hash(config: BriefConfig) -> str:
    canonical = json.dumps(config.model_dump(), sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()
