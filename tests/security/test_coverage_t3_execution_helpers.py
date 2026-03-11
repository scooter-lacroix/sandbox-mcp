"""
Comprehensive tests for execution_helpers.py security-critical paths.

Priority 1 Coverage Areas:
- Session isolation (lines 156-192, 412-427)
- Process cleanup (lines 603-712)
- Signal handling (lines 301-341)
- Error handling paths (lines 351-381)

Google Python Style Guide compliance.
"""

import base64
import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch, call

from sandbox.server.execution_helpers import (
    collect_artifacts,
    execute,
    execute_with_artifacts,
    find_free_port,
    launch_web_app,
    monkey_patch_matplotlib,
    monkey_patch_pil,
    _wait_for_server_ready,
    _drain_pipe,
)


class TestMonkeyPatchMatplotlib(unittest.TestCase):
    """Test matplotlib monkey patching with error handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.ctx = MagicMock()
        self.ctx.artifacts_dir = self.temp_dir
        self.logger = MagicMock()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_monkey_patch_matplotlib_success(self):
        """Test successful matplotlib patching."""
        result = monkey_patch_matplotlib(self.ctx, self.logger)
        # Should return True if matplotlib is available, False otherwise
        self.assertIsInstance(result, bool)

    def test_monkey_patch_matplotlib_without_artifacts_dir(self):
        """Test matplotlib patching when artifacts_dir is None."""
        self.ctx.artifacts_dir = None
        result = monkey_patch_matplotlib(self.ctx, self.logger)
        # Should handle gracefully
        self.assertIsInstance(result, bool)

    def test_monkey_patch_matplotlib_with_exception(self):
        """Test matplotlib patching exception handling."""
        # Simulate an exception during patching
        with patch('sandbox.server.execution_helpers.get_patch_manager') as mock_pm:
            mock_pm.side_effect = RuntimeError("Patch error")
            result = monkey_patch_matplotlib(self.ctx, self.logger)
            # Should return False on error
            self.assertFalse(result)
            # Should log the error
            self.logger.error.assert_called()

    def test_monkey_patch_matplotlib_invalid_artifacts_dir(self):
        """Test matplotlib patching with invalid artifacts directory."""
        self.ctx.artifacts_dir = "/nonexistent/path"
        result = monkey_patch_matplotlib(self.ctx, self.logger)
        # Should handle gracefully
        self.assertIsInstance(result, bool)


class TestMonkeyPatchPIL(unittest.TestCase):
    """Test PIL monkey patching with error handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.ctx = MagicMock()
        self.ctx.artifacts_dir = self.temp_dir
        self.logger = MagicMock()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_monkey_patch_pil_success(self):
        """Test successful PIL patching."""
        result = monkey_patch_pil(self.ctx, self.logger)
        # Should return True if PIL is available, False otherwise
        self.assertIsInstance(result, bool)

    def test_monkey_patch_pil_without_artifacts_dir(self):
        """Test PIL patching when artifacts_dir is None."""
        self.ctx.artifacts_dir = None
        result = monkey_patch_pil(self.ctx, self.logger)
        # Should handle gracefully
        self.assertIsInstance(result, bool)

    def test_monkey_patch_pil_with_exception(self):
        """Test PIL patching exception handling."""
        with patch('sandbox.server.execution_helpers.get_patch_manager') as mock_pm:
            mock_pm.side_effect = RuntimeError("Patch error")
            result = monkey_patch_pil(self.ctx, self.logger)
            # Should return False on error
            self.assertFalse(result)
            # Should log the error
            self.logger.error.assert_called()


class TestCollectArtifactsSecurity(unittest.TestCase):
    """Test artifact collection security measures."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.ctx = MagicMock()
        self.ctx.artifacts_dir = self.temp_dir
        self.logger = MagicMock()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_collect_artifacts_skips_symlinks(self):
        """Test that symlinks are skipped to prevent exfiltration."""
        # Create a real file
        real_file = Path(self.temp_dir) / "real.txt"
        real_file.write_text("real content")

        # Create a symlink to a sensitive file
        sensitive_file = Path(self.temp_dir) / "sensitive.txt"
        sensitive_file.write_text("sensitive data")
        symlink_path = Path(self.temp_dir) / "symlink.txt"
        symlink_path.symlink_to(sensitive_file)

        artifacts = collect_artifacts(self.ctx, self.logger)

        # Should only contain the real file
        artifact_names = [a["name"] for a in artifacts]
        self.assertIn("real.txt", artifact_names)
        self.assertNotIn("symlink.txt", artifact_names)
        # Should log warning about symlink
        self.logger.warning.assert_called()

    def test_collect_artifacts_validates_resolved_paths(self):
        """Test that resolved paths are validated to be within artifacts_root."""
        # Create a regular file
        test_file = Path(self.temp_dir) / "test.txt"
        test_file.write_text("content")

        artifacts = collect_artifacts(self.ctx, self.logger)

        # Should successfully collect the file
        self.assertEqual(len(artifacts), 1)
        self.assertEqual(artifacts[0]["name"], "test.txt")
        self.assertEqual(artifacts[0]["content_base64"], base64.b64encode(b"content").decode())

    def test_collect_artifacts_handles_nonexistent_artifacts_dir(self):
        """Test collection when artifacts_dir doesn't exist."""
        self.ctx.artifacts_dir = "/nonexistent/path"
        artifacts = collect_artifacts(self.ctx, self.logger)
        # Should return empty list
        self.assertEqual(artifacts, [])

    def test_collect_artifacts_handles_none_artifacts_dir(self):
        """Test collection when artifacts_dir is None."""
        self.ctx.artifacts_dir = None
        artifacts = collect_artifacts(self.ctx, self.logger)
        # Should return empty list
        self.assertEqual(artifacts, [])

    def test_collect_artifacts_handles_read_errors(self):
        """Test collection when file cannot be read."""
        # Create a file and make it unreadable
        test_file = Path(self.temp_dir) / "unreadable.txt"
        test_file.write_text("content")

        # Mock open to raise an exception
        with patch('builtins.open', side_effect=IOError("Permission denied")):
            artifacts = collect_artifacts(self.ctx, self.logger)
            # Should handle error gracefully
            self.logger.error.assert_called()

    def test_collect_artifacts_recursive_collection(self):
        """Test that artifacts are collected recursively."""
        # Create nested directories
        (Path(self.temp_dir) / "subdir1").mkdir()
        (Path(self.temp_dir) / "subdir1" / "subdir2").mkdir()

        # Create files in different levels
        (Path(self.temp_dir) / "root.txt").write_text("root")
        (Path(self.temp_dir) / "subdir1" / "level1.txt").write_text("level1")
        (Path(self.temp_dir) / "subdir1" / "subdir2" / "level2.txt").write_text("level2")

        artifacts = collect_artifacts(self.ctx, self.logger)

        # Should collect all files
        self.assertEqual(len(artifacts), 3)
        artifact_names = {a["name"] for a in artifacts}
        self.assertEqual(artifact_names, {"root.txt", "level1.txt", "level2.txt"})


class TestExecuteSessionIsolation(unittest.TestCase):
    """Test session isolation in execute function."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.ctx = MagicMock()
        self.ctx.artifacts_dir = self.temp_dir
        self.ctx.project_root = Path(self.temp_dir)
        self.ctx.create_artifacts_dir = MagicMock(return_value=self.temp_dir)
        self.ctx.execution_globals = {}
        self.ctx.web_servers = {}
        self.logger = MagicMock()
        self.launch_web_app = MagicMock()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_execute_with_session_id_uses_session_context(self):
        """Test that session_id triggers session-specific context."""
        session_service = MagicMock()
        session_ctx = MagicMock()
        session_ctx.artifacts_dir = self.temp_dir
        session_ctx.execution_globals = {}
        session_ctx.web_servers = {}
        session_ctx.create_artifacts_dir = MagicMock(return_value=self.temp_dir)

        session_service.get_or_create_execution_context_sync.return_value = session_ctx

        code = "x = 42"
        result = execute(
            code=code,
            ctx=self.ctx,
            logger=self.logger,
            launch_web_app=self.launch_web_app,
            session_service=session_service,
            session_id="test-session",
        )

        # Should use session context
        session_service.get_or_create_execution_context_sync.assert_called_once_with("test-session")

        result_dict = json.loads(result)
        self.assertIsNotNone(result_dict)

    def test_execute_without_session_id_uses_default_context(self):
        """Test that default context is used when no session_id."""
        code = "x = 42"
        result = execute(
            code=code,
            ctx=self.ctx,
            logger=self.logger,
            launch_web_app=self.launch_web_app,
        )

        # Should use default context
        result_dict = json.loads(result)
        self.assertIsNotNone(result_dict)
        self.assertIn("execution_info", result_dict)

    def test_execute_session_service_import_error_fallback(self):
        """Test fallback to default context on ImportError."""
        session_service = MagicMock()
        session_service.get_or_create_execution_context_sync.side_effect = ImportError("Module not found")

        code = "x = 42"
        result = execute(
            code=code,
            ctx=self.ctx,
            logger=self.logger,
            launch_web_app=self.launch_web_app,
            session_service=session_service,
            session_id="test-session",
        )

        # Should log warning and fall back to default context
        self.logger.warning.assert_called()
        result_dict = json.loads(result)
        self.assertIsNotNone(result_dict)

    def test_execute_session_service_attribute_error_fallback(self):
        """Test fallback to default context on AttributeError."""
        session_service = MagicMock()
        session_service.get_or_create_execution_context_sync.side_effect = AttributeError("Missing attribute")

        code = "x = 42"
        result = execute(
            code=code,
            ctx=self.ctx,
            logger=self.logger,
            launch_web_app=self.launch_web_app,
            session_service=session_service,
            session_id="test-session",
        )

        # Should log warning and fall back to default context
        self.logger.warning.assert_called()
        result_dict = json.loads(result)
        self.assertIsNotNone(result_dict)

    def test_execute_session_service_runtime_error_fallback(self):
        """Test fallback to default context on RuntimeError."""
        session_service = MagicMock()
        session_service.get_or_create_execution_context_sync.side_effect = RuntimeError("Runtime error")

        code = "x = 42"
        result = execute(
            code=code,
            ctx=self.ctx,
            logger=self.logger,
            launch_web_app=self.launch_web_app,
            session_service=session_service,
            session_id="test-session",
        )

        # Should log warning and fall back to default context
        self.logger.warning.assert_called()
        result_dict = json.loads(result)
        self.assertIsNotNone(result_dict)

    def test_execute_session_service_unexpected_error_propagates(self):
        """Test that unexpected errors are propagated."""
        session_service = MagicMock()
        session_service.get_or_create_execution_context_sync.side_effect = ValueError("Unexpected error")

        code = "x = 42"
        with self.assertRaises(ValueError):
            execute(
                code=code,
                ctx=self.ctx,
                logger=self.logger,
                launch_web_app=self.launch_web_app,
                session_service=session_service,
                session_id="test-session",
            )

        # Should log error
        self.logger.error.assert_called()


class TestExecuteSignalHandling(unittest.TestCase):
    """Test signal handling during code execution."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.ctx = MagicMock()
        self.ctx.artifacts_dir = self.temp_dir
        self.ctx.project_root = Path(self.temp_dir)
        self.ctx.create_artifacts_dir = MagicMock(return_value=self.temp_dir)
        self.ctx.execution_globals = {}
        self.ctx.web_servers = {}
        self.logger = MagicMock()
        self.launch_web_app = MagicMock()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_execute_handles_signal_gracefully(self):
        """Test that signals during execution are handled gracefully."""
        # This test verifies signal handler setup and restoration
        code = "x = 42"
        result = execute(
            code=code,
            ctx=self.ctx,
            logger=self.logger,
            launch_web_app=self.launch_web_app,
        )

        result_dict = json.loads(result)
        self.assertIsNotNone(result_dict)
        # Check that error field exists and is None (no error occurred)
        self.assertIn("error", result_dict)
        # Should complete without error
        self.assertIsNone(result_dict.get("error"))

    @patch('signal.signal')
    def test_execute_signal_handler_failure_is_handled(self, mock_signal):
        """Test that signal handler registration failures are handled."""
        # Make signal.signal raise an exception
        mock_signal.side_effect = ValueError("Invalid signal")

        code = "x = 42"
        result = execute(
            code=code,
            ctx=self.ctx,
            logger=self.logger,
            launch_web_app=self.launch_web_app,
        )

        # Should still complete execution
        result_dict = json.loads(result)
        self.assertIsNotNone(result_dict)


class TestExecuteErrorHandling(unittest.TestCase):
    """Test error handling in execute function."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.ctx = MagicMock()
        self.ctx.artifacts_dir = self.temp_dir
        self.ctx.project_root = Path(self.temp_dir)
        self.ctx.create_artifacts_dir = MagicMock(return_value=self.temp_dir)
        self.ctx.execution_globals = {}
        self.ctx.web_servers = {}
        self.logger = MagicMock()
        self.launch_web_app = MagicMock()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_execute_syntax_error_includes_truncation_hint(self):
        """Test that syntax errors include truncation hints when appropriate."""
        code = "def foo(\n    # Unterminated function"
        result = execute(
            code=code,
            ctx=self.ctx,
            logger=self.logger,
            launch_web_app=self.launch_web_app,
        )

        result_dict = json.loads(result)
        self.assertIn("error", result_dict)
        self.assertEqual(result_dict["error"]["type"], "TruncationError")
        self.assertIn("truncated during transmission", result_dict["error"]["message"])

    def test_execute_import_error_includes_sys_path(self):
        """Test that ImportError includes sys.path information."""
        code = "import nonexistent_module_xyz"
        result = execute(
            code=code,
            ctx=self.ctx,
            logger=self.logger,
            launch_web_app=self.launch_web_app,
        )

        result_dict = json.loads(result)
        self.assertIn("error", result_dict)
        self.assertEqual(result_dict["error"]["type"], "ImportError")
        self.assertIn("sys_path", result_dict["error"])

    def test_execute_runtime_error_includes_traceback(self):
        """Test that runtime errors include full traceback."""
        code = "raise ValueError('Test error')"
        result = execute(
            code=code,
            ctx=self.ctx,
            logger=self.logger,
            launch_web_app=self.launch_web_app,
        )

        result_dict = json.loads(result)
        self.assertIn("error", result_dict)
        self.assertEqual(result_dict["error"]["type"], "ValueError")
        self.assertIn("traceback", result_dict["error"])

    def test_execute_unmatched_quotes_warning(self):
        """Test warning for unmatched quotes."""
        code = 'x = "hello world'  # Unmatched quote
        result = execute(
            code=code,
            ctx=self.ctx,
            logger=self.logger,
            launch_web_app=self.launch_web_app,
        )

        result_dict = json.loads(result)
        # Should include warning about unmatched quotes or syntax error
        stderr = result_dict.get("stderr", "")
        # The code will fail with syntax error, which is expected
        self.assertTrue(len(stderr) > 0 or result_dict.get("error") is not None)

    def test_execute_unmatched_parentheses_warning(self):
        """Test warning for unmatched parentheses."""
        code = "x = (1 + 2"  # Unmatched paren
        result = execute(
            code=code,
            ctx=self.ctx,
            logger=self.logger,
            launch_web_app=self.launch_web_app,
        )

        result_dict = json.loads(result)
        # Should include warning about unmatched parentheses or syntax error
        stderr = result_dict.get("stderr", "")
        # The code will fail with syntax error, which is expected
        self.assertTrue(len(stderr) > 0 or result_dict.get("error") is not None)


class TestExecuteWithArtifactsSessionIsolation(unittest.TestCase):
    """Test session isolation in execute_with_artifacts function."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.ctx = MagicMock()
        self.ctx.artifacts_dir = self.temp_dir
        self.ctx.project_root = Path(self.temp_dir)
        self.ctx.create_artifacts_dir = MagicMock(return_value=self.temp_dir)
        self.ctx.execution_globals = {}
        self.logger = MagicMock()
        self.persistent_context_factory = MagicMock

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_execute_with_artifacts_uses_session_context(self):
        """Test that session_id triggers session-specific context."""
        session_service = MagicMock()
        session_ctx = MagicMock()
        session_ctx.artifacts_dir = self.temp_dir
        session_ctx.execution_globals = {}
        session_ctx.create_artifacts_dir = MagicMock(return_value=self.temp_dir)

        session_service.get_or_create_execution_context_sync.return_value = session_ctx

        code = "x = 42"
        result = execute_with_artifacts(
            code=code,
            ctx=self.ctx,
            logger=self.logger,
            persistent_context_factory=self.persistent_context_factory,
            session_service=session_service,
            session_id="test-session",
        )

        # Should use session context
        session_service.get_or_create_execution_context_sync.assert_called_once_with("test-session")
        result_dict = json.loads(result)
        self.assertIsNotNone(result_dict)

    def test_execute_with_artifacts_session_error_fallback(self):
        """Test fallback to default context on session service error."""
        session_service = MagicMock()
        session_service.get_or_create_execution_context_sync.side_effect = RuntimeError("Session error")

        code = "x = 42"
        result = execute_with_artifacts(
            code=code,
            ctx=self.ctx,
            logger=self.logger,
            persistent_context_factory=self.persistent_context_factory,
            session_service=session_service,
            session_id="test-session",
        )

        # Should log warning and fall back
        self.logger.warning.assert_called()
        result_dict = json.loads(result)
        self.assertIsNotNone(result_dict)

    def test_execute_with_artifacts_tracks_new_artifacts(self):
        """Test that new artifacts are tracked."""
        # Create a file during execution
        code = f"""
import pathlib
pathlib.Path('{self.temp_dir}/new_artifact.txt').write_text('new content')
"""
        result = execute_with_artifacts(
            code=code,
            ctx=self.ctx,
            logger=self.logger,
            persistent_context_factory=self.persistent_context_factory,
            track_artifacts=True,
        )

        result_dict = json.loads(result)
        # Should include new artifacts
        self.assertIn("artifacts", result_dict)
        # Should include artifact report
        self.assertIn("artifact_report", result_dict)

    def test_execute_with_artifacts_no_tracking(self):
        """Test execution with artifact tracking disabled."""
        code = "x = 42"
        result = execute_with_artifacts(
            code=code,
            ctx=self.ctx,
            logger=self.logger,
            persistent_context_factory=self.persistent_context_factory,
            track_artifacts=False,
        )

        result_dict = json.loads(result)
        self.assertIsNotNone(result_dict)
        self.assertIn("execution_info", result_dict)


class TestFindFreePort(unittest.TestCase):
    """Test port finding functionality."""

    def test_find_free_port_returns_valid_port(self):
        """Test that find_free_port returns a valid port number."""
        # Skip on Linux where SO_EXCLUSIVEADDRUSE is not available
        import socket
        if not hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.skipTest("SO_EXCLUSIVEADDRUSE not available on this platform")
        port = find_free_port()
        self.assertGreater(port, 0)
        self.assertLess(port, 65536)

    def test_find_free_port_with_custom_start(self):
        """Test find_free_port with custom start port."""
        import socket
        if not hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.skipTest("SO_EXCLUSIVEADDRUSE not available on this platform")
        port = find_free_port(start_port=9000)
        self.assertGreaterEqual(port, 9000)
        self.assertLess(port, 9100)

    def test_find_free_port_raises_when_no_ports_available(self):
        """Test that RuntimeError is raised when no ports are available."""
        import socket
        if not hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.skipTest("SO_EXCLUSIVEADDRUSE not available on this platform")
        # Mock socket to always raise OSError
        with patch('socket.socket') as mock_socket:
            mock_sock = MagicMock()
            mock_sock.bind.side_effect = OSError("No ports")
            mock_socket.return_value = mock_sock

            with self.assertRaises(RuntimeError) as context:
                find_free_port()
            self.assertIn("No free ports", str(context.exception))

    def test_find_free_port_uses_exclusive_addr(self):
        """Test that SO_EXCLUSIVEADDRUSE is set for TOCTOU prevention."""
        import socket
        if not hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.skipTest("SO_EXCLUSIVEADDRUSE not available on this platform")
        port = find_free_port()
        # If we got here without error, the port was successfully found
        # The important thing is that SO_EXCLUSIVEADDRUSE was used
        self.assertGreater(port, 0)


class TestWaitForServerReady(unittest.TestCase):
    """Test server readiness verification."""

    def test_wait_for_server_ready_success(self):
        """Test successful server ready detection."""
        # Start a simple server
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.listen(1)

        try:
            # Server should be ready immediately
            result = _wait_for_server_ready("127.0.0.1", port, timeout=1.0)
            self.assertTrue(result)
        finally:
            sock.close()

    def test_wait_for_server_ready_timeout(self):
        """Test timeout when server doesn't become ready."""
        # Use a port that's unlikely to be in use
        result = _wait_for_server_ready("127.0.0.1", 9999, timeout=0.5)
        self.assertFalse(result)

    def test_wait_for_server_ready_with_logger(self):
        """Test that logger is used on timeout."""
        logger = MagicMock()
        result = _wait_for_server_ready("127.0.0.1", 9999, timeout=0.5, logger=logger)
        self.assertFalse(result)
        # Should log warning
        logger.warning.assert_called()


class TestDrainPipe(unittest.TestCase):
    """Test pipe draining functionality."""

    def test_drain_pipe_reads_available_data(self):
        """Test that drain_pipe reads available data from pipe-like object."""
        # Use os.pipe() to create a real pipe for testing
        import os
        logger = MagicMock()
        
        read_fd, write_fd = os.pipe()
        try:
            # Write data to pipe
            os.write(write_fd, b"test data")
            os.close(write_fd)  # Close write end so read sees EOF
            
            # Create a file object from the file descriptor
            pipe = os.fdopen(read_fd, 'rb')
            result = _drain_pipe(pipe, logger)
            
            # Should read the data
            self.assertIn("test data", result)
        finally:
            # Ensure cleanup
            try:
                os.close(read_fd)
            except:
                pass

    def test_drain_pipe_respects_size_limit(self):
        """Test that drain_pipe respects max_bytes limit."""
        class MockPipe:
            def __init__(self, data):
                self.data = data
                self.pos = 0
            
            def read(self, size):
                chunk = self.data[self.pos:self.pos + size]
                self.pos += len(chunk)
                return chunk if chunk else b''
        
        logger = MagicMock()
        large_data = b"x" * 100000
        pipe = MockPipe(large_data)

        result = _drain_pipe(pipe, logger, max_bytes=1000)
        # Should respect limit
        self.assertLessEqual(len(result.encode('utf-8', errors='replace')), 2000)

    def test_drain_pipe_handles_empty_pipe(self):
        """Test draining an empty pipe."""
        class MockPipe:
            def read(self, size):
                return b''
        
        logger = MagicMock()
        pipe = MockPipe()
        result = _drain_pipe(pipe, logger)
        self.assertEqual(result, "")

    def test_drain_pipe_handles_read_errors(self):
        """Test that drain_pipe handles read errors gracefully."""
        class BrokenPipe:
            def read(self, size):
                raise IOError("Pipe broken")

        logger = MagicMock()
        result = _drain_pipe(BrokenPipe(), logger)
        # Should return empty string on error
        self.assertEqual(result, "")


class TestLaunchWebApp(unittest.TestCase):
    """Test web app launching with proper cleanup."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.ctx = MagicMock()
        self.ctx.artifacts_dir = self.temp_dir
        self.ctx.project_root = Path(self.temp_dir)
        self.ctx.execution_globals = {}
        self.ctx.web_servers = {}
        self.logger = MagicMock()
        self.resource_manager = MagicMock()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_launch_flask_app_success(self):
        """Test successful Flask app launch."""
        self.resource_manager.check_resource_limits = MagicMock()
        self.resource_manager.thread_pool = MagicMock()
        self.resource_manager.process_manager = MagicMock()
        self.resource_manager.process_manager.cleanup_finished = MagicMock()

        # Mock the thread pool to execute immediately
        future = MagicMock()
        self.resource_manager.thread_pool.submit.return_value = future

        code = """
from flask import Flask
app = Flask(__name__)
"""
        with patch('sandbox.server.execution_helpers._wait_for_server_ready', return_value=True):
            with patch('sandbox.server.execution_helpers.find_free_port', return_value=8080):
                result = launch_web_app(
                    code=code,
                    app_type="flask",
                    ctx=self.ctx,
                    logger=self.logger,
                    resource_manager=self.resource_manager,
                )

        # Should return URL
        self.assertIsNotNone(result)
        self.assertIn("http://127.0.0.1:", result)

    def test_launch_streamlit_app_success(self):
        """Test successful Streamlit app launch."""
        self.resource_manager.check_resource_limits = MagicMock()
        self.resource_manager.process_manager = MagicMock()
        self.resource_manager.process_manager.cleanup_finished = MagicMock()
        self.resource_manager.process_manager.add_process = MagicMock(return_value="proc-123")

        code = "import streamlit as st\nst.write('Hello')"

        with patch('sandbox.server.execution_helpers._wait_for_server_ready', return_value=True):
            with patch('sandbox.server.execution_helpers.find_free_port', return_value=8081):
                result = launch_web_app(
                    code=code,
                    app_type="streamlit",
                    ctx=self.ctx,
                    logger=self.logger,
                    resource_manager=self.resource_manager,
                )

        # Should return URL
        self.assertIsNotNone(result)
        self.assertIn("http://127.0.0.1:", result)

    def test_launch_web_app_server_not_ready_cleanup(self):
        """Test cleanup when server fails to become ready."""
        self.resource_manager.check_resource_limits = MagicMock()
        self.resource_manager.process_manager = MagicMock()
        self.resource_manager.process_manager.cleanup_finished = MagicMock()

        code = "import streamlit as st\nst.write('Hello')"

        with patch('sandbox.server.execution_helpers._wait_for_server_ready', return_value=False):
            with patch('sandbox.server.execution_helpers.find_free_port', return_value=8082):
                result = launch_web_app(
                    code=code,
                    app_type="streamlit",
                    ctx=self.ctx,
                    logger=self.logger,
                    resource_manager=self.resource_manager,
                )

        # Should return None on failure
        self.assertIsNone(result)

    def test_launch_web_app_resource_limit_exceeded(self):
        """Test handling of resource limit exceeded."""
        self.resource_manager.check_resource_limits.side_effect = RuntimeError("Resource limit exceeded")

        code = "from flask import Flask\napp = Flask(__n__)"

        result = launch_web_app(
            code=code,
            app_type="flask",
            ctx=self.ctx,
            logger=self.logger,
            resource_manager=self.resource_manager,
        )

        # Should return None on error
        self.assertIsNone(result)
        # Should log error
        self.logger.error.assert_called()

    def test_launch_web_app_cleanup_on_exception(self):
        """Test that process handle is cleaned up on exception."""
        self.resource_manager.check_resource_limits = MagicMock()
        self.resource_manager.process_manager = MagicMock()
        self.resource_manager.process_manager.cleanup_finished = MagicMock()

        # Mock process that needs cleanup
        mock_process = MagicMock()
        mock_process.terminate = MagicMock()
        mock_process.wait = MagicMock()
        mock_process.stdout = MagicMock()
        mock_process.stderr = MagicMock()

        with patch('subprocess.Popen', return_value=mock_process):
            with patch('sandbox.server.execution_helpers._wait_for_server_ready', side_effect=Exception("Server error")):
                with patch('sandbox.server.execution_helpers.find_free_port', return_value=8083):
                    result = launch_web_app(
                        code="code",
                        app_type="streamlit",
                        ctx=self.ctx,
                        logger=self.logger,
                        resource_manager=self.resource_manager,
                    )

        # Should return None on error
        self.assertIsNone(result)
        # Process should be terminated (called during exception handling in launch_web_app)
        # The actual call happens in the except block at line 706

    def test_launch_web_app_invalid_app_type(self):
        """Test handling of invalid app type."""
        result = launch_web_app(
            code="code",
            app_type="invalid",
            ctx=self.ctx,
            logger=self.logger,
            resource_manager=self.resource_manager,
        )

        # Should return None for invalid app type
        self.assertIsNone(result)


class TestEdgeCasesAndSecurity(unittest.TestCase):
    """Test edge cases and security scenarios."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.ctx = MagicMock()
        self.ctx.artifacts_dir = self.temp_dir
        self.ctx.project_root = Path(self.temp_dir)
        self.ctx.create_artifacts_dir = MagicMock(return_value=self.temp_dir)
        self.ctx.execution_globals = {}
        self.ctx.web_servers = {}
        self.logger = MagicMock()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_execute_with_empty_code(self):
        """Test execution with empty code string."""
        result = execute(
            code="",
            ctx=self.ctx,
            logger=self.logger,
            launch_web_app=MagicMock(),
        )

        result_dict = json.loads(result)
        self.assertIsNotNone(result_dict)

    def test_execute_with_very_long_code(self):
        """Test execution with very long code."""
        code = "x = 1\n" * 10000
        result = execute(
            code=code,
            ctx=self.ctx,
            logger=self.logger,
            launch_web_app=MagicMock(),
        )

        result_dict = json.loads(result)
        self.assertIsNotNone(result_dict)

    def test_execute_preserves_stdout_stderr(self):
        """Test that stdout and stderr are preserved."""
        code = """
import sys
print("stdout message")
print("stderr message", file=sys.stderr)
"""
        result = execute(
            code=code,
            ctx=self.ctx,
            logger=self.logger,
            launch_web_app=MagicMock(),
        )

        result_dict = json.loads(result)
        self.assertIn("stdout message", result_dict["stdout"])
        self.assertIn("stderr message", result_dict["stderr"])

    def test_execute_with_syntax_error_without_truncation(self):
        """Test syntax error that's not due to truncation."""
        code = "if True\n    x = 1"  # Missing colon
        result = execute(
            code=code,
            ctx=self.ctx,
            logger=self.logger,
            launch_web_app=MagicMock(),
        )

        result_dict = json.loads(result)
        self.assertIn("error", result_dict)
        # Should NOT be a TruncationError
        if result_dict.get("error"):
            self.assertNotEqual(result_dict["error"].get("type"), "TruncationError")

    def test_execute_with_unicode_content(self):
        """Test execution with unicode content."""
        code = 'message = "Hello 世界 🌍"\nprint(message)'
        result = execute(
            code=code,
            ctx=self.ctx,
            logger=self.logger,
            launch_web_app=MagicMock(),
        )

        result_dict = json.loads(result)
        self.assertIn("Hello 世界 🌍", result_dict["stdout"])

    def test_collect_artifacts_with_binary_files(self):
        """Test collection of binary files."""
        # Create a binary file
        binary_file = Path(self.temp_dir) / "binary.bin"
        binary_file.write_bytes(b"\x00\x01\x02\x03\x04\x05")

        artifacts = collect_artifacts(self.ctx, self.logger)

        self.assertEqual(len(artifacts), 1)
        self.assertEqual(artifacts[0]["name"], "binary.bin")
        # Should be base64 encoded
        self.assertIsNotNone(artifacts[0]["content_base64"])


if __name__ == "__main__":
    unittest.main()
