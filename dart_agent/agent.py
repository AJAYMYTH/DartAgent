"""Core agent loop — conversation management, streaming, and tool dispatch.

The Agent class owns the conversation history, calls the LLM with streaming,
processes tool-call deltas, executes tools, and loops until the model stops.
All visual output is delegated to the ``UI`` renderer so switching between
human-rich and JSON-line modes is transparent.
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

from openai import OpenAI
from rich.live import Live
from rich.markdown import Markdown
from rich.text import Text

from .tools import TOOL_DEFINITIONS, execute_tool
from .ui import UI

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a capable AI assistant running inside a user's terminal.
You have direct access to the local filesystem and shell via tools.

## Available tools
- **read_file** — read file contents (supports line ranges)
- **write_file** — create or overwrite files (creates parent directories)
- **list_directory** — browse directory contents
- **execute_command** — run shell commands
- **search_files** — grep-style search across files

## Guidelines
- Explore before editing: read relevant files to understand context first.
- Be precise: make targeted changes, don't rewrite entire files unnecessarily.
- Explain what you're doing and why at each step.
- For destructive operations, describe what will change before doing it.
- Keep responses concise and actionable.
"""

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class Agent:
    """Stateful conversational agent with tool-calling support."""

    def __init__(
        self,
        client: OpenAI,
        model: str,
        ui: UI,
        *,
        stream: bool = True,
    ) -> None:
        self.client = client
        self.model = model
        self.ui = ui
        self.stream = stream
        self.confirm_commands: bool = True
        cwd = os.getcwd()
        self._sys_prompt = SYSTEM_PROMPT + f"\n## Current Workspace\n- Working directory: `{cwd}`\n"
        self._history: list[dict[str, Any]] = [
            {"role": "system", "content": self._sys_prompt},
        ]

    # ── public API ────────────────────────────────────────────────────

    def clear(self) -> None:
        """Reset conversation history (keeps system prompt)."""
        self._history = [{"role": "system", "content": self._sys_prompt}]

    def abort_turn(self) -> None:
        """Clean up conversation history after an interrupted run."""
        if self._history and self._history[-1].get("role") == "user":
            self._history.pop()
        elif self._history and self._history[-1].get("role") == "tool":
            self._history.append(
                {"role": "assistant", "content": "[Operation interrupted by user]"}
            )

    def run(self, user_message: str) -> None:
        """Process *user_message* through the full agent loop."""
        self._history.append({"role": "user", "content": user_message})

        while True:
            response_text, tool_calls = self._complete()

            # Separate reasoning thoughts from clean response
            thoughts, clean_response = _parse_thoughts(response_text)
            for th in thoughts:
                self.ui.thought(th)

            if clean_response:
                self.ui.response(clean_response)

            if not tool_calls:
                if not response_text:
                    # Clean up user turn if error prevented any response
                    if self._history and self._history[-1].get("role") == "user":
                        self._history.pop()
                    else:
                        self._history.append({"role": "assistant", "content": ""})
                break

            # Record assistant message with tool calls
            self._history.append(
                {
                    "role": "assistant",
                    "content": response_text or None,
                    "tool_calls": tool_calls,
                }
            )

            # Execute each tool
            for tc in tool_calls:
                tc_id: str = tc["id"]
                fn_name: str = tc["function"]["name"]
                try:
                    fn_args: dict[str, Any] = json.loads(
                        tc["function"]["arguments"]
                    )
                except (json.JSONDecodeError, KeyError):
                    fn_args = {}

                self.ui.tool_call(fn_name, fn_args)

                # Safety gate for shell commands
                if fn_name == "execute_command" and self.confirm_commands:
                    verdict = self.ui.confirm_command(
                        fn_args.get("command", "")
                    )
                    if verdict == "always":
                        self.confirm_commands = False
                    elif verdict == "no":
                        result = "Command cancelled by user."
                        self._history.append(
                            {"role": "tool", "tool_call_id": tc_id, "content": result}
                        )
                        self.ui.tool_result(fn_name, result)
                        continue

                result = execute_tool(fn_name, fn_args)
                self._history.append(
                    {"role": "tool", "tool_call_id": tc_id, "content": result}
                )
                self.ui.tool_result(fn_name, result)

    # ── LLM call ──────────────────────────────────────────────────────

    def _complete(self) -> tuple[str, list[dict[str, Any]]]:
        kwargs: dict[str, Any] = dict(
            model=self.model,
            messages=self._history,
            tools=TOOL_DEFINITIONS,
            stream=self.stream,
        )
        try:
            if self.stream:
                return self._complete_stream(kwargs)
            return self._complete_sync(kwargs)
        except Exception as exc:
            err = str(exc)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                self.ui.error(
                    f"Quota Exceeded / Rate Limit (429) for '{self.model}'.\n"
                    f"  Tip: Use [bold cyan]/model[/bold cyan] to select another model."
                )
            elif "403" in err or "insufficient_user_quota" in err or "credit limit" in err.lower():
                self.ui.error(
                    f"Insufficient API Quota / Credit ($0.00) for '{self.model}'.\n"
                    f"  Tip: Your API provider balance is depleted. Please top up or use an API key with active credits."
                )
            elif "404" in err or "NOT_FOUND" in err:
                self.ui.error(
                    f"Model '{self.model}' not found or deprecated (404).\n"
                    f"  Tip: Use [bold cyan]/model[/bold cyan] to select an active model."
                )
            elif "timed out" in err.lower() or "timeout" in err.lower():
                self.ui.error(
                    f"Request timed out for '{self.model}'.\n"
                    f"  Tip: The API server took too long to respond. Try again or switch model with [bold cyan]/model[/bold cyan]."
                )
            else:
                self.ui.error(f"API error: {exc}")
            return "", []

    # ── synchronous (non-streaming) path ──────────────────────────────

    def _complete_sync(
        self, kwargs: dict[str, Any]
    ) -> tuple[str, list[dict[str, Any]]]:

        if not self.ui.json_mode:
            self.ui.console.print()

        with self.ui.console.status(
            "  [bold yellow]● Thinking…[/bold yellow]",
            spinner="dots",
            spinner_style="yellow",
        ) if not self.ui.json_mode else _noop_ctx():
            resp = self.client.chat.completions.create(**kwargs)

        msg = resp.choices[0].message
        text = msg.content or ""

        tool_calls: list[dict[str, Any]] = []
        if msg.tool_calls:
            for default_idx, tc in enumerate(msg.tool_calls):
                tc_entry: dict[str, Any] = {
                    "id": tc.id or f"call_{default_idx}",
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                # Preserve extra_content (e.g. Gemini thought_signature)
                extra = getattr(tc, "extra_content", None)
                if extra:
                    tc_entry["extra_content"] = extra
                tool_calls.append(tc_entry)

        if text and not tool_calls:
            self._history.append({"role": "assistant", "content": text})
        return text, tool_calls

    # ── streaming path ────────────────────────────────────────────────

    def _complete_stream(
        self, kwargs: dict[str, Any]
    ) -> tuple[str, list[dict[str, Any]]]:

        content_chunks: list[str] = []
        tc_map: dict[int, dict[str, Any]] = {}

        # --- JSON mode: no visual feedback, just collect -----------------
        if self.ui.json_mode:
            self.ui._emit("thinking")
            stream = self.client.chat.completions.create(**kwargs)
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta.content:
                    content_chunks.append(delta.content)
                if delta.tool_calls:
                    _accumulate_tool_calls(delta.tool_calls, tc_map)

            full_text = "".join(content_chunks)
            tool_calls = _finalise_tool_calls(tc_map)
            if full_text and not tool_calls:
                self._history.append({"role": "assistant", "content": full_text})
            return full_text, tool_calls

        # --- Human mode: spinner while accumulating stream chunks ----------
        with self.ui.console.status(
            "  [bold yellow]● Thinking…[/bold yellow]",
            spinner="dots",
            spinner_style="yellow",
        ):
            stream = self.client.chat.completions.create(**kwargs)
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta

                if delta.tool_calls:
                    _accumulate_tool_calls(delta.tool_calls, tc_map)

                if delta.content:
                    content_chunks.append(delta.content)

        full_text = "".join(content_chunks)
        tool_calls = _finalise_tool_calls(tc_map)

        if full_text and not tool_calls:
            self._history.append({"role": "assistant", "content": full_text})
        return full_text, tool_calls


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_thoughts(text: str) -> tuple[list[str], str]:
    """Extract <thought> or <think> blocks and return (thoughts, clean_text)."""
    if not text:
        return [], ""
    # Closed tags e.g. <thought>...</thought> or <think>...</think>
    pattern = r"<(?:thought|think)>(.*?)</(?:thought|think)>"
    thoughts = [t.strip() for t in re.findall(pattern, text, flags=re.DOTALL) if t.strip()]
    clean_text = re.sub(pattern, "", text, flags=re.DOTALL).strip()

    # Unclosed tag e.g. <thought>content without closing tag
    unclosed_match = re.search(r"<(?:thought|think)>(.*)$", clean_text, flags=re.DOTALL)
    if unclosed_match:
        unclosed = unclosed_match.group(1).strip()
        if unclosed:
            thoughts.append(unclosed)
        clean_text = clean_text[:unclosed_match.start()].strip()

    return thoughts, clean_text


def _accumulate_tool_calls(
    deltas: list, tc_map: dict[int, dict[str, Any]]
) -> None:
    for default_idx, tcd in enumerate(deltas):
        idx = tcd.index if getattr(tcd, "index", None) is not None else default_idx
        if idx not in tc_map:
            entry: dict[str, Any] = {
                "id": tcd.id or f"call_{idx}",
                "type": "function",
                "function": {
                    "name": tcd.function.name if tcd.function and tcd.function.name else "",
                    "arguments": (
                        tcd.function.arguments
                        if tcd.function and tcd.function.arguments
                        else ""
                    ),
                },
            }
            # Preserve extra_content (e.g. Gemini thought_signature) if present
            extra = getattr(tcd, "extra_content", None)
            if extra:
                entry["extra_content"] = extra
            tc_map[idx] = entry
        else:
            entry = tc_map[idx]
            if tcd.id:
                entry["id"] = tcd.id
            if tcd.function:
                if tcd.function.name:
                    entry["function"]["name"] = tcd.function.name
                if tcd.function.arguments:
                    entry["function"]["arguments"] += tcd.function.arguments
            extra = getattr(tcd, "extra_content", None)
            if extra and "extra_content" not in entry:
                entry["extra_content"] = extra


def _finalise_tool_calls(
    tc_map: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    return [tc_map[i] for i in sorted(tc_map)] if tc_map else []


class _noop_ctx:
    """No-op context manager for JSON mode."""

    def __enter__(self):
        return self

    def __exit__(self, *_: Any):
        pass
