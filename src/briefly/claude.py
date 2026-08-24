import asyncio
import json
from asyncio.subprocess import PIPE
from pathlib import Path
from typing import TypeVar

from pydantic import ValidationError

from briefly.briefing import BriefConfig, BriefOutcome, build_brief_model
from briefly.extraction import ExtractionOutcome, ExtractionPayload
from briefly.payload import PayloadModel
from briefly.prompting import build_briefing_prompt, build_extraction_prompt


class ClaudeCallError(Exception):
    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


Model = TypeVar("Model", bound=PayloadModel)


class ClaudeBackend:
    def __init__(self, brief_config: BriefConfig | None = None) -> None:
        self.brief_config = brief_config

    async def _run(
        self,
        prompt: str,
        model: type[Model],
        allowed_tools: list[str] | None = None,
    ) -> Model:
        schema = model.model_json_schema()
        try:
            argv = [
                "claude",
                "-p",
                "--output-format",
                "json",
                "--model",
                "claude-sonnet-5",
                "--json-schema",
                json.dumps(schema),
                "--permission-mode",
                "bypassPermissions",
            ]
            if allowed_tools:
                argv += ["--allowedTools", ",".join(allowed_tools)]

            process = await asyncio.create_subprocess_exec(
                *argv, stdin=PIPE, stdout=PIPE, stderr=PIPE
            )

            raw_stdout, _ = await process.communicate(prompt.encode("utf-8"))
        except OSError as exc:
            raise ClaudeCallError(str(exc), retryable=True) from exc

        try:
            envelope = json.loads(raw_stdout)
        except json.JSONDecodeError as exc:
            raise ClaudeCallError(str(exc), retryable=True) from exc

        if envelope.get("is_error"):
            raise ClaudeCallError(
                envelope.get("result") or "claude reported and error", retryable=True
            )

        try:
            result = json.loads(envelope["result"])
        except json.JSONDecodeError as exc:
            raise ClaudeCallError(str(exc), retryable=True) from exc

        try:
            payload = model.model_validate(result)
        except ValidationError as exc:
            raise ClaudeCallError(str(exc), retryable=False) from exc

        if payload.error:
            raise ClaudeCallError(payload.error, retryable=False)

        return payload

    async def extract(self, pdf_path: Path) -> ExtractionOutcome:
        try:
            payload = await self._run(
                build_extraction_prompt(pdf_path),
                ExtractionPayload,
                allowed_tools=["Read"],
            )
        except ClaudeCallError as exc:
            return ExtractionOutcome.failure(
                path=pdf_path,
                error=exc,
                retryable=exc.retryable,
            )
        return ExtractionOutcome.ok(path=pdf_path, payload=payload)

    async def brief(self, outcome: ExtractionOutcome) -> BriefOutcome:
        assert self.brief_config
        try:
            payload = await self._run(
                build_briefing_prompt(outcome.payload.markdown, self.brief_config),
                build_brief_model(self.brief_config),
            )
        except ClaudeCallError as exc:
            return BriefOutcome.failure(
                path=outcome.path,
                error=exc,
                retryable=exc.retryable,
            )
        return BriefOutcome.ok(
            path=outcome.path, fields=payload.model_dump(exclude={"error"})
        )
