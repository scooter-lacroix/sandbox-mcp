"""
Simple coverage tests for LocalSandbox module.

Focuses on achieving 60%+ coverage with working tests.
"""

import pytest
from pathlib import Path
from sandbox.sdk.local_sandbox import LocalSandbox


class TestLocalSandboxInit:
    """Test LocalSandbox initialization."""

    def test_init_default(self):
        """Test default initialization."""
        sandbox = LocalSandbox()
        assert sandbox.remote is False
        assert sandbox._is_started is False

    def test_init_forces_remote_false(self):
        """Test that remote is forced to False."""
        # Even if we pass remote=True, LocalSandbox sets it to False
        sandbox = LocalSandbox(remote=True)
        assert sandbox.remote is False

    def test_init_with_name(self):
        """Test initialization with name."""
        sandbox = LocalSandbox(name="test-sandbox")
        assert sandbox._name == "test-sandbox"


class TestLocalSandboxLifecycle:
    """Test sandbox lifecycle."""

    @pytest.mark.asyncio
    async def test_start(self):
        """Test starting sandbox."""
        sandbox = LocalSandbox()
        await sandbox.start()
        assert sandbox._is_started is True

    @pytest.mark.asyncio
    async def test_start_idempotent(self):
        """Test start can be called multiple times."""
        sandbox = LocalSandbox()
        await sandbox.start()
        await sandbox.start()
        assert sandbox._is_started is True

    @pytest.mark.asyncio
    async def test_stop(self):
        """Test stopping sandbox."""
        sandbox = LocalSandbox()
        await sandbox.start()
        await sandbox.stop()
        assert sandbox._is_started is False

    @pytest.mark.asyncio
    async def test_stop_when_not_started(self):
        """Test stop when not started is safe."""
        sandbox = LocalSandbox()
        await sandbox.stop()
        assert sandbox._is_started is False


class TestLocalSandboxExecution:
    """Test code execution."""

    @pytest.mark.asyncio
    async def test_run_simple_code(self):
        """Test running simple code."""
        sandbox = LocalSandbox()
        await sandbox.start()
        result = await sandbox.run("x = 1 + 1")
        assert result is not None
        assert hasattr(result, '_stdout')

    @pytest.mark.asyncio
    async def test_run_without_start_raises(self):
        """Test running without start raises RuntimeError."""
        sandbox = LocalSandbox()
        with pytest.raises(RuntimeError, match="not started"):
            await sandbox.run("print('test')")

    @pytest.mark.asyncio
    async def test_run_with_syntax_error(self):
        """Test running code with syntax error."""
        sandbox = LocalSandbox()
        await sandbox.start()
        result = await sandbox.run("this is not valid python")
        assert result is not None

    @pytest.mark.asyncio
    async def test_run_multiple_times(self):
        """Test running multiple times."""
        sandbox = LocalSandbox()
        await sandbox.start()
        result1 = await sandbox.run("x = 1")
        result2 = await sandbox.run("x += 1")
        assert result1 is not None
        assert result2 is not None


class TestLocalSandboxArtifacts:
    """Test artifact management."""

    @pytest.mark.asyncio
    async def test_artifacts_dir_property(self):
        """Test artifacts_dir property."""
        sandbox = LocalSandbox()
        await sandbox.start()
        artifacts_dir = sandbox.artifacts_dir
        assert artifacts_dir is not None
        assert isinstance(artifacts_dir, str)
        assert "artifacts" in artifacts_dir

    @pytest.mark.asyncio
    async def test_list_artifacts_default(self):
        """Test list_artifacts with default format."""
        sandbox = LocalSandbox()
        await sandbox.start()
        artifacts = sandbox.list_artifacts()
        assert isinstance(artifacts, list)

    @pytest.mark.asyncio
    async def test_list_artifacts_json_format(self):
        """Test list_artifacts in JSON format."""
        sandbox = LocalSandbox()
        await sandbox.start()
        artifacts = sandbox.list_artifacts(format_type='json')
        # Should be JSON string or list
        if isinstance(artifacts, str):
            import json
            parsed = json.loads(artifacts)
            assert isinstance(parsed, list)
        else:
            assert isinstance(artifacts, list)

    @pytest.mark.asyncio
    async def test_list_artifacts_detailed_format(self):
        """Test list_artifacts in detailed format."""
        sandbox = LocalSandbox()
        await sandbox.start()
        artifacts = sandbox.list_artifacts(format_type='detailed')
        assert isinstance(artifacts, dict)
        assert 'total' in artifacts

    @pytest.mark.asyncio
    async def test_list_artifacts_non_recursive(self):
        """Test list_artifacts non-recursive."""
        sandbox = LocalSandbox()
        await sandbox.start()
        artifacts = sandbox.list_artifacts(recursive=False)
        assert isinstance(artifacts, list)

    @pytest.mark.asyncio
    async def test_cleanup_artifacts(self):
        """Test cleanup_artifacts."""
        sandbox = LocalSandbox()
        await sandbox.start()
        sandbox.cleanup_artifacts()  # Should not raise


class TestLocalSandboxFileCategorization:
    """Test file categorization."""

    @pytest.mark.asyncio
    async def test_categorize_images(self):
        """Test image file categorization."""
        sandbox = LocalSandbox()
        await sandbox.start()
        assert sandbox._categorize_file(Path("test.png")) == "images"
        assert sandbox._categorize_file(Path("test.jpg")) == "images"
        assert sandbox._categorize_file(Path("test.jpeg")) == "images"
        assert sandbox._categorize_file(Path("test.gif")) == "images"
        assert sandbox._categorize_file(Path("test.svg")) == "images"

    @pytest.mark.asyncio
    async def test_categorize_videos(self):
        """Test video file categorization."""
        sandbox = LocalSandbox()
        await sandbox.start()
        assert sandbox._categorize_file(Path("test.mp4")) == "videos"
        assert sandbox._categorize_file(Path("test.avi")) == "videos"
        assert sandbox._categorize_file(Path("test.mov")) == "videos"

    @pytest.mark.asyncio
    async def test_categorize_data(self):
        """Test data file categorization."""
        sandbox = LocalSandbox()
        await sandbox.start()
        assert sandbox._categorize_file(Path("test.csv")) == "data"
        assert sandbox._categorize_file(Path("test.json")) == "data"
        assert sandbox._categorize_file(Path("test.yaml")) == "data"

    @pytest.mark.asyncio
    async def test_categorize_code(self):
        """Test code file categorization."""
        sandbox = LocalSandbox()
        await sandbox.start()
        assert sandbox._categorize_file(Path("test.py")) == "code"
        assert sandbox._categorize_file(Path("test.js")) == "code"
        assert sandbox._categorize_file(Path("test.html")) == "code"

    @pytest.mark.asyncio
    async def test_categorize_documents(self):
        """Test document file categorization."""
        sandbox = LocalSandbox()
        await sandbox.start()
        assert sandbox._categorize_file(Path("test.pdf")) == "documents"
        assert sandbox._categorize_file(Path("test.md")) == "documents"
        assert sandbox._categorize_file(Path("test.txt")) == "documents"

    @pytest.mark.asyncio
    async def test_categorize_manim_by_path(self):
        """Test Manim file categorization by path."""
        sandbox = LocalSandbox()
        await sandbox.start()
        assert sandbox._categorize_file(Path("manim/test.png")) == "manim"
        assert sandbox._categorize_file(Path("media/videos/test.mp4")) == "manim"

    @pytest.mark.asyncio
    async def test_categorize_other(self):
        """Test other file categorization."""
        sandbox = LocalSandbox()
        await sandbox.start()
        assert sandbox._categorize_file(Path("test.xyz")) == "other"


class TestLocalSandboxSessionManagement:
    """Test session management."""

    @pytest.mark.asyncio
    async def test_session_id_property(self):
        """Test session_id property."""
        sandbox = LocalSandbox()
        await sandbox.start()
        session_id = sandbox.session_id
        assert isinstance(session_id, str)
        assert len(session_id) > 0

    @pytest.mark.asyncio
    async def test_save_session(self):
        """Test save_session."""
        sandbox = LocalSandbox()
        await sandbox.start()
        sandbox.save_session()  # Should not raise

    @pytest.mark.asyncio
    async def test_cleanup_session(self):
        """Test cleanup_session."""
        sandbox = LocalSandbox()
        await sandbox.start()
        sandbox.cleanup_session()  # Should not raise

    @pytest.mark.asyncio
    async def test_clear_cache(self):
        """Test clear_cache."""
        sandbox = LocalSandbox()
        await sandbox.start()
        await sandbox.run("x = 1")
        sandbox.clear_cache()  # Should not raise


class TestLocalSandboxPerformanceStats:
    """Test performance and statistics."""

    @pytest.mark.asyncio
    async def test_get_execution_info(self):
        """Test get_execution_info."""
        sandbox = LocalSandbox()
        await sandbox.start()
        info = sandbox.get_execution_info()
        assert isinstance(info, dict)
        assert 'python_version' in info
        assert 'executable' in info
        assert 'artifacts_dir' in info

    @pytest.mark.asyncio
    async def test_get_performance_stats(self):
        """Test get_performance_stats."""
        sandbox = LocalSandbox()
        await sandbox.start()
        stats = sandbox.get_performance_stats()
        assert isinstance(stats, dict)

    @pytest.mark.asyncio
    async def test_get_execution_history(self):
        """Test get_execution_history."""
        sandbox = LocalSandbox()
        await sandbox.start()
        history = sandbox.get_execution_history()
        assert isinstance(history, list)

    @pytest.mark.asyncio
    async def test_get_execution_history_with_limit(self):
        """Test get_execution_history with limit."""
        sandbox = LocalSandbox()
        await sandbox.start()
        history = sandbox.get_execution_history(limit=10)
        assert isinstance(history, list)


class TestLocalSandboxArtifactReporting:
    """Test artifact reporting."""

    @pytest.mark.asyncio
    async def test_get_artifact_report(self):
        """Test get_artifact_report."""
        sandbox = LocalSandbox()
        await sandbox.start()
        report = sandbox.get_artifact_report()
        assert isinstance(report, dict)
        assert 'total_artifacts' in report

    @pytest.mark.asyncio
    async def test_categorize_artifacts(self):
        """Test categorize_artifacts."""
        sandbox = LocalSandbox()
        await sandbox.start()
        categorized = sandbox.categorize_artifacts()
        assert isinstance(categorized, dict)

    @pytest.mark.asyncio
    async def test_cleanup_artifacts_by_type(self):
        """Test cleanup_artifacts_by_type."""
        sandbox = LocalSandbox()
        await sandbox.start()
        count = sandbox.cleanup_artifacts_by_type('images')
        assert isinstance(count, int)

    @pytest.mark.asyncio
    async def test_cleanup_artifacts_by_nonexistent_type(self):
        """Test cleanup_artifacts_by_type with non-existent type."""
        sandbox = LocalSandbox()
        await sandbox.start()
        count = sandbox.cleanup_artifacts_by_type('nonexistent')
        assert count == 0

    @pytest.mark.asyncio
    async def test_get_manim_artifacts(self):
        """Test get_manim_artifacts."""
        sandbox = LocalSandbox()
        await sandbox.start()
        artifacts = sandbox.get_manim_artifacts()
        assert isinstance(artifacts, list)

    @pytest.mark.asyncio
    async def test_get_artifact_summary(self):
        """Test get_artifact_summary."""
        sandbox = LocalSandbox()
        await sandbox.start()
        summary = sandbox.get_artifact_summary()
        assert isinstance(summary, str)
        assert len(summary) > 0


class TestLocalSandboxHelpers:
    """Test helper functions."""

    @pytest.mark.asyncio
    async def test_get_code_template(self):
        """Test get_code_template."""
        sandbox = LocalSandbox()
        await sandbox.start()
        template = sandbox.get_code_template('basic')
        assert isinstance(template, str)

    @pytest.mark.asyncio
    async def test_get_available_templates(self):
        """Test get_available_templates."""
        sandbox = LocalSandbox()
        await sandbox.start()
        templates = sandbox.get_available_templates()
        assert isinstance(templates, list)

    @pytest.mark.asyncio
    async def test_validate_code(self):
        """Test validate_code."""
        sandbox = LocalSandbox()
        await sandbox.start()
        result = sandbox.validate_code("x = 1")
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_get_manim_helper(self):
        """Test get_manim_helper."""
        sandbox = LocalSandbox()
        await sandbox.start()
        helper = sandbox.get_manim_helper()
        assert helper is not None


class TestLocalSandboxDefaultImage:
    """Test default image."""

    @pytest.mark.asyncio
    async def test_get_default_image(self):
        """Test get_default_image."""
        sandbox = LocalSandbox()
        image = await sandbox.get_default_image()
        assert image == "local-python"


class TestLocalSandboxFormattingHelpers:
    """Test formatting helper methods."""

    @pytest.mark.asyncio
    async def test_format_empty_artifacts_list(self):
        """Test _format_empty_artifacts for list format."""
        sandbox = LocalSandbox()
        await sandbox.start()
        result = sandbox._format_empty_artifacts('list')
        assert result == []

    @pytest.mark.asyncio
    async def test_format_empty_artifacts_json(self):
        """Test _format_empty_artifacts for JSON format."""
        sandbox = LocalSandbox()
        await sandbox.start()
        result = sandbox._format_empty_artifacts('json')
        assert result == "[]"

    @pytest.mark.asyncio
    async def test_format_empty_artifacts_csv(self):
        """Test _format_empty_artifacts for CSV format."""
        sandbox = LocalSandbox()
        await sandbox.start()
        result = sandbox._format_empty_artifacts('csv')
        assert "name,path" in result

    @pytest.mark.asyncio
    async def test_format_empty_artifacts_detailed(self):
        """Test _format_empty_artifacts for detailed format."""
        sandbox = LocalSandbox()
        await sandbox.start()
        result = sandbox._format_empty_artifacts('detailed')
        assert isinstance(result, dict)
        assert result['total'] == 0
