# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## CRITICAL: LeIndex MCP Requirement

**LeIndex MCP MUST be used for ALL code analysis actions.** NEVER use standard search, read, grep, or glob tools. LeIndex tools ALWAYS take precedence.

- Use `leindex_project_map` for codebase structure
- Use `leindex_file_summary` for file analysis (supersedes Read)
- Use `leindex_search` for semantic code search
- Use `leindex_grep_symbols` for symbol-aware searching (supersedes Grep)
- Use `leindex_read_symbol` for reading specific symbols
- Use `leindex_symbol_lookup` for finding definitions and relationships

Only use Bash for system commands, never for code/file operations.

## Project Overview

Sandbox MCP Server is a secure Python code execution environment with Model Context Protocol (MCP) server integration. It provides sandboxed execution, artifact management, Manim animation support, and web application hosting capabilities.

## Development Commands

```bash
# Installation (editable mode)
uv pip install -e .

# Run the MCP stdio server (for LM Studio, Claude Desktop)
sandbox-server-stdio

# Run the HTTP MCP server
python -m sandbox.mcp_sandbox_server --port 8765

# Run tests
uv run pytest tests/

# Run specific test file
uv run pytest tests/test_integration.py

# Check test with verbose output
uv run pytest tests/ -v
```

## Architecture

### Entry Points
- `sandbox-server` → HTTP MCP server (`src/sandbox/mcp_sandbox_server.py`)
- `sandbox-server-stdio` → stdio MCP server (`src/sandbox/mcp_sandbox_server_stdio.py`)

### Core Modules

**SDK Layer** (`src/sandbox/sdk/`)
- `LocalSandbox` - Local Python execution environment with artifact capture
- `PythonSandbox` - Factory for creating local or remote Python sandboxes
- `NodeSandbox` - Node.js execution environment
- `RemoteSandbox` - Microsandbox microVM integration
- `SandboxOptions` - Builder pattern configuration
- `Execution` / `CommandExecution` - Result types for code and shell execution

**Core Layer** (`src/sandbox/core/`)
- `PersistentExecutionContext` - Heart of the system: manages execution state, artifacts (matplotlib/PIL capture), SQLite persistence, directory security
- `CodeValidator` - Input validation and formatting
- `SecurityManager` - Command filtering and access control
- `ResourceManager` - Process and cleanup management
- `ManimSupport` - Mathematical animation rendering

**MCP Server Layer**
- Uses FastMCP for protocol implementation
- Provides 12+ tools: execute, shell_execute, create_manim_animation, list_artifacts, cleanup_artifacts, start_web_app, etc.
- Dual transport: stdio (for AI apps) and HTTP (for web integration)

### Key Architectural Patterns

**State Persistence**: Session state is stored in SQLite at `sessions/{session_id}/state.db` with automatic serialization (JSON + pickle fallback).

**Artifact Capture**: Monkey-patches `matplotlib.pyplot.show()` and `PIL.Image.show()` to automatically capture plots and images to the artifacts directory.

**Directory Security**: `DirectoryChangeMonitor` enforces that file operations stay within the user's home directory.

**Virtual Environment Detection**: Automatically detects `.venv` and configures `sys.path` to include site-packages for proper package imports.

**Compilation Caching**: Compiled code objects are cached in-memory for repeated executions with the same `cache_key`.

## Project Structure Notes

- **Session Layout**: Each execution session creates `sessions/{session_id}/` with subdirectories for `artifacts/`, `plots/`, `images/`, `videos/`, `manim/`, etc.
- **Project Root Detection**: Walks up from `__file__` looking for `pyproject.toml`, `setup.py`, `.git`, or `README.md`.
- **Entry Points**: Defined in `pyproject.toml` under `[project.scripts]`

## Common Patterns

### Adding a New MCP Tool
1. Add a FastMCP-decorated function to the server class in `mcp_sandbox_server_stdio.py`
2. Use the `ExecutionContext` instance for execution/state operations
3. Return structured JSON responses

### Extending Artifact Categories
Modify `PersistentExecutionContext.categorize_artifacts()` to add new file type mappings and category directories.

### Testing Sandbox Behavior
Use `LocalSandbox` directly with async context managers:
```python
async with LocalSandbox.create(name="test") as sandbox:
    result = await sandbox.run("print('hello')")
```
