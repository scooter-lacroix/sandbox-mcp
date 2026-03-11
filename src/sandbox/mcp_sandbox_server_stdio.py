from __future__ import annotations

import logging
import os
import sys
import tempfile
from pathlib import Path

from fastmcp import FastMCP

from .core.execution_context import PersistentExecutionContext
from .core.execution_services import ExecutionContext
from .core.resource_manager import get_resource_manager
from .core.security import SecurityLevel, get_security_manager
from .server.catalog import SERVER_ID, SERVER_INSTRUCTIONS, register_catalog_primitives
from .server.tool_registry import create_tool_registry
from . import __version__

# Set up logging to file instead of stderr to avoid MCP protocol interference
log_file = Path(tempfile.gettempdir()) / "sandbox_mcp_server.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stderr)
        if os.getenv("SANDBOX_MCP_DEBUG")
        else logging.NullHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Create FastMCP server with explicit instructions for discovery-oriented clients.
mcp = FastMCP(
    SERVER_ID,
    instructions=SERVER_INSTRUCTIONS,
    version=__version__,
)

# Create shared execution context using core services
ctx = ExecutionContext()
# Setup environment and log configuration
ctx._setup_environment()
logger.info(f"Project root: {ctx.project_root}")
logger.info(
    f"Virtual env: {ctx.venv_path if ctx.venv_path.exists() else 'Not found'}"
)
logger.info(f"sys.executable: {sys.executable}")
logger.info(f"sys.path (first 5): {sys.path[:5]}")
logger.info(f"VIRTUAL_ENV: {os.environ.get('VIRTUAL_ENV', 'Not set')}")

resource_manager = get_resource_manager()
security_manager = get_security_manager(SecurityLevel.MEDIUM)

tool_registry = create_tool_registry(
    mcp,
    ctx,
    logger=logger,
    resource_manager=resource_manager,
    security_manager=security_manager,
    persistent_context_factory=PersistentExecutionContext,
)
tool_registry.register_all()
register_catalog_primitives(mcp)


def main() -> None:
    """Entry point for the stdio MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
