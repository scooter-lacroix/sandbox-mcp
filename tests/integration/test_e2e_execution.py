"""
End-to-end tests for Sandbox MCP.

These tests verify the complete user workflow:
1. Import sandbox package
2. Create execution context
3. Execute code with artifact generation
4. Verify artifacts are captured correctly

Following Phase 5 quality patterns:
- Type hints with from __future__ import annotations
- Comprehensive error handling
- Tests for both success and error paths
"""

from __future__ import annotations

import tempfile
import shutil
from pathlib import Path

import pytest


class TestEndToEndExecution:
    """End-to-end tests for code execution with artifacts."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory for test artifacts."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_sandbox_import_succeeds(self) -> None:
        """Test that sandbox package imports successfully."""
        import sandbox
        
        assert sandbox.__version__ is not None
        assert isinstance(sandbox.__version__, str)

    def test_execution_context_creation(self, temp_dir: Path) -> None:
        """Test creating an execution context."""
        from sandbox.core.execution_context import PersistentExecutionContext
        
        ctx = PersistentExecutionContext()
        assert ctx is not None
        assert ctx.globals_dict is not None
        assert isinstance(ctx.globals_dict, dict)

    def test_basic_code_execution(self, temp_dir: Path) -> None:
        """Test basic Python code execution."""
        from sandbox.core.execution_context import PersistentExecutionContext
        
        ctx = PersistentExecutionContext()
        
        # Execute simple code
        code = "x = 5\ny = 10\nresult = x + y"
        exec(code, ctx.globals_dict)
        
        assert ctx.globals_dict.get("result") == 15

    def test_variable_persistence(self, temp_dir: Path) -> None:
        """Test that variables persist across executions."""
        from sandbox.core.execution_context import PersistentExecutionContext
        
        ctx = PersistentExecutionContext()
        
        # First execution
        exec("counter = 1", ctx.globals_dict)
        assert ctx.globals_dict["counter"] == 1
        
        # Second execution - variable should persist
        exec("counter += 1", ctx.globals_dict)
        assert ctx.globals_dict["counter"] == 2

    def test_function_definition_persistence(self, temp_dir: Path) -> None:
        """Test that function definitions persist."""
        from sandbox.core.execution_context import PersistentExecutionContext
        
        ctx = PersistentExecutionContext()
        
        # Define function
        func_code = """
def greet(name):
    return f"Hello, {name}!"
"""
        exec(func_code, ctx.globals_dict)
        
        # Call function
        result = exec("greeting = greet('World')", ctx.globals_dict)
        assert ctx.globals_dict.get("greeting") == "Hello, World!"

    def test_artifact_directory_creation(self, temp_dir: Path) -> None:
        """Test that artifact directories are created correctly."""
        from sandbox.core.execution_context import PersistentExecutionContext
        
        ctx = PersistentExecutionContext()
        
        # Create artifacts directory manually
        artifacts_dir = temp_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        ctx.artifacts_dir = artifacts_dir
        
        assert ctx.artifacts_dir is not None
        assert ctx.artifacts_dir.exists()
        assert ctx.artifacts_dir.is_dir()

    def test_matplotlib_artifact_capture(self, temp_dir: Path) -> None:
        """Test that matplotlib plots are captured as artifacts."""
        try:
            import matplotlib
            matplotlib.use('Agg')  # Use non-interactive backend
            import matplotlib.pyplot as plt
        except ImportError:
            pytest.skip("matplotlib not installed")
        
        from sandbox.core.execution_context import PersistentExecutionContext
        
        ctx = PersistentExecutionContext()
        artifacts_dir = temp_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        ctx.artifacts_dir = artifacts_dir
        
        # Execute code that creates a plot
        plot_code = f"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

fig, ax = plt.subplots()
ax.plot([1, 2, 3], [1, 4, 9])
ax.set_title('Test Plot')
plt.savefig('{artifacts_dir}/test_plot.png')
plt.close()
"""
        exec(plot_code, ctx.globals_dict)
        
        # Verify plot was saved
        plot_file = artifacts_dir / "test_plot.png"
        assert plot_file.exists()
        assert plot_file.stat().st_size > 0

    def test_json_artifact_creation(self, temp_dir: Path) -> None:
        """Test that JSON artifacts are created correctly."""
        import json
        from sandbox.core.execution_context import PersistentExecutionContext
        
        ctx = PersistentExecutionContext()
        artifacts_dir = temp_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        ctx.artifacts_dir = artifacts_dir
        
        # Execute code that creates JSON
        json_code = f"""
import json

data = {{'name': 'test', 'value': 42}}
with open('{artifacts_dir}/data.json', 'w') as f:
    json.dump(data, f)
"""
        exec(json_code, ctx.globals_dict)
        
        # Verify JSON file
        json_file = artifacts_dir / "data.json"
        assert json_file.exists()
        
        with open(json_file) as f:
            data = json.load(f)
        assert data == {'name': 'test', 'value': 42}

    def test_error_handling_in_execution(self, temp_dir: Path) -> None:
        """Test that errors are handled gracefully."""
        from sandbox.core.execution_context import PersistentExecutionContext
        
        ctx = PersistentExecutionContext()
        
        # Execute code with error
        error_code = """
try:
    result = 1 / 0
except ZeroDivisionError:
    error_handled = True
"""
        exec(error_code, ctx.globals_dict)
        
        assert ctx.globals_dict.get("error_handled") is True

    def test_import_in_execution(self, temp_dir: Path) -> None:
        """Test that imports work in executed code."""
        from sandbox.core.execution_context import PersistentExecutionContext
        
        ctx = PersistentExecutionContext()
        
        # Execute code with import
        import_code = """
import os
import sys
current_dir = os.getcwd()
python_version = sys.version_info.major
"""
        exec(import_code, ctx.globals_dict)
        
        assert "current_dir" in ctx.globals_dict
        assert ctx.globals_dict.get("python_version") >= 3


class TestEndToEndArtifactManagement:
    """End-to-end tests for artifact management workflow."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory for test artifacts."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_artifact_listing(self, temp_dir: Path) -> None:
        """Test that artifacts can be listed."""
        from sandbox.core.execution_context import PersistentExecutionContext
        
        ctx = PersistentExecutionContext()
        artifacts_dir = temp_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        ctx.artifacts_dir = artifacts_dir
        
        # Create some test files
        (artifacts_dir / "test1.txt").write_text("content1")
        (artifacts_dir / "test2.txt").write_text("content2")
        
        # List artifacts
        artifacts = list(artifacts_dir.iterdir())
        assert len(artifacts) == 2

    def test_artifact_cleanup(self, temp_dir: Path) -> None:
        """Test that artifacts can be cleaned up."""
        from sandbox.core.execution_context import PersistentExecutionContext
        
        ctx = PersistentExecutionContext()
        artifacts_dir = temp_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        ctx.artifacts_dir = artifacts_dir
        
        # Create test files
        (artifacts_dir / "test.txt").write_text("content")
        
        # Clean up
        shutil.rmtree(artifacts_dir)
        
        assert not artifacts_dir.exists()


class TestEndToEndWebExport:
    """End-to-end tests for web application export."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory for test exports."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_web_export_service_creation(self, temp_dir: Path) -> None:
        """Test that WebExportService can be created."""
        from sandbox.server.web_export_service import WebExportService
        
        service = WebExportService(artifacts_dir=temp_dir)
        assert service is not None

    def test_flask_export_creates_files(self, temp_dir: Path) -> None:
        """Test that Flask export creates expected files."""
        from sandbox.server.web_export_service import WebExportService
        
        service = WebExportService(artifacts_dir=temp_dir)
        flask_code = "from flask import Flask\napp = Flask(__name__)"
        
        result = service.export_flask_app(flask_code, export_name="test_flask")
        
        assert result["success"] is True
        export_dir = Path(result["export_dir"])
        
        # Verify expected files
        assert (export_dir / "app.py").exists()
        assert (export_dir / "requirements.txt").exists()
        assert (export_dir / "Dockerfile").exists()
        assert (export_dir / "docker-compose.yml").exists()
        assert (export_dir / "README.md").exists()

    def test_streamlit_export_creates_files(self, temp_dir: Path) -> None:
        """Test that Streamlit export creates expected files."""
        from sandbox.server.web_export_service import WebExportService
        
        service = WebExportService(artifacts_dir=temp_dir)
        streamlit_code = "import streamlit as st\nst.title('Test')"
        
        result = service.export_streamlit_app(streamlit_code, export_name="test_streamlit")
        
        assert result["success"] is True
        export_dir = Path(result["export_dir"])
        
        # Verify expected files
        assert (export_dir / "app.py").exists()
        assert (export_dir / "requirements.txt").exists()
        assert (export_dir / "Dockerfile").exists()
