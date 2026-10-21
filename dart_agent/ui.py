"""Dual-mode UI renderer — rich human output or structured JSON lines.

Every visual element in the CLI flows through this module. Switching to
``json_mode=True`` converts *all* output into clean, parseable JSONL on
stdout — no ANSI codes, no spinners, no emoji — so upstream AI agents
can pipe and parse without friction.
"""

from __future__ import annotations

import atexit
import json
import os
import re
import shutil
import sys
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

# ── ASCII Art Logo ─────────────────────────────────────────────────────────

ASCII_LOGO = """\
  ████   ██   ███  █████     ██   ███  ████ █   █ █████
  █   █ █  █  █  █   █      █  █ █   █ █    ██  █   █  
  █   █ ████  ███    █      ████ █ ███ ███  █ █ █   █  
  █   █ █  █  █  █   █      █  █ █   █ █    █  ██   █  
  ████  █  █  █  █   █      █  █  ███  ████ █   █   █  \
"""

COLOR_LOGO_LINES = [
    "\033[0;90m─\033[0;37m \033[0;34m▄▄▄▄▄▄▄▄▄▄▄▄▄▄\033[0;37m \033[0;97m─\033[0;37m─\033[0;90m─\033[0;37m \033[0;34m▄▄▄▄▄▄▄▄▄▄▄\033[0;37m \033[0;90m─\033[0;37m─\033[0;90m─\033[0;37m \033[0;34m▄▄▄▄▄▄▄▄▄▄▄▄▄▄\033[0;37m \033[0;97m─\033[0;90m─\033[0;37m \033[0;34m▄▄▄▄▄▄▄▄▄▄▄▄▄\033[0;37m ─    ─\033[0;90m─\033[0;37m \033[0;34m▄▄▄▄▄▄▄▄▄▄▄\033[0;37m \033[0;90m─\033[0;37m─\033[0;90m─\033[0;37m \033[0;34m▄▄▄▄▄▄▄▄▄▄▄\033[0;37m ─\033[0;90m─\033[0;37m \033[0;34m▄▄▄▄▄▄▄▄▄▄▄\033[0;37m ─\033[0;90m─\033[0;37m \033[0;34m▄▄▄▄▄▄▄▄▄▄▄\033[0;37m ─\033[0;90m─\033[0;37m \033[0;34m▄▄▄▄▄▄▄▄▄▄▄▄▄\033[0;37m ─\033[0m",
    "\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m████████████\033[0;34m█\033[0;37m \033[0;97m─\033[0;37m─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m█████████\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m████████████\033[0;34m█\033[0;37m \033[0;97m─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94m████\033[0;94;47m███████\033[0;34m█\033[0;37m ─    ─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m█████████\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m█████████\033[0;34m█\033[0;37m ─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m█████████\033[0;34m█\033[0;37m ─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m█████████\033[0;34m█\033[0;37m ─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94m████\033[0;94;47m███████\033[0;34m█\033[0;37m ─\033[0m",
    "\033[0;90m─\033[0;37m \033[0;34m▀▀▀█\033[0;94;47m▓▓\033[0;34m█▀▀▀█\033[0;94;47m▓▓\033[0;34m█\033[0;37m \033[0;97m─\033[0;37m─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m▓▓\033[0;34m█▀▀▀█\033[0;94;47m▓▓\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m─\033[0;90m─\033[0;37m \033[0;34m▀▀▀█\033[0;94;47m▓▓\033[0;34m█▀▀▀█\033[0;94;47m▓▓\033[0;34m█\033[0;37m \033[0;97m─\033[0;90m─\033[0;37m \033[0;34m▀▀▀▀█\033[0;94;47m▓▓\033[0;34m█▀▀▀▀▀\033[0;37m ─    ─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m▓▓\033[0;34m█▀▀▀█\033[0;94;47m▓▓\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m▓▓\033[0;34m█▀▀▀▀▀▀▀\033[0;37m ─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m▓▓\033[0;34m█▀▀▀▀▀▀▀\033[0;37m ─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m▓▓\033[0;34m█▀▀▀█\033[0;94;47m▓▓\033[0;34m█\033[0;37m ─\033[0;90m─\033[0;37m \033[0;34m▀▀▀▀█\033[0;94;47m▓▓\033[0;34m█▀▀▀▀▀\033[0;37m ─\033[0m",
    "\033[0;97m─\033[0;37m──\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m▒▒\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m▒▒\033[0;34m█\033[0;37m \033[0;97m─\033[0;37m─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m▒▒\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m▒▒\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m─\033[0;97m─\033[0;37m──\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m▒▒\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m▒▒\033[0;34m█\033[0;37m \033[0;97m─\033[0;37m─\033[0;97m─\033[0;37m──\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m▒▒\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m─\033[0;97m───\033[0;37m─    ─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m▒▒\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m▒▒\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m▒▒\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m───\033[0;97m────\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m▒▒\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m───\033[0;97m────\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m▒▒\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m▒▒\033[0;34m█\033[0;37m \033[0;97m─\033[0;37m─\033[0;97m─\033[0;37m──\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m▒▒\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m─\033[0;97m───\033[0;37m─\033[0m",
    "\033[0;97m─\033[0;37m──\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m░░\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m░░\033[0;34m█\033[0;37m \033[0;97m─\033[0;37m─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m░░\033[0;34m█▄▄▄█\033[0;94;47m░░\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m─\033[0;97m─\033[0;37m──\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m░░\033[0;34m█▄▄▄█\033[0;94;47m░░\033[0;34m█\033[0;37m \033[0;97m─\033[0;37m─\033[0;97m─\033[0;37m──\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m░░\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m─\033[0;97m───\033[0;37m─    ─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m░░\033[0;34m█▄▄▄█\033[0;94;47m░░\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m░░\033[0;34m█\033[0;37m \033[0;34m▄▄▄▄▄▄\033[0;37m \033[0;97m─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m░░\033[0;34m█▄▄▄▄\033[0;37m \033[0;90m─\033[0;37m─\033[0;97m──\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m░░\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m░░\033[0;34m█\033[0;37m \033[0;97m─\033[0;37m─\033[0;97m─\033[0;37m──\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;47m░░\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m─\033[0;97m───\033[0;37m─\033[0m",
    "\033[0;97m─\033[0;37m──\033[0;90m─\033[0;37m \033[0;34m█\033[0;34;44m  \033[0;34m█\033[0;37m \033[0;90m─\033[0;37m \033[0;34m█\033[0;34;44m  \033[0;34m█\033[0;37m \033[0;97m─\033[0;37m─\033[0;90m─\033[0;37m \033[0;34m█\033[0;34;44m  \033[0;34m█████\033[0;34;44m  \033[0;34m█\033[0;37m \033[0;90m─\033[0;37m─\033[0;97m─\033[0;37m──\033[0;90m─\033[0;37m \033[0;34m█\033[0;34;44m  \033[0;34m███████\033[0;37m \033[0;90m─\033[0;97m─\033[0;37m─\033[0;97m─\033[0;37m──\033[0;90m─\033[0;37m \033[0;34m█\033[0;34;44m  \033[0;34m█\033[0;37m \033[0;90m─\033[0;37m─\033[0;97m───\033[0;37m─    ─\033[0;90m─\033[0;37m \033[0;34m█\033[0;34;44m  \033[0;34m█████\033[0;34;44m  \033[0;34m█\033[0;37m \033[0;90m─\033[0;37m─\033[0;90m─\033[0;37m \033[0;34m█\033[0;34;44m  \033[0;34m█\033[0;37m \033[0;34m██████\033[0;37m \033[0;97m─\033[0;90m─\033[0;37m \033[0;34m█\033[0;34;44m  \033[0;34m█████\033[0;37m \033[0;90m─\033[0;37m─\033[0;97m──\033[0;90m─\033[0;37m \033[0;34m█\033[0;34;44m  \033[0;34m█\033[0;37m \033[0;90m─\033[0;37m \033[0;34m█\033[0;34;44m  \033[0;34m█\033[0;37m \033[0;97m─\033[0;37m─\033[0;97m─\033[0;37m──\033[0;90m─\033[0;37m \033[0;34m█\033[0;34;44m  \033[0;34m█\033[0;37m \033[0;90m─\033[0;37m─\033[0;97m───\033[0;37m─\033[0m",
    "\033[0;97m─\033[0;37m──\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m░░\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m░░\033[0;34m█\033[0;37m \033[0;97m─\033[0;37m─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m░░\033[0;34m█▀▀▀█\033[0;94;44m░░\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m─\033[0;97m─\033[0;37m──\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m░░\033[0;34m█▀▀▀█\033[0;94;44m░░\033[0;34m█\033[0;37m \033[0;97m─\033[0;37m─\033[0;97m─\033[0;37m──\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m░░\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m─\033[0;97m───\033[0;37m─    ─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m░░\033[0;34m█▀▀▀█\033[0;94;44m░░\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m░░\033[0;34m█\033[0;37m \033[0;34m▀▀█\033[0;94;44m░░\033[0;34m█\033[0;37m \033[0;97m─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m░░\033[0;34m█▀▀▀▀\033[0;37m \033[0;90m─\033[0;37m─\033[0;97m──\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m░░\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m░░\033[0;34m█\033[0;37m \033[0;97m─\033[0;37m─\033[0;97m─\033[0;37m──\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m░░\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m─\033[0;97m───\033[0;37m─\033[0m",
    "\033[0;97m─\033[0;37m──\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▒▒\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▒▒\033[0;34m█\033[0;37m \033[0;97m─\033[0;37m─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▒▒\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▒▒\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m─\033[0;97m─\033[0;37m──\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▒▒\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▒▒\033[0;34m█\033[0;37m \033[0;97m─\033[0;37m─\033[0;97m─\033[0;37m──\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▒▒\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m─\033[0;97m───\033[0;37m─    ─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▒▒\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▒▒\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▒▒\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▒▒\033[0;34m█\033[0;37m \033[0;97m─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▒▒\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m───\033[0;97m────\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▒▒\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▒▒\033[0;34m█\033[0;37m \033[0;97m─\033[0;37m─\033[0;97m─\033[0;37m──\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▒▒\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m─\033[0;97m───\033[0;37m─\033[0m",
    "\033[0;97m─\033[0;37m──\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▓▓\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▓▓\033[0;34m█\033[0;37m \033[0;97m─\033[0;37m─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▓▓\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▓▓\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m─\033[0;97m─\033[0;37m──\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▓▓\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▓▓\033[0;34m█\033[0;37m \033[0;97m─\033[0;37m─\033[0;97m─\033[0;37m──\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▓▓\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m─\033[0;97m───\033[0;37m─    ─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▓▓\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▓▓\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▓▓\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▓▓\033[0;34m█\033[0;37m \033[0;97m─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▓▓\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m───\033[0;97m────\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▓▓\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▓▓\033[0;34m█\033[0;37m \033[0;97m─\033[0;37m─\033[0;97m─\033[0;37m──\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▓▓\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m─\033[0;97m───\033[0;37m─\033[0m",
    "\033[0;90m─\033[0;37m \033[0;34m▄▄▄█\033[0;94;44m▓▓\033[0;34m█▄▄▄█\033[0;94;44m▓▓\033[0;34m█\033[0;37m \033[0;97m─\033[0;90m─\033[0;37m \033[0;34m▄█\033[0;94;44m▓▓\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▓▓\033[0;34m█▄\033[0;37m \033[0;90m──\033[0;37m──\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▓▓\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▓▓\033[0;34m█\033[0;37m \033[0;97m─\033[0;37m─\033[0;97m─\033[0;37m──\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▓▓\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m─\033[0;97m───\033[0;37m─    \033[0;90m─\033[0;37m \033[0;34m▄█\033[0;94;44m▓▓\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▓▓\033[0;34m█▄\033[0;37m \033[0;90m──\033[0;37m \033[0;34m█\033[0;94;44m▓▓\033[0;34m█▄▄▄█\033[0;94;44m██\033[0;34m█\033[0;37m ─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▓▓\033[0;34m█▄▄▄▄▄▄▄\033[0;37m ─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▓▓\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▓▓\033[0;34m█\033[0;37m ──\033[0;97m─\033[0;37m──\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m▓▓\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m─\033[0;97m───\033[0;37m─\033[0m",
    "\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m████████████\033[0;34m█\033[0;37m \033[0;97m─\033[0;90m─\033[0;37m \033[0;34m█\033[0;94m█\033[0;94;44m██\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m██\033[0;94m█\033[0;34m█\033[0;37m \033[0;90m──\033[0;37m──\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m██\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m██\033[0;34m█\033[0;37m \033[0;97m─\033[0;37m─\033[0;97m─\033[0;37m──\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m██\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m─\033[0;97m───\033[0;37m─    \033[0;90m─\033[0;37m \033[0;34m█\033[0;94m█\033[0;94;44m██\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m██\033[0;94m█\033[0;34m█\033[0;37m \033[0;90m──\033[0;37m \033[0;34m█\033[0;94;44m█████████\033[0;34m█\033[0;37m \033[0;90m──\033[0;37m \033[0;34m█\033[0;94;44m█████████\033[0;34m█\033[0;37m \033[0;90m──\033[0;37m \033[0;34m█\033[0;94;44m██\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m██\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m─\033[0;97m─\033[0;37m──\033[0;90m─\033[0;37m \033[0;34m█\033[0;94;44m██\033[0;34m█\033[0;37m \033[0;90m─\033[0;37m─\033[0;97m───\033[0;37m─\033[0m",
    "\033[0;90m─\033[0;37m \033[0;34m▀▀▀▀▀▀▀▀▀▀▀▀▀▀\033[0;37m \033[0;97m─\033[0;90m─\033[0;37m \033[0;34m▀▀▀▀▀\033[0;37m \033[0;90m─\033[0;37m \033[0;34m▀▀▀▀▀\033[0;37m \033[0;90m──\033[0;37m──\033[0;90m─\033[0;37m \033[0;34m▀▀▀▀\033[0;37m \033[0;90m─\033[0;37m \033[0;34m▀▀▀▀\033[0;37m \033[0;97m─\033[0;37m─\033[0;97m─\033[0;37m──\033[0;90m─\033[0;37m \033[0;34m▀▀▀▀\033[0;37m \033[0;90m─\033[0;37m─\033[0;97m───\033[0;37m─    \033[0;90m─\033[0;37m \033[0;34m▀▀▀▀▀\033[0;37m \033[0;90m─\033[0;37m \033[0;34m▀▀▀▀▀\033[0;37m \033[0;90m──\033[0;37m \033[0;34m▀▀▀▀▀▀▀▀▀▀▀\033[0;37m \033[0;90m──\033[0;37m \033[0;34m▀▀▀▀▀▀▀▀▀▀▀\033[0;37m \033[0;90m──\033[0;37m \033[0;34m▀▀▀▀\033[0;37m \033[0;90m─\033[0;37m \033[0;34m▀▀▀▀\033[0;37m \033[0;90m─\033[0;37m─\033[0;97m─\033[0;37m──\033[0;90m─\033[0;37m \033[0;34m▀▀▀▀\033[0;37m \033[0;90m─\033[0;37m─\033[0;97m───\033[0;37m─\033[0m",
]

# ── tool metadata ──────────────────────────────────────────────────────────

TOOL_META: dict[str, dict[str, str]] = {
    "read_file":       {"icon": "📖", "label": "read_file",       "desc": "Read file contents with optional line range"},
    "write_file":      {"icon": "✏️",  "label": "write_file",      "desc": "Create or overwrite files on disk"},
    "list_directory":  {"icon": "📁", "label": "list_directory",  "desc": "Browse directory contents with sizes"},
    "execute_command": {"icon": "⚡", "label": "execute_command", "desc": "Run shell commands with timeout"},
    "search_files":    {"icon": "🔍", "label": "search_files",    "desc": "Grep-style search across files"},
}

# ── UI class ───────────────────────────────────────────────────────────────


class UI:
    """Centralised renderer with human / JSON dual output."""

    def __init__(self, console: Console, *, json_mode: bool = False) -> None:
        self.console = console
        self.json_mode = json_mode

    # ── JSON helpers ───────────────────────────────────────────────────

    def _emit(self, event: str, **data: Any) -> None:
        """Write a single JSON-line event to stdout."""
        sys.stdout.write(json.dumps({"type": event, **data}) + "\n")
        sys.stdout.flush()

    # ── startup sequence ───────────────────────────────────────────────

    def banner(self, version: str) -> None:
        if self.json_mode:
            self._emit("init", version=version)
            return
        self.console.print()
        cols, _ = shutil.get_terminal_size((80, 24))

        if cols >= 158:
            for line in COLOR_LOGO_LINES:
                sys.stdout.write(line + "\n")
        elif cols >= 76:
            for line in COLOR_LOGO_LINES:
                parts = line.split("    ")
                sys.stdout.write(parts[0] + "\033[0m\n")
            sys.stdout.write("\n")
            for line in COLOR_LOGO_LINES:
                parts = line.split("    ")
                sys.stdout.write(" " + parts[1] + "\n")
        else:
            for line in ASCII_LOGO.splitlines():
                self.console.print(f"[bold green]{line}[/bold green]")

        sys.stdout.flush()
        self.console.print()
        self.console.print(
            f"  [bold green]🎯 dart-agent[/bold green] [dim]v{version} — Lightweight AI Agent for your Terminal[/dim]\n"
        )

    def config_summary(
        self,
        base_url: str,
        model: str,
        workspace: str | Path | None = None,
        trusted: bool = False,
    ) -> None:
        ws_str = str(workspace or os.getcwd())
        if self.json_mode:
            self._emit("config", base_url=base_url, model=model, workspace=ws_str, trusted=trusted)
            return
        trust_badge = "[bold green]✔ trusted[/bold green]" if trusted else "[dim yellow]⚠ confirm commands[/dim yellow]"
        self.console.print(f"  [bold green]●[/]  [dim]Provider[/]    {base_url}")
        self.console.print(f"  [bold green]●[/]  [dim]Model[/]       [bold cyan]{model}[/]")
        self.console.print(f"  [bold green]●[/]  [dim]Workspace[/]   [bold]{ws_str}[/] {trust_badge}")
        self.console.print()

    def tool_table(self) -> None:
        if self.json_mode:
            self._emit("tools", names=list(TOOL_META.keys()))
            return
        table = Table(
            title="🔧 Active Tools",
            title_style="bold",
            show_header=True,
            header_style="bold dim",
            border_style="dim cyan",
            padding=(0, 1),
            expand=False,
        )
        table.add_column("", width=3, justify="center")
        table.add_column("Tool", style="bold cyan", min_width=18)
        table.add_column("Description", style="dim")
        for meta in TOOL_META.values():
            table.add_row(meta["icon"], meta["label"], meta["desc"])
        self.console.print(table)
        self.console.print()

    def ready(self) -> None:
        if self.json_mode:
            self._emit("ready")
            return
        self.console.print(
            "  [dim]Type your message.  Commands: [bold]/clear[/] [bold]/model[/] [bold]/help[/] [bold]/exit[/][/]\n"
        )

    # ── model selection ────────────────────────────────────────────────

    def models_table(self, models: list[str]) -> None:
        if self.json_mode:
            self._emit("models", models=models)
            return
        table = Table(
            title="Available Models",
            show_header=True,
            header_style="bold cyan",
            title_style="bold",
            border_style="dim",
            padding=(0, 1),
        )
        table.add_column("#", style="dim", width=4, justify="right")
        table.add_column("Model ID")
        for i, mid in enumerate(models, 1):
            table.add_row(str(i), mid)
        self.console.print(table)
        self.console.print()

    # ── credential input ───────────────────────────────────────────────

    def ask_api_key(self) -> str:
        """Prompt for API key, echoing asterisks as characters are entered or pasted.

        After submission, displays the key masked with asterisks and length confirmation.
        """
        if self.json_mode:
            raise ValueError("API_KEY must be specified via --api-key or environment in --json mode")

        while True:
            self.console.print("[bold]? API Key[/]: ", end="")
            sys.stdout.flush()

            chars: list[str] = []
            is_tty = hasattr(sys.stdin, "isatty") and sys.stdin.isatty()

            if is_tty:
                try:
                    import msvcrt
                    while True:
                        ch = msvcrt.getwch()
                        if ch in ("\r", "\n"):
                            sys.stdout.write("\n")
                            sys.stdout.flush()
                            break
                        elif ch in ("\x08", "\x7f"):  # Backspace
                            if chars:
                                chars.pop()
                                sys.stdout.write("\b \b")
                                sys.stdout.flush()
                        elif ch == "\x03":  # Ctrl+C
                            sys.stdout.write("\n")
                            sys.stdout.flush()
                            raise KeyboardInterrupt
                        elif ch == "\x04":  # Ctrl+D
                            sys.stdout.write("\n")
                            sys.stdout.flush()
                            raise EOFError
                        elif ch in ("\x00", "\xe0"):  # Windows special key prefix
                            msvcrt.getwch()
                        else:
                            chars.append(ch)
                            sys.stdout.write("*")
                            sys.stdout.flush()
                except ImportError:
                    try:
                        import termios
                        import tty
                        fd = sys.stdin.fileno()
                        old_settings = termios.tcgetattr(fd)
                        try:
                            tty.setraw(fd)
                            while True:
                                ch = sys.stdin.read(1)
                                if ch in ("\r", "\n"):
                                    sys.stdout.write("\r\n")
                                    sys.stdout.flush()
                                    break
                                elif ch in ("\x08", "\x7f"):
                                    if chars:
                                        chars.pop()
                                        sys.stdout.write("\b \b")
                                        sys.stdout.flush()
                                elif ch == "\x03":
                                    raise KeyboardInterrupt
                                elif ch == "\x04":
                                    raise EOFError
                                else:
                                    chars.append(ch)
                                    sys.stdout.write("*")
                                    sys.stdout.flush()
                        finally:
                            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                    except Exception:
                        import getpass
                        raw = getpass.getpass("")
                        chars = list(raw)
            else:
                line = sys.stdin.readline()
                chars = list(line.strip("\r\n"))

            key = "".join(chars).strip()
            if key:
                masked = "*" * min(len(key), 32)
                self.console.print(f"  [bold green]✔[/] [dim]API Key received:[/dim] [cyan]{masked}[/] [dim]({len(key)} chars)[/]\n")
                return key
            self.warning("API key cannot be empty. Please enter or paste your key.")

    # ── conversation events ────────────────────────────────────────────

    def thinking_spinner(self) -> Spinner:
        """Return a Rich Spinner renderable for the Live display."""
        return Spinner("dots", text="[bold yellow]  Thinking…[/]", style="yellow")

    def tool_call(self, name: str, args: dict[str, Any]) -> None:
        if self.json_mode:
            self._emit("tool_call", name=name, arguments=args)
            return
        meta = TOOL_META.get(name, {"icon": "🔧"})
        detail = _format_tool_detail(name, args)
        self.console.print(f"  ├─ {meta['icon']}  [bold cyan]{name}[/]({detail})")

    def tool_result(self, name: str, result: str) -> None:
        if self.json_mode:
            self._emit("tool_result", name=name, output=result)
            return
        lines = result.strip().splitlines()
        if len(lines) <= 2:
            preview = result.strip().replace("\n", "  ")
        else:
            preview = lines[0] + f"  [dim italic]… {len(lines)} lines[/]"
        self.console.print(f"  │  [dim]→ {preview}[/]")
        self.console.print("  │")

    def thought(self, content: str) -> None:
        """Render model thought / reasoning process in a dedicated styled panel."""
        if self.json_mode:
            self._emit("thought", content=content)
            return
        if not content or not content.strip():
            return
        self.console.print()
        self.console.print(
            Panel(
                Text(content.strip(), style="dim italic"),
                title="[bold yellow]💭 Thought Process[/bold yellow]",
                title_align="left",
                border_style="yellow",
                padding=(0, 2),
            )
        )

    def response(self, content: str) -> None:
        """Render final assistant response in a styled Markdown panel."""
        if self.json_mode:
            self._emit("response", content=content)
            return
        if not content or not content.strip():
            return
        self.console.print()
        self.console.print(
            Panel(
                Markdown(content.strip()),
                title="[bold green]🎯 dart-agent[/bold green]",
                title_align="left",
                border_style="green",
                padding=(1, 2),
            )
        )

    def user_turn(self, content: str) -> None:
        """Render the user query in the scrollable log area."""
        if self.json_mode:
            self._emit("user", content=content)
            return
        self.console.print(f"[bold green]You >[/bold green] {content}")

    # ── docked bottom input mode ───────────────────────────────────────

    def enable_docked_mode(self) -> bool:
        """Configure terminal scrolling margins to keep bottom lines static."""
        if self.json_mode:
            return False
        if not (hasattr(sys.stdin, "isatty") and sys.stdin.isatty()):
            return False

        cols, lines = shutil.get_terminal_size((80, 24))
        if lines < 10:
            return False

        if sys.platform == "win32":
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                hStdOut = kernel32.GetStdHandle(-11)
                mode = ctypes.c_ulong()
                kernel32.GetConsoleMode(hStdOut, ctypes.byref(mode))
                # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
                kernel32.SetConsoleMode(hStdOut, mode.value | 0x0004)
            except Exception:
                pass

        self._docked_active = True
        atexit.register(self.disable_docked_mode)
        self._update_scroll_margins()
        return True

    def disable_docked_mode(self) -> None:
        """Reset terminal scroll margins and restore cursor."""
        if getattr(self, "_docked_active", False):
            self._docked_active = False
            try:
                sys.stdout.write("\x1b[r\x1b[?25h\n")
                sys.stdout.flush()
            except Exception:
                pass

    def _update_scroll_margins(self) -> tuple[int, int]:
        """Set DECSTBM scroll region to lines 1..(lines-3). Returns (lines, cols)."""
        cols, lines = shutil.get_terminal_size((80, 24))
        bottom_scroll = max(5, lines - 3)
        sys.stdout.write(f"\x1b[1;{bottom_scroll}r")
        sys.stdout.flush()
        return lines, cols

    def prompt_input(self) -> str:
        """Prompt for user input with static docked position or standard fallback."""
        if not getattr(self, "_docked_active", False):
            return self.console.input("[bold green]You >[/bold green] ").strip()

        lines, cols = self._update_scroll_margins()
        if lines < 10:
            return self.console.input("[bold green]You >[/bold green] ").strip()

        sep_row = lines - 2
        input_row = lines - 1
        hint_row = lines

        # Draw the static docked frame at the bottom
        # Row lines-2: Separator bar
        sys.stdout.write(f"\x1b[{sep_row};1H\x1b[2K\x1b[2m{'─' * cols}\x1b[0m")
        # Row lines: Hint line
        hint = " [Ctrl+C] Clear/Interrupt  [Ctrl+D] Exit  [/help] Commands"
        hint_padded = hint.ljust(cols)[:cols]
        sys.stdout.write(f"\x1b[{hint_row};1H\x1b[2K\x1b[2m{hint_padded}\x1b[0m")
        # Row lines-1: Prompt
        prompt_prefix = "You > "
        sys.stdout.write(f"\x1b[{input_row};1H\x1b[2K\x1b[1;32m{prompt_prefix}\x1b[0m")
        sys.stdout.flush()

        chars: list[str] = []
        is_windows = sys.platform == "win32"

        if is_windows:
            import msvcrt
            while True:
                ch = msvcrt.getwch()
                if ch in ("\r", "\n"):
                    break
                elif ch in ("\x08", "\x7f"):  # Backspace
                    if chars:
                        chars.pop()
                        current_str = "".join(chars)
                        sys.stdout.write(
                            f"\x1b[{input_row};1H\x1b[2K\x1b[1;32m{prompt_prefix}\x1b[0m{current_str}"
                        )
                        sys.stdout.flush()
                elif ch == "\x03":  # Ctrl+C
                    chars.clear()
                    sys.stdout.write(
                        f"\x1b[{input_row};1H\x1b[2K\x1b[1;32m{prompt_prefix}\x1b[0m"
                    )
                    sys.stdout.flush()
                    raise KeyboardInterrupt
                elif ch == "\x04":  # Ctrl+D
                    raise EOFError
                elif ch == "\x1a":  # Ctrl+Z
                    raise EOFError
                elif ch in ("\x00", "\xe0"):  # Windows special key prefix
                    msvcrt.getwch()
                elif ord(ch) >= 32:  # Printable character
                    chars.append(ch)
                    sys.stdout.write(ch)
                    sys.stdout.flush()
        else:
            try:
                import termios
                import tty
                fd = sys.stdin.fileno()
                old_settings = termios.tcgetattr(fd)
                try:
                    tty.setraw(fd)
                    while True:
                        ch = sys.stdin.read(1)
                        if ch in ("\r", "\n"):
                            break
                        elif ch in ("\x08", "\x7f"):
                            if chars:
                                chars.pop()
                                current_str = "".join(chars)
                                sys.stdout.write(
                                    f"\x1b[{input_row};1H\x1b[2K\x1b[1;32m{prompt_prefix}\x1b[0m{current_str}"
                                )
                                sys.stdout.flush()
                        elif ch == "\x03":
                            raise KeyboardInterrupt
                        elif ch == "\x04":
                            raise EOFError
                        elif ord(ch) >= 32:
                            chars.append(ch)
                            sys.stdout.write(ch)
                            sys.stdout.flush()
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except Exception:
                return self.console.input("[bold green]You >[/bold green] ").strip()

        result = "".join(chars).strip()

        # Update input row while agent runs
        sys.stdout.write(f"\x1b[{input_row};1H\x1b[2K\x1b[33m● dart-agent is working...\x1b[0m")
        # Place cursor in scroll region so output streams inside lines 1..(lines-3)
        scroll_bottom = max(5, lines - 3)
        sys.stdout.write(f"\x1b[{scroll_bottom};1H\n")
        sys.stdout.flush()

        return result

    def confirm_command(self, command: str) -> str:
        """Prompt for shell-command approval.

        Returns ``"yes"``, ``"no"``, or ``"always"``.
        In JSON mode, always auto-approves.
        """
        if self.json_mode:
            return "yes"
        self.console.print(
            f"\n  [bold yellow]⚠  Execute:[/]  [white on grey23] {command} [/]"
        )
        try:
            ans = input("  Allow? [Y/n/always] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "no"
        if ans in ("always", "a"):
            return "always"
        return "yes" if ans in ("", "y", "yes") else "no"

    # ── utility output ─────────────────────────────────────────────────

    def success(self, msg: str) -> None:
        if self.json_mode:
            self._emit("info", message=msg)
        else:
            self.console.print(f"  [bold green]✔[/]  {msg}")

    def warning(self, msg: str) -> None:
        if self.json_mode:
            self._emit("warning", message=msg)
        else:
            self.console.print(f"  [bold yellow]⚠[/]  {msg}")

    def error(self, msg: str) -> None:
        if self.json_mode:
            self._emit("error", message=msg)
        else:
            self.console.print(f"  [bold red]✖[/]  {msg}")

    def info(self, msg: str) -> None:
        if self.json_mode:
            self._emit("info", message=msg)
        else:
            self.console.print(msg)


# ── helpers ────────────────────────────────────────────────────────────────


def _format_tool_detail(name: str, args: dict[str, Any]) -> str:
    if name == "read_file":
        s = args.get("path", "?")
        if "start_line" in args:
            s += f"  L{args['start_line']}"
            if "end_line" in args:
                s += f"–{args['end_line']}"
        return s
    if name == "write_file":
        return args.get("path", "?")
    if name == "list_directory":
        return args.get("path", ".")
    if name == "execute_command":
        return args.get("command", "?")
    if name == "search_files":
        s = f"\"{args.get('pattern', '?')}\""
        if fp := args.get("file_pattern"):
            s += f"  in {fp}"
        return s
    return json.dumps(args)
