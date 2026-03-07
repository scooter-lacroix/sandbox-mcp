"""
Unified Execution Services for Sandbox MCP.

This module consolidates duplicate execution context logic from both
MCP servers (stdio and HTTP) into a single source of truth.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from collections import OrderedDict


class ExecutionContext:
    """
    Unified execution context for sandbox environments.
    
    This class replaces the duplicate ExecutionContext classes
    in mcp_sandbox_server_stdio.py and mcp_sandbox_server.py.
    """
    
    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize execution context.
        
        Args:
            project_root: Optional project root path. If not provided,
                         will be computed from current file location.
        """
        if project_root is None:
            # Compute project_root dynamically from current file location
            current_file = Path(__file__).resolve()
            if 'src/sandbox/core' in str(current_file):
                # Installed package: go from src/sandbox/core to project root
                self.project_root = current_file.parent.parent.parent
            else:
                # Development: assume file is in project root
                self.project_root = current_file.parent
        
        # Set up sandbox working area one level above project root
        self.sandbox_area = self.project_root.parent / "sandbox_area"
        self.sandbox_area.mkdir(exist_ok=True)
        
        self.venv_path = self.project_root / ".venv"
        self.artifacts_dir: Optional[Path] = None
        self.web_servers: Dict[str, Any] = {}  # Track running web servers
        self.execution_globals: Dict[str, Any] = {}  # Persistent globals
        self.compilation_cache: Dict[str, Any] = {}  # Cache for compiled code
        self.cache_hits = 0
        self.cache_misses = 0


class ExecutionContextService:
    """
    Service for managing execution contexts.
    
    This service provides a unified interface for creating and managing
    execution contexts, replacing duplicate logic in both MCP servers.
    """
    
    def __init__(self):
        """Initialize the execution context service."""
        self._contexts: Dict[str, ExecutionContext] = {}
    
    def create_context(self, context_id: Optional[str] = None) -> ExecutionContext:
        """
        Create a new execution context.
        
        Args:
            context_id: Optional context identifier. If not provided,
                       a new context will be created with default settings.
        
        Returns:
            A new ExecutionContext instance.
        """
        context = ExecutionContext()
        
        if context_id:
            self._contexts[context_id] = context
        
        return context
    
    def get_context(self, context_id: str) -> Optional[ExecutionContext]:
        """
        Get an existing execution context by ID.
        
        Args:
            context_id: The context identifier.
        
        Returns:
            The ExecutionContext if found, None otherwise.
        """
        return self._contexts.get(context_id)
    
    async def setup_environment(self, context: ExecutionContext) -> None:
        """
        Setup sys.path and virtual environment for execution.
        
        Args:
            context: The execution context to setup.
        """
        project_root_str = str(context.project_root)
        project_parent_str = str(context.project_root.parent)
        
        # Detect venv site-packages dynamically
        venv_site_packages = None
        if context.venv_path.exists():
            # Try multiple Python versions
            for py_version in ['python3.11', 'python3.12', 'python3.10', 'python3.9']:
                candidate = context.venv_path / "lib" / py_version / "site-packages"
                if candidate.exists():
                    venv_site_packages = candidate
                    break
        
        # De-duplicate sys.path using OrderedDict to preserve order
        current_paths = OrderedDict.fromkeys(sys.path)
        
        # Paths to add (parent first for package imports, then project root)
        paths_to_add = [project_parent_str, project_root_str]
        if venv_site_packages:
            paths_to_add.append(str(venv_site_packages))
        
        # Add new paths at the beginning, preserving order and avoiding duplicates
        new_sys_path = []
        for path in paths_to_add:
            if path not in current_paths:
                new_sys_path.append(path)
                current_paths[path] = None  # Mark as added
        
        # Rebuild sys.path with new paths first
        sys.path[:] = new_sys_path + list(current_paths.keys())
        
        # Set up virtual environment activation
        if context.venv_path.exists():
            venv_python = context.venv_path / "bin" / "python"
            venv_bin = context.venv_path / "bin"
            
            if venv_python.exists():
                # Set environment variables for venv activation
                os.environ['VIRTUAL_ENV'] = str(context.venv_path)
                
                # Prepend venv/bin to PATH if not already present
                current_path = os.environ.get('PATH', '')
                venv_bin_str = str(venv_bin)
                if venv_bin_str not in current_path.split(os.pathsep):
                    os.environ['PATH'] = f"{venv_bin_str}{os.pathsep}{current_path}"
                
                # Update sys.executable to point to venv python
                sys.executable = str(venv_python)
    
    def add_to_path(self, path: str) -> None:
        """
        Add a path to sys.path if not already present.
        
        Args:
            path: The path to add.
        """
        if path not in sys.path:
            sys.path.insert(0, path)
    
    async def cleanup(self, context: ExecutionContext) -> None:
        """
        Cleanup execution context resources.
        
        Args:
            context: The execution context to cleanup.
        """
        # Stop any running web servers
        for server_name, server_info in context.web_servers.items():
            try:
                if hasattr(server_info, 'stop'):
                    await server_info.stop()
            except Exception:
                pass  # Ignore cleanup errors
        
        context.web_servers.clear()
    
    def create_artifacts_dir(self, context: ExecutionContext, session_id: str) -> Path:
        """
        Create artifacts directory for a session.
        
        Args:
            context: The execution context.
            session_id: The session identifier.
        
        Returns:
            Path to the artifacts directory.
        """
        artifacts_dir = context.sandbox_area / session_id / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        context.artifacts_dir = artifacts_dir
        return artifacts_dir


# Singleton instance for convenience
_execution_service: Optional[ExecutionContextService] = None


def get_execution_service() -> ExecutionContextService:
    """
    Get the global execution context service instance.
    
    Returns:
        The singleton ExecutionContextService instance.
    """
    global _execution_service
    if _execution_service is None:
        _execution_service = ExecutionContextService()
    return _execution_service
