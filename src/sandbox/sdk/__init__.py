"""
Enhanced Sandbox SDK - Merging microsandbox and existing sandbox functionality

This module provides a unified interface for both local sandbox execution
and remote microsandbox-style execution with microVM isolation.
"""

# Version is read from package metadata to ensure consistency
import importlib.metadata

try:
    __version__ = importlib.metadata.version("sandbox")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.3.0-dev"

from .base_sandbox import BaseSandbox
from .local_sandbox import LocalSandbox
from .remote_sandbox import RemoteSandbox
from .python_sandbox import PythonSandbox
from .node_sandbox import NodeSandbox
from .execution import Execution
from .command_execution import CommandExecution
from .command import Command
from .metrics import Metrics
from .config import SandboxConfig, SandboxOptions

__all__ = [
    "BaseSandbox",
    "LocalSandbox", 
    "RemoteSandbox",
    "PythonSandbox",
    "NodeSandbox",
    "Execution",
    "CommandExecution",
    "Command",
    "Metrics",
    "SandboxConfig",
    "SandboxOptions",
]
