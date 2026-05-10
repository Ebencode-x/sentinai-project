"""SentinAI CLI — run scans and manage the agent from the terminal.

Usage examples:
    sentinai scan logs/app.log
    sentinai scan logs/app.log --tail 50
    sentinai version
"""

from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(
    name="sentinai",
    help="SentinAI — self-healing DevOps agent CLI.",
    add_completion=False,
)


@app.command()
def scan(
    log_file: Path = typer.Argument(
        ...,
        help="Path to the log file to scan for incidents.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    tail: int = typer.Option(
        100,
        "--tail",
        "-n",
        help="Number of lines to read from the end of the log file.",
        min=1,
        max=10_000,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed output.",
    ),
) -> None:
    """Scan a log file for incidents and print a summary."""
    typer.echo(f"[sentinai] Scanning: {log_file.resolve()}")

    try:
        lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        typer.echo(f"[sentinai] ERROR: Cannot read file — {exc}", err=True)
        raise typer.Exit(code=1) from exc

    window = lines[-tail:] if len(lines) > tail else lines
    typer.echo(f"[sentinai] Lines loaded: {len(window)} (of {len(lines)} total)")

    # Detect incidents using the same keyword logic as the watcher
    keywords = ["ERROR", "CRITICAL", "FATAL", "Exception", "Traceback"]
    incidents = [ln for ln in window if any(kw in ln for kw in keywords)]

    if not incidents:
        typer.echo("[sentinai] No incidents detected.")
        raise typer.Exit(code=0)

    typer.echo(f"[sentinai] Incidents found: {len(incidents)}")

    if verbose:
        for i, incident in enumerate(incidents, 1):
            typer.echo(f"  [{i}] {incident}")

    raise typer.Exit(code=0)


@app.command()
def version() -> None:
    """Print the SentinAI version."""
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as pkg_version

    try:
        v = pkg_version("sentinai")
    except PackageNotFoundError:
        v = "0.1.0-dev"
    typer.echo(f"sentinai {v}")


if __name__ == "__main__":
    app()
