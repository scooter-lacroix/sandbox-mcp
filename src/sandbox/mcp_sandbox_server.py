"""HTTP MCP Server for Sandbox MCP.

This server provides HTTP transport for the Sandbox MCP tools using FastMCP.
It uses the same tool registry and helper modules as the stdio server for consistency.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastmcp import FastMCP

from .core.execution_context import PersistentExecutionContext
from .core.execution_services import ExecutionContext
from .core.resource_manager import get_resource_manager
from .core.security import SecurityLevel, get_security_manager
from .server.catalog import SERVER_ID, SERVER_INSTRUCTIONS, register_catalog_primitives
from .server.session_service import get_session_service
from .server.tool_registry import create_tool_registry
from . import __version__

# Create FastMCP server with explicit instructions for discovery-oriented clients.
mcp = FastMCP(
    SERVER_ID,
    instructions=SERVER_INSTRUCTIONS,
    version=__version__,
)

# Create shared execution context using core services
ctx = ExecutionContext()
# Setup environment (logging happens in _setup_environment)
ctx._setup_environment()

resource_manager = get_resource_manager()
security_manager = get_security_manager(SecurityLevel.MEDIUM)
session_service = get_session_service()

# Create tool registry and register all tools (same as stdio server)
tool_registry = create_tool_registry(
    mcp,
    ctx,
    logger=None,  # HTTP server uses standard logging
    resource_manager=resource_manager,
    security_manager=security_manager,
    persistent_context_factory=PersistentExecutionContext,
    session_service=session_service,
)
tool_registry.register_all()
register_catalog_primitives(mcp)


def main() -> None:
    """Entry point for the HTTP MCP server."""
    host = os.getenv("SANDBOX_MCP_HOST", "127.0.0.1")
    port = int(os.getenv("SANDBOX_MCP_PORT", "8765"))
    mcp.run(transport="http", host=host, port=port)


if __name__ == "__main__":
    main()
