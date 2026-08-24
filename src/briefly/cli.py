import argparse
import asyncio
from pathlib import Path

import yaml
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
from briefly.briefing import BriefConfig, BriefOutcome
from briefly.claude import ClaudeBackend
from briefly.extraction import ExtractionOutcome, extract_images
from briefly.extraction.image_extraction import ImageExtractionOutcome
from briefly.queue import WorkerQueue
from briefly.writing import (
    build_index_html,
    render_brief_page,
    render_paper_page,
    sync_css,
    sync_images,
    write_brief,
    write_markdown,
)


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
            process=ClaudeBackend().extract,
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

        def on_error(outcome: ExtractionOutcome, exc: BaseException) -> None:
            progress.advance(overall)
            report.record_crash(outcome.path, exc)
            progress.console.print(
                f"[bold red]crashed:[/bold red] {outcome.path.name}: {exc}"
            )

        queue = WorkerQueue(
            process=lambda outcome: extract_images(
                outcome.path, images_dir, outcome.payload.images
            ),
            on_result=on_result,
            on_error=on_error,
            max_workers=4,
        )

        asyncio.run(queue.run(successful))


def run_briefing_stage(
    engine: Engine,
    successful: list[ExtractionOutcome],
    report: report.StageReport,
    brief_config: BriefConfig,
) -> None:
    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
    ) as progress:
        overall = progress.add_task(
            "Creating briefs for documents", total=len(successful)
        )
        currently_running: dict[Path, TaskID] = {}

        def on_start(outcome: ExtractionOutcome) -> None:
            currently_running[outcome.path] = progress.add_task(
                f"  {outcome.path.name}", total=None
            )

        def on_result(outcome: BriefOutcome) -> None:
            progress.advance(overall)
            store.save_brief(engine, outcome)
            report.record(outcome)
            if not outcome.succeeded:
                color = "yellow" if outcome.retryable else "red"
                progress.console.print(
                    f"[{color}]failed:[/{color}] {outcome.path.name}: {outcome.error}"
                )

        def on_error(outcome: ExtractionOutcome, exc: BaseException) -> None:
            progress.advance(overall)
            report.record_crash(outcome.path, exc)
            progress.console.print(
                f"[bold red]crashed:[/bold red] {outcome.path.name}: {exc}"
            )

        queue = WorkerQueue(
            process=ClaudeBackend(brief_config).brief,
            on_start=on_start,
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


def run_brief_writing_stage(
    engine: Engine,
    successful: list[BriefOutcome],
    brief_config: BriefConfig,
    output_dir: Path,
) -> None:
    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
    ) as progress:
        overall = progress.add_task("Writing briefs to markdown", total=len(successful))

        def on_result(path: Path) -> None:
            progress.advance(overall)

        queue = WorkerQueue(
            process=lambda outcome: write_brief(outcome, brief_config, output_dir),
            on_result=on_result,
            max_workers=4,
        )

        asyncio.run(queue.run(successful))


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


def run_site_stage(
    engine: Engine,
    extraction_dir: Path,
    briefing_dir: Path,
    site_dir: Path,
    brief_config: BriefConfig,
) -> None:
    site_dir.mkdir(exist_ok=True)
    sync_images(extraction_dir, site_dir)
    sync_css(site_dir)

    rows = store.brief_index_rows(engine)
    for row in rows:
        render_paper_page(extraction_dir, site_dir, row.path, row.title)
        render_brief_page(briefing_dir, site_dir, row.path, row.title)

    (site_dir / "index.html").write_text(
        build_index_html(rows, brief_config.frontmatter)
    )


def main() -> int:

    parser = argparse.ArgumentParser(description="Process PDF papers into a summary")
    parser.add_argument("--literature-dir", type=str, default="literature")
    parser.add_argument("--extraction-dir", type=str, default="extractions")
    parser.add_argument("--briefing-dir", type=str, default="briefs")
    parser.add_argument("--site-dir", type=str, default="web")
    parser.add_argument("--briefing-config", type=str, default="brief.yaml")
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

    extraction_dir = Path(args.extraction_dir)
    extraction_dir.mkdir(exist_ok=True)
    images_dir = extraction_dir / "images"

    run_extraction_stage(engine, pdf_paths, text_extraction_report)
    run_image_extraction_stage(
        engine,
        store.successful_outcomes(engine),
        images_dir,
        image_extraction_report,
    )
    run_writing_stage(engine, store.successful_outcomes(engine), extraction_dir)

    reports = [text_extraction_report, image_extraction_report]

    if Confirm.ask(
        "Do you want to run brief creation (requires a valid briefing config?",
        default=True,
    ):
        briefing_report = report.StageReport(name="Brief Creation")
        briefing_dir = Path(args.briefing_dir)
        briefing_dir.mkdir(exist_ok=True)

        with open(args.briefing_config) as config:
            brief_config = BriefConfig.model_validate(yaml.safe_load(config))

        run_briefing_stage(
            engine, store.pending_briefs(engine), briefing_report, brief_config
        )
        run_brief_writing_stage(
            engine,
            store.successful_briefs(engine, brief_config),
            brief_config,
            briefing_dir,
        )
        reports.append(briefing_report)

        site_dir = Path(args.site_dir)
        run_site_stage(engine, extraction_dir, briefing_dir, site_dir, brief_config)

    report.print_summary(console, reports)

    review_failures(engine, console, text_extraction_report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
