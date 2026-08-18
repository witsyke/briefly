import argparse
import asyncio
import re
from pathlib import Path

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.prompt import Confirm
from sqlalchemy import Engine

from briefly import report, store
from briefly.claude import ClaudeBackend
from briefly.extraction import ExtractionOutcome, extract_images
from briefly.extraction.image_extraction import ImageExtractionOutcome
from briefly.prompting import BackendType
from briefly.queue import WorkerQueue

PLACEHOLDER_RE = re.compile(r"\{\{IMAGE:(\d+)\}\}")


def run_extraction_stage(
    engine: Engine, pdf_paths: list[Path], report: report.StageReport
) -> None:
    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
    ) as progress:
        overall = progress.add_task(
            "Extracting literature from PDF", total=len(pdf_paths)
        )
        currently_running: dict[Path, TaskID] = {}

        def on_start(path: Path) -> None:
            currently_running[path] = progress.add_task(f"  {path.name}", total=None)

        def on_result(outcome: ExtractionOutcome) -> None:
            progress.remove_task(currently_running.pop(outcome.path))
            progress.advance(overall)
            store.save_extraction(engine, outcome)
            report.record(outcome)

            if not outcome.succeeded:
                color = "yellow" if outcome.retryable else "red"
                progress.console.print(
                    f"[{color}]failed:[/{color}] {outcome.path.name}: {outcome.error}"
                )

        def on_error(path: Path, exc: BaseException) -> None:
            progress.remove_task(currently_running.pop(path))
            progress.advance(overall)
            report.record_crash(path, exc)
            progress.console.print(f"[bold red]crashed:[/bold red] {path.name}: {exc}")

        queue = WorkerQueue(
            process=ClaudeBackend(BackendType.EXTRACTION).extract,
            on_start=on_start,
            on_result=on_result,
            on_error=on_error,
            max_workers=4,
        )
        asyncio.run(queue.run(pdf_paths))


def run_image_extraction_stage(
    engine: Engine,
    successful: list[ExtractionOutcome],
    images_dir: Path,
    report: report.StageReport,
) -> None:
    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
    ) as progress:
        overall = progress.add_task("Extracting images from PDF", total=len(successful))

        def on_result(outcome: ImageExtractionOutcome) -> None:
            progress.advance(overall)
            store.save_images(engine, outcome)
            report.record(outcome)
            if not outcome.succeeded:
                color = "yellow" if outcome.retryable else "red"
                progress.console.print(
                    f"[{color}]failed:[/{color}] {outcome.path.name}: {outcome.error}"
                )

        def on_error(path: Path, exc: BaseException) -> None:
            progress.advance(overall)
            report.record_crash(path, exc)
            progress.console.print(f"[bold red]crashed:[/bold red] {path.name}: {exc}")

        queue = WorkerQueue(
            process=lambda outcome: extract_images(
                outcome.path, images_dir, outcome.payload.images
            ),
            on_result=on_result,
            on_error=on_error,
            max_workers=4,
        )

        asyncio.run(queue.run(successful))


def run_writing_stage(
    engine: Engine, successful: list[ExtractionOutcome], output_dir: Path
) -> None:
    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
    ) as progress:
        overall = progress.add_task(
            "Writing extractions to markdown", total=len(successful)
        )

        def on_result(path: Path) -> None:
            progress.advance(overall)

        queue = WorkerQueue(
            process=lambda outcome: write_markdown(
                outcome, store.images_for(engine, outcome.path), output_dir
            ),
            on_result=on_result,
            max_workers=4,
        )

        asyncio.run(queue.run(successful))


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


def review_failures(
    engine: Engine, console: Console, report: report.StageReport
) -> None:
    failures = (
        [(path, error, True) for path, error in report.retryable_failures]
        + [(path, error, False) for path, error in report.permanent_failures]
        + [(path, error, True) for path, error in report.crashed]
    )
    if not failures:
        return

    console.print("\n[bold]Review failures[/bold]")
    for path, error, currently_retryable in failures:
        console.print(f"{path}: {error}")
        retryable = Confirm.ask("Retry next run?", default=currently_retryable)
        if retryable != currently_retryable:
            store.set_retryable(engine, path, retryable, error=error)


def main() -> int:

    parser = argparse.ArgumentParser(description="Process PDF papers into a summary")
    parser.add_argument("--literature-dir", type=str, default="literature")
    parser.add_argument("--output-dir", type=str, default="extractions")
    parser.add_argument("--database", type=str, default="briefly.sqlite3")
    args = parser.parse_args()

    console = Console()
    text_extraction_report = report.StageReport(name="Text Extraction")
    image_extraction_report = report.StageReport(name="Image Extraction")

    engine = store.connect(Path(args.database))

    all_pdf_paths = list(Path(args.literature_dir).glob("*.pdf"))
    pdf_paths = store.pending_paths(engine, all_pdf_paths)
    console.print(
        f"{len(all_pdf_paths) - len(pdf_paths)} documents in {args.literature_dir} are already done, {len(pdf_paths)} left to extract"
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    images_dir = output_dir / "images"

    run_extraction_stage(engine, pdf_paths, text_extraction_report)
    run_image_extraction_stage(
        engine,
        store.successful_outcomes(engine),
        images_dir,
        image_extraction_report,
    )
    run_writing_stage(engine, store.successful_outcomes(engine), output_dir)

    report.print_summary(console, [text_extraction_report, image_extraction_report])

    review_failures(engine, console, text_extraction_report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
