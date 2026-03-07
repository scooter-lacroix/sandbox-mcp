"""
Tests for server artifact service module.

Following TDD: These tests should FAIL initially, then pass after
implementing src/sandbox/server/artifact_service.py
"""

import pytest
import pytest_asyncio
from pathlib import Path
import tempfile


@pytest.mark.asyncio
class TestServerArtifactService:
    """Test server artifact service."""

    async def test_server_artifact_service_module_exists(self):
        """Test that artifact_service module can be imported."""
        from sandbox.server.artifact_service import ServerArtifactService
        assert ServerArtifactService is not None

    async def test_server_artifact_service_initialization(self):
        """Test that ServerArtifactService can be instantiated."""
        from sandbox.server.artifact_service import ServerArtifactService
        
        service = ServerArtifactService()
        assert service is not None

    async def test_server_artifact_service_has_list_artifacts(self):
        """Test that service has list_artifacts method."""
        from sandbox.server.artifact_service import ServerArtifactService
        
        service = ServerArtifactService()
        assert hasattr(service, 'list_artifacts')

    async def test_server_artifact_service_has_get_artifact(self):
        """Test that service has get_artifact method."""
        from sandbox.server.artifact_service import ServerArtifactService
        
        service = ServerArtifactService()
        assert hasattr(service, 'get_artifact')

    async def test_server_artifact_service_lists_files(self):
        """Test that service can list artifacts in a directory."""
        from sandbox.server.artifact_service import ServerArtifactService
        
        service = ServerArtifactService()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            (tmpdir / 'test1.png').touch()
            (tmpdir / 'test2.csv').touch()
            
            artifacts = await service.list_artifacts(tmpdir)
            
            assert isinstance(artifacts, list)
            assert len(artifacts) == 2

    async def test_server_artifact_service_categorizes_files(self):
        """Test that service categorizes files by type."""
        from sandbox.server.artifact_service import ServerArtifactService
        
        service = ServerArtifactService()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            (tmpdir / 'plot.png').touch()
            (tmpdir / 'data.csv').touch()
            (tmpdir / 'video.mp4').touch()
            
            artifacts = await service.list_artifacts(tmpdir)
            
            # Should have category information
            categories = set(a.get('category') for a in artifacts)
            assert 'images' in categories or 'image' in categories
            assert 'data' in categories

    async def test_server_artifact_service_gets_file_info(self):
        """Test that service can get file information."""
        from sandbox.server.artifact_service import ServerArtifactService
        
        service = ServerArtifactService()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            test_file = tmpdir / 'test.txt'
            test_file.write_text('Hello, World!')
            
            info = await service.get_artifact(test_file)
            
            assert info is not None
            assert info['name'] == 'test.txt'
            assert info['size'] > 0

    async def test_server_artifact_service_recursive_scan(self):
        """Test that service can scan directories recursively."""
        from sandbox.server.artifact_service import ServerArtifactService
        
        service = ServerArtifactService()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            subdir = tmpdir / 'subdir'
            subdir.mkdir()
            
            (tmpdir / 'file1.txt').touch()
            (subdir / 'file2.txt').touch()
            
            # Recursive scan
            artifacts = await service.list_artifacts(tmpdir, recursive=True)
            
            assert len(artifacts) == 2

    async def test_server_artifact_service_non_recursive_scan(self):
        """Test that service can scan directories non-recursively."""
        from sandbox.server.artifact_service import ServerArtifactService
        
        service = ServerArtifactService()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            subdir = tmpdir / 'subdir'
            subdir.mkdir()
            
            (tmpdir / 'file1.txt').touch()
            (subdir / 'file2.txt').touch()
            
            # Non-recursive scan
            artifacts = await service.list_artifacts(tmpdir, recursive=False)
            
            assert len(artifacts) == 1


@pytest.mark.asyncio
class TestServerArtifactServiceIntegration:
    """Test server artifact service integration."""

    async def test_server_artifact_service_with_session(self):
        """Test that artifact service works with sessions."""
        from sandbox.server.artifact_service import ServerArtifactService
        from sandbox.server.session_service import SessionService
        
        artifact_service = ServerArtifactService()
        session_service = SessionService()
        
        session = await session_service.create_session()
        
        # Should be able to use artifact service with session
        assert session is not None
        assert artifact_service is not None
