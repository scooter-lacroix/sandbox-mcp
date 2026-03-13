# Sandbox MCP

<!-- mcp-name: io.github.scooter-lacroix/sandbox-mcp -->

> General-purpose Python execution sandbox for MCP clients, with persistent execution, artifact capture, Manim rendering, guarded shell access, and lightweight web app workflows.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastMCP](https://img.shields.io/badge/FastMCP-2.10.5-green.svg)](https://github.com/jlowin/fastmcp)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

Sandbox MCP is designed to stay broadly useful across coding assistants and MCP directories. It can run Python, generate plots and files, render Manim animations, launch or export small Flask/Streamlit demos, and expose prompts/resources that help an LLM discover how to use the sandbox well.

## 🎬 Demo: Manim Animation in Action

See the Sandbox MCP server creating beautiful mathematical animations with Manim:

<div align="center">
  <img src="examples/SquareToCircle.gif" alt="Manim Animation Demo" width="480" height="360">
</div>

**Alternative formats**: [MP4 Video](examples/SquareToCircle.mp4) | [GIF Animation](examples/SquareToCircle.gif)

*Example: 3D mathematical animation generated automatically by the sandbox*

## 🚀 Quick Start

### One-Line Install (Recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/scooter-lacroix/sandbox-mcp/main/install.sh | bash
```

This will:
- Install sandbox-mcp globally using `uv tool`
- Auto-configure all detected MCP clients (Claude, Cursor, Windsurf, VS Code, Zed, etc.)
- Star the repository
- Work with externally-managed Python environments

### Manual Install

```bash
# Clone the repository
git clone https://github.com/scooter-lacroix/sandbox-mcp.git
cd sandbox-mcp

# Install globally with uv tool
uv tool install --force --editable .

# Or install in venv
uv venv && uv pip install -e .

# Run the MCP server
sandbox-server-stdio
```

## ✨ Features

### 🔧 **Enhanced Python Execution**
- **Code Validation**: Automatic input validation and formatting
- **Virtual Environment**: Auto-detects and activates `.venv`
- **Persistent Context**: Variables persist across executions
- **Enhanced Error Handling**: Detailed diagnostics with colored output
- **Interactive REPL**: Real-time Python shell with tab completion

### 🎨 **Intelligent Artifact Management**
- **Automatic Capture**: Matplotlib plots and PIL images
- **Categorization**: Smart file type detection and organization
- **Multiple Formats**: JSON, CSV, and structured output
- **Recursive Scanning**: Deep directory traversal
- **Smart Cleanup**: Configurable cleanup by type or age

### 🎬 **Manim Animation Support**
- **Pre-compiled Examples**: One-click animation execution
- **Quality Control**: Multiple rendering presets
- **Video Generation**: Auto-saves MP4 animations
- **Example Library**: Built-in templates and tutorials
- **Environment Verification**: Automatic dependency checking

### 🌐 **Web Application Hosting**
- **Flask & Streamlit**: Launch web apps with auto port detection
- **Process Management**: Track and manage running servers
- **URL Generation**: Returns accessible endpoints

### 🔒 **Security & Safety**
- **Command Filtering**: Blocks dangerous shell commands (configurable)
- **Guarded Execution**: Code runs with resource limits and timeouts
- **Timeout Control**: Configurable execution limits (default 30s)
- **Resource Monitoring**: Memory and CPU usage tracking
- **Multiple Isolation Levels**: In-process, process pool, worktree, and container
- **Note**: This is a *guarded execution environment*, not a strongly isolated sandbox. For production use with untrusted code, consider running in a container or VM.

### 🛡️ **Isolation Levels**
Choose the right isolation level for your use case:

| Level | Isolation | Performance | Use Case |
|-------|-----------|-------------|----------|
| **In-Process** | Session globals only | ⭐⭐⭐⭐⭐ | Single LLM, trusted code |
| **Process Pool** | Process-level module isolation | ⭐⭐⭐⭐ | Multiple LLMs, resource limits |
| **Worktree** | Filesystem isolation via git | ⭐⭐⭐ | Parallel development workflows |
| **Container** | Full OS-level isolation | ⭐⭐ | Untrusted code, production |

**Process Pool Example:**
```python
from sandbox.sdk import LocalSandbox, SandboxConfig, IsolationLevel

config = SandboxConfig(
    isolation_level=IsolationLevel.PROCESS_POOL,
    max_workers=4,
    memory_limit_mb=256,
)

async with LocalSandbox.create(name="my-session", config=config) as sandbox:
    result = await sandbox.run("print('Isolated execution')")
```

See [SECURITY.md](SECURITY.md) for detailed threat model and isolation strategies.

### 🔌 **MCP Integration**
- **Dual Transport**: HTTP and stdio support
- **LM Studio Ready**: Drop-in AI model integration
- **FastMCP Powered**: Modern MCP implementation
- **Discoverable Interface Surface**: Tools, prompts, resources, skills, and interactive templates

## 📦 Installation

### Prerequisites
- Python 3.11+
- uv (recommended) or pip

### Method 1: Install from PyPI (Recommended)

Install the latest stable release from PyPI:

```bash
# Using uv (fastest)
uv pip install sandbox-mcp

# Or using pip
pip install sandbox-mcp
```

For immediate use with AI applications:

```bash
# Run directly with uvx
uvx sandbox-mcp
```

### Method 2: Direct Git Installation

For the latest development version:

```bash
# Using uv
uvx git+https://github.com/scooter-lacroix/sandbox-mcp.git

# Or clone and install
git clone https://github.com/scooter-lacroix/sandbox-mcp.git
cd sandbox-mcp
uv venv
uv pip install -e .
```

### Method 3: Development Installation

For contributing or customization:

#### Using uv (Recommended)

```bash
git clone https://github.com/scooter-lacroix/sandbox-mcp.git
cd sandbox-mcp
uv venv
uv pip install -e ".[dev]"
```

#### Using pip

```bash
git clone https://github.com/scooter-lacroix/sandbox-mcp.git
cd sandbox-mcp
python -m venv .venv
# On Linux/Mac:
source .venv/bin/activate
# On Windows:
# .venv\\Scripts\\activate
pip install -e ".[dev]"
```

### Verify Installation

```bash
# Check version
sandbox-mcp --version

# Test HTTP server
sandbox-server --help

# Test stdio server
sandbox-mcp --help
```


## 🖥️ Usage
## 🖥️ Usage

### Command Line Interface

```bash
# Start HTTP server (web integration)
sandbox-server

# Start stdio server (LM Studio integration)
sandbox-mcp

# Backward-compatible stdio alias
sandbox-server-stdio
```

### MCP Integration

The Sandbox MCP server supports multiple integration methods:

#### Method 1: Direct Git Integration (Recommended)

For LM Studio, Claude Desktop, VS Code, and other MCP-compatible applications:

```json
{
  "mcpServers": {
    "sandbox": {
      "command": "uvx",
      "args": ["git+https://github.com/scooter-lacroix/sandbox-mcp.git"],
      "env": {},
      "start_on_launch": true
    }
  }
}
```

#### Method 2: Local Installation

For locally installed versions:

```json
{
  "mcpServers": {
    "sandbox": {
      "command": "sandbox-server-stdio",
      "args": [],
      "env": {},
      "start_on_launch": true
    }
  }
}
```

#### Method 3: HTTP Server Mode

For web-based integrations:

```bash
# Start HTTP server
python -m sandbox.mcp_sandbox_server --port 8765
```

Then configure your application:

```json
{
  "mcpServers": {
    "sandbox": {
      "transport": "http",
      "url": "http://localhost:8765/mcp",
      "headers": {
        "Authorization": "Bearer your-token-here"
      }
    }
  }
}
```

#### Application-Specific Configurations

**VS Code/Cursor/Windsurf** (using MCP extension):
```json
{
  "mcp.servers": {
    "sandbox": {
      "command": "sandbox-server-stdio",
      "args": [],
      "env": {},
      "transport": "stdio"
    }
  }
}
```

**Jan AI**:
```json
{
  "mcp_servers": {
    "sandbox": {
      "command": "sandbox-server-stdio",
      "args": [],
      "env": {}
    }
  }
}
```

**OpenHands**:
```json
{
  "mcp": {
    "servers": {
      "sandbox": {
        "command": "sandbox-server-stdio",
        "args": [],
        "env": {}
      }
    }
  }
}
```

### Available MCP Tools

Sandbox MCP exposes a broader tool surface than the quick table below. For the machine-readable catalog used by marketplace-style listings, see [`docs/marketplace-profile.json`](docs/marketplace-profile.json).

| Tool | Description |
|------|-------------|
| `execute` | Execute Python code with artifact capture |
| `shell_execute` | Execute shell commands safely with security filtering |
| `list_artifacts` | List generated artifacts |
| `cleanup_artifacts` | Clean up temporary files |
| `get_execution_info` | Get environment diagnostics |
| `start_repl` | Start interactive session |
| `start_web_app` | Launch Flask/Streamlit apps |
| `cleanup_temp_artifacts` | Maintenance operations |
| `create_manim_animation` | Create mathematical animations using Manim |
| `list_manim_animations` | List all created Manim animations |
| `cleanup_manim_animation` | Clean up specific animation files |
| `get_manim_examples` | Get example Manim code snippets |

### Skills, Prompts, and Resources

- **Skill**: `manim_storyboard_skill` turns a concept into a storyboard, ready-to-render Manim code, and a suggested sandbox workflow.
- **Interactive template**: `manim_scene_template` creates a focused Manim scene from a concept, duration target, and quality preset.
- **Interactive template**: `sandbox_example_template` creates runnable artifact-focused examples for plots, images, tables, or generated files.
- **Interactive template**: `sandbox_web_app_template` creates small Flask or Streamlit demos ready for `start_web_app` or `export_web_app`.
- **Resource**: `sandbox://server/overview` exposes a succinct server summary and capability map.
- **Resource**: `sandbox://catalog/interfaces` exposes a machine-readable list of tools, prompts, resources, skills, and templates.

### Hosted Deployment Notes

For local IDE assistants, use `sandbox-server-stdio`. For remote or directory-hosted use cases such as MCPHub-compatible listings, run the HTTP server behind TLS and authentication, then point clients at the Streamable HTTP endpoint:

```bash
python -m sandbox.mcp_sandbox_server

# Optional for hosted deployments
SANDBOX_MCP_HOST=0.0.0.0 SANDBOX_MCP_PORT=8765 python -m sandbox.mcp_sandbox_server
```

Deployment checklist:
- Put the HTTP transport behind a reverse proxy or ingress that terminates TLS.
- Add authentication before exposing the server outside a trusted network.
- Treat this as a guarded execution environment, not a hardened isolation boundary.
- Use `export_web_app` and `build_docker_image` when you want to turn sandbox-generated demos into deployable examples.
- Keep marketplace metadata in sync with [`docs/marketplace-profile.json`](docs/marketplace-profile.json) and deployment notes in [`docs/marketplace.md`](docs/marketplace.md).

## 💡 Examples

### Enhanced SDK Usage

#### Local Python Execution

```python
import asyncio
from sandbox import PythonSandbox

async def local_example():
    async with PythonSandbox.create_local(name="my-sandbox") as sandbox:
        # Execute Python code
        result = await sandbox.run("print('Hello from local sandbox!')")
        print(await result.output())
        
        # Execute code with artifacts
        plot_code = """
import matplotlib.pyplot as plt
import numpy as np

x = np.linspace(0, 10, 100)
y = np.sin(x)

plt.figure(figsize=(8, 6))
plt.plot(x, y)
plt.title('Sine Wave')
plt.show()  # Automatically captured as artifact
"""
        result = await sandbox.run(plot_code)
        print(f"Artifacts created: {result.artifacts}")
        
        # Execute shell commands
        cmd_result = await sandbox.command.run("ls", ["-la"])
        print(await cmd_result.output())

asyncio.run(local_example())
```

#### Remote Python Execution (with microsandbox)

```python
import asyncio
from sandbox import PythonSandbox

async def remote_example():
    async with PythonSandbox.create_remote(
        server_url="http://127.0.0.1:5555",
        api_key="your-api-key",
        name="remote-sandbox"
    ) as sandbox:
        # Execute Python code in secure microVM
        result = await sandbox.run("print('Hello from microVM!')")
        print(await result.output())
        
        # Get sandbox metrics
        metrics = await sandbox.metrics.all()
        print(f"CPU usage: {metrics.get('cpu_usage', 0)}%")
        print(f"Memory usage: {metrics.get('memory_usage', 0)} MB")

asyncio.run(remote_example())
```

#### Node.js Execution

```python
import asyncio
from sandbox import NodeSandbox

async def node_example():
    async with NodeSandbox.create(
        server_url="http://127.0.0.1:5555",
        api_key="your-api-key",
        name="node-sandbox"
    ) as sandbox:
        # Execute JavaScript code
        js_code = """
console.log('Hello from Node.js!');
const sum = [1, 2, 3, 4, 5].reduce((a, b) => a + b, 0);
console.log(`Sum: ${sum}`);
"""
        result = await sandbox.run(js_code)
        print(await result.output())

asyncio.run(node_example())
```

#### Builder Pattern Configuration

```python
import asyncio
from sandbox import LocalSandbox, SandboxOptions

async def builder_example():
    config = (SandboxOptions.builder()
              .name("configured-sandbox")
              .memory(1024)
              .cpus(2.0)
              .timeout(300.0)
              .env("DEBUG", "true")
              .build())
    
    async with LocalSandbox.create(**config.__dict__) as sandbox:
        result = await sandbox.run("import os; print(os.environ.get('DEBUG'))")
        print(await result.output())  # Should print: true

asyncio.run(builder_example())
```

### MCP Server Examples

#### Basic Python Execution

```python
# Execute simple code
result = execute(code="print('Hello, World!')")
```

### Matplotlib Artifact Generation

```python
code = """
import matplotlib.pyplot as plt
import numpy as np

# Generate plot
x = np.linspace(0, 10, 100)
y = np.sin(x)

plt.figure(figsize=(8, 6))
plt.plot(x, y, 'b-', linewidth=2)
plt.title('Sine Wave')
plt.xlabel('x')
plt.ylabel('sin(x)')
plt.grid(True)
plt.show()  # Automatically captured as artifact
"""

result = execute(code)
# Returns JSON with base64-encoded PNG
```

### Flask Web Application

```python
flask_code = """
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return '<h1>Sandbox Flask App</h1>'

@app.route('/api/status')
def status():
    return jsonify({"status": "running", "server": "sandbox"})
"""

result = start_web_app(flask_code, "flask")
# Returns URL where app is accessible
```

### Shell Command Execution

```python
# Install packages via shell
result = shell_execute("uv pip install matplotlib")

# Check environment
result = shell_execute("which python")

# List directory contents
result = shell_execute("ls -la")

# Custom working directory and timeout
result = shell_execute(
    "find . -name '*.py' | head -10", 
    working_directory="/path/to/search",
    timeout=60
)
```

### Manim Animation Creation

```python
# Simple circle animation
manim_code = """
from manim import *

class SimpleCircle(Scene):
    def construct(self):
        circle = Circle()
        circle.set_fill(PINK, opacity=0.5)
        self.play(Create(circle))
        self.wait(1)
"""

result = create_manim_animation(manim_code, quality="medium_quality")
# Returns JSON with video path and metadata

# Mathematical graph visualization
math_animation = """
from manim import *

class GraphPlot(Scene):
    def construct(self):
        axes = Axes(
            x_range=[-3, 3, 1],
            y_range=[-3, 3, 1],
            x_length=6,
            y_length=6
        )
        axes.add_coordinates()
        
        graph = axes.plot(lambda x: x**2, color=BLUE)
        graph_label = axes.get_graph_label(graph, label="f(x) = x^2")
        
        self.play(Create(axes))
        self.play(Create(graph))
        self.play(Write(graph_label))
        self.wait(1)
"""

result = create_manim_animation(math_animation, quality="high_quality")

# List all animations
animations = list_manim_animations()

# Get example code snippets
examples = get_manim_examples()
```

### Error Handling

```python
# Import error with detailed diagnostics
result = execute(code="import nonexistent_module")
# Returns structured error with sys.path info

# Security-blocked shell command
result = shell_execute("rm -rf /")
# Returns security error with blocked pattern info
```

## 🏗️ Architecture

### Project Structure

```
sandbox-mcp/
├── src/
│   └── sandbox/                   # Main package
│       ├── __init__.py           # Package initialization
│       ├── mcp_sandbox_server.py # HTTP MCP server
│       ├── mcp_sandbox_server_stdio.py # stdio MCP server
│       ├── server/               # Server modules
│       │   ├── __init__.py
│       │   └── main.py
│       └── utils/                # Utility modules
│           ├── __init__.py
│           └── helpers.py
├── tests/
│   ├── test_integration.py       # Main test suite
│   └── test_simple_integration.py
├── pyproject.toml                # Package configuration
├── README.md                     # This file
├── .gitignore
└── uv.lock                       # Dependency lock file
```

### Core Components

#### ExecutionContext
Manages the execution environment:
- **Project Root Detection**: Dynamic path resolution
- **Virtual Environment**: Auto-detection and activation
- **sys.path Management**: Intelligent path handling
- **Artifact Management**: Temporary directory lifecycle
- **Global State**: Persistent execution context

#### Monkey Patching System
Non-intrusive artifact capture:
- **matplotlib.pyplot.show()**: Intercepts and saves plots
- **PIL.Image.show()**: Captures image displays
- **Conditional Patching**: Only applies if libraries available
- **Original Functionality**: Preserved through wrapper functions

#### MCP Integration
FastMCP-powered server with:
- **Dual Transport**: HTTP and stdio protocols
- **Tool Registry**: 7 available MCP tools
- **Streaming Support**: Ready for real-time interaction
- **Error Handling**: Structured error responses

## 🔒 Security Model

**Important**: Sandbox MCP is designed for **single-user development scenarios**, not multi-tenant production use.

### What It Provides
✅ Isolated execution contexts for LLM code generation
✅ Artifact management and capture
✅ Path traversal prevention
✅ Session isolation

### What It Does NOT Provide
❌ Multi-tenant isolation
❌ Protection against malicious code
❌ Process-level security boundaries

For production use or multi-tenant scenarios, use **RemoteSandbox** with container isolation.

See [SECURITY.md](SECURITY.md) for complete threat model.

## 📚 Documentation

For comprehensive usage information, troubleshooting guides, and advanced features:

- **[FAQ and Limitations](docs/FAQ_AND_LIMITATIONS.md)** - Common issues and sandbox restrictions
- **[Enhanced Features Guide](ENHANCED_FEATURES.md)** - Advanced capabilities and examples
- **[API Reference](src/sandbox/)** - Complete API documentation

## 🧪 Testing

Run the test suite to verify installation:

```bash
uv run pytest tests/ -v
```

Test categories include:
- Package import and sys.path tests
- Error handling and ImportError reporting
- Artifact capture (matplotlib/PIL)
- Web application launching
- Virtual environment detection

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests: `uv run pytest`
4. Submit a pull request

For development setup:
```bash
uv venv && uv pip install -e ".[dev]"
```

## License

[Apache License](LICENSE)

## Attribution

This project includes minor inspiration from:

- **[Microsandbox](https://github.com/microsandbox/microsandbox.git)** - Referenced for secure microVM isolation concepts

The majority of the functionality in this project is original implementation focused on MCP server integration and enhanced Python execution environments.

## Changelog

### v0.3.0 (Enhanced SDK Release)
- **🚀 Enhanced SDK**: Complete integration with microsandbox functionality
- **🔄 Unified API**: Single interface for both local and remote execution
- **🛡️ MicroVM Support**: Secure remote execution via microsandbox server
- **🌐 Multi-Language**: Python and Node.js execution environments
- **🏗️ Builder Pattern**: Fluent configuration API with SandboxOptions
- **📊 Metrics & Monitoring**: Real-time resource usage tracking
- **⚡ Async/Await**: Modern Python async support throughout
- **🔒 Enhanced Security**: Improved command filtering and validation
- **📦 Artifact Management**: Comprehensive file artifact handling
- **🎯 Command Execution**: Safe shell command execution with timeouts
- **🔧 Configuration**: Flexible sandbox configuration options
- **📝 Documentation**: Comprehensive examples and usage guides

### v0.2.0
- **Manim Integration**: Complete mathematical animation support
- **4 New MCP Tools**: create_manim_animation, list_manim_animations, cleanup_manim_animation, get_manim_examples
- **Quality Control**: Multiple animation quality presets
- **Video Artifacts**: Auto-saves MP4 animations to artifacts directory
- **Example Library**: Built-in Manim code examples
- **Virtual Environment Manim**: Uses venv-installed Manim executable

### v0.1.0
- Initial enhanced package structure
- Dynamic project root detection
- Robust virtual environment integration
- Enhanced error handling with detailed tracebacks
- Artifact management with matplotlib/PIL support
- Web application launching (Flask/Streamlit)
- Comprehensive test suite
- MCP server integration (HTTP and stdio)
- CLI entry points
- LM Studio compatibility
