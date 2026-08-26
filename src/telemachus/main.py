"""CLI entry point for Telemachus.

Provides the `telemachus` command with subcommands for starting,
checking status, chatting, and interacting with the system.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from telemachus import __version__
from telemachus.bootstrap import BootstrapProtocol, BootstrapResult
from telemachus.config import ConfigError, TelemachusConfig, load_config_from_path
from telemachus.logging_config import get_logger, setup_logging
from telemachus.runtime import PreviousTermination, RecoveryBriefing
from telemachus.wiring import build_runtime

app = typer.Typer(
    name="telemachus",
    help="Telemachus — A local-first autonomous AI companion.",
    add_completion=False,
)

console = Console()
logger = get_logger("main")


def _print_banner() -> None:
    """Print the Telemachus startup banner."""
    banner = Panel.fit(
        "[bold cyan]Telemachus[/bold cyan] — A local-first autonomous AI companion\n"
        f"[dim]Version {__version__}[/dim]",
        border_style="cyan",
    )
    console.print(banner)


@app.command()
def start(
    config_path: Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-c",
            help="Path to configuration file",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose (DEBUG) logging"),
    ] = False,
) -> None:
    """Start the Telemachus system.

    Loads configuration, initializes logging, and begins the bootstrap sequence.
    """
    _print_banner()

    try:
        config = load_config_from_path(config_path)
    except (FileNotFoundError, ConfigError) as exc:
        console.print(f"[bold red]ERROR:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc

    # Override log level if verbose
    if verbose:
        config = config.with_log_level("DEBUG")

    # Initialize logging
    log = setup_logging(config)
    log.info("Telemachus starting", extra={"extra": {"version": __version__}})

    # Create required directories
    config.paths.data_dir.mkdir(parents=True, exist_ok=True)
    config.paths.log_dir.mkdir(parents=True, exist_ok=True)

    # Display startup information
    _display_startup_info(config)

    # Delegate lifecycle ownership to the Runtime. It installs signal
    # handlers, opens runtime.db, determines installation/recovery state,
    # runs the Core's five-phase bootstrap protocol at the correct point,
    # and reaches RUNNING (or FAILED).
    console.print("\n[bold]Starting Runtime...[/bold]")
    runtime = build_runtime(config)
    result = runtime.start()

    # Display bootstrap results
    _display_bootstrap_result(result)
    _display_recovery_briefing(runtime.recovery_briefing)

    if not result.success:
        console.print(
            "\n[bold red]Bootstrap failed.[/bold red] "
            "Check logs for details."
        )
        runtime.shutdown()
        raise typer.Exit(code=1)

    # Display first awakening questions if this is a first awakening
    if result.first_awakening and runtime.bootstrap_protocol is not None:
        _display_first_awakening(runtime.bootstrap_protocol)

    log.info(
        "Telemachus started successfully",
        extra={"extra": {"lifecycle_state": runtime.state.value}},
    )
    console.print("\n[green]✓[/green] Telemachus is running.")
    console.print("[dim]Press Ctrl+C to shut down.[/dim]")

    try:
        runtime.wait_for_shutdown_request()
    finally:
        log.info("Shutdown signal received")
        console.print("\n[yellow]Shutting down...[/yellow]")
        runtime.shutdown()
        log.info("Telemachus shutdown complete")
        console.print("[green]Goodbye.[/green]")


@app.command()
def version() -> None:
    """Display the Telemachus version."""
    console.print(f"Telemachus version [bold]{__version__}[/bold]")


@app.command()
def config_check(
    config_path: Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-c",
            help="Path to configuration file",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ] = None,
) -> None:
    """Validate the configuration file without starting the system."""
    try:
        config = load_config_from_path(config_path)
    except (FileNotFoundError, ConfigError) as exc:
        console.print(f"[red]FAIL:[/red] {exc}")
        sys.exit(1)

    console.print("[green]✓[/green] Configuration is valid")

    # Display loaded configuration
    table = Table(title="Configuration Summary")
    table.add_column("Section", style="cyan")
    table.add_column("Key", style="dim")
    table.add_column("Value")

    table.add_row("identity", "name", config.identity.name)
    table.add_row("identity", "creator", config.identity.creator)
    table.add_row("paths", "data_dir", str(config.paths.data_dir))
    table.add_row("paths", "codex_dir", str(config.paths.codex_dir))
    table.add_row("paths", "log_dir", str(config.paths.log_dir))
    table.add_row("database", "path", config.database.path)
    table.add_row("logging", "level", config.logging.level)
    table.add_row("bootstrap", "first_awakening", str(config.bootstrap.first_awakening))
    table.add_row(
        "governance", "default_autonomy_level", str(config.governance.default_autonomy_level)
    )
    table.add_row("communication", "default_mode", config.communication.default_mode)

    console.print(table)


@app.command()
def chat(
    config_path: Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-c",
            help="Path to configuration file",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose (DEBUG) logging"),
    ] = False,
) -> None:
    """Start an interactive chat session with Telemachus.

    Opens a REPL-style chat interface with adaptive communication modes.
    Use /help for available commands, /exit to quit.
    """
    from telemachus.interaction.cli_chat import start_chat

    start_chat(config_path=config_path, verbose=verbose)


def _display_startup_info(config: TelemachusConfig) -> None:
    """Display startup information to the console."""
    console.print(f"  Data directory: [dim]{config.paths.data_dir}[/dim]")
    console.print(f"  Codex directory: [dim]{config.paths.codex_dir}[/dim]")
    console.print(f"  Log level: [dim]{config.logging.level}[/dim]")
    console.print(f"  Database: [dim]{config.paths.data_dir / config.database.path}[/dim]")
    console.print()


def _display_bootstrap_result(result: BootstrapResult) -> None:
    """Display the bootstrap protocol results.

    Args:
        result: The BootstrapResult from the bootstrap protocol.
    """
    from telemachus.bootstrap import PhaseStatus

    table = Table(title="Bootstrap Protocol Results")
    table.add_column("Phase", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Message")

    for phase_result in result.phases:
        status_style = {
            PhaseStatus.COMPLETED: "[green]✓[/green]",
            PhaseStatus.SKIPPED: "[yellow]○[/yellow]",
            PhaseStatus.FAILED: "[red]✗[/red]",
            PhaseStatus.IN_PROGRESS: "[blue]…[/blue]",
            PhaseStatus.PENDING: "[dim]-[/dim]",
        }.get(phase_result.status, "[dim]?[/dim]")

        table.add_row(
            phase_result.phase.value,
            status_style,
            phase_result.message,
        )

    console.print(table)

    if result.errors:
        console.print("\n[bold red]Errors:[/bold red]")
        for error in result.errors:
            console.print(f"  [red]•[/red] {error}")


def _display_recovery_briefing(briefing: RecoveryBriefing | None) -> None:
    """Display what Runtime Recovery/Reconciliation found, plainly.

    Delivered here, in the startup summary for `telemachus start`, per
    docs/lifecycle.md: the operator ran this command deliberately, so
    this is not an unwanted interruption. Reports facts only — no
    interpretation, which remains Core work.

    Args:
        briefing: The Runtime's RecoveryBriefing, or None if unavailable.
    """
    if briefing is None:
        return

    if briefing.is_new_installation:
        console.print("[dim]New Runtime installation — no prior session to recover.[/dim]")
        return

    if briefing.previous_termination == PreviousTermination.UNCLEAN:
        last_state = (
            briefing.previous_session.last_state
            if briefing.previous_session is not None
            else "unknown"
        )
        console.print(
            f"[yellow]Previous session did not shut down cleanly[/yellow] "
            f"[dim](last recorded state: {last_state})[/dim]"
        )
    elif briefing.previous_termination == PreviousTermination.CLEAN:
        console.print("[dim]Previous session ended cleanly.[/dim]")

    if briefing.offline_seconds is not None:
        console.print(f"[dim]Offline for approximately {briefing.offline_seconds:.0f}s.[/dim]")


def _display_first_awakening(bootstrap: BootstrapProtocol) -> None:
    """Display the first awakening questions.

    Args:
        bootstrap: The BootstrapProtocol instance.
    """
    questions = bootstrap.get_first_awakening_questions()

    console.print(
        "\n[bold yellow]⚠ First Awakening Detected[/bold yellow]"
    )
    console.print(
        "[dim]Telemachus has not yet been initialized. "
        "Before proceeding, please consider:[/dim]\n"
    )

    for i, question in enumerate(questions, 1):
        console.print(f"  [cyan]{i}.[/cyan] {question}")

    console.print(
        "\n[dim]Answer these questions in the interactive chat session "
        "or via the configuration file.[/dim]\n"
    )


def main() -> None:
    """Entry point for the telemachus CLI."""
    app()


if __name__ == "__main__":
    main()
