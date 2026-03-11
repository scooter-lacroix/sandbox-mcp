"""
Directory change monitoring for persistent execution context.

This module provides directory change tracking with security validation
to prevent unauthorized directory traversal. Extracted from execution_context.py
to reduce module size and improve maintainability.

Features:
- Path validation against home directory boundary
- Directory change logging
- Default directory reset capability
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class DirectoryChangeMonitor:
    """Monitor and control directory changes within authorized boundaries."""

    def __init__(self, default_working_dir: Path, home_dir: Path) -> None:
        """
        Initialize directory change monitor.

        Args:
            default_working_dir: Default working directory for the session
            home_dir: Home directory boundary for security validation
        """
        self.current_dir = default_working_dir
        self.default_dir = default_working_dir
        self.home_dir = home_dir

    def change_directory(self, new_dir: Path) -> None:
        """
        Change to a new directory with security validation.

        Args:
            new_dir: Target directory to change to

        Raises:
            PermissionError: If new_dir is outside the home directory boundary
        """
        if new_dir.resolve() != self.default_dir.resolve() and not new_dir.resolve().is_relative_to(self.home_dir):
            logger.warning(f"Unauthorized attempt to change directory: {new_dir}")
            raise PermissionError(f"Cannot change to directory outside home: {new_dir}")
        logger.info(f"Changing directory from {self.current_dir} to {new_dir}")
        self.current_dir = new_dir

    def reset_to_default(self) -> None:
        """Reset to the default working directory."""
        logger.info(f"Resetting to default directory: {self.default_dir}")
        self.current_dir = self.default_dir
