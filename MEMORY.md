# dart-agent — Project Memory

## Overview
Lightweight, production-grade terminal AI agent that connects to any OpenAI-compatible API.
Gives the model file read/write, shell execution, directory listing, and file search capabilities.

## Location
- Repository: `https://github.com/AJAYMYTH/DartAgent.git`
- Root Directory: `C:\Users\javal\Videos\Dart-Agent`
- Global Executables:
  - `C:\Users\javal\.cargo\bin\drt.exe` (Global short alias, on user PATH)
  - `C:\Users\javal\.cargo\bin\dart-agent.exe` (Global full command, on user PATH)
  - `C:\Users\javal\AppData\Local\Programs\Python\Python314\Scripts\drt.cmd` & `dart-agent.cmd`
- PowerShell Profile Integration: `C:\Users\javal\OneDrive\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1`
- Build Output: `C:\Users\javal\Videos\Dart-Agent\dist\`
- Trust Storage: `~/.dart-agent/trusted.json`

## Status: ✅ v1.3.0 — Global `drt` Alias, Working Directory Tracking & Workspace Trust Permissions

## Deliverables Built
1. **Python CLI Package (Wheel & Sdist)**:
   - `dist/dart_agent-1.0.0-py3-none-any.whl`
   - `dist/dart_agent-1.0.0.tar.gz`
   - Dual script entry points in `pyproject.toml`: `drt` and `dart-agent`.
2. **Standalone Windows App Executables**:
   - `dist/dart-agent.exe` and `dist/drt.exe`
   - Copied globally to `C:\Users\javal\.cargo\bin\` and callable from any directory in CMD, PowerShell, or Git Bash.
3. **Global Shell Shims & Profile Integrations**:
   - Batch shims `drt.cmd` and `dart-agent.cmd` in Python Scripts PATH.
   - PowerShell profile functions for seamless argument forwarding in all PowerShell sessions.
4. **Dual Agentic Interface**:
   - **Human UX**: Rich-Click styled help menu, branded banner panels, toolkit tables, and status spinners.
   - **AI-Agent / Machine Mode (`--json`)**: Emits clean JSON lines (JSONL) on stdout for upstream automated agent calling and pipelines.

## Architecture
- `dart_agent/trust.py` -> Workspace trust management, canonical path resolution, persistence in `~/.dart-agent/trusted.json`, and interactive trust prompts.
- `dart_agent/cli.py` -> Rich-click CLI interface with argument groups, docked terminal loop, working directory switching (`--dir`), trust flags (`--trust`, `--no-trust`), and `/trust` REPL command.
- `dart_agent/ui.py` -> Dual-mode renderer, ANSI shaded logo, docked bottom bar, and workspace/trust summary badge.
- `dart_agent/agent.py` -> Core agent loop, dynamic workspace context in system prompt, thought tag parsing (`<thought>` / `<think>`), streaming accumulator, and tool dispatch.
- `dart_agent/tools.py` -> 5 core native system tools with OpenAI function calling schemas.
- `run_app.py` -> Bundling harness for PyInstaller.


## Features Implemented
- [x] Global `drt` short alias and `dart-agent` executable callable from anywhere
- [x] Dynamic working directory: runs in current working directory from where it was invoked, or custom directory via `--dir` / `-d`
- [x] Workspace trust permissions (`dart_agent/trust.py`):
  - Automatically checks `~/.dart-agent/trusted.json`
  - First-time interactive prompt: `? Trust workspace: <path> [Y/n]`
  - Trusted workspaces bypass manual confirmation prompts for all tools and commands
  - `--trust` / `-t` flag to force trust
  - `--no-trust` flag to enforce manual confirmation
  - Interactive REPL command `/trust` (`/trust on`, `/trust off`, `/trust list`)
  - Workspace directory and trust status displayed in startup configuration table
- [x] LLM system prompt dynamically informs model of the active working directory
- [x] Config: CLI args → env vars → .env → interactive prompts
- [x] Model discovery: fetch from `/v1/models`, interactive table selector
- [x] 5 tools: read_file, write_file, list_directory, execute_command, search_files
- [x] Thought extraction & styled panel: `<thought>` and `<think>` tags parsed into `💭 Thought Process` panel
- [x] Formatted Markdown response panel: clean final response rendered in `🎯 dart-agent` panel with syntax highlighting
- [x] 3D Shaded ANSI logo: 12-line shaded multi-color ANSI block font with adaptive stacking for 80-col terminals
- [x] Static docked bottom input: DECSTBM scroll margins keep the prompt fixed at the bottom while logs scroll
- [x] Non-streaming fallback (`--no-stream`)
- [x] Safety confirmation for shell commands (`Allow? [Y/n/always]`) in untrusted folders
- [x] Slash commands: /trust, /clear, /model, /help, /exit
- [x] Graceful Ctrl+C handling (interrupts agent run, doesn't exit)
- [x] Ctrl+D to close/exit the CLI tool
- [x] API key input masked with asterisks (character-by-character echo)
- [x] API key confirmation with masked display and length
- [x] Smart error messages for 429/404/403/timeout with actionable tips
- [x] Non-chat model filtering (hides embedding, tts, image, audio models from model list)
- [x] Smart default model suggestion during model selection
- [x] Gemini thought_signature preservation for tool call round-trips
- [x] Conversation history cleanup on interrupted runs
- [x] Output truncation (100K read, 50K command output, 200 search matches)
- [x] Binary file skip list for search
- [x] Noise directory skip list (.git, node_modules, __pycache__, etc.)
- [x] 30s API request timeout

## Providers Tested For
- OpenAI, Groq, Together, Ollama, OpenRouter, Cerebras
- TokenRouter (api.tokenrouter.com)
- Google Gemini (generativelanguage.googleapis.com)

## Default API Endpoint
- `https://api.tokenrouter.com/v1` (shown as default when prompting for Base URL)

## Changelog
- **2026-10-21** — Initial push to GitHub repository `AJAYMYTH/DartAgent`.
- **2026-10-20 (v1.3.0)** — Global `drt` alias, dynamic working directory & workspace trust:
  - Added global `drt` alias and `dart-agent` executables to `~/.cargo/bin` and Windows Scripts PATH.
  - Added PowerShell profile integration in `Microsoft.PowerShell_profile.ps1` for instant terminal access.
  - Automatically operates in the invoking terminal's current working directory or explicit `--dir` / `-d`.
  - Workspace directory dynamically passed to LLM system prompt (`## Current Workspace`).
  - Added persistent workspace trust system (`dart_agent/trust.py`) storing permissions in `~/.dart-agent/trusted.json`.
  - Interactive prompt on first run in an untrusted directory: `? Trust workspace: <path> [Y/n]`.
  - In trusted workspaces, all tools and shell commands are auto-approved without confirmation interruptions.
  - Added `/trust` interactive slash command (`/trust`, `/trust on`, `/trust off`, `/trust list`).
  - Added `--trust` (`-t`) and `--no-trust` CLI flags.
  - Rebuilt PyInstaller binaries and wheel/sdist distributions.
- **2026-10-20 (v1.2.0)** — Response formatting, docked input & ANSI shaded logo:
  - Added 12-line shaded 3D ANSI colored "DART AGENT" logo with automatic viewport detection (side-by-side on wide terminals, stacked on standard terminals).
  - Model thought tags (`<thought>...</thought>` and `<think>...</think>`) extracted into dedicated `💭 Thought Process` panels.
  - Model responses cleanly formatted in `🎯 dart-agent` Markdown panels with code syntax highlighting.
  - Docked static bottom input area using ANSI DECSTBM scroll margins so the prompt remains anchored at the bottom even during output scrolling.
  - Graceful fallback for non-interactive / small terminals.
- **2026-10-20 (v1.1.0)** — UX & reliability fixes:
  - Fixed streaming: replaced Rich Live (transient=True ate output) with direct stdout token streaming
  - API key prompt now shows asterisks `****` as you type/paste (not blank)
  - Ctrl+C interrupts agent mid-run (doesn't exit the REPL)
  - Ctrl+D cleanly exits the CLI tool
  - Better error messages for 429/404/timeout with tips
  - Model list filters out non-chat models (embedding, tts, image, etc.)
  - Preserves Gemini thought_signature on tool call round-trips
  - Default base URL changed to TokenRouter
  - 30s request timeout
- **2026-10-20 (v1.0.0)** — Initial build. All 5 phases complete.
