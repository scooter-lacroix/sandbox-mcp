"""
Tests for tool registry module.
"""

import pytest
from unittest.mock import MagicMock, Mock


class TestToolRegistry:
    """Test MCP tool registry."""

    def test_tool_registry_module_exists(self):
        """Test that tool_registry module can be imported."""
        from sandbox.server.tool_registry import ToolRegistry
        assert ToolRegistry is not None

    def test_tool_registry_initialization(self):
        """Test that ToolRegistry can be instantiated."""
        from sandbox.server.tool_registry import ToolRegistry
        
        mock_mcp = MagicMock()
        mock_ctx = MagicMock()
        
        registry = ToolRegistry(mock_mcp, mock_ctx)
        assert registry is not None
        assert registry.mcp == mock_mcp
        assert registry.ctx == mock_ctx

    def test_tool_registry_has_all_tools(self):
        """Test that tool registry has all expected tool registration methods."""
        from sandbox.server.tool_registry import ToolRegistry
        
        mock_mcp = MagicMock()
        mock_ctx = MagicMock()
        
        registry = ToolRegistry(mock_mcp, mock_ctx)
        
        # Check for key tool registration methods
        assert hasattr(registry, '_register_execute_tool')
        assert hasattr(registry, '_register_list_artifacts_tool')
        assert hasattr(registry, '_register_start_web_app_tool')
        assert hasattr(registry, '_register_export_web_app_tool')
        assert hasattr(registry, '_register_get_comprehensive_help_tool')

    def test_create_tool_registry_function(self):
        """Test the create_tool_registry helper function."""
        from sandbox.server.tool_registry import create_tool_registry, ToolRegistry
        
        mock_mcp = MagicMock()
        mock_ctx = MagicMock()
        
        registry = create_tool_registry(mock_mcp, mock_ctx)
        assert registry is not None
        assert isinstance(registry, ToolRegistry)


class TestToolRegistryHelpers:
    """Test tool registry helper modules."""

    def test_execution_helpers_import(self):
        """Test that execution_helpers module can be imported."""
        from sandbox.server import execution_helpers
        assert execution_helpers is not None
        assert hasattr(execution_helpers, 'execute_code_with_context')

    def test_artifact_helpers_import(self):
        """Test that artifact_helpers module can be imported."""
        from sandbox.server import artifact_helpers
        assert artifact_helpers is not None
        assert hasattr(artifact_helpers, 'list_artifacts_helper')

    def test_web_helpers_import(self):
        """Test that web_helpers module can be imported."""
        from sandbox.server import web_helpers
        assert web_helpers is not None
        assert hasattr(web_helpers, 'start_web_app_helper')

    def test_manim_helpers_import(self):
        """Test that manim_helpers module can be imported."""
        from sandbox.server import manim_helpers
        assert manim_helpers is not None
        assert hasattr(manim_helpers, 'get_manim_examples_helper')

    def test_package_helpers_import(self):
        """Test that package_helpers module can be imported."""
        from sandbox.server import package_helpers
        assert package_helpers is not None
        assert hasattr(package_helpers, 'install_package_helper')

    def test_shell_helpers_import(self):
        """Test that shell_helpers module can be imported."""
        from sandbox.server import shell_helpers
        assert shell_helpers is not None
        assert hasattr(shell_helpers, 'shell_execute_helper')

    def test_info_helpers_import(self):
        """Test that info_helpers module can be imported."""
        from sandbox.server import info_helpers
        assert info_helpers is not None
        assert hasattr(info_helpers, 'get_execution_info_helper')


class TestHelperFunctions:
    """Test helper function outputs."""

    def test_list_artifacts_helper_returns_json(self):
        """Test that list_artifacts_helper returns valid JSON."""
        from sandbox.server.artifact_helpers import list_artifacts_helper
        import json
        
        mock_ctx = MagicMock()
        result = list_artifacts_helper(None, mock_ctx)
        
        # Should be valid JSON
        parsed = json.loads(result)
        assert 'status' in parsed

    def test_get_execution_info_helper_returns_json(self):
        """Test that get_execution_info_helper returns valid JSON."""
        from sandbox.server.info_helpers import get_execution_info_helper
        import json
        
        mock_ctx = MagicMock()
        mock_ctx.project_root = '/test'
        mock_ctx.artifacts_dir = '/test/artifacts'
        
        result = get_execution_info_helper(mock_ctx)
        
        # Should be valid JSON
        parsed = json.loads(result)
        assert 'status' in parsed
        assert 'execution_info' in parsed

    def test_get_comprehensive_help_helper_returns_json(self):
        """Test that get_comprehensive_help_helper returns valid JSON."""
        from sandbox.server.info_helpers import get_comprehensive_help_helper
        import json
        
        result = get_comprehensive_help_helper()
        
        # Should be valid JSON
        parsed = json.loads(result)
        assert 'status' in parsed
        assert 'help' in parsed
