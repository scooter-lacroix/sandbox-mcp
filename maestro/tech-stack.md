# Technology Stack - Sandbox MCP Server

## Core

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.11+ | Primary language |
| FastMCP | 2.10.5+ | MCP protocol framework |

## Key Dependencies

| Library | Version | Purpose |
|---------|---------|---------|
| aiohttp | >=3.9.0 | Async HTTP client for sandbox operations |
| Manim | 0.19.0 | Mathematical animation rendering |
| Matplotlib | 3.8.4+ | Plot generation and capture |
| Pillow | 11.3.0+ | Image processing |
| IPython | 9.4.0+ | Interactive REPL |
| NumPy | 1.26.4+ | Numerical computing |
| scikit-learn | 1.5.2 | Machine learning utilities |
| seaborn | 0.12.0 | Statistical data visualization |
| ffmpeg-python | 0.2.0 | Video processing for animations |
| requests | 2.32.4+ | HTTP client for remote execution |
| psutil | 7.0.0+ | System resource monitoring |
| pytest | >=8.4.1 | Testing framework (271 tests passing) |

## Architecture

| Module | Purpose |
|--------|---------|
| sandbox/core/ | Shared core services (ExecutionContextService, ArtifactService, PatchManager) |
| sandbox/mcp/ | MCP server implementations (stdio, HTTP) |
| sandbox/sdk/ | SDK for programmatic access |
| sandbox/services/ | Business logic services (WebExportService, etc.) |

## Data Storage

| Technology | Purpose |
|------------|---------|
| SQLite3 | Session state persistence, execution history, artifact metadata |

## Entry Points

| Command | Purpose |
|---------|---------|
| `sandbox-server` | HTTP MCP server (web integration) |
| `sandbox-server-stdio` | stdio MCP server (AI app integration) |

## Development Tools

| Tool | Purpose |
|------|---------|
| uv | Package management and installation |
| pytest | Testing framework |
| hatchling | Build backend |
