"""
Artifact management utilities for PersistentExecutionContext.

This module provides functions for managing, categorizing, and reporting
on artifacts generated during code execution.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Any, Set, List


logger = logging.getLogger(__name__)


def get_current_artifacts(artifacts_dir: Path) -> Set[str]:
    """Get current set of artifact files.

    Security: Symlinks are skipped to prevent host file exfiltration attacks.

    Args:
        artifacts_dir: The artifacts directory path

    Returns:
        Set of relative artifact file paths
    """
    artifacts = set()
    if artifacts_dir.exists():
        artifacts_root = artifacts_dir.resolve()
        for file_path in artifacts_root.rglob('*'):
            # SECURITY S1: Skip symlinks to prevent host file exfiltration
            if file_path.is_symlink():
                continue
            if not file_path.is_file():
                continue

            # SECURITY S1: Verify resolved path is still within artifacts_root
            try:
                resolved_path = file_path.resolve()
                if not resolved_path.is_relative_to(artifacts_root):
                    continue
            except (ValueError, OSError):
                continue

            artifacts.add(str(file_path.relative_to(artifacts_root)))
    return artifacts


def categorize_artifacts(artifacts_dir: Path) -> Dict[str, List[Dict[str, Any]]]:
    """Categorize artifacts by type with detailed metadata.

    Args:
        artifacts_dir: The artifacts directory path

    Returns:
        Dictionary mapping category names to lists of file info dicts
    """
    categories = {
        'images': [],
        'videos': [],
        'plots': [],
        'data': [],
        'code': [],
        'documents': [],
        'audio': [],
        'manim': [],
        'other': []
    }

    if not artifacts_dir.exists():
        return categories

    # File type mappings
    type_mappings = {
        'images': {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.svg', '.webp'},
        'videos': {'.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv'},
        'plots': {'.png', '.jpg', '.jpeg', '.pdf', '.svg'},  # When in plots directory
        'data': {'.csv', '.json', '.xml', '.yaml', '.yml', '.pkl', '.pickle', '.h5', '.hdf5'},
        'code': {'.py', '.js', '.html', '.css', '.sql', '.sh', '.bat'},
        'documents': {'.pdf', '.docx', '.doc', '.txt', '.md', '.rtf'},
        'audio': {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a'},
        'manim': {'.mp4', '.png', '.gif'}  # When in manim-related directories
    }

    for file_path in artifacts_dir.rglob('*'):
        # SECURITY CRIT-3: Skip symlinks to prevent host file exfiltration
        if file_path.is_symlink():
            logger.warning(f"Skipping symlink in artifacts: {file_path}")
            continue
        if not file_path.is_file():
            continue

        relative_path = file_path.relative_to(artifacts_dir)
        suffix = file_path.suffix.lower()

        # Get file info
        try:
            stat = file_path.stat()
            file_info = {
                'path': str(relative_path),
                'full_path': str(file_path),
                'size': stat.st_size,
                'created': stat.st_ctime,
                'modified': stat.st_mtime,
                'extension': suffix,
                'name': file_path.name
            }
        except Exception as e:
            logger.warning(f"Failed to get file info for {file_path}: {e}")
            continue

        # Categorize based on location and extension
        categorized = False

        # Check if it's in a specific subdirectory
        parts = relative_path.parts
        if len(parts) > 1:
            subdir = parts[0]
            if subdir in categories:
                categories[subdir].append(file_info)
                categorized = True

        # Enhanced Manim detection - check for various Manim output patterns
        if not categorized:
            path_str = str(relative_path).lower()
            if any(pattern in path_str for pattern in [
                'manim', 'scene', 'media', 'videos', 'images', 'tex', 'text'
            ]) and any(pattern in path_str for pattern in [
                'manim_', 'scene_', 'media/', 'videos/', 'images/'
            ]):
                categories['manim'].append(file_info)
                categorized = True

        # If not categorized by directory, use extension
        if not categorized:
            for category, extensions in type_mappings.items():
                if suffix in extensions:
                    # Additional Manim detection by content and path patterns
                    if category in ['videos', 'images'] and any(pattern in str(relative_path).lower() for pattern in [
                        'manim', 'scene', 'media/', 'videos/', 'images/', 'tex/', 'text/'
                    ]):
                        categories['manim'].append(file_info)
                    else:
                        categories[category].append(file_info)
                    categorized = True
                    break

        # If still not categorized, put in 'other'
        if not categorized:
            categories['other'].append(file_info)

    return categories


def get_artifact_report(artifacts_dir: Path) -> Dict[str, Any]:
    """Generate comprehensive artifact report.

    Args:
        artifacts_dir: The artifacts directory path

    Returns:
        Dictionary containing artifact statistics and metadata
    """
    categorized = categorize_artifacts(artifacts_dir)

    report = {
        'total_artifacts': sum(len(files) for files in categorized.values()),
        'categories': {},
        'recent_artifacts': [],
        'largest_artifacts': [],
        'total_size': 0
    }

    all_artifacts = []

    for category, files in categorized.items():
        if files:
            category_size = sum(f['size'] for f in files)
            report['categories'][category] = {
                'count': len(files),
                'size': category_size,
                'files': files
            }
            report['total_size'] += category_size
            all_artifacts.extend(files)

    # Sort by modification time for recent artifacts
    if all_artifacts:
        all_artifacts.sort(key=lambda x: x['modified'], reverse=True)
        report['recent_artifacts'] = all_artifacts[:10]

        # Sort by size for largest artifacts
        all_artifacts.sort(key=lambda x: x['size'], reverse=True)
        report['largest_artifacts'] = all_artifacts[:10]

    return report
