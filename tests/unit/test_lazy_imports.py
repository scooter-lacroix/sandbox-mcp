"""
Tests for lazy import helpers.

Following quality patterns from Phase 5:
- Type hints with `from __future__ import annotations`
- Comprehensive error handling
- Tests for both success and failure paths
"""

from __future__ import annotations

import pytest
from typing import Any


class TestLazyImport:
    """Test LazyImport class for optional module loading."""

    def test_lazy_import_module_exists(self) -> None:
        """Test that lazy_imports module can be imported."""
        from sandbox.utils.lazy_imports import LazyImport
        assert LazyImport is not None

    def test_lazy_import_available_module(self) -> None:
        """Test lazy import with an available module (json)."""
        from sandbox.utils.lazy_imports import LazyImport
        
        lazy_json = LazyImport("json")
        assert lazy_json.is_available() is True
        
        # Access should work
        assert lazy_json.dumps({"key": "value"}) == '{"key": "value"}'

    def test_lazy_import_unavailable_module(self) -> None:
        """Test lazy import with a non-existent module."""
        from sandbox.utils.lazy_imports import LazyImport
        
        lazy_fake = LazyImport("this_module_does_not_exist_12345")
        assert lazy_fake.is_available() is False
        
        # Access should return None when not required
        assert lazy_fake._import() is None

    def test_lazy_import_required_module_missing(self) -> None:
        """Test that required lazy import raises ImportError."""
        from sandbox.utils.lazy_imports import LazyImport
        
        lazy_fake = LazyImport(
            "this_module_does_not_exist_12345",
            required=True
        )
        
        with pytest.raises(ImportError):
            _ = lazy_fake.some_attribute

    def test_lazy_import_caches_result(self) -> None:
        """Test that lazy import caches the module after first access."""
        from sandbox.utils.lazy_imports import LazyImport
        
        lazy_json = LazyImport("json")
        
        # First access
        assert lazy_json.dumps({}) == "{}"
        cached_module = lazy_json._module
        
        # Second access should use cache
        assert lazy_json.loads("[]") == []
        assert lazy_json._module is cached_module

    def test_lazy_import_getattr_delegation(self) -> None:
        """Test that attribute access is delegated to module."""
        from sandbox.utils.lazy_imports import LazyImport
        
        lazy_json = LazyImport("json")
        
        # Test various json module functions
        assert lazy_json.dumps({"a": 1}) == '{"a": 1}'
        assert lazy_json.loads('{"b": 2}') == {"b": 2}
        assert lazy_json.dumps([1, 2, 3]) == "[1, 2, 3]"


class TestLazyClass:
    """Test LazyClass for optional class loading."""

    def test_lazy_class_module_exists(self) -> None:
        """Test that LazyClass can be imported."""
        from sandbox.utils.lazy_imports import LazyClass
        assert LazyClass is not None

    def test_lazy_class_instantiation(self) -> None:
        """Test lazy class instantiation with a real class."""
        from sandbox.utils.lazy_imports import LazyClass
        
        # Use Path as a test class
        LazyPath = LazyClass("pathlib", "Path")
        
        path_instance = LazyPath("/test/path")
        assert str(path_instance) == "/test/path"
        assert path_instance.name == "path"

    def test_lazy_class_with_install_hint(self) -> None:
        """Test LazyClass with install hint raises helpful error."""
        from sandbox.utils.lazy_imports import LazyClass
        
        LazyFake = LazyClass(
            "nonexistent_module",
            "FakeClass",
            install_hint="pip install fake-package"
        )
        
        with pytest.raises(ImportError) as exc_info:
            LazyFake()
        
        assert "pip install fake-package" in str(exc_info.value)

    def test_lazy_class_getattr_delegation(self) -> None:
        """Test that class attribute access is delegated."""
        from sandbox.utils.lazy_imports import LazyClass
        
        LazyPath = LazyClass("pathlib", "Path")
        
        # Access class methods
        assert hasattr(LazyPath, 'exists')
        assert hasattr(LazyPath, 'is_file')
        assert hasattr(LazyPath, 'is_dir')


class TestGetLazyImport:
    """Test get_lazy_import function for module access."""

    def test_get_lazy_import_function_exists(self) -> None:
        """Test that get_lazy_import can be imported."""
        from sandbox.utils.lazy_imports import get_lazy_import
        assert get_lazy_import is not None

    def test_get_lazy_import_returns_singleton(self) -> None:
        """Test that get_lazy_import returns same instance for same module."""
        from sandbox.utils.lazy_imports import get_lazy_import
        
        lazy1 = get_lazy_import("json")
        lazy2 = get_lazy_import("json")
        
        assert lazy1 is lazy2

    def test_get_lazy_import_different_modules(self) -> None:
        """Test that different modules get different instances."""
        from sandbox.utils.lazy_imports import get_lazy_import
        
        lazy_json = get_lazy_import("json")
        lazy_os = get_lazy_import("os")
        
        assert lazy_json is not lazy_os
        assert lazy_json._module_name == "json"
        assert lazy_os._module_name == "os"


class TestCheckOptionalFeature:
    """Test check_optional_feature function."""

    def test_check_optional_feature_function_exists(self) -> None:
        """Test that check_optional_feature can be imported."""
        from sandbox.utils.lazy_imports import check_optional_feature
        assert check_optional_feature is not None

    def test_check_optional_feature_available(self) -> None:
        """Test checking an available feature."""
        from sandbox.utils.lazy_imports import check_optional_feature
        
        result = check_optional_feature("JSON support", "json")
        assert result is True

    def test_check_optional_feature_unavailable(self) -> None:
        """Test checking an unavailable feature."""
        from sandbox.utils.lazy_imports import check_optional_feature
        
        result = check_optional_feature(
            "Fake feature",
            "this_module_does_not_exist_12345"
        )
        assert result is False


class TestRequireFeature:
    """Test require_feature function."""

    def test_require_feature_function_exists(self) -> None:
        """Test that require_feature can be imported."""
        from sandbox.utils.lazy_imports import require_feature
        assert require_feature is not None

    def test_require_feature_available(self) -> None:
        """Test requiring an available feature."""
        from sandbox.utils.lazy_imports import require_feature
        
        lazy_json = require_feature("JSON support", "json")
        assert lazy_json.is_available() is True
        assert lazy_json.dumps({"test": "value"}) == '{"test": "value"}'

    def test_require_feature_unavailable(self) -> None:
        """Test requiring an unavailable feature raises ImportError."""
        from sandbox.utils.lazy_imports import require_feature
        
        with pytest.raises(ImportError) as exc_info:
            require_feature(
                "Fake feature",
                "this_module_does_not_exist_12345",
                install_command="pip install fake-package"
            )
        
        assert "Fake feature" in str(exc_info.value)
        assert "pip install fake-package" in str(exc_info.value)


class TestPredefinedLazyImports:
    """Test pre-defined lazy imports in the module."""

    def test_predefined_imports_exist(self) -> None:
        """Test that pre-defined lazy imports exist."""
        from sandbox.utils import lazy_imports
        
        assert hasattr(lazy_imports, 'aiohttp')
        assert hasattr(lazy_imports, 'ipython')
        assert hasattr(lazy_imports, 'matplotlib')
        assert hasattr(lazy_imports, 'pil')
        assert hasattr(lazy_imports, 'flask')
        assert hasattr(lazy_imports, 'streamlit')
        assert hasattr(lazy_imports, 'manim')

    def test_aiohttp_available(self) -> None:
        """Test that aiohttp lazy import works (should be installed)."""
        from sandbox.utils.lazy_imports import aiohttp
        
        # aiohttp should be available in test environment
        assert aiohttp.is_available() is True


class TestLazyImportsWithSandbox:
    """Integration tests for lazy imports with sandbox package."""

    def test_sandbox_uses_lazy_imports(self) -> None:
        """Test that sandbox package uses lazy imports correctly."""
        # Import should work without aiohttp being loaded yet
        import sandbox
        
        # Check that lazy imports are set up
        assert hasattr(sandbox, 'server')
        assert hasattr(sandbox, 'sdk')
        
        # Access should trigger lazy loading
        # This will work if the modules exist
        assert sandbox.server is not None
