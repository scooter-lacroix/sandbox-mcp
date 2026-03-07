"""
Lazy import helpers for optional features.

This module provides lazy loading for optional dependencies to reduce
import time and memory usage when features are not used.
"""

from __future__ import annotations

import importlib
from typing import Any, Callable, Dict, Optional, Type, TypeVar

T = TypeVar("T")


class LazyImport:
    """
    Lazy importer for optional modules.

    Defers module import until first access, reducing initial import time
    and memory usage for optional features.
    """

    def __init__(self, module_name: str, *, required: bool = False) -> None:
        """
        Initialize lazy importer.

        Args:
            module_name: Full module path to import (e.g., 'aiohttp')
            required: If True, raise ImportError immediately on access
        """
        self._module_name = module_name
        self._required = required
        self._module: Optional[Any] = None
        self._import_error: Optional[ImportError] = None

    def _import(self) -> Any:
        """Perform the actual import with error caching."""
        if self._module is not None:
            return self._module

        if self._import_error is not None:
            if self._required:
                raise self._import_error
            return None

        try:
            self._module = importlib.import_module(self._module_name)
        except ImportError as e:
            self._import_error = e
            if self._required:
                raise
            return None

        return self._module

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to the imported module."""
        module = self._import()
        if module is None:
            raise AttributeError(
                f"Optional module '{self._module_name}' is not installed"
            )
        return getattr(module, name)

    def is_available(self) -> bool:
        """Check if the module is available without importing it."""
        if self._module is not None:
            return True
        if self._import_error is not None:
            return False

        try:
            importlib.import_module(self._module_name)
            return True
        except ImportError:
            return False


class LazyClass:
    """
    Lazy class importer for optional features.

    Defers class import until first instantiation, useful for
    optional sandbox implementations (e.g., remote, node).
    """

    def __init__(
        self,
        module_path: str,
        class_name: str,
        *,
        install_hint: Optional[str] = None,
    ) -> None:
        """
        Initialize lazy class importer.

        Args:
            module_path: Module containing the class (e.g., 'sandbox.sdk')
            class_name: Name of the class to import
            install_hint: Optional hint for installing the dependency
        """
        self._module_path = module_path
        self._class_name = class_name
        self._install_hint = install_hint
        self._class: Optional[Type[Any]] = None
        self._import_error: Optional[ImportError] = None

    def _get_class(self) -> Type[Any]:
        """Get the class, importing if necessary."""
        if self._class is not None:
            return self._class

        if self._import_error is not None:
            raise self._import_error

        try:
            module = importlib.import_module(self._module_path)
            self._class = getattr(module, self._class_name)
        except ImportError as e:
            self._import_error = e
            if self._install_hint:
                raise ImportError(
                    f"{e}. {self._install_hint}"
                ) from e
            raise

        return self._class

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Instantiate the class with lazy import."""
        cls = self._get_class()
        return cls(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        """Delegate class attribute access."""
        cls = self._get_class()
        return getattr(cls, name)


# Global lazy import registry for tracking
_lazy_imports: Dict[str, LazyImport] = {}


def get_lazy_import(
    module_name: str,
    *,
    required: bool = False,
) -> LazyImport:
    """
    Get or create a lazy import for a module.

    Args:
        module_name: Module path to import
        required: If True, raise ImportError on access if missing

    Returns:
        LazyImport instance for the module
    """
    if module_name not in _lazy_imports:
        _lazy_imports[module_name] = LazyImport(module_name, required=required)
    return _lazy_imports[module_name]


# Pre-defined lazy imports for common optional dependencies
aiohttp = get_lazy_import("aiohttp")
ipython = get_lazy_import("IPython")
matplotlib = get_lazy_import("matplotlib")
pil = get_lazy_import("PIL")
flask = get_lazy_import("flask")
streamlit = get_lazy_import("streamlit")
manim = get_lazy_import("manim")


def check_optional_feature(
    feature_name: str,
    module_name: str,
    *,
    install_command: Optional[str] = None,
) -> bool:
    """
    Check if an optional feature is available.

    Args:
        feature_name: Human-readable feature name
        module_name: Module to check
        install_command: Optional pip install command for error message

    Returns:
        True if feature is available, False otherwise
    """
    lazy = get_lazy_import(module_name)
    return lazy.is_available()


def require_feature(
    feature_name: str,
    module_name: str,
    *,
    install_command: Optional[str] = None,
) -> LazyImport:
    """
    Require an optional feature, raising a helpful error if missing.

    Args:
        feature_name: Human-readable feature name
        module_name: Module to require
        install_command: Optional pip install command for error message

    Returns:
        LazyImport instance for the module

    Raises:
        ImportError: If feature is not available
    """
    lazy = get_lazy_import(module_name, required=True)

    if not lazy.is_available():
        error_msg = f"Feature '{feature_name}' requires '{module_name}'"
        if install_command:
            error_msg += f". Install with: {install_command}"
        raise ImportError(error_msg)

    return lazy
