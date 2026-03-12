"""
Transport parity tests - CRIT-6

Tests to verify HTTP and stdio transports have identical security posture.
This test file ensures critical security components are present in both transports.
"""

import pytest
import ast
import importlib.util
from pathlib import Path


class TestTransportSessionServiceParity:
    """Test that both transports inject session_service."""

    @pytest.fixture
    def stdio_server_path(self):
        """Path to stdio server module."""
        return Path(__file__).parent.parent.parent / "src" / "sandbox" / "mcp_sandbox_server_stdio.py"

    @pytest.fixture
    def http_server_path(self):
        """Path to HTTP server module."""
        return Path(__file__).parent.parent.parent / "src" / "sandbox" / "mcp_sandbox_server.py"

    def _get_imports(self, file_path: Path) -> set[str]:
        """Extract imported module names from a Python file."""
        source = file_path.read_text()
        tree = ast.parse(source)

        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    # Get the base module name
                    imports.add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])
        return imports

    def _get_function_calls(self, file_path: Path, function_name: str) -> list[ast.Call]:
        """Extract calls to a specific function from a Python file."""
        source = file_path.read_text()
        tree = ast.parse(source)

        calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == function_name:
                    calls.append(node)
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr == function_name:
                        calls.append(node)
        return calls

    def _get_create_tool_registry_kwargs(self, file_path: Path) -> dict:
        """
        Extract keyword arguments passed to create_tool_registry.

        Returns a dict of keyword argument names to their presence (True/False).
        """
        source = file_path.read_text()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check if this is a call to create_tool_registry
                func_name = None
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr

                if func_name == "create_tool_registry":
                    kwargs = {}
                    for keyword in node.keywords:
                        kwargs[keyword.arg] = True
                    return kwargs

        return {}

    def test_stdio_server_has_session_service_import(self, stdio_server_path):
        """RED Test: stdio server should import session_service module."""
        imports = self._get_imports(stdio_server_path)
        # Check for the session_service import from server
        source = stdio_server_path.read_text()
        assert "from .server.session_service import" in source, \
            "stdio server must import session_service from server module"

    def test_http_server_has_session_service_import(self, http_server_path):
        """RED Test: HTTP server should import session_service module."""
        imports = self._get_imports(http_server_path)
        source = http_server_path.read_text()
        # This test should fail before the fix (RED)
        assert "from .server.session_service import" in source, \
            "HTTP server must import session_service from server module for security parity"

    def test_stdio_server_calls_get_session_service(self, stdio_server_path):
        """RED Test: stdio server should call get_session_service."""
        source = stdio_server_path.read_text()
        assert "get_session_service()" in source, \
            "stdio server must call get_session_service()"

    def test_http_server_calls_get_session_service(self, http_server_path):
        """RED Test: HTTP server should call get_session_service."""
        source = http_server_path.read_text()
        # This test should fail before the fix (RED)
        assert "get_session_service()" in source, \
            "HTTP server must call get_session_service() for security parity"

    def test_stdio_server_passes_session_service_to_registry(self, stdio_server_path):
        """RED Test: stdio server should pass session_service to create_tool_registry."""
        kwargs = self._get_create_tool_registry_kwargs(stdio_server_path)
        assert "session_service" in kwargs, \
            "stdio server must pass session_service to create_tool_registry"

    def test_http_server_passes_session_service_to_registry(self, http_server_path):
        """RED Test: HTTP server should pass session_service to create_tool_registry."""
        kwargs = self._get_create_tool_registry_kwargs(http_server_path)
        # This test should fail before the fix (RED)
        assert "session_service" in kwargs, \
            "HTTP server must pass session_service to create_tool_registry for security parity"

    def test_transport_parity_session_service(self, stdio_server_path, http_server_path):
        """RED Test: Both transports must have identical session_service configuration."""
        stdio_kwargs = self._get_create_tool_registry_kwargs(stdio_server_path)
        http_kwargs = self._get_create_tool_registry_kwargs(http_server_path)

        # Both should have session_service
        assert "session_service" in stdio_kwargs, \
            "stdio server must have session_service"
        assert "session_service" in http_kwargs, \
            "HTTP server must have session_service for security parity with stdio transport"


class TestTransportSecurityParity:
    """Test other security-critical components are present in both transports."""

    @pytest.fixture
    def stdio_server_path(self):
        return Path(__file__).parent.parent.parent / "src" / "sandbox" / "mcp_sandbox_server_stdio.py"

    @pytest.fixture
    def http_server_path(self):
        return Path(__file__).parent.parent.parent / "src" / "sandbox" / "mcp_sandbox_server.py"

    def test_both_transports_use_same_tool_registry(self, stdio_server_path, http_server_path):
        """Both transports should use the same tool_registry module."""
        for path in [stdio_server_path, http_server_path]:
            source = path.read_text()
            assert "from .server.tool_registry import" in source, \
                f"{path.name} must import from tool_registry module"

    def test_both_transports_use_same_execution_context(self, stdio_server_path, http_server_path):
        """Both transports should use the same ExecutionContext factory."""
        for path in [stdio_server_path, http_server_path]:
            source = path.read_text()
            assert "ExecutionContext()" in source, \
                f"{path.name} must create ExecutionContext"

    def test_both_transports_use_security_manager(self, stdio_server_path, http_server_path):
        """Both transports should use SecurityManager."""
        for path in [stdio_server_path, http_server_path]:
            source = path.read_text()
            assert "get_security_manager(" in source, \
                f"{path.name} must use security_manager"
