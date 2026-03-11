# Sandbox MCP Server Configuration Guide

## Overview

The Sandbox MCP Server provides a general-purpose Python execution environment for MCP clients, with persistent execution state, artifact tracking, guarded shell access, Manim rendering, and lightweight Flask/Streamlit workflows.

## Key Features

- **Secure Code Execution**: Execute Python code in a controlled environment
- **Directory Management**: Controlled access to directories within user home
- **Artifact Tracking**: Automatic tracking and categorization of generated files
- **Persistent Sessions**: Maintain state across executions
- **Enhanced Security**: Built-in security monitoring and access controls
- **Verbose Logging**: Detailed logging for debugging and audit trails

## Installation

### Local Installation
```bash
# Clone and install
git clone https://github.com/scooter-lacroix/sandbox-mcp.git
cd sandbox-mcp
uv pip install -e .

# Or install from package
pip install sandbox-mcp
```

### Direct UV Installation
```bash
uvx git+https://github.com/scooter-lacroix/sandbox-mcp.git
```

## Configuration Examples

### 1. LM Studio

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

### 2. Claude Desktop

```json
{
  "mcpServers": {
    "sandbox": {
      "command": "sandbox-server-stdio",
      "args": [],
      "env": {}
    }
  }
}
```

### 3. VS Code / Cursor / Windsurf

#### Using MCP Extension
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

#### Using Continue Extension
```json
{
  "mcpServers": [
    {
      "name": "sandbox",
      "command": "sandbox-server-stdio",
      "args": [],
      "env": {}
    }
  ]
}
```

### 4. Jan AI

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

### 5. OpenHands

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

### 6. HTTP/HTTPS Server Mode

For web-based integrations and hosted MCP directory listings:

```bash
# Start HTTP server
python -m sandbox.mcp_sandbox_server

# Optional for hosted deployments
SANDBOX_MCP_HOST=0.0.0.0 SANDBOX_MCP_PORT=8765 python -m sandbox.mcp_sandbox_server

# Or using the convenience script
python run_sandbox.py mcp-http
```

Configuration:
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

### Marketplace Deployment Notes

If you plan to publish a hosted endpoint on MCPHub or a similar directory:

- Put the HTTP server behind TLS termination and authentication.
- Treat the sandbox as a guarded environment, not as a hardened isolation boundary.
- Consider an outer isolation layer such as Docker or a VM for internet-facing deployments.
- Keep listing metadata aligned with `README.md`, `docs/marketplace.md`, and `docs/marketplace-profile.json`.

### 7. Git Link Installation

For environments that support git installation:

```json
{
  "mcpServers": {
    "sandbox": {
      "command": "uvx",
      "args": [
        "git+https://github.com/scooter-lacroix/sandbox-mcp.git"
      ],
      "env": {}
    }
  }
}
```

## Environment Variables

### Required
- `VIRTUAL_ENV`: Path to Python virtual environment (auto-detected)
- `HOME`: User home directory (auto-detected)

### Optional
- `SANDBOX_LOG_LEVEL`: Set logging level (DEBUG, INFO, WARNING, ERROR)
- `SANDBOX_MAX_EXECUTION_TIME`: Maximum execution time in seconds (default: 300)
- `SANDBOX_MEMORY_LIMIT`: Memory limit in MB (default: 512)
- `SANDBOX_ARTIFACT_DIR`: Custom artifact directory path

## Available Tools

### Core Execution
- `execute_python`: Execute Python code with validation and artifact tracking
- `get_execution_history`: Retrieve execution history with filtering
- `clear_execution_cache`: Clear compilation and execution cache

### Directory Management
- `change_working_directory`: Change to different directory within home
- `list_directory`: List directory contents with security checks
- `find_files`: Search for files with glob patterns
- `reset_to_default_directory`: Return to default sandbox area
- `get_current_directory_info`: Get current directory status

### Artifact Management
- `list_artifacts`: List all generated artifacts with categorization
- `get_artifact_report`: Get comprehensive artifact statistics
- `categorize_artifacts`: Organize artifacts by type
- `cleanup_artifacts`: Clean up artifacts by type or all

### Session Management
- `get_session_info`: Get current session information
- `save_session`: Manually save session state
- `get_performance_stats`: Get execution performance metrics

### Security & Monitoring
- `get_security_status`: Get security audit information
- `get_system_info`: Get system and environment information

## Security Features

### Directory Access Control
- Restricts access to user home directory and subdirectories
- Prevents unauthorized access to system directories
- Logs all directory change attempts
- Automatic reset to default directory after operations

### Code Validation
- Syntax checking before execution
- Security pattern detection
- Import validation
- Resource usage monitoring

### Audit Logging
- Detailed execution logging
- Security violation tracking
- Performance metrics collection
- Error details preservation

## Usage Examples

### Basic Code Execution
```python
# Execute simple Python code
result = execute_python("print('Hello, World!')")

# Execute with validation
result = execute_python("import numpy as np; print(np.__version__)", validate=True)
```

### Directory Operations
```python
# Change to a different directory
change_working_directory("/home/user/Documents")

# List directory contents
list_directory("/home/user/Projects", include_hidden=True)

# Find Python files
find_files("*.py", "/home/user/Projects")

# Reset to default
reset_to_default_directory()
```

### Artifact Management
```python
# List all artifacts
artifacts = list_artifacts(format_type="detailed")

# Get artifact report
report = get_artifact_report()

# Clean up image artifacts
cleanup_artifacts_by_type("images")
```

## Troubleshooting

### Common Issues

1. **Permission Denied**: Ensure the executable has proper permissions
   ```bash
   chmod +x ~/.venv/bin/sandbox-server-stdio
   ```

2. **Module Not Found**: Reinstall the package
   ```bash
   uv pip install -e . --force-reinstall
   ```

3. **Virtual Environment Issues**: Verify virtual environment activation
   ```bash
   source ~/.venv/bin/activate
   python -c "import sandbox; print('OK')"
   ```

### Debug Mode

Enable debug logging:
```bash
export SANDBOX_LOG_LEVEL=DEBUG
sandbox-server-stdio
```

### Health Check

Test the server:
```bash
echo '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}' | sandbox-server-stdio
```

## Advanced Configuration

### Custom Artifact Directory
```json
{
  "sandbox": {
    "command": "sandbox-server-stdio",
    "env": {
      "SANDBOX_ARTIFACT_DIR": "/home/user/custom-artifacts"
    }
  }
}
```

### Memory and Time Limits
```json
{
  "sandbox": {
    "command": "sandbox-server-stdio",
    "env": {
      "SANDBOX_MEMORY_LIMIT": "1024",
      "SANDBOX_MAX_EXECUTION_TIME": "600"
    }
  }
}
```

### Security Level
```json
{
  "sandbox": {
    "command": "sandbox-server-stdio",
    "env": {
      "SANDBOX_SECURITY_LEVEL": "high"
    }
  }
}
```

## Performance Optimization

### For High-Volume Usage
- Increase memory limits
- Use compilation caching
- Enable persistent sessions
- Monitor resource usage

### For Security-Critical Environments
- Set security level to "high"
- Enable comprehensive logging
- Use restricted directory access
- Monitor security violations

## Support

For issues and support:
1. Check the troubleshooting section
2. Review logs for detailed error information
3. Verify configuration syntax
4. Test with minimal configuration first

## License

This project is licensed under the [Apache License 2.0](LICENSE) - see the LICENSE file for details.
