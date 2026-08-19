import asyncio
import json
from asyncio.subprocess import PIPE
from pathlib import Path

from pydantic import ValidationError

from briefly.extraction import ExtractionOutcome, ExtractionPayload
from briefly.prompting import BackendType, build_prompt


class ClaudeBackend:
    def __init__(self, type: BackendType) -> None:
        self.type = type

    async def extract(self, pdf_path: Path) -> ExtractionOutcome:
        prompt = build_prompt(pdf_path, type=self.type)
        schema = ExtractionPayload.model_json_schema()

        try:
            argv = [
                "claude",
                "-p",
                "--allowedTools",
                "Read",
                "--output-format",
                "json",
                "--model",
                "claude-sonnet-5",
                "--json-schema",
                json.dumps(schema),
                "--permission-mode",
                "bypassPermissions",
            ]
            process = await asyncio.create_subprocess_exec(
                *argv, stdin=PIPE, stdout=PIPE, stderr=PIPE
            )
            raw_stdout, raw_stderr = await process.communicate(prompt.encode("utf-8"))
        except OSError as exc:
            return ExtractionOutcome.failure(pdf_path, exc, retryable=True)

        try:
            envelope = json.loads(raw_stdout)
        except json.JSONDecodeError as exc:
            return ExtractionOutcome.failure(pdf_path, exc, retryable=True)

        if envelope.get("is_error"):
            return ExtractionOutcome.failure(
                pdf_path,
                RuntimeError(envelope.get("result") or "claude reported and error"),
                retryable=True,
            )
        try:
            result = json.loads(envelope["result"])
        except json.JSONDecodeError as exc:
            return ExtractionOutcome.failure(pdf_path, exc, retryable=True)

        try:
            payload = ExtractionPayload.model_validate(result)
        except ValidationError as exc:
            return ExtractionOutcome.failure(pdf_path, exc, retryable=False)

        if payload.error:
            return ExtractionOutcome.failure(
                pdf_path,
                RuntimeError(payload.error),
                retryable=False,
            )

        return ExtractionOutcome.ok(pdf_path, payload)
