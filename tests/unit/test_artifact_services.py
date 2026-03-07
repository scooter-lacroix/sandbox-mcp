"""
Tests for unified artifact services.

Following TDD: These tests should FAIL initially, then pass after
implementing src/sandbox/core/artifact_services.py
"""

import pytest
import pytest_asyncio
from pathlib import Path
import tempfile


@pytest.mark.asyncio
class TestArtifactServices:
    """Test unified artifact service interface."""

    async def test_artifact_services_module_exists(self):
        """Test that artifact_services module can be imported."""
        # This test should FAIL initially (module doesn't exist)
        from sandbox.core.artifact_services import ArtifactService
        assert ArtifactService is not None

    async def test_artifact_service_initialization(self):
        """Test that ArtifactService can be instantiated."""
        from sandbox.core.artifact_services import ArtifactService
        
        service = ArtifactService()
        assert service is not None

    async def test_artifact_service_has_categorize_method(self):
        """Test that artifact service has categorize method."""
        from sandbox.core.artifact_services import ArtifactService
        
        service = ArtifactService()
        assert hasattr(service, 'categorize')

    async def test_artifact_service_categorizes_images(self):
        """Test that artifact service categorizes image files."""
        from sandbox.core.artifact_services import ArtifactService
        
        service = ArtifactService()
        
        # Test image categorization
        category = service.categorize('test.png')
        assert category == 'images'
        
        category = service.categorize('photo.jpg')
        assert category == 'images'

    async def test_artifact_service_categorizes_plots(self):
        """Test that artifact service categorizes plot files."""
        from sandbox.core.artifact_services import ArtifactService
        
        service = ArtifactService()
        
        category = service.categorize('plot.png')
        # Plots might be categorized as images or plots depending on implementation
        assert category in ['images', 'plots']

    async def test_artifact_service_categorizes_data_files(self):
        """Test that artifact service categorizes data files."""
        from sandbox.core.artifact_services import ArtifactService
        
        service = ArtifactService()
        
        category = service.categorize('data.csv')
        assert category == 'data'
        
        category = service.categorize('results.json')
        assert category == 'data'

    async def test_artifact_service_scan_directory(self):
        """Test that artifact service can scan directories."""
        from sandbox.core.artifact_services import ArtifactService
        
        service = ArtifactService()
        
        # Create temp directory with test files
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            (tmpdir / 'test.png').touch()
            (tmpdir / 'data.csv').touch()
            
            artifacts = await service.scan_directory(tmpdir)
            
            assert isinstance(artifacts, list)
            assert len(artifacts) >= 2

    async def test_artifact_service_get_report(self):
        """Test that artifact service can generate reports."""
        from sandbox.core.artifact_services import ArtifactService
        
        service = ArtifactService()
        
        # Should have a method to get artifact report
        assert hasattr(service, 'get_report') or hasattr(service, 'generate_report')


@pytest.mark.asyncio  
class TestArtifactServicesIntegration:
    """Test artifact services integration."""

    async def test_artifact_service_with_execution_context(self):
        """Test that artifact service works with execution context."""
        from sandbox.core.artifact_services import ArtifactService
        from sandbox.core.execution_services import ExecutionContextService
        
        artifact_service = ArtifactService()
        execution_service = ExecutionContextService()
        
        context = execution_service.create_context()
        
        # Should be able to create artifacts dir
        artifacts_dir = artifact_service.create_artifacts_dir(context, 'test-session')
        assert artifacts_dir is not None
        assert artifacts_dir.exists()
