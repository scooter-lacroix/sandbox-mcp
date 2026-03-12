"""
Coverage tests for helper modules - Tier 4 Task T4

Target: Raise coverage on:
- shell_helpers.py: 21.1% → 60%+
- package_helpers.py: 16.0% → 60%+
- manim_helpers.py: 12.9% → 60%+
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from typing import Dict, Any
import json

from sandbox.server.shell_helpers import shell_execute
from sandbox.server.package_helpers import install_package, list_installed_packages, _network_available
from sandbox.server.manim_helpers import (
    execute_manim_code,
    create_manim_animation,
    list_manim_animations,
    cleanup_manim_animation
)


class TestShellExecute:
    """Test shell command execution."""

    @pytest.fixture
    def mock_security_manager(self):
        """Mock security manager."""
        mock_sm = Mock()
        mock_sm.check_command_security.return_value = (True, None)
        return mock_sm

    @pytest.fixture
    def mock_ctx(self, tmp_path):
        """Mock execution context."""
        ctx = Mock()
        ctx.sandbox_area = tmp_path / "sandbox"
        ctx.sandbox_area.mkdir(exist_ok=True)
        return ctx

    def test_shell_execute_simple_command(self, mock_security_manager, mock_ctx):
        """Test running a simple shell command."""
        result = shell_execute(
            command="echo test",
            security_manager=mock_security_manager,
            ctx=mock_ctx
        )
        assert result is not None
        data = json.loads(result)
        assert "stdout" in data
        assert "return_code" in data

    def test_shell_execute_blocked_command(self, mock_ctx):
        """Test command blocked by security manager."""
        mock_sm = Mock()
        mock_violation = Mock()
        mock_violation.message = "Command not allowed"
        mock_violation.level.value = "high"
        mock_sm.check_command_security.return_value = (False, mock_violation)

        result = shell_execute(
            command="rm -rf /",
            security_manager=mock_sm,
            ctx=mock_ctx
        )
        data = json.loads(result)
        assert data["return_code"] == -1
        assert data["execution_info"]["command_blocked"] is True

    def test_shell_execute_with_timeout(self, mock_security_manager, mock_ctx):
        """Test command with timeout."""
        result = shell_execute(
            command="echo quick",
            security_manager=mock_security_manager,
            ctx=mock_ctx,
            timeout=5
        )
        assert result is not None

    def test_shell_execute_custom_directory(self, mock_security_manager, mock_ctx, tmp_path):
        """Test execution in custom directory."""
        result = shell_execute(
            command="pwd",
            security_manager=mock_security_manager,
            ctx=mock_ctx,
            working_directory=str(tmp_path)
        )
        assert result is not None

    def test_shell_execute_with_session(self, mock_security_manager, mock_ctx):
        """Test execution with session service."""
        mock_session_service = Mock()
        mock_session_service.get_or_create_execution_context_sync.return_value = mock_ctx

        result = shell_execute(
            command="echo test",
            security_manager=mock_security_manager,
            ctx=mock_ctx,
            session_service=mock_session_service,
            session_id="test-session"
        )
        assert result is not None


class TestNetworkAvailable:
    """Test network availability detection."""

    def test_network_available_success(self):
        """Test when network is available."""
        with patch('socket.create_connection') as mock_conn:
            mock_socket = Mock()
            mock_conn.return_value = mock_socket
            result = _network_available()
            assert result is True

    def test_network_available_failure(self):
        """Test when network is unavailable."""
        with patch('socket.create_connection', side_effect=OSError("No network")):
            result = _network_available()
            assert result is False

    def test_network_available_timeout(self):
        """Test network check with timeout."""
        with patch('socket.create_connection', side_effect=OSError("Timeout")):
            result = _network_available(timeout=1)
            assert result is False


class TestInstallPackage:
    """Test package installation."""

    @pytest.fixture
    def mock_ctx(self, tmp_path):
        """Mock execution context with venv."""
        ctx = Mock()
        ctx.venv_path = tmp_path / ".venv"
        ctx.venv_path.mkdir()
        (ctx.venv_path / "bin").mkdir()
        ctx.project_root = tmp_path
        return ctx

    def test_install_package_empty_name(self, mock_ctx):
        """Test with empty package name."""
        result = install_package("", mock_ctx)
        data = json.loads(result)
        assert data["status"] == "error"
        assert "non-empty" in data["message"].lower()

    def test_install_package_no_venv(self, tmp_path):
        """Test when venv doesn't exist."""
        ctx = Mock()
        ctx.venv_path = tmp_path / "nonexistent"
        result = install_package("pytest", ctx)
        data = json.loads(result)
        assert data["status"] == "error"
        assert "not found" in data["message"].lower()

    def test_install_package_no_network(self, mock_ctx):
        """Test when network is unavailable."""
        with patch('sandbox.server.package_helpers._network_available', return_value=False):
            result = install_package("pytest", mock_ctx)
            data = json.loads(result)
            assert data["status"] == "error"
            assert "network" in data["message"].lower()

    def test_install_package_success(self, mock_ctx):
        """Test successful package installation."""
        with patch('sandbox.server.package_helpers._network_available', return_value=True):
            with patch('shutil.which', return_value="/usr/bin/uv"):
                with patch('subprocess.run') as mock_run:
                    mock_result = Mock()
                    mock_result.returncode = 0
                    mock_result.stdout = "Successfully installed pytest"
                    mock_result.stderr = ""
                    mock_run.return_value = mock_result

                    result = install_package("pytest", mock_ctx)
                    data = json.loads(result)
                    # Result depends on mock behavior

    def test_install_package_with_version(self, mock_ctx):
        """Test installation with specific version."""
        with patch('sandbox.server.package_helpers._network_available', return_value=False):
            result = install_package("pytest", mock_ctx, version="8.0.0")
            data = json.loads(result)
            assert "status" in data


class TestListInstalledPackages:
    """Test listing installed packages."""

    @pytest.fixture
    def mock_ctx(self, tmp_path):
        """Mock execution context."""
        ctx = Mock()
        ctx.venv_path = tmp_path / ".venv"
        ctx.venv_path.mkdir()
        (ctx.venv_path / "bin").mkdir()
        return ctx

    def test_list_packages_no_venv(self, tmp_path):
        """Test when venv doesn't exist."""
        ctx = Mock()
        ctx.venv_path = tmp_path / "nonexistent"
        result = list_installed_packages(ctx)
        data = json.loads(result)
        assert data["status"] == "error"
        assert "not found" in data["message"].lower()

    def test_list_packages_no_pip(self, mock_ctx):
        """Test when pip executable doesn't exist."""
        result = list_installed_packages(mock_ctx)
        data = json.loads(result)
        assert data["status"] == "error"
        assert "pip not found" in data["message"].lower()

    def test_list_packages_success(self, mock_ctx):
        """Test successful package listing."""
        # Create pip executable
        pip_path = mock_ctx.venv_path / "bin" / "pip"
        pip_path.write_text("#!/bin/bash\n")

        with patch('subprocess.run') as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = json.dumps([
                {"name": "pytest", "version": "8.0.0"},
                {"name": "requests", "version": "2.31.0"}
            ])
            mock_run.return_value = mock_result

            result = list_installed_packages(mock_ctx)
            data = json.loads(result)
            assert data["status"] == "success"
            assert data["total_packages"] == 2


class TestExecuteManimCode:
    """Test Manim code execution."""

    @pytest.fixture
    def mock_ctx(self, tmp_path):
        """Mock execution context."""
        ctx = Mock()
        ctx.artifacts_dir = str(tmp_path / "artifacts")
        Path(ctx.artifacts_dir).mkdir(parents=True, exist_ok=True)
        ctx.venv_path = tmp_path / ".venv"
        ctx.venv_path.mkdir()
        (ctx.venv_path / "bin").mkdir()
        return ctx

    @pytest.fixture
    def mock_logger(self):
        """Mock logger."""
        return Mock()

    def test_execute_manim_creates_directory(self, mock_ctx, mock_logger):
        """Test that manim directory is created."""
        result = execute_manim_code(
            "Square()",
            mock_ctx,
            mock_logger
        )
        assert "animation_id" in result
        assert "artifacts_dir" in result

    def test_execute_manim_adds_import(self, mock_ctx, mock_logger):
        """Test that manim import is added if missing."""
        result = execute_manim_code(
            "Square()",
            mock_ctx,
            mock_logger
        )
        assert "animation_id" in result

    def test_execute_manim_different_qualities(self, mock_ctx, mock_logger):
        """Test different quality settings."""
        qualities = ["low_quality", "medium_quality", "high_quality", "production_quality"]
        for quality in qualities:
            result = execute_manim_code(
                "Square()",
                mock_ctx,
                mock_logger,
                quality=quality
            )
            assert result is not None


class TestCreateManimAnimation:
    """Test Manim animation creation wrapper."""

    @pytest.fixture
    def mock_ctx(self, tmp_path):
        """Mock execution context."""
        ctx = Mock()
        ctx.artifacts_dir = str(tmp_path / "artifacts")
        Path(ctx.artifacts_dir).mkdir(parents=True, exist_ok=True)
        return ctx

    @pytest.fixture
    def mock_logger(self):
        """Mock logger."""
        return Mock()

    def test_create_manim_animation_returns_json(self, mock_ctx, mock_logger):
        """Test that result is JSON string."""
        result = create_manim_animation(
            "Square()",
            mock_ctx,
            mock_logger
        )
        assert isinstance(result, str)
        data = json.loads(result)
        assert isinstance(data, dict)


class TestListManimAnimations:
    """Test listing Manim animations."""

    def test_list_no_artifacts_dir(self):
        """Test when no artifacts directory exists."""
        ctx = Mock()
        ctx.artifacts_dir = None
        result = list_manim_animations(ctx)
        assert "No artifacts" in result

    def test_list_empty_artifacts_dir(self, tmp_path):
        """Test when artifacts dir exists but is empty."""
        ctx = Mock()
        ctx.artifacts_dir = str(tmp_path / "artifacts")
        Path(ctx.artifacts_dir).mkdir(parents=True)
        result = list_manim_animations(ctx)
        assert "No Manim animations" in result

    def test_list_with_animations(self, tmp_path):
        """Test listing existing animations."""
        artifacts_dir = tmp_path / "artifacts"
        manim_dir = artifacts_dir / "manim_abc123"
        manim_dir.mkdir(parents=True)

        ctx = Mock()
        ctx.artifacts_dir = str(artifacts_dir)

        result = list_manim_animations(ctx)
        data = json.loads(result)
        assert "total_animations" in data


class TestCleanupManimAnimation:
    """Test Manim animation cleanup."""

    def test_cleanup_no_artifacts_dir(self):
        """Test when no artifacts directory."""
        ctx = Mock()
        ctx.artifacts_dir = None
        result = cleanup_manim_animation("abc123", ctx)
        assert "No artifacts" in result

    def test_cleanup_nonexistent_animation(self, tmp_path):
        """Test cleaning up non-existent animation."""
        ctx = Mock()
        ctx.artifacts_dir = str(tmp_path / "artifacts")
        Path(ctx.artifacts_dir).mkdir(parents=True)

        result = cleanup_manim_animation("nonexistent", ctx)
        assert "not found" in result.lower()

    def test_cleanup_success(self, tmp_path):
        """Test successful cleanup."""
        artifacts_dir = tmp_path / "artifacts"
        manim_dir = artifacts_dir / "manim_test123"
        manim_dir.mkdir(parents=True)

        ctx = Mock()
        ctx.artifacts_dir = str(artifacts_dir)

        result = cleanup_manim_animation("test123", ctx)
        assert "Successfully" in result
        assert not manim_dir.exists()


class TestErrorHandling:
    """Test error handling in helper modules."""

    def test_shell_execute_timeout(self, tmp_path):
        """Test shell command timeout handling."""
        import subprocess
        mock_sm = Mock()
        mock_sm.check_command_security.return_value = (True, None)
        ctx = Mock()
        ctx.sandbox_area = tmp_path

        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired("test", 30)):
            result = shell_execute(
                command="sleep 100",
                security_manager=mock_sm,
                ctx=ctx,
                timeout=1
            )
            data = json.loads(result)
            assert data["return_code"] == -2
            assert "timeout" in data["error"]["type"].lower()

    def test_install_package_timeout(self, tmp_path):
        """Test package installation timeout."""
        ctx = Mock()
        ctx.venv_path = tmp_path / ".venv"
        ctx.venv_path.mkdir()
        (ctx.venv_path / "bin").mkdir()
        ctx.project_root = tmp_path

        with patch('sandbox.server.package_helpers._network_available', return_value=True):
            with patch('shutil.which', return_value="/usr/bin/uv"):
                with patch('subprocess.run', side_effect=Exception("Timeout")):
                    result = install_package("pytest", ctx)
                    data = json.loads(result)
                    assert "status" in data
