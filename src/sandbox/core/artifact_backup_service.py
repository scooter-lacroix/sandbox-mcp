"""
Artifact Backup Service for Sandbox MCP.

This service provides artifact backup and rollback functionality,
extracted from the stdio server's ExecutionContext to provide
a single source of truth for both transport implementations.

Security S3: All backup names are sanitized to prevent path traversal attacks.
"""

from __future__ import annotations

import datetime
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class HasArtifactPaths(Protocol):
    """Protocol for objects that have artifact paths."""
    project_root: Path
    artifacts_dir: Optional[Path]


class ArtifactBackupService:
    """
    Service for managing artifact backups.

    This service provides backup, rollback, and cleanup operations
    for artifact directories. It is designed to work with any context
    that has project_root and artifacts_dir attributes.

    Security: All backup names are sanitized to prevent path traversal.
    """

    def __init__(self, max_backups: int = 10):
        """
        Initialize the backup service.

        Args:
            max_backups: Maximum number of backups to keep (default 10)
        """
        self._max_backups = max_backups
        self._services: Dict[str, "ArtifactBackupService"] = {}

    def sanitize_backup_name(self, backup_name: str) -> str:
        """
        Sanitize backup name to prevent path traversal attacks.

        Security S3: Only alphanumeric characters, hyphens, and underscores
        are allowed. Path traversal sequences and special characters are rejected.

        Args:
            backup_name: The backup name to sanitize

        Returns:
            The sanitized backup name

        Raises:
            ValueError: If backup_name contains invalid characters or patterns
        """
        if not backup_name:
            raise ValueError("backup_name cannot be empty")

        # Check for null bytes
        if '\x00' in backup_name:
            raise ValueError("backup_name cannot contain null bytes")

        # Check for path traversal patterns
        if '..' in backup_name:
            raise ValueError("backup_name cannot contain '..' (path traversal)")

        # Check for path separators
        if '/' in backup_name or '\\' in backup_name:
            raise ValueError("backup_name cannot contain path separators")

        # Check for newlines or whitespace
        if any(c in backup_name for c in '\n\r\t '):
            raise ValueError("backup_name cannot contain whitespace")

        # Only allow alphanumeric characters, hyphens, and underscores
        safe_name = backup_name.replace('-', '').replace('_', '')
        if not safe_name.isalnum():
            raise ValueError(
                f"backup_name must be alphanumeric with hyphens/underscores: {backup_name!r}"
            )

        # Limit length to prevent DoS
        if len(backup_name) > 128:
            raise ValueError(f"backup_name too long: {len(backup_name)} > 128")

        return backup_name

    def get_backup_root(self, ctx: HasArtifactPaths) -> Path:
        """
        Get the backup root directory for a context.

        Args:
            ctx: Context with project_root attribute

        Returns:
            Path to the backup root directory
        """
        backup_root = ctx.project_root / "artifact_backups"
        backup_root.mkdir(exist_ok=True, parents=True)
        return backup_root

    def backup_artifacts(
        self,
        ctx: HasArtifactPaths,
        backup_name: Optional[str] = None
    ) -> str:
        """
        Create a versioned backup of current artifacts.

        Args:
            ctx: Context with project_root and artifacts_dir attributes
            backup_name: Optional name for the backup

        Returns:
            Path to the backup directory or error message
        """
        if not ctx.artifacts_dir or not ctx.artifacts_dir.exists():
            return "No artifacts directory to backup"

        backup_root = self.get_backup_root(ctx)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        # SECURITY S3: Sanitize backup_name if provided
        if backup_name is not None:
            try:
                backup_name = self.sanitize_backup_name(backup_name)
            except ValueError as e:
                return f"Invalid backup name: {e}"

        safe_backup_name = (
            f"{backup_name}_{timestamp}" if backup_name else f"backup_{timestamp}"
        )
        backup_path = backup_root / safe_backup_name

        shutil.copytree(ctx.artifacts_dir, backup_path)
        self._cleanup_old_backups(ctx, backup_root)

        return str(backup_path)

    def rollback_artifacts(
        self,
        ctx: HasArtifactPaths,
        backup_name: str
    ) -> str:
        """
        Rollback to a previous artifact version.

        Args:
            ctx: Context with project_root and artifacts_dir attributes
            backup_name: Name of the backup to restore

        Returns:
            Success message or error description
        """
        backup_root = self.get_backup_root(ctx)

        # SECURITY S3: Sanitize backup_name to prevent path traversal
        try:
            safe_backup_name = self.sanitize_backup_name(backup_name)
        except ValueError as e:
            return f"Invalid backup name: {e}"

        backup_path = backup_root / safe_backup_name

        if not backup_path.exists():
            available_backups = [d.name for d in backup_root.iterdir() if d.is_dir()]
            if available_backups:
                preview = ", ".join(available_backups[:5])
                suffix = "..." if len(available_backups) > 5 else ""
                return f"Backup '{safe_backup_name}' not found. Available backups: {preview}{suffix}"
            return f"Backup '{safe_backup_name}' not found. No backups available."

        if not ctx.artifacts_dir:
            return "No current artifacts directory. Please create artifacts first."

        current_backup = self.backup_artifacts(ctx, "pre_rollback")

        try:
            if ctx.artifacts_dir and ctx.artifacts_dir.exists():
                shutil.rmtree(ctx.artifacts_dir)

            shutil.copytree(backup_path, ctx.artifacts_dir)

            return (
                f"Successfully rolled back to backup '{safe_backup_name}'. "
                f"Previous state saved as '{Path(current_backup).name}'"
            )
        except Exception as e:
            return f"Failed to rollback: {str(e)}"

    def list_backups(self, ctx: HasArtifactPaths) -> List[Dict[str, Any]]:
        """
        List all available artifact backups.

        Args:
            ctx: Context with project_root attribute

        Returns:
            List of backup info dictionaries
        """
        backup_root = ctx.project_root / "artifact_backups"
        if not backup_root.exists():
            return []

        backups = []
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

    def get_backup_info(
        self,
        ctx: HasArtifactPaths,
        backup_name: str
    ) -> Dict[str, Any]:
        """
        Get detailed information about a specific backup.

        Security S3: Sanitizes backup_name and verifies path containment
        to prevent path traversal attacks.

        Args:
            ctx: Context with project_root attribute
            backup_name: Name of the backup

        Returns:
            Dictionary with backup information
        """
        # SECURITY S3: Sanitize backup_name to prevent path traversal
        try:
            safe_backup_name = self.sanitize_backup_name(backup_name)
        except ValueError as e:
            return {"error": f"Invalid backup name: {e}"}

        backup_root = ctx.project_root / "artifact_backups"
        backup_path = backup_root / safe_backup_name

        # Additional check: verify path is within backup_root
        if not backup_path.resolve().is_relative_to(backup_root.resolve()):
            return {"error": f"Invalid backup path: '{backup_name}'"}

        if not backup_path.exists():
            return {"error": f"Backup '{backup_name}' not found"}

        try:
            stat = backup_path.stat()
            files = list(backup_path.rglob("*"))

            categories: Dict[str, List[Dict[str, Any]]] = {}
            for file_path in files:
                if file_path.is_file():
                    category = file_path.parent.name
                    categories.setdefault(category, []).append(
                        {
                            "name": file_path.name,
                            "size": file_path.stat().st_size,
                            "extension": file_path.suffix,
                        }
                    )

            return {
                "name": backup_name,
                "path": str(backup_path),
                "created": stat.st_ctime,
                "modified": stat.st_mtime,
                "total_files": len([f for f in files if f.is_file()]),
                "total_size_bytes": sum(f.stat().st_size for f in files if f.is_file()),
                "categories": categories,
            }
        except Exception as e:
            return {"error": f"Failed to get backup info: {str(e)}"}

    def cleanup_old_backups(
        self,
        ctx: HasArtifactPaths,
        max_backups: Optional[int] = None
    ) -> int:
        """
        Clean up old backup directories to prevent storage overflow.

        Args:
            ctx: Context with project_root attribute
            max_backups: Maximum backups to keep (default from instance)

        Returns:
            Number of backups removed
        """
        backup_root = ctx.project_root / "artifact_backups"
        if not backup_root.exists():
            return 0

        max_to_keep = max_backups or self._max_backups
        return self._cleanup_old_backups(ctx, backup_root, max_to_keep)

    def _cleanup_old_backups(
        self,
        ctx: HasArtifactPaths,
        backup_root: Path,
        max_backups: Optional[int] = None
    ) -> int:
        """
        Internal method to clean up old backups.

        Args:
            ctx: Context (for logging)
            backup_root: Path to backup directory
            max_backups: Maximum backups to keep

        Returns:
            Number of backups removed
        """
        max_to_keep = max_backups or self._max_backups
        removed_count = 0

        try:
            backups = [d for d in backup_root.iterdir() if d.is_dir()]
            backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)

            for backup in backups[max_to_keep:]:
                shutil.rmtree(backup, ignore_errors=True)
                logger.info(f"Removed old backup: {backup}")
                removed_count += 1
        except Exception as e:
            logger.warning(f"Failed to cleanup old backups: {e}")

        return removed_count


# Singleton instance for convenience
_backup_service: Optional[ArtifactBackupService] = None


def get_backup_service() -> ArtifactBackupService:
    """
    Get the global artifact backup service instance.

    Returns:
        The singleton ArtifactBackupService instance.
    """
    global _backup_service
    if _backup_service is None:
        _backup_service = ArtifactBackupService()
    return _backup_service
