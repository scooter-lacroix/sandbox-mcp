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
                         Must be within expected boundaries.
        """
        if project_root is None:
            # Compute project_root dynamically from current file location
            current_file = Path(__file__).resolve()
            if "src/sandbox/core" in str(current_file):
                # Installed package: go from src/sandbox/core to project root
                self.project_root = current_file.parent.parent.parent
            else:
                # Development: assume file is in project root
                self.project_root = current_file.parent
        else:
            # Use provided project_root, but validate it
            self.project_root = project_root.resolve()

        # Validate project_root is within expected boundaries
        if not self._is_valid_project_root(self.project_root):
            raise ValueError(f"Invalid project root: {self.project_root}")

        # Set up sandbox working area within project root (not parent)
        self.sandbox_area = self.project_root / "sandbox_area"
        self.sandbox_area.mkdir(exist_ok=True, parents=True)

        # Initialize additional instance variables
        self.venv_path = self.project_root / ".venv"
        self.artifacts_dir: Optional[Path] = None
        self.web_servers: Dict[str, Any] = {}
        self.execution_globals: Dict[str, Any] = {}
        self.compilation_cache: Dict[str, Any] = {}
        self.cache_hits = 0
        self.cache_misses = 0

        # Cache for resolved venv site-packages
        self._venv_site_packages_cache: Optional[Path] = None

    def _is_valid_project_root(self, path: Path) -> bool:
        """Validate that project root is within acceptable boundaries."""
        # Ensure path is absolute and normalized
        path = path.resolve()

        # Check for path traversal attempts
        if ".." in path.parts:
            return False

        # Check that path is within user's home directory or acceptable locations
        home_dir = Path.home()
        if not str(path).startswith(str(home_dir)):
            # Allow specific project directories
            allowed_prefixes = [
                str(home_dir / "Documents"),
                str(home_dir / "Projects"),
                str(home_dir / "work"),
                str(home_dir / "dev"),
            ]
            if not any(str(path).startswith(prefix) for prefix in allowed_prefixes):
                return False

        # Check that path exists and is a directory
        if not path.exists() or not path.is_dir():
            return False

        return True


class ExecutionContextService:
    """
    Service for managing execution contexts.

    This service provides a unified interface for creating and managing
    execution contexts, replacing duplicate logic in both MCP servers.
    """

    def __init__(self):
        """Initialize the execution context service."""
        self._contexts: Dict[str, ExecutionContext] = {}
        self._venv_site_packages_cache: Dict[Path, Optional[Path]] = {}

    def create_context(
        self, context_id: Optional[str] = None, project_root: Optional[Path] = None
    ) -> ExecutionContext:
        """
        Create a new execution context.

        Args:
            context_id: Optional context identifier. If not provided,
                       a new context will be created with default settings.
            project_root: Optional project root path. If not provided,
                         will be computed from current file location.

        Returns:
            A new ExecutionContext instance.
        """
        context = ExecutionContext(project_root=project_root)

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

        # Use cached venv site-packages if available
        venv_site_packages = None
        if context.venv_path.exists():
            if context.venv_path in self._venv_site_packages_cache:
                venv_site_packages = self._venv_site_packages_cache[context.venv_path]
            else:
                # Detect venv site-packages dynamically
                for py_version in [
                    "python3.11",
                    "python3.12",
                    "python3.10",
                    "python3.9",
                ]:
                    candidate = context.venv_path / "lib" / py_version / "site-packages"
                    if candidate.exists():
                        venv_site_packages = candidate
                        break
                # Cache the result (including None if not found)
                self._venv_site_packages_cache[context.venv_path] = venv_site_packages

        # Validate paths before adding to sys.path
        valid_paths = []
        for path in [project_parent_str, project_root_str]:
            if self._is_valid_path(path):
                valid_paths.append(path)

        if venv_site_packages:
            venv_path_str = str(venv_site_packages)
            if self._is_valid_path(venv_path_str):
                valid_paths.append(venv_path_str)

        # De-duplicate sys.path using OrderedDict to preserve order
        current_paths = OrderedDict.fromkeys(sys.path)

        # Add new paths at the beginning, preserving order and avoiding duplicates
        new_sys_path = []
        for path in valid_paths:
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
                # Validate venv paths before using
                if not self._is_valid_path(str(context.venv_path)):
                    return

                if not self._is_valid_path(str(venv_bin)):
                    return

                # Set environment variables for venv activation
                os.environ["VIRTUAL_ENV"] = str(context.venv_path)

                # Prepend venv/bin to PATH if not already present
                current_path = os.environ.get("PATH", "")
                venv_bin_str = str(venv_bin)
                if venv_bin_str not in current_path.split(os.pathsep):
                    os.environ["PATH"] = f"{venv_bin_str}{os.pathsep}{current_path}"

                # Update sys.executable to point to venv python
                sys.executable = str(venv_python)

    def _is_valid_path(self, path: str) -> bool:
        """Validate that a path is safe and within expected boundaries."""
        try:
            # Ensure path is absolute and normalized
            path_obj = Path(path).resolve()

            # Check for path traversal attempts
            if ".." in path_obj.parts:
                return False

            # Check that path is within user's home directory or acceptable locations
            home_dir = Path.home()
            if not str(path_obj).startswith(str(home_dir)):
                # Allow specific project directories
                allowed_prefixes = [
                    str(home_dir / "Documents"),
                    str(home_dir / "Projects"),
                    str(home_dir / "work"),
                    str(home_dir / "dev"),
                ]
                if not any(
                    str(path_obj).startswith(prefix) for prefix in allowed_prefixes
                ):
                    return False

            # Check that path exists and is a directory
            if not path_obj.exists() or not path_obj.is_dir():
                return False

            return True
        except Exception:
            return False

    def add_to_path(self, path: str) -> None:
        """
        Add a path to sys.path if not already present.

        Args:
            path: The path to add.
        """
        if path not in sys.path and self._is_valid_path(path):
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
                if hasattr(server_info, "stop"):
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

        Raises:
            ValueError: If session_id contains invalid characters or path traversal attempts.
        """
        # Validate session_id to prevent path traversal
        if (
            not session_id
            or ".." in session_id
            or "/" in session_id
            or "\\" in session_id
        ):
            raise ValueError(f"Invalid session_id: {session_id}")

        # Ensure session_id is alphanumeric (UUID format)
        if not session_id.replace("-", "").isalnum():
            raise ValueError(f"session_id must be alphanumeric: {session_id}")

        # Verify the resulting path stays within sandbox_area
        artifacts_dir = context.sandbox_area / session_id / "artifacts"

        # Resolve and verify the path is still within sandbox_area
        try:
            artifacts_dir = artifacts_dir.resolve()
            sandbox_area_resolved = context.sandbox_area.resolve()
            if not str(artifacts_dir).startswith(str(sandbox_area_resolved)):
                raise ValueError(f"Path traversal detected: {artifacts_dir}")
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            raise ValueError(f"Invalid path: {e}")

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
