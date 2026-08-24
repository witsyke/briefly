from pydantic import BaseModel, ConfigDict


class PayloadModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    error: str | None
