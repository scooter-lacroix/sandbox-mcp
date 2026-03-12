"""
Unified Execution Services for Sandbox MCP.

This module consolidates duplicate execution context logic from both
MCP servers (stdio and HTTP) into a single source of truth.

Security S4: Uses centralized PathValidator for path validation.
"""

from __future__ import annotations

import os
import shutil
import sys
import uuid
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .artifact_backup_service import get_backup_service
from .path_validation import is_safe_path


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
        if not is_safe_path(self.project_root, require_exists=True):
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

    def _setup_environment(self) -> None:
        """Setup sys.path and virtual environment with robust path detection."""
        project_root_str = str(self.project_root)
        project_parent_str = str(self.project_root.parent)

        # Detect venv site-packages dynamically
        venv_site_packages = None
        if self.venv_path.exists():
            for py_version in ["python3.11", "python3.12", "python3.10", "python3.9"]:
                candidate = self.venv_path / "lib" / py_version / "site-packages"
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
        if self.venv_path.exists():
            venv_python = self.venv_path / "bin" / "python"
            venv_bin = self.venv_path / "bin"

            if venv_python.exists():
                # Set environment variables for venv activation
                os.environ["VIRTUAL_ENV"] = str(self.venv_path)

                # Prepend venv/bin to PATH if not already present
                current_path = os.environ.get("PATH", "")
                venv_bin_str = str(venv_bin)
                if venv_bin_str not in current_path.split(os.pathsep):
                    os.environ["PATH"] = f"{venv_bin_str}{os.pathsep}{current_path}"

                # Update sys.executable to point to venv python
                sys.executable = str(venv_python)

    def create_artifacts_dir(self) -> str:
        """Create a structured directory for execution artifacts within the project."""
        if self.artifacts_dir and self.artifacts_dir.exists():
            return str(self.artifacts_dir)

        execution_id = str(uuid.uuid4())[:8]
        artifacts_root = self.project_root / "artifacts"
        artifacts_root.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = f"session_{timestamp}_{execution_id}"

        self.artifacts_dir = artifacts_root / session_dir
        self.artifacts_dir.mkdir(exist_ok=True)

        for subdir in [
            "plots",
            "images",
            "animations",
            "files",
            "audio",
            "data",
            "models",
            "documents",
            "web_assets",
        ]:
            (self.artifacts_dir / subdir).mkdir(exist_ok=True)

        return str(self.artifacts_dir)

    def cleanup_artifacts(self) -> None:
        """Clean up artifacts directory."""
        if self.artifacts_dir and self.artifacts_dir.exists():
            shutil.rmtree(self.artifacts_dir, ignore_errors=True)

    def _sanitize_backup_name(self, backup_name: str) -> str:
        """Delegate to ArtifactBackupService for sanitization."""
        return get_backup_service().sanitize_backup_name(backup_name)

    def backup_artifacts(self, backup_name: str | None = None) -> str:
        """Delegate to ArtifactBackupService for backup operations."""
        return get_backup_service().backup_artifacts(self, backup_name)

    def _cleanup_old_backups(self, backup_root: Path, max_backups: int = 10) -> None:
        """Clean up old backup directories to prevent storage overflow."""
        import logging

        logger = logging.getLogger(__name__)
        try:
            backups = [d for d in backup_root.iterdir() if d.is_dir()]
            backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)

            for backup in backups[max_backups:]:
                shutil.rmtree(backup, ignore_errors=True)
                logger.info(f"Removed old backup: {backup}")
        except Exception as e:
            logger.warning(f"Failed to cleanup old backups: {e}")

    def list_artifact_backups(self) -> List[Dict[str, Any]]:
        """List all available artifact backups."""
        import logging

        logger = logging.getLogger(__name__)
        backup_root = self.project_root / "artifact_backups"
        if not backup_root.exists():
            return []

        backups: List[Dict[str, Any]] = []
        for backup_dir in backup_root.iterdir():
            if backup_dir.is_dir():
                try:
                    stat = backup_dir.stat()
                    size = sum(
                        f.stat().st_size for f in backup_dir.rglob("*") if f.is_file()
                    )
                    backups.append(
                        {
                            "name": backup_dir.name,
                            "path": str(backup_dir),
                            "created": stat.st_ctime,
                            "modified": stat.st_mtime,
                            "size_bytes": size,
                            "size_mb": size / (1024 * 1024),
                            "file_count": len(list(backup_dir.rglob("*"))),
                        }
                    )
                except Exception as e:
                    logger.warning(f"Failed to stat backup {backup_dir}: {e}")

        backups.sort(key=lambda x: x["created"], reverse=True)
        return backups

    def rollback_artifacts(self, backup_name: str) -> str:
        """Delegate to ArtifactBackupService for rollback operations."""
        return get_backup_service().rollback_artifacts(self, backup_name)

    def get_backup_info(self, backup_name: str) -> Dict[str, Any]:
        """
        Delegate to ArtifactBackupService for backup info.

        Security CRIT-2 fix: Uses hardened path validation from
        ArtifactBackupService to prevent path traversal attacks.
        """
        return get_backup_service().get_backup_info(self, backup_name)


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
            if is_safe_path(Path(path), require_exists=True):
                valid_paths.append(path)

        if venv_site_packages:
            venv_path_str = str(venv_site_packages)
            if is_safe_path(Path(venv_path_str), require_exists=True):
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
                if not is_safe_path(context.venv_path, require_exists=True):
                    return

                if not is_safe_path(venv_bin, require_exists=True):
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

    def add_to_path(self, path: str) -> None:
        """
        Add a path to sys.path if not already present.

        Args:
            path: The path to add.
        """
        if path not in sys.path and is_safe_path(Path(path), require_exists=True):
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
        # Security S4: Use is_relative_to() instead of startswith() to prevent
        # path traversal via symlinks and similar-prefix attacks
        try:
            artifacts_dir = artifacts_dir.resolve()
            sandbox_area_resolved = context.sandbox_area.resolve()
            if not artifacts_dir.is_relative_to(sandbox_area_resolved):
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
