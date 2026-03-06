# Product Guide - Sandbox MCP Server

## Product Vision

Sandbox MCP Server is a secure Python code execution environment designed for AI assistants and power users. It provides a Model Context Protocol (MCP) server interface that enables seamless integration with AI applications like LM Studio, Claude Desktop, and VS Code/Cursor.

The project serves three primary purposes:

1. **AI Code Execution Sandbox** - A controlled environment for AI assistants to execute Python code safely
2. **MCP Server Provider** - Standardized MCP protocol integration for AI tool ecosystems
3. **Manim Animation Platform** - Mathematical animation generation capabilities for educational content

## Target Users

- **AI Application Developers** - Integrating AI capabilities into their applications
- **AI Power Users** - LM Studio, Claude Desktop, VS Code/Cursor users seeking enhanced AI coding tools
- **Educators and Researchers** - Creating educational content with mathematical animations

## Key Features

- **Automatic Artifact Management** - Captures and organizes plots, images, videos, and other generated files automatically
- **Persistent Execution Context** - Maintains state across code execution sessions with SQLite-backed persistence
- **Security and Resource Limits** - Controlled execution with directory access restrictions, timeout controls, and memory monitoring
- **Manim Animation Support** - Built-in support for creating mathematical animations with multiple quality presets
- **Dual Transport Support** - Both stdio (for AI apps) and HTTP (for web integration) MCP transports
- **Interactive REPL** - IPython-powered interactive shell with tab completion and magic commands
