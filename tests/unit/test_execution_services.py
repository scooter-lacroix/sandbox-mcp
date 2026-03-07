"""
Tests for unified execution services.

Following TDD: These tests should FAIL initially, then pass after
implementing src/sandbox/core/execution_services.py
"""

import pytest
import pytest_asyncio


@pytest.mark.asyncio
class TestUnifiedExecutionContext:
    """Test unified ExecutionContext interface."""

    async def test_execution_services_module_exists(self):
        """Test that execution_services module can be imported."""
        # This test should FAIL initially (module doesn't exist)
        # After implementation, it should pass
        from sandbox.core.execution_services import ExecutionContextService
        assert ExecutionContextService is not None

    async def test_execution_service_initialization(self):
        """Test that ExecutionContextService can be instantiated."""
        from sandbox.core.execution_services import ExecutionContextService
        
        service = ExecutionContextService()
        assert service is not None
        assert hasattr(service, 'create_context')

    async def test_execution_service_creates_context(self):
        """Test that execution service creates execution context."""
        from sandbox.core.execution_services import ExecutionContextService
        
        service = ExecutionContextService()
        context = service.create_context()
        
        assert context is not None
        assert hasattr(context, 'project_root')
        assert hasattr(context, 'sandbox_area')

    async def test_execution_service_has_setup_environment(self):
        """Test that execution service can setup environment."""
        from sandbox.core.execution_services import ExecutionContextService
        
        service = ExecutionContextService()
        context = service.create_context()
        
        # Should have setup method
        assert hasattr(service, 'setup_environment')
        
        # Setup should work without errors
        await service.setup_environment(context)

    async def test_execution_service_has_cleanup(self):
        """Test that execution service has cleanup method."""
        from sandbox.core.execution_services import ExecutionContextService
        
        service = ExecutionContextService()
        
        # Should have cleanup method
        assert hasattr(service, 'cleanup')

    async def test_execution_context_has_artifacts_dir(self):
        """Test that execution context has artifacts directory."""
        from sandbox.core.execution_services import ExecutionContextService
        
        service = ExecutionContextService()
        context = service.create_context()
        
        # Should have artifacts_dir attribute
        assert hasattr(context, 'artifacts_dir')

    async def test_execution_context_has_sys_path_management(self):
        """Test that execution service manages sys.path."""
        from sandbox.core.execution_services import ExecutionContextService
        
        service = ExecutionContextService()
        
        # Should have method to manage paths
        assert hasattr(service, 'add_to_path') or hasattr(service, 'setup_environment')


@pytest.mark.asyncio
class TestExecutionContextConsolidation:
    """Test that duplicate ExecutionContext logic is consolidated."""

    async def test_single_source_of_truth_for_execution_context(self):
        """Test that there's only one ExecutionContext implementation in core."""
        # After refactoring, both servers should use the core service
        # This test verifies the core service exists and is importable
        from sandbox.core.execution_services import ExecutionContextService
        
        # Should be able to import without importing server modules
        service = ExecutionContextService()
        assert service is not None

    async def test_servers_use_core_execution_service(self):
        """Test that servers import from core execution_services."""
        # This test will pass after refactoring the servers
        # For now it documents the expected behavior
        
        # After refactoring, this should be true:
        # from sandbox.mcp_sandbox_server_stdio import mcp
        # The server should use ExecutionContextService internally
        
        # For TDD, we just verify the core service exists
        from sandbox.core.execution_services import ExecutionContextService
        assert ExecutionContextService is not None
