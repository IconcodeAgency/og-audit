from __future__ import annotations

import asyncio
import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .audit import Auditor
from .models import AuditReport, Severity
from .network import FetchError, SafeFetcher
from .reporting import render_html, render_json

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Audit SEO, Open Graph, robots, JSON-LD and sitemap metadata.",
)
console = Console()
error_console = Console(stderr=True)


class OutputFormat(StrEnum):
    CONSOLE = "console"
    JSON = "json"
    HTML = "html"


class FailOn(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    NEVER = "never"


def version_callback(value: bool) -> None:
    if value:
        console.print(f"og-audit {__version__}")
        raise typer.Exit()


def _render_console(report: AuditReport) -> None:
    counts = report.counts
    console.print(
        f"\n[bold]OG Audit[/bold]  {report.final_url}\n"
        f"Score [bold]{report.score}/100[/bold]  "
        f"[red]{counts['error']} errors[/red]  "
        f"[yellow]{counts['warning']} warnings[/yellow]  "
        f"[cyan]{counts['info']} info[/cyan]\n"
    )
    table = Table(show_header=True, header_style="bold", expand=True)
    table.add_column("Level", width=9)
    table.add_column("Category", width=16)
    table.add_column("Finding", ratio=2)
    table.add_column("Details", ratio=3)
    styles = {Severity.ERROR: "red", Severity.WARNING: "yellow", Severity.INFO: "cyan"}
    for item in report.findings:
        details = item.message
        if item.value is not None:
            details += f"\n[dim]{item.value}[/dim]"
        table.add_row(
            f"[{styles[item.severity]}]{item.severity.value.upper()}[/]",
            item.category,
            item.title,
            details,
        )
    console.print(table)


async def _audit(url: str, timeout: float, allow_private: bool) -> AuditReport:
    fetcher = SafeFetcher(timeout=timeout, allow_private=allow_private)
    try:
        return await Auditor(fetcher).run(url)
    finally:
        await fetcher.close()


@app.command()
def main(
    url: Annotated[str, typer.Argument(help="Public HTTP(S) page to audit.")],
    output_format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format."),
    ] = OutputFormat.CONSOLE,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Write the report to a file."),
    ] = None,
    fail_on: Annotated[
        FailOn,
        typer.Option(help="Return exit code 1 for this severity or higher."),
    ] = FailOn.ERROR,
    timeout: Annotated[
        float,
        typer.Option(min=1.0, max=60.0, help="Per-request timeout in seconds."),
    ] = 10.0,
    allow_private: Annotated[
        bool,
        typer.Option(help="Allow localhost/private targets. Use only for trusted URLs."),
    ] = False,
    version: Annotated[
        bool | None,
        typer.Option("--version", callback=version_callback, is_eager=True),
    ] = None,
) -> None:
    del version
    try:
        report = asyncio.run(_audit(url, timeout, allow_private))
    except (FetchError, ValueError, json.JSONDecodeError) as exc:
        error_console.print(f"[red]Audit failed:[/red] {exc}")
        raise typer.Exit(2) from exc

    if output_format == OutputFormat.CONSOLE:
        if output:
            output.write_text(render_json(report), encoding="utf-8")
            console.print(f"Report written to {output}")
        else:
            _render_console(report)
    else:
        rendered = (
            render_json(report) if output_format == OutputFormat.JSON else render_html(report)
        )
        if output:
            output.write_text(rendered, encoding="utf-8")
            error_console.print(f"Report written to {output}")
        else:
            typer.echo(rendered)

    counts = report.counts
    failed = (
        fail_on == FailOn.ERROR
        and counts["error"] > 0
        or fail_on == FailOn.WARNING
        and (counts["error"] > 0 or counts["warning"] > 0)
    )
    if failed:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
