"""Modern Rich-Click styled CLI entry point for dart-agent.

Supports dual modes:
1. Interactive Human CLI: Panels, color-coded tables, spinners, markdown stream.
2. AI-Agent / Script Mode (--json): Pure JSON lines (JSONL) on stdout, ideal for upstream AI agents.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

import rich_click as click
from openai import OpenAI
from rich.console import Console
from rich.prompt import Prompt

from . import __version__
from .agent import Agent
from .trust import (
    get_trusted_directories,
    is_directory_trusted,
    resolve_workspace_trust,
    trust_directory,
    untrust_directory,
)
from .ui import UI

# ── rich-click styling configuration ───────────────────────────────────────

click.rich_click.USE_RICH_MARKUP = True
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.STYLE_ERRORS_SUGGESTION = "bold red"
click.rich_click.ERRORS_SUGGESTION = "Try 'dart-agent --help' for options."
click.rich_click.HEADER_TEXT = f"[bold green]🎯 dart-agent[/bold green] [dim]v{__version__} — Production-Grade Terminal Agent[/dim]"
click.rich_click.FOOTER_TEXT = "[dim]Supports any OpenAI-compatible API: OpenAI, Groq, Gemini, Ollama, Together, OpenRouter.[/dim]"

click.rich_click.OPTION_GROUPS = {
    "dart-agent": [
        {
            "name": "Workspace & Permissions",
            "options": ["--dir", "--trust", "--no-trust"],
        },
        {
            "name": "Connection Options",
            "options": ["--base-url", "--api-key", "--model"],
        },
        {
            "name": "Execution & Behavior",
            "options": ["--prompt", "--no-stream", "--no-confirm"],
        },
        {
            "name": "Agentic & Machine Output",
            "options": ["--json", "--help", "--version"],
        },
    ]
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NON_CHAT_KEYWORDS = (
    "embedding", "embed", "tts", "image", "veo", "lyria",
    "audio", "robotics", "aqa", "banana", "transcribe",
)


def _resolve_credentials(
    base_url: Optional[str],
    api_key: Optional[str],
    model: Optional[str],
    ui: UI,
) -> tuple[str, str, Optional[str]]:
    """Resolve credentials from flag -> env -> interactive prompt."""
    b_url = base_url or os.getenv("BASE_URL") or os.getenv("OPENAI_BASE_URL")
    key = api_key or os.getenv("API_KEY") or os.getenv("OPENAI_API_KEY")
    mdl = model or os.getenv("MODEL")

    if not b_url:
        if ui.json_mode:
            raise ValueError("BASE_URL must be specified via --base-url or environment in --json mode")
        b_url = Prompt.ask("[bold]? Base URL[/]", console=ui.console, default="https://api.tokenrouter.com/v1")
    
    if not key:
        key = ui.ask_api_key()

    return b_url.rstrip("/"), key, mdl


def _fetch_and_select_model(client: OpenAI, ui: UI) -> str:
    """Fetch available models and prompt selection."""
    if ui.json_mode:
        try:
            models = [m.id for m in client.models.list().data]
            chat_models = [m for m in models if not any(nc in m.lower() for nc in _NON_CHAT_KEYWORDS)]
            return chat_models[0] if chat_models else (models[0] if models else "gpt-4o")
        except Exception:
            return "gpt-4o"

    with ui.console.status("[bold cyan]Fetching available models…[/bold cyan]", spinner="dots"):
        try:
            models_data = client.models.list()
            raw_models = sorted(m.id for m in models_data.data)
            models = [m for m in raw_models if not any(nc in m.lower() for nc in _NON_CHAT_KEYWORDS)]
            if not models:
                models = raw_models
        except Exception as exc:
            ui.error(f"Failed to fetch models from API: {exc}")
            models = []

    if not models:
        ui.warning("No models auto-detected. Please type your model name manually.")
        return Prompt.ask("[bold]? Model[/]", console=ui.console)

    ui.models_table(models)

    # Suggest smart default if available
    default_model = None
    for cand in ["gemini-3-flash-preview", "gemini-3.5-flash", "gpt-4o", "gpt-4o-mini"]:
        for m in models:
            if cand in m:
                default_model = m
                break
        if default_model:
            break
    if not default_model and models:
        default_model = models[0]

    while True:
        choice = Prompt.ask(
            f"[bold]? Select model[/] [dim](1-{len(models)} or name)[/]",
            default=default_model,
            console=ui.console,
        )
        try:
            n = int(choice) - 1
            if 0 <= n < len(models):
                return models[n]
            ui.error("Number out of range.")
            continue
        except ValueError:
            pass

        if choice in models:
            return choice

        hits = [m for m in models if choice.lower() in m.lower()]
        if len(hits) == 1:
            return hits[0]
        if hits:
            ui.warning(f"Ambiguous match: {', '.join(hits[:6])}")
            continue

        return choice


# ---------------------------------------------------------------------------
# REPL
# ---------------------------------------------------------------------------

_HELP_TEXT = """
[bold cyan]Interactive Commands:[/bold cyan]
  [bold]/trust[/bold]     View or manage workspace trust permission (/trust on, /trust off, /trust list)
  [bold]/clear[/bold]     Clear conversation history and reset context
  [bold]/model[/bold]     Switch active model without restarting
  [bold]/help[/bold]      Show this reference command menu
  [bold]/exit[/bold]      Exit the agent session

[bold cyan]Keyboard Shortcuts:[/bold cyan]
  [bold]Ctrl+C[/bold]     Interrupt the agent while running / clear input line
  [bold]Ctrl+D[/bold]     Close and exit dart-agent
"""

def _repl(agent: Agent, client: OpenAI, ui: UI) -> None:
    ui.ready()
    docked = ui.enable_docked_mode()
    try:
        while True:
            try:
                user_input = ui.prompt_input()
            except EOFError:
                ui.disable_docked_mode()
                ui.info("\n[dim]👋 Goodbye![/dim]")
                break
            except KeyboardInterrupt:
                # Ctrl+C at the prompt: cancel current line without exiting
                ui.info("\n[dim](Press Ctrl+D or type /exit to close dart-agent)[/dim]")
                continue

            # Check for Ctrl+D character (0x04) on Windows or Ctrl+Z (0x1a)
            if user_input in ("\x04", "\x1a") or user_input.endswith("\x04"):
                ui.disable_docked_mode()
                ui.info("\n[dim]👋 Goodbye![/dim]")
                break

            if not user_input:
                continue

            if user_input.startswith("/"):
                cmd = user_input.lower().split()[0]
                if cmd in ("/exit", "/quit", "/q"):
                    ui.disable_docked_mode()
                    ui.info("[dim]👋 Goodbye![/dim]")
                    break
                if cmd == "/clear":
                    agent.clear()
                    ui.success("Conversation context cleared.\n")
                    continue
                if cmd == "/model":
                    new_model = _fetch_and_select_model(client, ui)
                    if new_model:
                        agent.model = new_model
                        agent.clear()
                        ui.success(f"Switched model to [bold]{new_model}[/bold]\n")
                    continue
                if cmd == "/trust":
                    args = user_input.split()[1:]
                    cwd_path = Path.cwd().resolve()
                    if not args:
                        status = (
                            "[bold green]trusted (commands run automatically)[/bold green]"
                            if not agent.confirm_commands
                            else "[dim yellow]untrusted (commands require confirmation)[/dim yellow]"
                        )
                        ui.info(f"\n  Current workspace [bold]{cwd_path}[/bold] is {status}.")
                        ui.info("  Options: [bold]/trust on[/bold] (trust), [bold]/trust off[/bold] (untrust), [bold]/trust list[/bold]\n")
                    elif args[0].lower() in ("on", "yes", "true", "1"):
                        trust_directory(cwd_path)
                        agent.confirm_commands = False
                        ui.success(f"Workspace [bold]{cwd_path}[/bold] is now trusted. Tool commands will run automatically.\n")
                    elif args[0].lower() in ("off", "no", "false", "0"):
                        untrust_directory(cwd_path)
                        agent.confirm_commands = True
                        ui.info(f"  Workspace [bold]{cwd_path}[/bold] is untrusted. Commands will require confirmation.\n")
                    elif args[0].lower() == "list":
                        trusted_list = get_trusted_directories()
                        if trusted_list:
                            ui.info("\n  [bold cyan]Trusted Directories:[/bold cyan]")
                            for d in trusted_list:
                                ui.info(f"    • {d}")
                            ui.info("")
                        else:
                            ui.info("\n  [dim]No trusted directories configured yet.[/dim]\n")
                    continue
                if cmd == "/help":
                    ui.info(_HELP_TEXT)
                    continue
                ui.warning(f"Unknown command '{cmd}'. Try /help")
                continue

            if docked:
                ui.user_turn(user_input)

            try:
                agent.run(user_input)
                ui.console.print()
            except KeyboardInterrupt:
                ui.warning("\n⏹ Agent interrupted by user.\n")
                agent.abort_turn()
            except Exception as exc:
                ui.error(f"Error during agent loop: {exc}\n")
    finally:
        ui.disable_docked_mode()


# ---------------------------------------------------------------------------
# Click Command Line
# ---------------------------------------------------------------------------

@click.command(context_settings=dict(help_option_names=["-h", "--help"]))
@click.version_option(__version__, "-v", "--version", prog_name="dart-agent")
@click.option("--base-url", "-b", envvar="BASE_URL", help="OpenAI-compatible base URL endpoint.")
@click.option("--api-key", "-k", envvar="API_KEY", help="API authentication key.")
@click.option("--model", "-m", envvar="MODEL", help="Specific model ID (skips interactive selection).")
@click.option(
    "--dir", "-d", "directory",
    type=click.Path(file_okay=False, dir_okay=True, path_type=str),
    help="Target working directory to open in (defaults to current directory).",
)
@click.option(
    "--trust", "-t", is_flag=True, default=False,
    help="Grant permission to trust this working directory (auto-approves tools and commands).",
)
@click.option(
    "--no-trust", is_flag=True, default=False,
    help="Enforce manual confirmation for all commands in this directory.",
)
@click.option("--prompt", "-p", help="Single prompt execution mode (runs once and exits).")
@click.option("--no-stream", is_flag=True, default=False, help="Disable streaming response tokens.")
@click.option("--no-confirm", is_flag=True, default=False, help="Auto-approve all tool and shell commands.")
@click.option(
    "--json", "json_mode", is_flag=True, default=False,
    help="Emit pure unformatted JSON lines to stdout for upstream AI agents or scripts."
)
def main(
    base_url: Optional[str],
    api_key: Optional[str],
    model: Optional[str],
    directory: Optional[str],
    trust: bool,
    no_trust: bool,
    prompt: Optional[str],
    no_stream: bool,
    no_confirm: bool,
    json_mode: bool,
) -> None:
    """[bold]dart-agent[/bold] gives terminal agents file I/O, search, and shell execution capabilities."""
    console = Console(stderr=json_mode)  # In JSON mode, write human logs/errors to stderr, stdout for pure json
    ui = UI(console, json_mode=json_mode)

    # 1. Switch working directory if requested
    target_dir = Path(directory).resolve() if directory else Path.cwd().resolve()
    if directory:
        if not target_dir.exists():
            ui.error(f"Specified working directory does not exist: {target_dir}")
            sys.exit(1)
        os.chdir(target_dir)

    ui.banner(__version__)

    # 2. Resolve workspace trust & permissions
    is_trusted = resolve_workspace_trust(
        target_dir,
        explicit_trust=trust,
        explicit_no_trust=no_trust,
        ui=ui,
    )

    try:
        b_url, key, selected_model = _resolve_credentials(base_url, api_key, model, ui)
    except Exception as exc:
        ui.error(str(exc))
        sys.exit(1)

    client = OpenAI(base_url=b_url, api_key=key, timeout=30.0)

    if not selected_model:
        selected_model = _fetch_and_select_model(client, ui)

    ui.config_summary(b_url, selected_model, workspace=target_dir, trusted=is_trusted)
    ui.tool_table()

    agent = Agent(
        client=client,
        model=selected_model,
        ui=ui,
        stream=not no_stream,
    )
    if no_confirm or json_mode or is_trusted:
        agent.confirm_commands = False

    # Single-shot execution mode
    if prompt:
        agent.run(prompt)
        sys.exit(0)

    # Interactive REPL mode
    _repl(agent, client, ui)


if __name__ == "__main__":
    main()
