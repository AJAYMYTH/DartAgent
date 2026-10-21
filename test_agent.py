"""Integration test for dart-agent using TokenRouter API."""

from openai import OpenAI
from rich.console import Console
from dart_agent.agent import Agent
from dart_agent.ui import UI

client = OpenAI(
    base_url="https://api.tokenrouter.com/v1",
    api_key="sk-17s6DWNKbpSfj09vzuk721aV1zIYPZX3oxMqrAxLKAQut8PL",
    timeout=30.0,
)
console = Console()
ui = UI(console)
agent = Agent(client=client, model="google/gemini-3.8-flash", ui=ui)
agent.confirm_commands = False  # auto-approve for testing


def divider(label: str) -> None:
    console.print(f"\n[bold magenta]{'='*50}[/]")
    console.print(f"[bold magenta]  {label}[/]")
    console.print(f"[bold magenta]{'='*50}[/]")


# Test 1: Tool use — list directory
divider("TEST 1: List directory (list_directory tool)")
agent.run("List the files in the current directory. Top level only, be brief.")

# Test 2: Read a file
divider("TEST 2: Read a file (read_file tool)")
agent.clear()
agent.run("Read the pyproject.toml file and tell me the project name and its dependencies.")

# Test 3: Search across files
divider("TEST 3: Search files (search_files tool)")
agent.clear()
agent.run("Search for the word 'execute' in all .py files under the dart_agent folder. Show me what you find.")

# Test 4: Multi-tool chain (read + execute)
divider("TEST 4: Multi-step (read + execute)")
agent.clear()
agent.run("What Python version is being used? Run 'python --version' to find out.")

console.print(f"\n[bold green]{'='*50}[/]")
console.print("[bold green]  ALL TESTS COMPLETE[/]")
console.print(f"[bold green]{'='*50}[/]")
