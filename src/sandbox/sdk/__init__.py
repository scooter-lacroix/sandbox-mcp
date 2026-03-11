"""
Enhanced Sandbox SDK - Merging microsandbox and existing sandbox functionality

This module provides a unified interface for both local sandbox execution
and remote microsandbox-style execution with microVM isolation.
"""

from __future__ import annotations

# Version is read from package metadata to ensure consistency
import importlib.metadata

for _distribution_name in ("sandbox-mcp", "sandbox"):
    try:
        __version__ = importlib.metadata.version(_distribution_name)
        break
    except importlib.metadata.PackageNotFoundError:
        continue
else:
    __version__ = "0.1.0-dev"

# Core classes - always available
from .base_sandbox import BaseSandbox
from .local_sandbox import LocalSandbox
from .execution import Execution
from .command import Command
from .metrics import Metrics
from .config import SandboxConfig, SandboxOptions

# Lazy imports for optional features
from ..utils.lazy_imports import LazyClass

# Remote and Node sandboxes - lazy loaded (require aiohttp)
RemoteSandbox = LazyClass(
    "sandbox.sdk.remote_sandbox",
    "RemoteSandbox",
    install_hint="Install with: pip install sandbox-mcp[sdk-remote]",
)

NodeSandbox = LazyClass(
    "sandbox.sdk.node_sandbox",
    "NodeSandbox",
    install_hint="Install with: pip install sandbox-mcp[sdk-remote]",
)

# PythonSandbox - lazy loaded
PythonSandbox = LazyClass(
    "sandbox.sdk.python_sandbox",
    "PythonSandbox",
    install_hint="Ensure sandbox is properly installed",
)

# CommandExecution - lazy loaded
CommandExecution = LazyClass(
    "sandbox.sdk.command_execution",
    "CommandExecution",
    install_hint="Ensure sandbox is properly installed",
)

__all__ = [
    "BaseSandbox",
    "LocalSandbox",
    "RemoteSandbox",
    "NodeSandbox",
    "PythonSandbox",
    "Execution",
    "CommandExecution",
    "Command",
    "Metrics",
    "SandboxConfig",
    "SandboxOptions",
    "__version__",
]
