# Dart Agent (`drt`)

<div align="center">

**Lightweight, production-grade terminal AI agent connecting to any OpenAI-compatible API.**

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-active-success.svg)]()

</div>

---

Dart Agent (`drt` / `dart-agent`) is a fast, responsive CLI AI coding agent built for the terminal. It provides full agency to LLMs with file read/write, shell execution, directory inspection, and recursive file search capabilities—all wrapped in a clean Rich terminal interface.

## ✨ Features

- **Global Alias**: Run instantly from any terminal as `drt` or `dart-agent`.
- **Dynamic Working Directory**: Automatically runs in your current terminal directory, or switch contexts via `--dir` / `-d <path>`.
- **Workspace Trust System**:
  - Persistent trust tracking (`~/.dart-agent/trusted.json`).
  - Interactive approval prompts on first run in new directories.
  - Trusted workspaces bypass repetitive tool/command confirmation interruptions.
  - Interactive `/trust` REPL command (`/trust on`, `/trust off`, `/trust list`).
- **Rich Terminal UI**:
  - Dual-mode renderer: human interactive mode and machine JSON lines (`--json`).
  - 3D shaded ANSI banner and docked bottom input area.
  - Dedicated `💭 Thought Process` panel for `<thought>` / `<think>` tags.
  - Beautiful syntax-highlighted Markdown output panels.
- **5 Core Agentic Tools**:
  - `read_file` — Reads files with line limits and byte offsets.
  - `write_file` — Overwrite or append files with automatic directory creation.
  - `list_directory` — Explore directories recursively or shallow.
  - `execute_command` — Run shell commands with configurable timeouts.
  - `search_files` — Regex or text pattern file search with smart binary/noise skipping.
- **Multi-Provider Support**: Works with TokenRouter, OpenAI, Groq, Together, Ollama, OpenRouter, Cerebras, and Google Gemini.
- **Safety Controls**: Manual confirmation gates in untrusted directories for shell commands and dangerous writes.
- **Interactive Slash Commands**: `/trust`, `/model`, `/clear`, `/help`, `/exit`.

---

## 🚀 Installation & Setup

### Using uv / pip
```bash
# Clone the repository
git clone https://github.com/AJAYMYTH/DartAgent.git
cd DartAgent

# Install dependencies with uv
uv sync

# Run locally
uv run dart-agent
```

### Environment Variables
Configure your credentials via `.env` or system environment variables:
```env
DART_BASE_URL=https://api.tokenrouter.com/v1
DART_API_KEY=your-api-key-here
DART_MODEL=anthropic/claude-3.5-sonnet
```
You can also copy the example template:
```bash
cp .env.example .env
```

---

## 🛠️ Usage

### Interactive Mode
```bash
drt
```
Or with custom flags:
```bash
# Work in a specific project directory
drt -d C:\Projects\MyAwesomeApp

# Run with trusted mode enabled
drt --trust

# Run in machine-readable JSON mode
drt --json "Inspect the repository and list all endpoints"
```

### Interactive Commands
Inside the REPL session:
- `/trust` — View or toggle workspace trust status (`/trust on`, `/trust off`, `/trust list`).
- `/model` — Switch models interactively.
- `/clear` — Clear current conversation context.
- `/help` — Display commands and shortcuts.
- `/exit` — Exit the agent session.

---

## 🏗️ Project Architecture

```
DartAgent/
├── dart_agent/
│   ├── __init__.py
│   ├── agent.py        # Core agent loop, prompt generation, tool dispatch
│   ├── cli.py          # Rich-click CLI, arguments, REPL loop
│   ├── tools.py        # System tools & function calling schemas
│   ├── trust.py        # Workspace trust management & persistence
│   └── ui.py           # Terminal rendering, ANSI art, docking & panels
├── pyproject.toml      # Build metadata and entry points
├── run_app.py          # Standalone launcher harness
└── MEMORY.md           # Project state and changelog
```

---

## 📄 License

MIT License.
