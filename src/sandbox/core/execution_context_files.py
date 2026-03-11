"""
File operation methods for execution context.

This module contains methods for file and directory operations
with security checks and proper logging.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def save_error_details(
    artifacts_dir: Path,
    error: Exception,
    code: str,
    traceback_str: str,
    session_id: str
) -> None:
    """
    Save detailed error information for debugging.

    Args:
        artifacts_dir: Path to the artifacts directory
        error: The exception that occurred
        code: The code that caused the error
        traceback_str: Full traceback string
        session_id: Current session ID
    """
    try:
        error_dir = artifacts_dir / "logs"
        error_dir.mkdir(exist_ok=True)

        error_file = error_dir / f"error_{int(time.time())}.log"
        with open(error_file, 'w') as f:
            f.write(f"Error occurred at: {time.ctime()}\n")
            f.write(f"Error type: {type(error).__name__}\n")
            f.write(f"Error message: {str(error)}\n")
            f.write(f"Session ID: {session_id}\n")
            f.write("\n" + "="*50 + "\n")
            f.write("Code that caused the error:\n")
            f.write("="*50 + "\n")
            f.write(code)
            f.write("\n" + "="*50 + "\n")
            f.write("Full traceback:\n")
            f.write("="*50 + "\n")
            f.write(traceback_str)

        logger.info(f"Error details saved to: {error_file}")
    except Exception as e:
        logger.error(f"Failed to save error details: {e}")


def change_working_directory(
    path: str,
    temporary: bool,
    directory_monitor,
    home_dir: Path
) -> Dict[str, Any]:
    """
    Change the working directory with security checks and logging.

    Args:
        path: The new directory path
        temporary: Whether this is a temporary change (returns to default after operation)
        directory_monitor: DirectoryChangeMonitor instance for security checks
        home_dir: Home directory path for security validation

    Returns:
        Dictionary containing operation result and current directory info
    """
    try:
        new_path = Path(path).resolve()

        # Security check through directory monitor
        directory_monitor.change_directory(new_path)

        # Change actual working directory
        original_cwd = os.getcwd()
        os.chdir(new_path)

        logger.info(f"Changed working directory to: {new_path}")

        return {
            'success': True,
            'current_directory': str(new_path),
            'previous_directory': original_cwd,
            'is_default': new_path == directory_monitor.default_dir,
            'is_temporary': temporary
        }

    except PermissionError as e:
        logger.error(f"Permission denied changing directory: {e}")
        return {
            'success': False,
            'error': str(e),
            'current_directory': os.getcwd()
        }
    except Exception as e:
        logger.error(f"Error changing directory: {e}")
        return {
            'success': False,
            'error': str(e),
            'current_directory': os.getcwd()
        }


def list_directory(
    path: Optional[str],
    include_hidden: bool,
    home_dir: Path
) -> Dict[str, Any]:
    """
    List contents of a directory with security checks.

    Args:
        path: Directory to list (defaults to current directory)
        include_hidden: Whether to include hidden files
        home_dir: Home directory path for security validation

    Returns:
        Dictionary containing directory contents and metadata
    """
    try:
        target_path = Path(path) if path else Path.cwd()
        target_path = target_path.resolve()

        # Security check
        if not target_path.is_relative_to(home_dir):
            raise PermissionError(f"Cannot access directory outside home: {target_path}")

        if not target_path.exists():
            return {
                'success': False,
                'error': f"Directory does not exist: {target_path}",
                'path': str(target_path)
            }

        items = []
        for item in target_path.iterdir():
            if not include_hidden and item.name.startswith('.'):
                continue

            try:
                stat = item.stat()
                items.append({
                    'name': item.name,
                    'type': 'directory' if item.is_dir() else 'file',
                    'size': stat.st_size if item.is_file() else None,
                    'modified': stat.st_mtime,
                    'permissions': oct(stat.st_mode)[-3:]
                })
            except Exception as e:
                logger.warning(f"Failed to get info for {item}: {e}")

        logger.info(f"Listed directory: {target_path} ({len(items)} items)")

        return {
            'success': True,
            'path': str(target_path),
            'items': sorted(items, key=lambda x: (x['type'], x['name'])),
            'total_items': len(items)
        }

    except PermissionError as e:
        logger.error(f"Permission denied listing directory: {e}")
        return {
            'success': False,
            'error': str(e),
            'path': str(target_path) if 'target_path' in locals() else path
        }
    except Exception as e:
        logger.error(f"Error listing directory: {e}")
        return {
            'success': False,
            'error': str(e),
            'path': str(target_path) if 'target_path' in locals() else path
        }


def find_files(
    pattern: str,
    search_path: Optional[str],
    max_results: int,
    home_dir: Path
) -> Dict[str, Any]:
    """
    Find files matching a pattern with security checks.

    Args:
        pattern: Glob pattern to search for
        search_path: Directory to search in (defaults to current directory)
        max_results: Maximum number of results to return
        home_dir: Home directory path for security validation

    Returns:
        Dictionary containing search results
    """
    try:
        base_path = Path(search_path) if search_path else Path.cwd()
        base_path = base_path.resolve()

        # Security check
        if not base_path.is_relative_to(home_dir):
            raise PermissionError(f"Cannot search directory outside home: {base_path}")

        matches = []
        for file_path in base_path.glob(pattern):
            if len(matches) >= max_results:
                break

            try:
                stat = file_path.stat()
                matches.append({
                    'path': str(file_path),
                    'relative_path': str(file_path.relative_to(base_path)),
                    'name': file_path.name,
                    'type': 'directory' if file_path.is_dir() else 'file',
                    'size': stat.st_size if file_path.is_file() else None,
                    'modified': stat.st_mtime
                })
            except Exception as e:
                logger.warning(f"Failed to get info for {file_path}: {e}")

        logger.info(f"Found {len(matches)} files matching pattern '{pattern}' in {base_path}")

        return {
            'success': True,
            'pattern': pattern,
            'search_path': str(base_path),
            'matches': matches,
            'total_matches': len(matches),
            'truncated': len(matches) >= max_results
        }

    except PermissionError as e:
        logger.error(f"Permission denied searching files: {e}")
        return {
            'success': False,
            'error': str(e),
            'pattern': pattern,
            'search_path': str(base_path) if 'base_path' in locals() else search_path
        }
    except Exception as e:
        logger.error(f"Error searching files: {e}")
        return {
            'success': False,
            'error': str(e),
            'pattern': pattern,
            'search_path': str(base_path) if 'base_path' in locals() else search_path
        }


def reset_to_default_directory(directory_monitor) -> Dict[str, Any]:
    """
    Reset working directory to the default sandbox area.

    Args:
        directory_monitor: DirectoryChangeMonitor instance

    Returns:
        Dictionary containing operation result
    """
    try:
        directory_monitor.reset_to_default()
        os.chdir(directory_monitor.default_dir)

        logger.info(f"Reset to default directory: {directory_monitor.default_dir}")

        return {
            'success': True,
            'current_directory': str(directory_monitor.default_dir),
            'message': 'Reset to default sandbox directory'
        }

    except Exception as e:
        logger.error(f"Error resetting directory: {e}")
        return {
            'success': False,
            'error': str(e),
            'current_directory': os.getcwd()
        }


def get_current_directory_info(
    directory_monitor,
    home_dir: Path,
    artifacts_dir: Path
) -> Dict[str, Any]:
    """
    Get information about the current working directory.

    Args:
        directory_monitor: DirectoryChangeMonitor instance
        home_dir: Home directory path
        artifacts_dir: Artifacts directory path

    Returns:
        Dictionary containing current directory information
    """
    try:
        current_dir = Path.cwd()

        return {
            'current_directory': str(current_dir),
            'default_directory': str(directory_monitor.default_dir),
            'home_directory': str(home_dir),
            'is_default': current_dir == directory_monitor.default_dir,
            'is_in_home': current_dir.is_relative_to(home_dir),
            'artifacts_directory': str(artifacts_dir)
        }

    except Exception as e:
        logger.error(f"Error getting directory info: {e}")
        return {
            'error': str(e),
            'current_directory': os.getcwd()
        }
