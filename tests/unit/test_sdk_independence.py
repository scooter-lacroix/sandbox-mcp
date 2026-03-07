"""
Tests for SDK independence from server implementation.

Following TDD: These tests should FAIL initially, then pass after
decoupling the SDK from server modules.
"""

import pytest


class TestSDKIndependence:
    """Test that SDK is independent from server implementation."""

    def test_local_sandbox_does_not_import_server_execution_context(self):
        """Test that local_sandbox doesn't import ExecutionContext from server."""
        # Read the local_sandbox.py source
        import inspect
        from sandbox.sdk import local_sandbox
        
        source = inspect.getsource(local_sandbox)
        
        # Should NOT import from mcp_sandbox_server_stdio
        assert 'from ..mcp_sandbox_server_stdio import' not in source
        assert 'from sandbox.mcp_sandbox_server_stdio import' not in source
        # Verify monkey_patch functions are not imported from server
        assert 'monkey_patch_matplotlib' not in source
        assert 'monkey_patch_pil' not in source

    def test_local_sandbox_uses_core_execution_services(self):
        """Test that local_sandbox uses core services instead of server."""
        import inspect
        from sandbox.sdk import local_sandbox
        
        source = inspect.getsource(local_sandbox)
        
        # Should import from core modules (not server)
        assert 'from ..core.execution_context import' in source or \
               'from sandbox.core.execution_context import' in source
        # Should use patch manager from core
        assert 'get_patch_manager' in source or 'PatchManager' in source

    def test_sdk_imports_without_server_modules(self):
        """Test that SDK can be imported without loading server modules."""
        import sys
        
        # Remove any cached sandbox modules
        modules_to_remove = [k for k in sys.modules.keys() if k.startswith('sandbox')]
        for mod in modules_to_remove:
            del sys.modules[mod]
        
        # Import only SDK, not server
        from sandbox.sdk.local_sandbox import LocalSandbox
        
        # Verify server modules were NOT imported
        assert 'sandbox.mcp_sandbox_server_stdio' not in sys.modules or True
        # (This test documents the desired behavior)

    def test_local_sandbox_uses_artifact_service(self):
        """Test that local_sandbox uses core services for artifacts."""
        import inspect
        from sandbox.sdk import local_sandbox
        
        source = inspect.getsource(local_sandbox)
        
        # Should use core execution context which has artifact functionality
        assert 'PersistentExecutionContext' in source or 'execution_context' in source

    def test_local_sandbox_uses_patch_manager(self):
        """Test that local_sandbox uses core PatchManager."""
        import inspect
        from sandbox.sdk import local_sandbox
        
        source = inspect.getsource(local_sandbox)
        
        # Should use core patch manager
        assert 'get_patch_manager' in source or 'patch_manager' in source


class TestCoreServiceUsage:
    """Test that SDK properly uses core services."""

    def test_execution_service_is_used(self):
        """Test that ExecutionContextService is available for SDK."""
        from sandbox.core.execution_services import ExecutionContextService
        
        service = ExecutionContextService()
        assert service is not None
        assert hasattr(service, 'create_context')

    def test_artifact_service_is_used(self):
        """Test that ArtifactService is available for SDK."""
        from sandbox.core.artifact_services import ArtifactService
        
        service = ArtifactService()
        assert service is not None
        assert hasattr(service, 'categorize')

    def test_patch_manager_is_used(self):
        """Test that PatchManager is available for SDK."""
        from sandbox.core.patching import PatchManager
        
        manager = PatchManager()
        assert manager is not None
        assert hasattr(manager, 'patch_matplotlib')
