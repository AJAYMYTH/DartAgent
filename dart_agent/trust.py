"""Workspace trust management for dart-agent.

Allows users to grant permission / trust to their project directories.
In trusted folders, tools and shell commands are executed without repeated
manual confirmation prompts.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .ui import UI


def _trust_file() -> Path:
    """Return path to global trusted folders configuration file."""
    p = Path.home() / ".dart-agent" / "trusted.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def get_trusted_directories() -> list[str]:
    """Return list of all trusted directory paths."""
    tf = _trust_file()
    if not tf.exists():
        return []
    try:
        data = json.loads(tf.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [str(Path(p).resolve()) for p in data]
    except Exception:
        pass
    return []


def is_directory_trusted(target_dir: str | Path | None = None) -> bool:
    """Check if the given directory (or CWD) is trusted."""
    target = Path(target_dir or Path.cwd()).resolve()
    target_posix = target.as_posix().lower()

    for trusted_path in get_trusted_directories():
        trusted_posix = Path(trusted_path).resolve().as_posix().lower()
        if target_posix == trusted_posix or target_posix.startswith(trusted_posix + "/"):
            return True
    return False


def trust_directory(target_dir: str | Path | None = None) -> str:
    """Add directory to trusted list."""
    target = Path(target_dir or Path.cwd()).resolve()
    target_str = str(target)
    target_posix = target.as_posix().lower()

    current = get_trusted_directories()
    # Filter out duplicate canonical representations
    filtered = [p for p in current if Path(p).resolve().as_posix().lower() != target_posix]
    filtered.append(target_str)

    tf = _trust_file()
    tf.write_text(json.dumps(filtered, indent=2), encoding="utf-8")
    return target_str


def untrust_directory(target_dir: str | Path | None = None) -> bool:
    """Remove directory from trusted list."""
    target = Path(target_dir or Path.cwd()).resolve()
    target_posix = target.as_posix().lower()

    current = get_trusted_directories()
    filtered = [p for p in current if Path(p).resolve().as_posix().lower() != target_posix]

    if len(filtered) == len(current):
        return False

    tf = _trust_file()
    tf.write_text(json.dumps(filtered, indent=2), encoding="utf-8")
    return True


def resolve_workspace_trust(
    workspace_dir: Path,
    *,
    explicit_trust: bool = False,
    explicit_no_trust: bool = False,
    ui: UI | None = None,
) -> bool:
    """Determine if *workspace_dir* is trusted, with interactive prompt if first time."""
    if explicit_trust:
        trust_directory(workspace_dir)
        return True

    if explicit_no_trust:
        return False

    if is_directory_trusted(workspace_dir):
        return True

    # If interactive human mode, prompt once to trust the workspace
    if ui and not ui.json_mode and hasattr(os, "isatty") and hasattr(__import__("sys").stdin, "isatty") and __import__("sys").stdin.isatty():
        ui.console.print(
            f"  [bold yellow]? Trust workspace:[/] [bold cyan]{workspace_dir}[/] [dim](grant permission to run tools without confirmation)[/]"
        )
        try:
            ans = input("  Grant permission to trust this folder? [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = "n"

        if ans in ("", "y", "yes"):
            trust_directory(workspace_dir)
            ui.success(f"Granted trust to [bold]{workspace_dir}[/bold]\n")
            return True
        else:
            ui.info("  [dim]Running in untrusted mode — shell commands will ask for approval.[/dim]\n")
            return False

    return False
