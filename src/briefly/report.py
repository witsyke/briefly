from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.table import Table


@dataclass
class StageReport:
    name: str
    total: int = 0
    succeeded: int = 0
    retryable_failures: list[tuple[Path, str]] = field(default_factory=list)
    permanent_failures: list[tuple[Path, str]] = field(default_factory=list)
    crashed: list[tuple[Path, str]] = field(default_factory=list)

    def record(self, outcome) -> None:
        self.total += 1
        if outcome.succeeded:
            self.succeeded += 1
        elif outcome.retryable:
            self.retryable_failures.append((outcome.path, outcome.error or ""))
        else:
            self.permanent_failures.append((outcome.path, outcome.error or ""))

    def record_crash(self, path: Path, exc: BaseException) -> None:
        self.crashed.append((path, str(exc)))


def print_summary(console: Console, reports: list[StageReport]) -> None:
    table = Table(title="Briefly Summary")
    table.add_column("Stage")
    table.add_column("Total", justify="right")
    table.add_column("Succeeded", justify="right")
    table.add_column("Failed (retryable)", justify="right")
    table.add_column("Failed (permanent)", justify="right")
    table.add_column("Crashed", justify="right")

    for report in reports:
        table.add_row(
            report.name,
            str(report.total),
            str(report.succeeded),
            str(len(report.retryable_failures)),
            str(len(report.permanent_failures)),
            str(len(report.crashed)),
        )
    console.print(table)

    for report in reports:
        for path, error in report.retryable_failures:
            console.print(
                f"[yellow]{report.name}[/yellow] {path}: {error} (will retry next run)"
            )
        for path, error in report.permanent_failures:
            console.print(f"[red]{report.name}[/red] {path}: {error}")
        for path, error in report.crashed:
            console.print(
                f"[bold red]{report.name}[/bold red] {path}: {error} (unexpected -> investigate)"
            )
