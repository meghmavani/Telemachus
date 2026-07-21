"""CLI Chat Interface — interactive chat loop for Telemachus.

Provides the `telemachus chat` command with an interactive REPL-style
interface. Integrates the cognitive pipeline with the communication
engine for mode-aware, emotionally adaptive responses.
"""

from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

from telemachus.config import TelemachusConfig, load_config_from_path
from telemachus.core.types import CommunicationMode, PipelineContext
from telemachus.interaction.communication import CommunicationEngine
from telemachus.logging_config import get_logger, setup_logging
from telemachus.pipeline import CognitivePipeline

logger = get_logger("cli_chat")


class ChatSession:
    """Interactive CLI chat session.

    Manages the chat loop, session state, and integration between the
    cognitive pipeline and communication engine.

    Usage:
        session = ChatSession(config)
        session.run()
    """

    def __init__(
        self,
        config: TelemachusConfig,
        *,
        pipeline: CognitivePipeline | None = None,
        communication: CommunicationEngine | None = None,
    ) -> None:
        """Initialize a chat session.

        Args:
            config: Loaded Telemachus configuration.
            pipeline: Optional pre-configured CognitivePipeline.
            communication: Optional pre-configured CommunicationEngine.
        """
        self._config = config
        self._console = Console()
        self._running = False
        self._session_id: str | None = None

        # Initialize components
        self._pipeline = pipeline or CognitivePipeline()
        self._communication = communication or CommunicationEngine()

        # Session state
        self._message_count = 0
        self._explicit_mode: CommunicationMode | None = None

        logger.info("Chat session initialized")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Run the interactive chat loop.

        Displays welcome banner, then enters the REPL loop. Handles
        graceful shutdown on Ctrl+C or /exit command.
        """
        self._running = True
        self._print_welcome()

        try:
            while self._running:
                try:
                    user_input = self._read_input()
                    if user_input is None:
                        continue  # Empty input, prompt again

                    if self._handle_command(user_input):
                        continue  # Was a command, already handled

                    response = self._process_input(user_input)
                    self._display_response(response)

                except KeyboardInterrupt:
                    self._console.print("\n[yellow]Use /exit or /quit to leave.[/yellow]")
                    continue

        except Exception as exc:
            logger.error("Chat session error", exc_info=True)
            self._console.print(f"\n[red]An unexpected error occurred: {exc}[/red]")
        finally:
            self._shutdown()

    def process_single(self, user_input: str) -> str:
        """Process a single input and return the formatted response.

        Useful for programmatic use or testing.

        Args:
            user_input: The user's input text.

        Returns:
            The formatted response string.
        """
        return self._process_input(user_input)

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------

    def _read_input(self) -> str | None:
        """Read a line of input from the user.

        Returns:
            The input string, or None if empty.
        """
        try:
            prompt_text = self._build_prompt()
            user_input = Prompt.ask(prompt_text, console=self._console)
            stripped = user_input.strip()
            if not stripped:
                return None
            return stripped
        except EOFError:
            self._running = False
            return None

    def _build_prompt(self) -> Text:
        """Build the prompt text with session context."""
        mode_indicator = ""
        if self._explicit_mode:
            mode_indicator = f" [{self._explicit_mode.value}]"

        return Text.from_markup(f"[bold cyan]You[/bold cyan]{mode_indicator} › ")

    def _handle_command(self, user_input: str) -> bool:
        """Handle slash commands. Returns True if input was a command.

        Supported commands:
            /exit, /quit — Exit the chat session
            /help — Show help
            /mode <mode> — Set communication mode (direct/explained/collaborative)
            /clear — Clear the screen
            /stats — Show session statistics
        """
        text = user_input.strip().lower()

        if text in ("/exit", "/quit"):
            self._console.print("[yellow]Goodbye.[/yellow]")
            self._running = False
            return True

        if text == "/help":
            self._print_help()
            return True

        if text.startswith("/mode "):
            mode_name = text[6:].strip()
            try:
                self._explicit_mode = CommunicationMode(mode_name)
                self._console.print(
                    f"[green]Communication mode set to: {self._explicit_mode.value}[/green]"
                )
            except ValueError:
                self._console.print(
                    f"[red]Invalid mode: {mode_name}. "
                    f"Use: direct, explained, collaborative[/red]"
                )
            return True

        if text == "/mode":
            # Reset to auto-detect
            self._explicit_mode = None
            self._console.print("[green]Communication mode reset to auto-detect.[/green]")
            return True

        if text == "/clear":
            self._console.clear()
            return True

        if text == "/stats":
            self._print_stats()
            return True

        return False

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    def _process_input(self, user_input: str) -> str:
        """Process user input through the pipeline and format the response.

        Args:
            user_input: The user's input text.

        Returns:
            The formatted response string.
        """
        self._message_count += 1

        # Build pipeline context
        ctx = PipelineContext(
            user_input=user_input,
            session_id=self._session_id or "cli-session",
            communication_mode=self._explicit_mode or CommunicationMode.COLLABORATIVE,
            metadata={
                "message_number": self._message_count,
                "source": "cli_chat",
            },
        )

        # Run through pipeline
        logger.debug(
            "Processing input through pipeline",
            extra={"extra": {"input_length": len(user_input)}},
        )
        result = self._pipeline.process(ctx)

        # Format response through communication engine
        emotional_state = self._communication.detect_emotional_state(user_input)
        formatted = self._communication.format_response(
            result,
            user_input=user_input,
            mode=self._explicit_mode,
            emotional_state=emotional_state,
        )

        return formatted

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def _display_response(self, response: str) -> None:
        """Display the formatted response to the user."""
        # Determine panel style based on content
        style = "green"
        if "can't proceed" in response.lower() or "blocked" in response.lower():
            style = "yellow"
        elif "error" in response.lower() or "mistake" in response.lower():
            style = "red"

        panel = Panel.fit(
            response,
            title="Telemachus",
            border_style=style,
            padding=(1, 2),
        )
        self._console.print()
        self._console.print(panel)
        self._console.print()

    def _print_welcome(self) -> None:
        """Print the chat welcome banner."""
        self._console.clear()
        self._console.print()
        self._console.print(
            Panel.fit(
                "[bold cyan]Telemachus Chat[/bold cyan]\n\n"
                "Interactive chat with adaptive communication modes.\n\n"
                "[dim]Commands:[/dim]\n"
                "  /mode direct|explained|collaborative — Set communication mode\n"
                "  /mode — Reset to auto-detect\n"
                "  /clear — Clear screen\n"
                "  /stats — Session statistics\n"
                "  /help — Show help\n"
                "  /exit, /quit — Exit chat\n\n"
                "[dim]Type your message and press Enter to begin.[/dim]",
                border_style="cyan",
                padding=(1, 2),
            )
        )
        self._console.print()

    def _print_help(self) -> None:
        """Print the help text."""
        help_text = """
[bold]Telemachus Chat Help[/bold]

[cyan]Communication Modes:[/cyan]
  • [bold]direct[/bold] — Brief, factual responses for simple questions
  • [bold]explained[/bold] — Detailed responses with reasoning
  • [bold]collaborative[/bold] — Discussion-oriented for complex/emotional topics

[cyan]Commands:[/cyan]
  • /mode <mode> — Set communication mode
  • /mode — Reset to auto-detect
  • /clear — Clear the screen
  • /stats — Show session statistics
  • /exit, /quit — Exit chat

[cyan]Tips:[/cyan]
  • Telemachus adapts its communication style based on context
  • High-risk or emotional topics automatically use collaborative mode
  • Governance transparency is shown in explained and collaborative modes
"""
        self._console.print(Panel.fit(help_text.strip(), border_style="blue"))
        self._console.print()

    def _print_stats(self) -> None:
        """Print session statistics."""
        stats_text = f"""
[bold]Session Statistics[/bold]

Messages processed: {self._message_count}
Communication mode: {self._explicit_mode.value if self._explicit_mode else 'auto-detect'}
"""
        self._console.print(Panel.fit(stats_text.strip(), border_style="dim"))
        self._console.print()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _shutdown(self) -> None:
        """Clean shutdown of the chat session."""
        logger.info(
            "Chat session ending",
            extra={"extra": {"messages_processed": self._message_count}},
        )
        self._console.print()


# ---------------------------------------------------------------------------
# CLI entry point (used by main.py)
# ---------------------------------------------------------------------------


def start_chat(
    config_path: Path | None = None,
    verbose: bool = False,
) -> None:
    """Start an interactive chat session.

    Args:
        config_path: Optional path to configuration file.
        verbose: Enable verbose (DEBUG) logging.
    """
    console = Console()

    # Load configuration
    try:
        config = load_config_from_path(config_path)
    except Exception as exc:
        console.print(f"[bold red]ERROR:[/bold red] {exc}")
        sys.exit(1)

    # Override log level if verbose
    if verbose:
        config = config.__class__(
            identity=config.identity,
            paths=config.paths,
            database=config.database,
            logging=config.logging.__class__(
                level="DEBUG",
                format=config.logging.format,
                max_bytes=config.logging.max_bytes,
                backup_count=config.logging.backup_count,
            ),
            bootstrap=config.bootstrap,
            pipeline=config.pipeline,
            governance=config.governance,
            communication=config.communication,
            memory=config.memory,
        )

    # Initialize logging
    log = setup_logging(config)
    log.info("Starting chat session", extra={"extra": {"version": "0.1.0"}})

    # Create required directories
    config.paths.data_dir.mkdir(parents=True, exist_ok=True)
    config.paths.log_dir.mkdir(parents=True, exist_ok=True)

    # Initialize pipeline with memory store if configured
    db_path = config.paths.data_dir / config.database.path
    pipeline = CognitivePipeline(db_path=str(db_path))

    # Create and run chat session
    session = ChatSession(config, pipeline=pipeline)
    session.run()

    log.info("Chat session ended")
