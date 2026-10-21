"""Tool definitions and implementations for the agent.

Each tool is a pure function that takes typed arguments and returns a string result.
The TOOL_DEFINITIONS list provides OpenAI function-calling schemas.
The TOOL_REGISTRY maps tool names to their implementations.
"""

from __future__ import annotations

import fnmatch
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable

# ---------------------------------------------------------------------------
# OpenAI function-calling schemas
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read the contents of a file at the given path. "
                "Optionally specify a line range to read a subset."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative or absolute path to the file.",
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "First line to read (1-indexed, inclusive). Optional.",
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Last line to read (1-indexed, inclusive). Optional.",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Write content to a file. Creates the file and any parent directories "
                "if they don't exist. Overwrites existing content."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative or absolute path to the file.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Full content to write.",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List the contents of a directory with file types and sizes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path. Defaults to '.'.",
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "List recursively. Default false.",
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Max recursion depth. Default 3.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": (
                "Execute a shell command and return stdout/stderr. "
                "Use for running scripts, git, build tools, package managers, etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to run.",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds. Default 30.",
                    },
                    "working_directory": {
                        "type": "string",
                        "description": "Working directory. Defaults to CWD.",
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": (
                "Search for a text pattern across files in a directory (like grep). "
                "Returns matching lines with file paths and line numbers."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Text pattern to search for.",
                    },
                    "path": {
                        "type": "string",
                        "description": "Root directory to search. Defaults to '.'.",
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "Glob to filter files, e.g. '*.py'. Optional.",
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "description": "Case-sensitive search. Default true.",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MAX_READ_CHARS = 100_000
_MAX_OUTPUT_CHARS = 50_000
_MAX_SEARCH_MATCHES = 200
_MAX_SEARCH_FILES = 5_000
_MAX_LIST_ENTRIES = 500

_BINARY_EXTENSIONS: frozenset[str] = frozenset({
    ".pyc", ".pyo", ".so", ".dll", ".exe", ".bin", ".o", ".a",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".ico", ".svg", ".webp",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".mp3", ".mp4", ".avi", ".mov", ".mkv", ".wav", ".flac",
    ".db", ".sqlite", ".sqlite3",
    ".class", ".jar", ".war",
})

_SKIP_DIRS: frozenset[str] = frozenset({
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    ".tox", ".mypy_cache", ".pytest_cache", "dist", "build",
    ".next", ".nuxt", ".svelte-kit",
})


def _fmt_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def read_file(
    path: str,
    start_line: int | None = None,
    end_line: int | None = None,
) -> str:
    """Read file contents with optional line range."""
    p = Path(path).resolve()
    if not p.exists():
        return f"Error: file not found — {path}"
    if not p.is_file():
        return f"Error: not a file — {path}"

    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except PermissionError:
        return f"Error: permission denied — {path}"
    except Exception as exc:
        return f"Error reading file: {exc}"

    lines = text.splitlines(keepends=True)
    total = len(lines)

    if start_line is not None or end_line is not None:
        s = max(1, start_line or 1)
        e = min(total, end_line or total)
        lines = lines[s - 1 : e]
        header = f"[lines {s}–{e} of {total}]\n"
    else:
        header = f"[{total} lines]\n"

    body = "".join(lines)
    if len(body) > _MAX_READ_CHARS:
        body = body[:_MAX_READ_CHARS] + f"\n… truncated ({len(body) - _MAX_READ_CHARS} chars omitted)"

    return header + body


def write_file(path: str, content: str) -> str:
    """Write *content* to *path*, creating parent dirs as needed."""
    p = Path(path).resolve()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        size = len(content.encode("utf-8"))
        return f"Wrote {size} bytes to {path}"
    except PermissionError:
        return f"Error: permission denied — {path}"
    except Exception as exc:
        return f"Error writing file: {exc}"


def list_directory(
    path: str = ".",
    recursive: bool = False,
    max_depth: int = 3,
) -> str:
    """List directory contents."""
    root = Path(path).resolve()
    if not root.exists():
        return f"Error: directory not found — {path}"
    if not root.is_dir():
        return f"Error: not a directory — {path}"

    lines: list[str] = []

    def _walk(dir_path: Path, depth: int) -> None:
        if recursive and depth > max_depth:
            return
        try:
            entries = sorted(
                dir_path.iterdir(),
                key=lambda e: (not e.is_dir(), e.name.lower()),
            )
        except PermissionError:
            lines.append(f"{'  ' * depth}⛔ [permission denied]")
            return

        for entry in entries:
            if entry.name in _SKIP_DIRS:
                continue

            indent = "  " * depth
            if entry.is_dir():
                lines.append(f"{indent}📁 {entry.name}/")
                if recursive:
                    _walk(entry, depth + 1)
            else:
                try:
                    sz = _fmt_size(entry.stat().st_size)
                except OSError:
                    sz = "?"
                lines.append(f"{indent}📄 {entry.name}  ({sz})")

            if len(lines) >= _MAX_LIST_ENTRIES:
                lines.append(f"{indent}… truncated at {_MAX_LIST_ENTRIES} entries")
                return

    _walk(root, 0)
    if not lines:
        return f"Directory is empty: {path}"
    return f"Contents of {root}:\n" + "\n".join(lines)


def execute_command(
    command: str,
    timeout: int = 30,
    working_directory: str | None = None,
) -> str:
    """Run a shell command and return its output."""
    cwd = working_directory or os.getcwd()
    try:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {timeout}s"
    except Exception as exc:
        return f"Error executing command: {exc}"

    parts: list[str] = []
    if proc.stdout.strip():
        parts.append(proc.stdout.strip())
    if proc.stderr.strip():
        parts.append(f"[stderr]\n{proc.stderr.strip()}")

    output = "\n".join(parts) if parts else "(no output)"
    if len(output) > _MAX_OUTPUT_CHARS:
        output = output[:_MAX_OUTPUT_CHARS] + "\n… truncated"

    return f"[exit {proc.returncode}]\n{output}"


def search_files(
    pattern: str,
    path: str = ".",
    file_pattern: str | None = None,
    case_sensitive: bool = True,
) -> str:
    """Grep-like search across files."""
    root = Path(path).resolve()
    if not root.exists():
        return f"Error: path not found — {path}"

    needle = pattern if case_sensitive else pattern.lower()
    matches: list[str] = []
    files_checked = 0

    for fp in root.rglob("*"):
        if not fp.is_file():
            continue
        if fp.suffix.lower() in _BINARY_EXTENSIONS:
            continue
        if any(part in _SKIP_DIRS for part in fp.parts):
            continue
        if file_pattern and not fnmatch.fnmatch(fp.name, file_pattern):
            continue

        files_checked += 1
        if files_checked > _MAX_SEARCH_FILES:
            matches.append(f"… stopped after scanning {_MAX_SEARCH_FILES} files")
            break

        try:
            content = fp.read_text(encoding="utf-8", errors="ignore")
        except (PermissionError, OSError):
            continue

        for lineno, line in enumerate(content.splitlines(), 1):
            hay = line if case_sensitive else line.lower()
            if needle in hay:
                rel = fp.relative_to(root)
                matches.append(f"{rel}:{lineno}: {line.strip()}")
                if len(matches) >= _MAX_SEARCH_MATCHES:
                    matches.append("… truncated (too many matches)")
                    return (
                        f"Found {len(matches)}+ matches in {files_checked} files:\n"
                        + "\n".join(matches)
                    )

    if not matches:
        return f"No matches for '{pattern}' in {files_checked} files"
    return f"Found {len(matches)} match(es) in {files_checked} files:\n" + "\n".join(matches)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

TOOL_REGISTRY: dict[str, Callable[..., str]] = {
    "read_file": read_file,
    "write_file": write_file,
    "list_directory": list_directory,
    "execute_command": execute_command,
    "search_files": search_files,
}


def execute_tool(name: str, arguments: dict[str, Any]) -> str:
    """Look up *name* in the registry and call it with *arguments*."""
    fn = TOOL_REGISTRY.get(name)
    if fn is None:
        return f"Error: unknown tool '{name}'"
    try:
        return fn(**arguments)
    except TypeError as exc:
        return f"Error: bad arguments for '{name}' — {exc}"
    except Exception as exc:
        return f"Error in '{name}': {exc}"
