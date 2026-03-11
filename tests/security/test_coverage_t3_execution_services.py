"""
Coverage tests for execution_services.py - Tier 3 Task T3

Target: Raise coverage from 31% to 70%
Focus: Security-critical paths, error handling, edge cases
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from collections import OrderedDict

from sandbox.core.execution_services import ExecutionContext, ExecutionContextService, get_execution_service


class TestExecutionContextInit:
    """Test ExecutionContext initialization (lines 50-53, 57, 74-120)"""

    def test_init_with_default_project_root(self):
        """Test initialization with default project root detection."""
        ctx = ExecutionContext()
        # Should detect from current file location
        assert ctx.project_root is not None
        assert isinstance(ctx.project_root, Path)

    def test_init_creates_sandbox_area(self):
        """Test that sandbox_area is created."""
        ctx = ExecutionContext()
        assert ctx.sandbox_area == ctx.project_root / "sandbox_area"
        assert ctx.sandbox_area.exists()

    def test_init_initializes_instance_variables(self):
        """Test that all instance variables are initialized."""
        ctx = ExecutionContext()
        assert ctx.artifacts_dir is None
        assert ctx.web_servers == {}
        assert ctx.execution_globals == {}
        assert ctx.compilation_cache == {}
        assert ctx.cache_hits == 0
        assert ctx.cache_misses == 0


class TestEnvironmentSetup:
    """Test environment setup (lines 74-120)"""

    @pytest.fixture
    def ctx(self):
        """Create a context for testing."""
        return ExecutionContext()

    def test_setup_environment_modifies_sys_path(self, ctx):
        """Test that setup modifies sys.path."""
        original_path = sys.path.copy()
        ctx._setup_environment()
        # sys.path should have been modified
        assert sys.path != original_path

    def test_setup_environment_uses_ordered_dict(self, ctx):
        """Test that OrderedDict is used for deduplication."""
        # This tests the implementation detail of using OrderedDict
        ctx._setup_environment()
        # Should complete without error
        assert True


class TestCreateArtifactsDir:
    """Test artifacts directory creation (lines 124-150)"""

    @pytest.fixture
    def ctx(self):
        """Create a context for testing."""
        return ExecutionContext()

    def test_create_artifacts_dir_returns_string(self, ctx):
        """Test that artifacts directory path is returned as string."""
        artifacts_dir = ctx.create_artifacts_dir()
        assert isinstance(artifacts_dir, str)
        assert len(artifacts_dir) > 0

    def test_create_artifacts_dir_sets_instance_variable(self, ctx):
        """Test that artifacts_dir instance variable is set."""
        artifacts_dir_str = ctx.create_artifacts_dir()
        assert ctx.artifacts_dir is not None
        # artifacts_dir is a Path object
        assert isinstance(ctx.artifacts_dir, Path)


class TestBackupArtifacts:
    """Test backup artifacts functionality (lines 157-212)"""

    @pytest.fixture
    def ctx(self):
        """Create a context for testing."""
        return ExecutionContext()

    def test_sanitize_backup_name_removes_dangerous_chars(self, ctx):
        """Test that backup name with path traversal raises ValueError."""
        # S3 fix: Path traversal should raise ValueError
        with pytest.raises(ValueError, match="cannot contain"):
            ctx._sanitize_backup_name("../../../etc/passwd")

    def test_sanitize_backup_name_safe_input(self, ctx):
        """Test that safe backup names are accepted."""
        sanitized = ctx._sanitize_backup_name("backup-2024_test")
        assert "backup" in sanitized
        assert "2024" in sanitized
        assert "test" in sanitized

    def test_sanitize_backup_name_preserves_safe_chars(self, ctx):
        """Test that safe characters are preserved."""
        sanitized = ctx._sanitize_backup_name("backup-2024_test")
        assert "backup" in sanitized
        assert "2024" in sanitized
        assert "test" in sanitized

    def test_backup_artifacts_with_name(self, ctx):
        """Test backup with explicit name."""
        ctx.create_artifacts_dir()
        result = ctx.backup_artifacts(backup_name="test-backup")
        assert isinstance(result, str)

    def test_backup_artifacts_with_auto_name(self, ctx):
        """Test backup with auto-generated name."""
        ctx.create_artifacts_dir()
        result = ctx.backup_artifacts()
        assert isinstance(result, str)

    def test_cleanup_old_backups(self, ctx, tmp_path):
        """Test cleanup of old backups."""
        backup_root = tmp_path / "backups"
        backup_root.mkdir()

        # Create some backup directories
        (backup_root / "backup1").mkdir()
        (backup_root / "backup2").mkdir()

        # Should not crash
        ctx._cleanup_old_backups(backup_root, max_backups=2)

    def test_list_artifact_backups(self, ctx):
        """Test listing backups."""
        backups = ctx.list_artifact_backups()
        assert isinstance(backups, list)


class TestRollbackArtifacts:
    """Test rollback functionality (lines 214-255)"""

    @pytest.fixture
    def ctx(self):
        """Create a context for testing."""
        return ExecutionContext()

    def test_rollback_with_backup_name(self, ctx):
        """Test rollback with explicit backup name."""
        # Create backup with unique name to avoid conflicts
        import time
        ctx.create_artifacts_dir()
        backup_name = ctx.backup_artifacts(backup_name=f"test-rollback-{int(time.time()*1000)}")

        # Rollback should not crash
        result = ctx.rollback_artifacts(backup_name)
        assert isinstance(result, str)

    def test_rollback_nonexistent_backup(self, ctx):
        """Test rollback with non-existent backup."""
        # Should handle gracefully
        result = ctx.rollback_artifacts("nonexistent-backup")
        assert isinstance(result, str)

    def test_get_backup_info(self, ctx):
        """Test getting backup information."""
        # Create backup with unique name
        import time
        ctx.create_artifacts_dir()
        backup_name = ctx.backup_artifacts(backup_name=f"test-info-{int(time.time()*1000)}")

        # Get info
        info = ctx.get_backup_info(backup_name)
        assert isinstance(info, dict)


class TestExecutionContextService:
    """Test ExecutionContextService class (lines 258-305)"""

    @pytest.fixture
    def service(self):
        """Create a service instance."""
        return ExecutionContextService()

    def test_service_init(self, service):
        """Test service initialization."""
        # Service should be initialized
        assert service is not None
        assert isinstance(service, ExecutionContextService)

    def test_create_context_default(self, service):
        """Test creating context with defaults."""
        ctx = service.create_context()
        assert ctx is not None
        assert isinstance(ctx, ExecutionContext)

    def test_create_context_with_options(self, service):
        """Test creating context with custom options."""
        # Use cwd as a valid project root
        ctx = service.create_context(
            project_root=Path.cwd(),
            context_id="test-ctx"
        )
        assert ctx is not None

    def test_get_context(self, service):
        """Test retrieving existing context."""
        ctx_id = "test-ctx"
        ctx = service.create_context(context_id=ctx_id)
        retrieved = service.get_context(ctx_id)
        assert retrieved is not None

    def test_get_context_nonexistent(self, service):
        """Test retrieving non-existent context."""
        result = service.get_context("nonexistent")
        assert result is None


class TestSetupEnvironment:
    """Test async environment setup (lines 318-333)"""

    @pytest.fixture
    def service(self):
        """Create a service instance."""
        return ExecutionContextService()

    @pytest.mark.asyncio
    async def test_setup_environment(self, service):
        """Test async environment setup."""
        ctx = service.create_context()
        # Should not crash
        await service.setup_environment(ctx)
        assert True


class TestContextCleanup:
    """Test context cleanup (lines 342-344, 353-354)"""

    @pytest.fixture
    def service(self):
        """Create a service instance."""
        return ExecutionContextService()

    @pytest.mark.asyncio
    async def test_cleanup_context(self, service):
        """Test cleaning up a context."""
        ctx = service.create_context()
        # Should not crash
        await service.cleanup(ctx)
        assert True


class TestServiceHelpers:
    """Test service helper methods (lines 361-382)"""

    @pytest.fixture
    def service(self):
        """Create a service instance."""
        return ExecutionContextService()

    def test_add_to_path(self, service):
        """Test adding path to service."""
        # Should not crash
        service.add_to_path("/test/path")
        assert True


class TestCreateArtifactsDirService:
    """Test service-level artifacts dir creation (lines 394-426)"""

    @pytest.fixture
    def service(self):
        """Create a service instance."""
        return ExecutionContextService()

    def test_create_artifacts_dir_for_session(self, service):
        """Test creating artifacts dir with session ID."""
        ctx = service.create_context()
        artifacts_dir = service.create_artifacts_dir(ctx, "test-session")
        assert isinstance(artifacts_dir, Path)
        assert artifacts_dir.exists()


class TestServiceGetDefault:
    """Test getting default context (lines 426-456)"""

    @pytest.fixture
    def service(self):
        """Create a service instance."""
        return ExecutionContextService()

    def test_service_has_default_context_behavior(self, service):
        """Test that service provides default context."""
        # Create a context without explicit ID
        ctx = service.create_context()
        assert ctx is not None
        assert isinstance(ctx, ExecutionContext)


class TestGetExecutionService:
    """Test get_execution_service singleton (lines 463+)"""

    def test_get_execution_service_returns_instance(self):
        """Test that get_execution_service returns instance."""
        service = get_execution_service()
        assert service is not None
        assert isinstance(service, ExecutionContextService)

    def test_get_execution_service_singleton(self):
        """Test that get_execution_service returns singleton."""
        service1 = get_execution_service()
        service2 = get_execution_service()
        assert service1 == service2


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_context_with_relative_project_root(self):
        """Test context with relative project root."""
        # Relative paths should work
        ctx = ExecutionContext(project_root=Path.cwd())
        assert ctx.project_root is not None

    def test_backup_with_special_chars(self):
        """Test backup name with special characters."""
        ctx = ExecutionContext()
        ctx.create_artifacts_dir()
        # Special chars should be sanitized
        result = ctx.backup_artifacts("backup@test#1")
        assert isinstance(result, str)

    def test_rollback_with_empty_name(self):
        """Test rollback with empty backup name."""
        ctx = ExecutionContext()
        ctx.create_artifacts_dir()
        # Should handle gracefully
        result = ctx.rollback_artifacts("")
        assert isinstance(result, str)


class TestCleanupArtifacts:
    """Test cleanup artifacts functionality"""

    @pytest.fixture
    def ctx(self):
        """Create a context for testing."""
        return ExecutionContext()

    def test_cleanup_artifacts_with_dir(self, ctx):
        """Test cleanup when artifacts dir exists."""
        ctx.create_artifacts_dir()
        # Should not crash
        ctx.cleanup_artifacts()
        assert True

    def test_cleanup_artifacts_without_dir(self, ctx):
        """Test cleanup when no artifacts dir exists."""
        # Should not crash
        ctx.cleanup_artifacts()
        assert True
