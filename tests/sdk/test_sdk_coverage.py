"""
Comprehensive coverage tests for SDK modules.

This file contains tests for all SDK modules to achieve 60%+ coverage.
Modules covered:
- command_execution.py
- execution.py
- config.py
- metrics.py
"""

import asyncio
import subprocess
import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock

from sandbox.sdk.command_execution import CommandExecution
from sandbox.sdk.execution import Execution
from sandbox.sdk.config import SandboxConfig, SandboxOptions


# ============================================================================
# CommandExecution Tests
# ============================================================================

class TestCommandExecutionInit:
    """Test CommandExecution initialization."""

    def test_init_default(self):
        """Test default initialization."""
        ce = CommandExecution()
        assert ce._stdout == ""
        assert ce._stderr == ""
        assert ce._exit_code == 0
        assert ce._command == ""
        assert ce._timeout is False

    def test_init_with_all_params(self):
        """Test initialization with all parameters."""
        ce = CommandExecution(
            stdout="output",
            stderr="error",
            exit_code=1,
            command="ls",
            timeout=True
        )
        assert ce._stdout == "output"
        assert ce._stderr == "error"
        assert ce._exit_code == 1
        assert ce._command == "ls"
        assert ce._timeout is True

    def test_init_with_output_data(self):
        """Test initialization with output_data dict."""
        output_data = {
            "stdout": "remote out",
            "stderr": "remote err",
            "exit_code": 2,
            "command": "test",
            "timeout": False
        }
        ce = CommandExecution(output_data=output_data)
        assert ce._stdout == "remote out"
        assert ce._stderr == "remote err"
        assert ce._exit_code == 2
        assert ce._command == "test"
        assert ce._timeout is False


class TestCommandExecutionAsync:
    """Test async methods."""

    @pytest.mark.asyncio
    async def test_output(self):
        """Test output async method."""
        ce = CommandExecution(stdout="test output")
        output = await ce.output()
        assert output == "test output"

    @pytest.mark.asyncio
    async def test_error(self):
        """Test error async method."""
        ce = CommandExecution(stderr="test error")
        error = await ce.error()
        assert error == "test error"


class TestCommandExecutionProperties:
    """Test properties."""

    def test_exit_code(self):
        """Test exit_code property."""
        ce = CommandExecution(exit_code=42)
        assert ce.exit_code == 42

    def test_command(self):
        """Test command property."""
        ce = CommandExecution(command="test command")
        assert ce.command == "test command"

    def test_timeout(self):
        """Test timeout property."""
        ce = CommandExecution(timeout=True)
        assert ce.timeout is True


class TestCommandExecutionHasError:
    """Test has_error method."""

    def test_has_error_false(self):
        """Test has_error returns False."""
        ce = CommandExecution()
        assert ce.has_error() is False

    def test_has_error_nonzero_exit(self):
        """Test has_error with non-zero exit code."""
        ce = CommandExecution(exit_code=1)
        assert ce.has_error() is True

    def test_has_error_with_stderr(self):
        """Test has_error with stderr."""
        ce = CommandExecution(stderr="error")
        assert ce.has_error() is True

    def test_has_error_with_timeout(self):
        """Test has_error with timeout."""
        ce = CommandExecution(timeout=True)
        assert ce.has_error() is True


class TestCommandExecutionToDict:
    """Test to_dict method."""

    def test_to_dict(self):
        """Test to_dict conversion."""
        ce = CommandExecution(
            stdout="out",
            stderr="err",
            exit_code=1,
            command="cmd"
        )
        result = ce.to_dict()
        assert result["stdout"] == "out"
        assert result["stderr"] == "err"
        assert result["exit_code"] == 1
        assert result["command"] == "cmd"
        assert result["has_error"] is True


# ============================================================================
# Execution Tests
# ============================================================================

class TestExecutionInit:
    """Test Execution initialization."""

    def test_init_default(self):
        """Test default initialization."""
        e = Execution()
        assert e._stdout == ""
        assert e._stderr == ""
        assert e._return_value is None
        assert e._exception is None
        assert e._artifacts == []
        assert e._status == "unknown"
        assert e._language == "unknown"
        assert e._has_error is False

    def test_init_with_local_params(self):
        """Test initialization with local parameters."""
        exc = ValueError("test error")
        e = Execution(
            stdout="output",
            stderr="error",
            return_value=42,
            exception=exc,
            artifacts=["/path/file.png"]
        )
        assert e._stdout == "output"
        assert e._stderr == "error"
        assert e._return_value == 42
        assert e._exception is exc
        assert e._artifacts == ["/path/file.png"]
        assert e._has_error is True

    def test_init_with_output_data(self):
        """Test initialization with remote output data."""
        output_data = {
            "output": [{"stream": "stdout", "text": "remote out"}],
            "status": "success",
            "language": "python"
        }
        e = Execution(output_data=output_data)
        assert e._status == "success"
        assert e._language == "python"
        assert e._has_error is False

    def test_init_with_error_status(self):
        """Test initialization with error status."""
        output_data = {"output": [], "status": "error"}
        e = Execution(output_data=output_data)
        assert e._status == "error"
        assert e._has_error is True


class TestExecutionAsync:
    """Test async methods."""

    @pytest.mark.asyncio
    async def test_output_local(self):
        """Test output for local execution."""
        e = Execution(stdout="local output")
        output = await e.output()
        assert output == "local output"

    @pytest.mark.asyncio
    async def test_output_remote(self):
        """Test output for remote execution."""
        output_data = {
            "output": [
                {"stream": "stdout", "text": "line1"},
                {"stream": "stdout", "text": "line2"}
            ]
        }
        e = Execution(output_data=output_data)
        output = await e.output()
        assert output == "line1\nline2"

    @pytest.mark.asyncio
    async def test_error_local(self):
        """Test error for local execution."""
        e = Execution(stderr="local error")
        error = await e.error()
        assert error == "local error"

    @pytest.mark.asyncio
    async def test_error_remote(self):
        """Test error for remote execution."""
        output_data = {
            "output": [{"stream": "stderr", "text": "remote error"}]
        }
        e = Execution(output_data=output_data)
        error = await e.error()
        assert error == "remote error"


class TestExecutionProperties:
    """Test properties."""

    def test_status(self):
        """Test status property."""
        e = Execution()
        assert e.status == "unknown"

        output_data = {"status": "completed"}
        e2 = Execution(output_data=output_data)
        assert e2.status == "completed"

    def test_language(self):
        """Test language property."""
        e = Execution()
        assert e.language == "unknown"

        output_data = {"language": "javascript"}
        e2 = Execution(output_data=output_data)
        assert e2.language == "javascript"

    def test_return_value(self):
        """Test return_value property."""
        e = Execution(return_value=123)
        assert e.return_value == 123

    def test_exception(self):
        """Test exception property."""
        exc = RuntimeError("test")
        e = Execution(exception=exc)
        assert e.exception is exc

    def test_artifacts(self):
        """Test artifacts property."""
        artifacts = ["/path/file1.png", "/path/file2.png"]
        e = Execution(artifacts=artifacts)
        assert e.artifacts == artifacts


class TestExecutionHasError:
    """Test has_error method."""

    def test_has_error_false(self):
        """Test has_error returns False."""
        e = Execution()
        assert e.has_error() is False

    def test_has_error_with_exception(self):
        """Test has_error with exception."""
        e = Execution(exception=ValueError("test"))
        assert e.has_error() is True

    def test_has_error_with_stderr(self):
        """Test has_error with stderr."""
        e = Execution(stderr="error")
        assert e.has_error() is True

    def test_has_error_with_error_status(self):
        """Test has_error with error status."""
        output_data = {"output": [], "status": "error"}
        e = Execution(output_data=output_data)
        assert e.has_error() is True


class TestExecutionToDict:
    """Test to_dict method."""

    def test_to_dict(self):
        """Test to_dict conversion."""
        exc = ValueError("test")
        e = Execution(
            stdout="out",
            stderr="err",
            return_value=42,
            exception=exc,
            artifacts=["/file.png"]
        )
        result = e.to_dict()
        assert result["stdout"] == "out"
        assert result["stderr"] == "err"
        assert result["return_value"] == 42
        assert result["exception"] == "test"
        assert result["artifacts"] == ["/file.png"]
        assert result["has_error"] is True


# ============================================================================
# SandboxConfig Tests
# ============================================================================

class TestSandboxConfig:
    """Test SandboxConfig dataclass."""

    def test_init_default(self):
        """Test default initialization."""
        config = SandboxConfig()
        assert config.remote is False
        assert config.server_url is None
        assert config.namespace == "default"
        assert config.name is None
        assert config.api_key is None
        assert config.memory == 512
        assert config.cpus == 1.0
        assert config.timeout == 180.0
        assert config.image is None
        assert config.env == {}
        assert config.mounts == []
        assert config.working_directory is None

    def test_init_with_all_params(self):
        """Test initialization with all parameters."""
        config = SandboxConfig(
            remote=True,
            server_url="http://server:8080",
            namespace="test-ns",
            name="test-sb",
            api_key="key",
            memory=2048,
            cpus=2.0,
            timeout=600.0,
            image="python:3.11",
            env={"VAR": "val"},
            mounts=["/host:/container"],
            working_directory="/work"
        )
        assert config.remote is True
        assert config.server_url == "http://server:8080"
        assert config.namespace == "test-ns"
        assert config.name == "test-sb"
        assert config.api_key == "key"
        assert config.memory == 2048
        assert config.cpus == 2.0
        assert config.timeout == 600.0
        assert config.image == "python:3.11"
        assert config.env == {"VAR": "val"}
        assert config.mounts == ["/host:/container"]
        assert config.working_directory == "/work"


# ============================================================================
# SandboxOptions Tests
# ============================================================================

class TestSandboxOptions:
    """Test SandboxOptions builder."""

    def test_init_default(self):
        """Test default initialization."""
        options = SandboxOptions()
        assert isinstance(options._config, SandboxConfig)
        assert options._config.remote is False

    def test_builder_pattern(self):
        """Test builder pattern chaining."""
        config = (SandboxOptions()
                  .remote(True)
                  .server_url("http://test:8080")
                  .namespace("test-ns")
                  .name("test-sb")
                  .api_key("key")
                  .memory(2048)
                  .cpus(2.0)
                  .timeout(600.0)
                  .image("python:3.11")
                  .env("KEY", "val")
                  .envs({"ENV": "prod"})
                  .mount("/host", "/container")
                  .working_directory("/app")
                  .build())

        assert config.remote is True
        assert config.server_url == "http://test:8080"
        assert config.namespace == "test-ns"
        assert config.name == "test-sb"
        assert config.api_key == "key"
        assert config.memory == 2048
        assert config.cpus == 2.0
        assert config.timeout == 600.0
        assert config.image == "python:3.11"
        assert config.env == {"KEY": "val", "ENV": "prod"}
        assert config.mounts == ["/host:/container"]
        assert config.working_directory == "/app"

    def test_remote(self):
        """Test remote method."""
        options = SandboxOptions()
        result = options.remote(True)
        assert result is options
        assert options._config.remote is True

    def test_server_url(self):
        """Test server_url method."""
        options = SandboxOptions()
        result = options.server_url("http://custom:5555")
        assert result is options
        assert options._config.server_url == "http://custom:5555"

    def test_namespace(self):
        """Test namespace method."""
        options = SandboxOptions()
        result = options.namespace("production")
        assert result is options
        assert options._config.namespace == "production"

    def test_name(self):
        """Test name method."""
        options = SandboxOptions()
        result = options.name("my-sandbox")
        assert result is options
        assert options._config.name == "my-sandbox"

    def test_api_key(self):
        """Test api_key method."""
        options = SandboxOptions()
        result = options.api_key("secret-key")
        assert result is options
        assert options._config.api_key == "secret-key"

    def test_memory(self):
        """Test memory method."""
        options = SandboxOptions()
        result = options.memory(4096)
        assert result is options
        assert options._config.memory == 4096

    def test_cpus(self):
        """Test cpus method."""
        options = SandboxOptions()
        result = options.cpus(4.0)
        assert result is options
        assert options._config.cpus == 4.0

    def test_timeout(self):
        """Test timeout method."""
        options = SandboxOptions()
        result = options.timeout(300.0)
        assert result is options
        assert options._config.timeout == 300.0

    def test_image(self):
        """Test image method."""
        options = SandboxOptions()
        result = options.image("ubuntu:latest")
        assert result is options
        assert options._config.image == "ubuntu:latest"

    def test_env_single(self):
        """Test env method with single variable."""
        options = SandboxOptions()
        result = options.env("API_KEY", "secret")
        assert result is options
        assert options._config.env == {"API_KEY": "secret"}

    def test_env_multiple(self):
        """Test multiple env calls."""
        options = SandboxOptions()
        options.env("KEY1", "val1")
        options.env("KEY2", "val2")
        assert options._config.env == {"KEY1": "val1", "KEY2": "val2"}

    def test_envs_multiple(self):
        """Test envs method with multiple variables."""
        options = SandboxOptions()
        result = options.envs({"VAR1": "val1", "VAR2": "val2"})
        assert result is options
        assert options._config.env == {"VAR1": "val1", "VAR2": "val2"}

    def test_mount(self):
        """Test mount method."""
        options = SandboxOptions()
        result = options.mount("/host/path", "/container/path")
        assert result is options
        assert options._config.mounts == ["/host/path:/container/path"]

    def test_mount_multiple(self):
        """Test multiple mount calls."""
        options = SandboxOptions()
        options.mount("/h1", "/c1")
        options.mount("/h2", "/c2")
        assert options._config.mounts == ["/h1:/c1", "/h2:/c2"]

    def test_working_directory(self):
        """Test working_directory method."""
        options = SandboxOptions()
        result = options.working_directory("/workspace")
        assert result is options
        assert options._config.working_directory == "/workspace"

    def test_build(self):
        """Test build method."""
        options = SandboxOptions()
        options.memory(1024)
        config = options.build()
        assert isinstance(config, SandboxConfig)
        assert config.memory == 1024

    def test_builder_class_method(self):
        """Test builder class method."""
        builder = SandboxOptions.builder()
        assert isinstance(builder, SandboxOptions)
        assert isinstance(builder._config, SandboxConfig)


# ============================================================================
# Metrics Tests (with proper mocking)
# ============================================================================

class MockSandboxForMetrics:
    """Mock sandbox for Metrics testing."""
    def __init__(self, remote=False, is_started=False):
        self.remote = remote
        self._is_started = is_started
        self._api_key = None
        self._namespace = "default"
        self._name = "test-sandbox"
        self._server_url = "http://localhost:5555"


def test_metrics_init():
    """Test Metrics initialization."""
    from sandbox.sdk.metrics import Metrics
    sandbox = MockSandboxForMetrics()
    metrics = Metrics(sandbox)
    assert metrics._sandbox is sandbox


@pytest.mark.asyncio
async def test_metrics_all_local():
    """Test getting metrics for local sandbox."""
    from sandbox.sdk.metrics import Metrics
    sandbox = MockSandboxForMetrics(remote=False)
    metrics = Metrics(sandbox)
    result = await metrics.all()
    assert result == {}


@pytest.mark.asyncio
async def test_metrics_get_local_metrics():
    """Test _get_local_metrics method."""
    from sandbox.sdk.metrics import Metrics
    sandbox = MockSandboxForMetrics(remote=False)
    metrics = Metrics(sandbox)
    result = await metrics._get_local_metrics()
    assert result == {}


@pytest.mark.asyncio
async def test_metrics_remote_not_started():
    """Test that getting remote metrics when not started raises error."""
    from sandbox.sdk.metrics import Metrics
    sandbox = MockSandboxForMetrics(remote=True, is_started=False)
    metrics = Metrics(sandbox)
    with pytest.raises(RuntimeError, match="not started"):
        await metrics.all()
