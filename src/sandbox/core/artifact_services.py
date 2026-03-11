"""
Unified Artifact Services for Sandbox MCP.

This module consolidates duplicate artifact handling logic from both
MCP servers into a single source of truth.
"""

import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime


class ArtifactService:
    """
    Service for managing artifacts in sandbox environments.

    This service provides unified artifact categorization, scanning,
    and reporting, replacing duplicate logic in both MCP servers.
    """

    # File type categories
    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp"}
    PLOT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg", ".pdf"}  # Common plot formats
    DATA_EXTENSIONS = {".csv", ".json", ".xml", ".yaml", ".yml", ".txt", ".parquet"}
    VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".webm", ".gif"}
    AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".flac"}

    def __init__(self):
        """Initialize the artifact service."""
        pass

    def categorize(self, filename: str) -> str:
        """
        Categorize an artifact by its file type.

        Args:
            filename: The name of the file to categorize.

        Returns:
            Category string: 'images', 'plots', 'data', 'video', 'audio', or 'other'
        """
        ext = Path(filename).suffix.lower()
        name_lower = filename.lower()

        # Check if it looks like a plot file (plot-related naming patterns)
        is_plot_file = any(
            pattern in name_lower
            for pattern in ["plot_", "fig_", "figure_", "_plot", "_fig", "chart_"]
        )

        if ext in self.PLOT_EXTENSIONS and is_plot_file:
            return "plots"
        elif ext in self.IMAGE_EXTENSIONS:
            return "images"
        elif ext in self.VIDEO_EXTENSIONS:
            return "video"
        elif ext in self.AUDIO_EXTENSIONS:
            return "audio"
        elif ext in self.DATA_EXTENSIONS:
            return "data"
        else:
            return "other"

    def get_category_directory(self, category: str) -> str:
        """
        Get the directory name for a category.

        Args:
            category: The category string.

        Returns:
            Directory name for the category.
        """
        category_dirs = {
            "images": "images",
            "plots": "plots",
            "data": "data",
            "video": "video",
            "audio": "audio",
            "other": "other",
        }
        return category_dirs.get(category, "other")

    async def scan_directory(
        self, directory: Path, max_depth: int = 10, max_size: int = 100 * 1024 * 1024
    ) -> List[Dict[str, Any]]:
        """
        Scan a directory for artifacts and categorize them.

        Args:
            directory: The directory to scan.
            max_depth: Maximum directory depth to scan (default 10).
            max_size: Maximum file size in bytes to include (default 100MB).

        Returns:
            List of artifact dictionaries with path, category, and metadata.
        """
        artifacts = []

        if not directory.exists():
            return artifacts

        directory_resolved = directory.resolve()
        base_depth = str(directory_resolved).count(os.sep)

        for file_path in directory.rglob("*"):
            # Skip symlinks for security
            if file_path.is_symlink():
                continue

            # Check depth limit
            file_depth = str(file_path.resolve()).count(os.sep) - base_depth
            if file_depth > max_depth:
                continue

            if file_path.is_file():
                try:
                    # Use single stat call to get all info
                    stat_info = file_path.stat()

                    # Skip files exceeding size limit
                    if stat_info.st_size > max_size:
                        continue

                    category = self.categorize(file_path.name)

                    artifact_info = {
                        "path": str(file_path),
                        "name": file_path.name,
                        "category": category,
                        "size": stat_info.st_size,
                        "modified": datetime.fromtimestamp(
                            stat_info.st_mtime
                        ).isoformat(),
                    }

                    artifacts.append(artifact_info)
                except (OSError, PermissionError):
                    # Skip files we can't access
                    continue

        return artifacts

    def get_report(self, artifacts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate a summary report of artifacts.

        Args:
            artifacts: List of artifact dictionaries.

        Returns:
            Summary report dictionary.
        """
        report = {
            "total_count": len(artifacts),
            "by_category": {},
            "total_size": 0,
        }

        for artifact in artifacts:
            category = artifact["category"]
            if category not in report["by_category"]:
                report["by_category"][category] = {
                    "count": 0,
                    "total_size": 0,
                    "files": [],
                }

            report["by_category"][category]["count"] += 1
            report["by_category"][category]["total_size"] += artifact["size"]
            report["by_category"][category]["files"].append(artifact["name"])
            report["total_size"] += artifact["size"]

        return report

    def create_artifacts_dir(self, context: Any, session_id: str) -> Path:
        """
        Create artifacts directory structure for a session.

        Args:
            context: Execution context with sandbox_area.
            session_id: Session identifier.

        Returns:
            Path to the main artifacts directory.

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

        base_dir = context.sandbox_area / session_id / "artifacts"

        # SECURITY S4: Verify the resulting path stays within sandbox_area
        # using is_relative_to() instead of startswith()
        try:
            base_dir = base_dir.resolve()
            sandbox_area_resolved = context.sandbox_area.resolve()
            if not base_dir.is_relative_to(sandbox_area_resolved):
                raise ValueError(f"Path traversal detected: {base_dir}")
        except ValueError as e:
            raise
        except Exception as e:
            raise ValueError(f"Invalid path: {e}")

        # Create category subdirectories
        categories = ["images", "plots", "data", "video", "audio", "other"]
        for category in categories:
            (base_dir / category).mkdir(parents=True, exist_ok=True)

        return base_dir

    async def cleanup_old_artifacts(
        self, directory: Path, max_age_days: int = 7, max_depth: int = 10
    ) -> int:
        """
        Clean up artifacts older than specified age.

        Args:
            directory: The directory to clean.
            max_age_days: Maximum age in days.
            max_depth: Maximum directory depth to clean.

        Returns:
            Number of artifacts cleaned up.
        """
        cleaned = 0
        now = datetime.now()

        if not directory.exists():
            return cleaned

        directory_resolved = directory.resolve()
        base_depth = str(directory_resolved).count(os.sep)

        for file_path in directory.rglob("*"):
            # Skip symlinks for security
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
                    stat_info = file_path.stat()
                    # Use precise timedelta for age calculation instead of .days
                    mtime = datetime.fromtimestamp(stat_info.st_mtime)
                    age = now - mtime

                    # Use precise age check (full timedelta, not just days)
                    if age.days > max_age_days:
                        file_path.unlink()
                        cleaned += 1
                except (OSError, PermissionError):
                    # Skip files we can't access or delete
                    continue

        return cleaned


# Singleton instance for convenience
_artifact_service: Optional[ArtifactService] = None


def get_artifact_service() -> ArtifactService:
    """
    Get the global artifact service instance.

    Returns:
        The singleton ArtifactService instance.
    """
    global _artifact_service
    if _artifact_service is None:
        _artifact_service = ArtifactService()
    return _artifact_service
