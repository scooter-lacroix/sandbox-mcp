"""
Server Artifact Service for Sandbox MCP.

This module handles artifact listing and management for the server,
replacing duplicate logic from the stdio server.
"""

import os
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class ServerArtifactService:
    """
    Service for managing server artifacts.

    This service provides unified artifact listing, categorization,
    and retrieval, replacing duplicate logic in the stdio server.
    """

    # File type categories
    IMAGE_EXTENSIONS = {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".svg",
        ".webp",
        ".tiff",
    }
    VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm", ".mkv"}
    DATA_EXTENSIONS = {
        ".csv",
        ".json",
        ".xml",
        ".yaml",
        ".yml",
        ".parquet",
        ".pkl",
        ".pickle",
    }
    CODE_EXTENSIONS = {".py", ".js", ".html", ".css", ".sql", ".sh", ".bat"}
    DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md", ".rtf"}
    AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"}

    # Valid categories for filtering
    VALID_CATEGORIES = {
        "images",
        "videos",
        "data",
        "code",
        "documents",
        "audio",
        "other",
        "manim",
    }

    def __init__(self):
        """Initialize the server artifact service."""
        pass

    def _categorize_file(
        self, file_path: Path, base_path: Optional[Path] = None
    ) -> str:
        """
        Categorize a file based on its extension and path.

        Args:
            file_path: Path to the file.
            base_path: Base path for relative path checking.

        Returns:
            Category string.
        """
        suffix = file_path.suffix.lower()
        path_str = str(file_path).lower()

        # Check for Manim files with explicit scoping (not substring-based)
        # Only match if in explicit manim-related directories
        if base_path:
            try:
                rel_path = file_path.relative_to(base_path)
                rel_parts = rel_path.parts
                # Only categorize as manim if in explicit manim directories
                manim_dirs = {"manim", "media", "videos", "images"}
                if any(part in manim_dirs for part in rel_parts):
                    return "manim"
            except ValueError:
                pass

        # Extension-based categorization
        if suffix in self.IMAGE_EXTENSIONS:
            return "images"
        elif suffix in self.VIDEO_EXTENSIONS:
            return "videos"
        elif suffix in self.DATA_EXTENSIONS:
            return "data"
        elif suffix in self.CODE_EXTENSIONS:
            return "code"
        elif suffix in self.DOCUMENT_EXTENSIONS:
            return "documents"
        elif suffix in self.AUDIO_EXTENSIONS:
            return "audio"
        else:
            return "other"

    def _sanitize_category_filter(
        self, category_filter: Optional[str]
    ) -> Optional[str]:
        """
        Sanitize category filter to prevent injection.

        Args:
            category_filter: The category filter to sanitize.

        Returns:
            Sanitized category filter or None if invalid.
        """
        if category_filter is None:
            return None

        # Normalize and validate
        normalized = category_filter.lower().strip()
        if normalized in self.VALID_CATEGORIES:
            return normalized
        return None

    def _compute_checksum(self, file_path: Path) -> Optional[str]:
        """
        Compute SHA256 checksum of a file.

        Args:
            file_path: Path to the file.

        Returns:
            Hex digest of checksum or None if error.
        """
        try:
            sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                # Read in chunks to handle large files
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except (OSError, PermissionError):
            return None

    async def list_artifacts(
        self,
        directory: Path,
        recursive: bool = True,
        category_filter: Optional[str] = None,
        max_depth: int = 10,
        max_size: int = 100 * 1024 * 1024,
        include_checksums: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        List artifacts in a directory.

        Args:
            directory: The directory to scan.
            recursive: Whether to scan subdirectories recursively.
            category_filter: Optional category to filter by.
            max_depth: Maximum directory depth to scan.
            max_size: Maximum file size in bytes to include.
            include_checksums: Whether to compute and include checksums.

        Returns:
            List of artifact dictionaries.
        """
        artifacts = []

        if not directory.exists():
            logger.warning(f"Directory does not exist: {directory}")
            return artifacts

        # Sanitize category filter
        category_filter = self._sanitize_category_filter(category_filter)

        directory_resolved = directory.resolve()
        base_depth = str(directory_resolved).count(os.sep)

        pattern = "**/*" if recursive else "*"

        for file_path in directory.glob(pattern):
            # Skip symlinks for security (prevents host disclosure)
            if file_path.is_symlink():
                continue

            # Check depth limit
            try:
                file_depth = str(file_path.resolve()).count(os.sep) - base_depth
                if file_depth > max_depth:
                    continue
            except (OSError, ValueError):
                continue

            if file_path.is_file():
                try:
                    stat = file_path.stat()

                    # Skip files exceeding size limit
                    if stat.st_size > max_size:
                        continue

                    category = self._categorize_file(file_path, directory_resolved)

                    # Apply category filter if specified
                    if category_filter and category != category_filter:
                        continue

                    artifact_info = {
                        "name": file_path.name,
                        "path": str(file_path.relative_to(directory)),
                        "full_path": str(file_path),
                        "size": stat.st_size,
                        "created": datetime.fromtimestamp(
                            stat.st_ctime, tz=timezone.utc
                        ).isoformat(),
                        "modified": datetime.fromtimestamp(
                            stat.st_mtime, tz=timezone.utc
                        ).isoformat(),
                        "extension": suffix
                        if (suffix := file_path.suffix.lower())
                        else "",
                        "category": category,
                    }

                    # Optionally include checksum
                    if include_checksums:
                        artifact_info["checksum"] = self._compute_checksum(file_path)

                    artifacts.append(artifact_info)
                except Exception as e:
                    logger.warning(f"Failed to get info for {file_path}: {e}")

        return artifacts

    async def get_artifact(
        self, file_path: Path, include_checksum: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific artifact.

        Args:
            file_path: Path to the artifact.
            include_checksum: Whether to compute and include checksum.

        Returns:
            Artifact information dictionary, or None if not found.
        """
        # Skip symlinks for security
        if file_path.is_symlink():
            return None

        if not file_path.exists() or not file_path.is_file():
            return None

        try:
            stat = file_path.stat()
            category = self._categorize_file(file_path)

            artifact_info = {
                "name": file_path.name,
                "path": str(file_path),
                "size": stat.st_size,
                "created": datetime.fromtimestamp(
                    stat.st_ctime, tz=timezone.utc
                ).isoformat(),
                "modified": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).isoformat(),
                "extension": file_path.suffix.lower(),
                "category": category,
            }

            if include_checksum:
                artifact_info["checksum"] = self._compute_checksum(file_path)

            return artifact_info
        except Exception as e:
            logger.error(f"Failed to get artifact info for {file_path}: {e}")
            return None

    async def get_artifact_summary(self, directory: Path) -> Dict[str, Any]:
        """
        Get a summary of artifacts in a directory.

        Args:
            directory: The directory to summarize.

        Returns:
            Summary dictionary with counts and totals.
        """
        artifacts = await self.list_artifacts(directory)

        summary = {
            "total_count": len(artifacts),
            "total_size": sum(a["size"] for a in artifacts),
            "by_category": {},
        }

        for artifact in artifacts:
            category = artifact["category"]
            if category not in summary["by_category"]:
                summary["by_category"][category] = {
                    "count": 0,
                    "total_size": 0,
                }
            summary["by_category"][category]["count"] += 1
            summary["by_category"][category]["total_size"] += artifact["size"]

        return summary


# Singleton instance for convenience
_server_artifact_service: Optional[ServerArtifactService] = None


def get_server_artifact_service() -> ServerArtifactService:
    """
    Get the global server artifact service instance.

    Returns:
        The singleton ServerArtifactService instance.
    """
    global _server_artifact_service
    if _server_artifact_service is None:
        _server_artifact_service = ServerArtifactService()
    return _server_artifact_service
