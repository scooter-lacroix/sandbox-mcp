"""
Tests for session service module.

Following TDD: These tests should FAIL initially, then pass after
implementing src/sandbox/server/session_service.py
"""

import pytest
import pytest_asyncio


@pytest.mark.asyncio
class TestSessionService:
    """Test unified session service."""

    async def test_session_service_module_exists(self):
        """Test that session_service module can be imported."""
        # This test should FAIL initially (module doesn't exist)
        from sandbox.server.session_service import SessionService
        assert SessionService is not None

    async def test_session_service_initialization(self):
        """Test that SessionService can be instantiated."""
        from sandbox.server.session_service import SessionService
        
        service = SessionService()
        assert service is not None

    async def test_session_service_has_create_session(self):
        """Test that session service has create_session method."""
        from sandbox.server.session_service import SessionService
        
        service = SessionService()
        assert hasattr(service, 'create_session')

    async def test_session_service_has_get_session(self):
        """Test that session service has get_session method."""
        from sandbox.server.session_service import SessionService
        
        service = SessionService()
        assert hasattr(service, 'get_session')

    async def test_session_service_has_cleanup_session(self):
        """Test that session service has cleanup_session method."""
        from sandbox.server.session_service import SessionService
        
        service = SessionService()
        assert hasattr(service, 'cleanup_session')

    async def test_session_service_creates_unique_session_id(self):
        """Test that session service creates unique session IDs."""
        from sandbox.server.session_service import SessionService
        
        service = SessionService()
        
        session1 = await service.create_session()
        session2 = await service.create_session()
        
        assert session1['session_id'] != session2['session_id']

    async def test_session_service_stores_session(self):
        """Test that session service stores sessions."""
        from sandbox.server.session_service import SessionService
        
        service = SessionService()
        
        session = await service.create_session()
        retrieved = await service.get_session(session['session_id'])
        
        assert retrieved is not None
        assert retrieved['session_id'] == session['session_id']

    async def test_session_service_cleanup_removes_session(self):
        """Test that cleanup removes session."""
        from sandbox.server.session_service import SessionService
        
        service = SessionService()
        
        session = await service.create_session()
        await service.cleanup_session(session['session_id'])
        
        retrieved = await service.get_session(session['session_id'])
        assert retrieved is None


@pytest.mark.asyncio
class TestSessionServiceIntegration:
    """Test session service integration."""

    async def test_session_service_with_execution_context(self):
        """Test that session service works with execution context."""
        from sandbox.server.session_service import SessionService
        from sandbox.core.execution_services import ExecutionContextService
        
        session_service = SessionService()
        execution_service = ExecutionContextService()
        
        session = await session_service.create_session()
        context = execution_service.create_context(session['session_id'])
        
        assert session is not None
        assert context is not None

    async def test_session_service_tracks_active_sessions(self):
        """Test that session service tracks active sessions."""
        from sandbox.server.session_service import SessionService
        
        service = SessionService()
        
        # Create some sessions
        await service.create_session()
        await service.create_session()
        
        # Should have method to list sessions
        assert hasattr(service, 'list_sessions') or hasattr(service, 'get_active_sessions')
