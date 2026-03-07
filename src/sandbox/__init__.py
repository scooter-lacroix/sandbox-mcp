"""
Sandbox - Python Code Execution Environment

Enhanced Python code execution sandbox with FastMCP server integration,
designed for secure and feature-rich code execution with artifact management
and web application support.
"""

from __future__ import annotations

import importlib.metadata

try:
    __version__ = importlib.metadata.version("sandbox")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.3.0-dev"

__author__ = "Sandbox Development Team"
__description__ = "Enhanced Python code execution sandbox with microsandbox integration and FastMCP server support"

# Core modules (always available)
from . import utils

# Lazy imports for optional features
from .utils.lazy_imports import LazyClass, get_lazy_import

# Server modules - lazy loaded to avoid eager imports
server = get_lazy_import("sandbox.server")

# SDK - lazy loaded
sdk = get_lazy_import("sandbox.sdk")


def _get_python_sandbox() -> type:
    """Lazy loader for PythonSandbox."""
    from .sdk.python_sandbox import PythonSandbox
    return PythonSandbox


def _get_local_sandbox() -> type:
    """Lazy loader for LocalSandbox."""
    from .sdk.local_sandbox import LocalSandbox
    return LocalSandbox


def _get_remote_sandbox() -> type:
    """Lazy loader for RemoteSandbox."""
    from .sdk.remote_sandbox import RemoteSandbox
    return RemoteSandbox


def _get_node_sandbox() -> type:
    """Lazy loader for NodeSandbox."""
    from .sdk.node_sandbox import NodeSandbox
    return NodeSandbox


# Lazy class wrappers for sandbox implementations
PythonSandbox = LazyClass(
    "sandbox.sdk.python_sandbox",
    "PythonSandbox",
    install_hint="Ensure sandbox is properly installed",
)

LocalSandbox = LazyClass(
    "sandbox.sdk.local_sandbox",
    "LocalSandbox",
    install_hint="Ensure sandbox is properly installed",
)

RemoteSandbox = LazyClass(
    "sandbox.sdk.remote_sandbox",
    "RemoteSandbox",
    install_hint="Install with: pip install sandbox[sdk-remote]",
)

NodeSandbox = LazyClass(
    "sandbox.sdk.node_sandbox",
    "NodeSandbox",
    install_hint="Install with: pip install sandbox[sdk-remote]",
)

# Core execution context - always available
from .core.execution_context import PersistentExecutionContext

__all__ = [
    'utils',
    'server',
    'sdk',
    'PythonSandbox',
    'LocalSandbox',
    'RemoteSandbox',
    'NodeSandbox',
    'PersistentExecutionContext',
    '__version__',
    '__author__',
    '__description__',
]
