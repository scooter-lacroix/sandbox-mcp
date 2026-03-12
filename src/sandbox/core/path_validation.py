"""
Path Validation Utilities for Sandbox MCP.

Security S4: Centralized path validation using is_relative_to() to prevent
path traversal attacks via similar prefixes.

This module consolidates duplicate path validation logic from across
the codebase into a single authoritative source.
"""

from pathlib import Path
from typing import List, Optional, Set


class PathValidator:
    """
    Centralized path validation utilities.
    
    Security S4: Uses is_relative_to() instead of startswith() to prevent
    path traversal attacks (e.g., /home/user_evil vs /home/user).
    """
    
    def __init__(
        self,
        base_paths: Optional[List[Path]] = None,
        allowed_prefixes: Optional[List[Path]] = None,
    ):
        """
        Initialize path validator with allowed base paths.
        
        Args:
            base_paths: List of base paths that are considered safe.
            allowed_prefixes: Additional allowed prefix paths.
        """
        self._base_paths: Set[Path] = set()
        self._allowed_prefixes: Set[Path] = set()
        
        if base_paths:
            for bp in base_paths:
                self._base_paths.add(bp.resolve())
        
        if allowed_prefixes:
            for prefix in allowed_prefixes:
                self._allowed_prefixes.add(prefix.resolve())
    
    def add_base_path(self, path: Path) -> None:
        """Add a base path to the allowed list."""
        self._base_paths.add(path.resolve())
    
    def add_allowed_prefix(self, path: Path) -> None:
        """Add an allowed prefix path."""
        self._allowed_prefixes.add(path.resolve())
    
    def is_safe_path(self, path: Path, require_exists: bool = False) -> bool:
        """
        Check if a path is safe (within allowed boundaries).
        
        Security S4: Uses is_relative_to() to prevent prefix attacks.
        
        Args:
            path: The path to validate.
            require_exists: If True, path must exist.
            
        Returns:
            True if path is safe, False otherwise.
        """
        try:
            path_resolved = path.resolve()
        except (OSError, ValueError):
            return False
        
        # Check for path traversal patterns
        if ".." in path_resolved.parts:
            return False
        
        # Check if path is within any base path
        for base in self._base_paths:
            if self._is_within_base(path_resolved, base):
                if require_exists and not path_resolved.exists():
                    return False
                return True
        
        # Check if path is within any allowed prefix
        for prefix in self._allowed_prefixes:
            if self._is_within_base(path_resolved, prefix):
                if require_exists and not path_resolved.exists():
                    return False
                return True
        
        return False
    
    @staticmethod
    def sanitize_path_component(component: str) -> str:
        """
        Sanitize a string for use as a path component.

        Security CRIT-1: Prevents path traversal attacks via session_id or
        other user-provided path components. Rejects strings that would escape
        their intended directory.

        Args:
            component: The string to sanitize.

        Returns:
            The sanitized string (same as input if valid).

        Raises:
            ValueError: If component contains path traversal patterns.

        Examples:
            >>> PathValidator.sanitize_path_component("session_123")
            'session_123'
            >>> PathValidator.sanitize_path_component("../escape")
            ValueError: Path component contains invalid characters
        """
        if not component:
            raise ValueError("Path component cannot be empty")

        # Strip whitespace
        stripped = component.strip()
        if not stripped:
            raise ValueError("Path component cannot be empty or whitespace only")

        # Reject path traversal sequences
        if ".." in stripped:
            raise ValueError("Path component contains '..' (path traversal)")

        # Reject absolute paths (Unix)
        if stripped.startswith("/"):
            raise ValueError("Path component cannot be absolute path")

        # Reject absolute paths (Windows drive letters)
        if len(stripped) >= 2 and stripped[1] == ":":
            raise ValueError("Path component cannot be absolute path")

        # Reject path separators (after absolute path check for clearer errors)
        if "/" in stripped or "\\" in stripped:
            raise ValueError("Path component contains path separators")

        # Reject leading dots (hidden files that could be used for traversal)
        if stripped.startswith("."):
            raise ValueError("Path component cannot start with '.'")

        return stripped

    @staticmethod
    def _is_within_base(path: Path, base: Path) -> bool:
        """
        Check if path is within base directory.
        
        Security S4: Uses is_relative_to() instead of startswith().
        
        Example: /home/user_evil is NOT within /home/user
        """
        try:
            return path.is_relative_to(base)
        except (ValueError, TypeError):
            return False
    
    def validate_or_raise(
        self,
        path: Path,
        require_exists: bool = False,
        exception_type: type = ValueError,
    ) -> Path:
        """
        Validate path and raise exception if invalid.
        
        Args:
            path: The path to validate.
            require_exists: If True, path must exist.
            exception_type: Type of exception to raise.
            
        Returns:
            The validated path.
            
        Raises:
            exception_type: If path is not safe.
        """
        if not self.is_safe_path(path, require_exists):
            raise exception_type(f"Path not allowed: {path}")
        return path


# Default validator with common safe paths
_default_validator: Optional[PathValidator] = None


def get_default_validator() -> PathValidator:
    """Get or create default path validator with standard safe paths."""
    global _default_validator
    if _default_validator is None:
        home = Path.home()
        _default_validator = PathValidator(
            base_paths=[home],
            allowed_prefixes=[
                home / "Documents",
                home / "Projects",
                home / "work",
                home / "dev",
            ],
        )
    return _default_validator


def is_safe_path(path: Path, require_exists: bool = False) -> bool:
    """
    Check if path is safe using default validator.
    
    Security S4: Uses is_relative_to() to prevent prefix attacks.
    """
    return get_default_validator().is_safe_path(path, require_exists)


def validate_path(
    path: Path,
    require_exists: bool = False,
) -> Path:
    """
    Validate path using default validator.
    
    Security S4: Uses is_relative_to() to prevent prefix attacks.
    
    Raises:
        ValueError: If path is not safe.
    """
    return get_default_validator().validate_or_raise(path, require_exists)
