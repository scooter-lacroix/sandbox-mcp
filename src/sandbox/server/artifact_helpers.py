"""
Artifact helper functions for stdio server tools.
"""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

import datetime
import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Callable


def list_artifacts(collect_artifacts: Callable[[], list[dict[str, Any]]]) -> str:
    """List all current artifacts with grouped metadata."""
    artifacts = collect_artifacts()
    if not artifacts:
        return "No artifacts found."

    result = "Current artifacts:\n"
    result += "=" * 50 + "\n"

    by_category: dict[str, list[dict[str, Any]]] = {}
    for artifact in artifacts:
        category = str(artifact.get("category", "root"))
        by_category.setdefault(category, []).append(artifact)

    for category, items in by_category.items():
        result += f"\n{category.upper()}:\n"
        result += "-" * 20 + "\n"
        for artifact in items:
            size_kb = float(artifact.get("size", 0)) / 1024
            result += (
                f"  • {artifact.get('name', 'unknown')} "
                f"({size_kb:.1f} KB) - {artifact.get('type', '')}\n"
            )
            result += (
                f"    Path: {artifact.get('relative_path', artifact.get('path', ''))}\n"
            )

    result += f"\nTotal: {len(artifacts)} artifacts\n"
    return result


def clear_cache(ctx: Any, important_only: bool = False) -> str:
    """Clear the compilation cache, optionally preserving import/def/class entries."""
    if important_only:
        preserved_commands = ["import", "def", "class"]
        ctx.compilation_cache = {
            key: value
            for key, value in ctx.compilation_cache.items()
            if any(command in key for command in preserved_commands)
        }
    else:
        ctx.compilation_cache.clear()

    ctx.cache_hits = 0
    ctx.cache_misses = 0
    return "Cache cleared successfully."


def cleanup_artifacts(ctx: Any) -> str:
    """Clean up all artifacts and tracked web servers."""
    ctx.cleanup_artifacts()

    for _, process in list(ctx.web_servers.items()):
        try:
            process.terminate()
        except Exception:
            pass

    ctx.web_servers.clear()
    return "Artifacts and web servers cleaned up."


def cleanup_temp_artifacts(logger: Any, max_age_hours: int = 24) -> str:
    """Clean up old temporary artifact directories."""
    cleaned = 0
    temp_dir = Path(tempfile.gettempdir())

    try:
        for item in temp_dir.glob("sandbox_artifacts_*"):
            if item.is_dir():
                age_hours = (time.time() - item.stat().st_mtime) / 3600
                if age_hours > max_age_hours:
                    shutil.rmtree(item, ignore_errors=True)
                    cleaned += 1
    except Exception as exc:
        logger.error(f"Error during temp cleanup: {exc}")

    return json.dumps(
        {
            "cleaned_directories": cleaned,
            "max_age_hours": max_age_hours,
            "message": f"Cleaned {cleaned} old artifact directories",
        },
        indent=2,
    )


def get_artifact_report(ctx: Any, persistent_context_factory: Callable[[], Any]) -> str:
    """Get a comprehensive artifact report."""
    if not ctx.artifacts_dir or not Path(ctx.artifacts_dir).exists():
        return json.dumps(
            {
                "status": "no_artifacts",
                "message": "No artifacts directory found. Execute some code first.",
            },
            indent=2,
        )

    temp_ctx = persistent_context_factory()
    temp_ctx.artifacts_dir = Path(ctx.artifacts_dir)

    try:
        report = temp_ctx.get_artifact_report()
        return json.dumps(report, indent=2)
    except Exception as exc:
        return json.dumps(
            {
                "status": "error",
                "message": f"Failed to generate artifact report: {exc}",
            },
            indent=2,
        )


def categorize_artifacts(
    ctx: Any, persistent_context_factory: Callable[[], Any]
) -> str:
    """Categorize artifacts by type."""
    if not ctx.artifacts_dir or not Path(ctx.artifacts_dir).exists():
        return json.dumps(
            {
                "status": "no_artifacts",
                "message": "No artifacts directory found. Execute some code first.",
            },
            indent=2,
        )

    temp_ctx = persistent_context_factory()
    temp_ctx.artifacts_dir = Path(ctx.artifacts_dir)

    try:
        categories = temp_ctx.categorize_artifacts()
        return json.dumps(categories, indent=2)
    except Exception as exc:
        return json.dumps(
            {
                "status": "error",
                "message": f"Failed to categorize artifacts: {exc}",
            },
            indent=2,
        )


def cleanup_artifacts_by_type(
    artifact_type: str,
    ctx: Any,
    logger: Any,
    persistent_context_factory: Callable[[], Any],
) -> str:
    """Clean up artifacts of a specific type."""
    if not ctx.artifacts_dir or not Path(ctx.artifacts_dir).exists():
        return json.dumps(
            {
                "status": "no_artifacts",
                "message": "No artifacts directory found.",
            },
            indent=2,
        )

    temp_ctx = persistent_context_factory()
    temp_ctx.artifacts_dir = Path(ctx.artifacts_dir)

    try:
        categorized = temp_ctx.categorize_artifacts()

        if artifact_type not in categorized:
            return json.dumps(
                {
                    "status": "error",
                    "message": f'Artifact type "{artifact_type}" not found',
                    "available_types": list(categorized.keys()),
                },
                indent=2,
            )

        cleaned_count = 0
        for file_info in categorized[artifact_type]:
            try:
                file_path = Path(file_info["full_path"])
                if file_path.exists():
                    file_path.unlink()
                    cleaned_count += 1
            except Exception as exc:
                logger.warning(
                    f"Failed to delete {file_info.get('path', file_path)}: {exc}"
                )

        return json.dumps(
            {
                "status": "success",
                "artifact_type": artifact_type,
                "cleaned_count": cleaned_count,
                "message": f"Successfully cleaned {cleaned_count} {artifact_type} artifacts",
            },
            indent=2,
        )
    except Exception as exc:
        return json.dumps(
            {
                "status": "error",
                "message": f"Failed to cleanup artifacts: {exc}",
            },
            indent=2,
        )


def backup_current_artifacts(ctx: Any, backup_name: str | None = None) -> str:
    """Create a backup of current artifacts."""
    backup_path = ctx.backup_artifacts(backup_name)

    if backup_path and backup_path != "No artifacts directory to backup":
        return json.dumps(
            {
                "status": "success",
                "backup_path": backup_path,
                "backup_name": Path(backup_path).name,
                "message": f"Artifacts backed up successfully to {Path(backup_path).name}",
            },
            indent=2,
        )

    return json.dumps(
        {
            "status": "error",
            "message": backup_path or "Failed to create backup",
        },
        indent=2,
    )


def list_artifact_backups(ctx: Any) -> str:
    """List all available artifact backups."""
    backups = ctx.list_artifact_backups()

    if not backups:
        return json.dumps(
            {
                "status": "no_backups",
                "message": "No artifact backups found",
                "backups": [],
            },
            indent=2,
        )

    for backup in backups:
        backup["created_formatted"] = datetime.datetime.fromtimestamp(
            backup["created"]
        ).strftime("%Y-%m-%d %H:%M:%S")
        backup["modified_formatted"] = datetime.datetime.fromtimestamp(
            backup["modified"]
        ).strftime("%Y-%m-%d %H:%M:%S")

    return json.dumps(
        {
            "status": "success",
            "total_backups": len(backups),
            "backups": backups,
            "message": f"Found {len(backups)} artifact backups",
        },
        indent=2,
    )


def rollback_to_backup(ctx: Any, backup_name: str) -> str:
    """Rollback artifacts to a previous backup."""
    result = ctx.rollback_artifacts(backup_name)

    if "Successfully rolled back" in result:
        return json.dumps(
            {
                "status": "success",
                "message": result,
                "backup_name": backup_name,
            },
            indent=2,
        )

    return json.dumps(
        {
            "status": "error",
            "message": result,
            "backup_name": backup_name,
        },
        indent=2,
    )


def get_backup_details(ctx: Any, backup_name: str) -> str:
    """Get detailed information about a specific backup."""
    backup_info = ctx.get_backup_info(backup_name)

    if "error" in backup_info:
        return json.dumps(
            {
                "status": "error",
                "message": backup_info["error"],
            },
            indent=2,
        )

    backup_info["created_formatted"] = datetime.datetime.fromtimestamp(
        backup_info["created"]
    ).strftime("%Y-%m-%d %H:%M:%S")
    backup_info["modified_formatted"] = datetime.datetime.fromtimestamp(
        backup_info["modified"]
    ).strftime("%Y-%m-%d %H:%M:%S")
    backup_info["total_size_mb"] = backup_info["total_size_bytes"] / (1024 * 1024)

    return json.dumps(
        {
            "status": "success",
            "backup_info": backup_info,
        },
        indent=2,
    )


def cleanup_old_backups(ctx: Any, logger: Any, max_backups: int = 10) -> str:
    """Clean up old backups, keeping only the most recent ones."""
    backup_root = Path(ctx.project_root) / "artifact_backups"
    if not backup_root.exists():
        return json.dumps(
            {
                "status": "no_backups",
                "message": "No backup directory found",
                "cleaned_count": 0,
            },
            indent=2,
        )

    try:
        backups = [
            directory for directory in backup_root.iterdir() if directory.is_dir()
        ]
        backups.sort(key=lambda item: item.stat().st_mtime, reverse=True)

        cleaned_count = 0
        for backup in backups[max_backups:]:
            try:
                shutil.rmtree(backup, ignore_errors=True)
                cleaned_count += 1
                logger.info(f"Removed old backup: {backup}")
            except Exception as exc:
                logger.warning(f"Failed to remove backup {backup}: {exc}")

        return json.dumps(
            {
                "status": "success",
                "cleaned_count": cleaned_count,
                "remaining_backups": len(backups[:max_backups]),
                "max_backups": max_backups,
                "message": (
                    f"Cleaned up {cleaned_count} old backups, "
                    f"kept {len(backups[:max_backups])} most recent"
                ),
            },
            indent=2,
        )
    except Exception as exc:
        return json.dumps(
            {
                "status": "error",
                "message": f"Failed to cleanup backups: {exc}",
            },
            indent=2,
        )


__all__ = [
    "backup_current_artifacts",
    "categorize_artifacts",
    "cleanup_artifacts",
    "cleanup_artifacts_by_type",
    "cleanup_old_backups",
    "cleanup_temp_artifacts",
    "clear_cache",
    "get_artifact_report",
    "get_backup_details",
    "list_artifact_backups",
    "list_artifacts",
    "rollback_to_backup",
]
