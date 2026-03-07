"""
Sandbox - Python Code Execution Environment

Enhanced Python code execution sandbox with FastMCP server integration,
designed for secure and feature-rich code execution with artifact management
and web application support.
"""

import importlib.metadata

try:
    __version__ = importlib.metadata.version("sandbox")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.3.0-dev"

__author__ = "Sandbox Development Team"
__description__ = "Enhanced Python code execution sandbox with microsandbox integration and FastMCP server support"

# Core modules
from . import server, utils
from . import mcp_sandbox_server, mcp_sandbox_server_stdio

# Enhanced SDK
from . import sdk
from .sdk.python_sandbox import PythonSandbox
from .sdk.node_sandbox import NodeSandbox
from .sdk.local_sandbox import LocalSandbox
from .sdk.remote_sandbox import RemoteSandbox
from .sdk.execution import Execution
from .sdk.command_execution import CommandExecution
from .sdk.config import SandboxConfig, SandboxOptions
from .core.execution_context import PersistentExecutionContext

__all__ = [
    'server',
    'utils', 
    'mcp_sandbox_server',
    'mcp_sandbox_server_stdio',
    'sdk',
    'PythonSandbox',
    'NodeSandbox',
    'LocalSandbox',
    'RemoteSandbox',
    'Execution',
    'CommandExecution',
    'SandboxConfig',
    'SandboxOptions',
    'PersistentExecutionContext',
    '__version__',
    '__author__',
    '__description__'
]
