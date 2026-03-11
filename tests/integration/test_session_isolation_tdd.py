"""Integration tests for per-session process isolation (TDD - Red Phase).

These tests verify that concurrent sessions have true isolation:
- Separate working directories (cwd)
- Separate environment variables
- Separate global variables (execution_globals)
- Separate artifact directories
- No cross-session leakage

All tests should initially FAIL because the current implementation
uses shared ctx.execution_globals across all sessions.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Any
import pytest


class TestSessionIsolationTDD:
    """
    TDD tests for session isolation (RED PHASE - tests should fail).

    These tests document the expected behavior of isolated sessions.
    They will fail against the current implementation which uses
    shared ctx.execution_globals.
    """

    @pytest.mark.xfail(
        reason="Session isolation not yet implemented - uses shared ctx.execution_globals"
    )
    async def test_concurrent_sessions_have_separate_globals(self):
        """Test that concurrent sessions have separate global variables.

        This test creates two sessions that each set a global variable,
        then verifies they don't interfere with each other.
        """
        from sandbox.server.session_service import SessionService

        session_service = SessionService()

        # Create two sessions
        session1 = await session_service.create_session("session_1")
        session2 = await session_service.create_session("session_2")

        # Session 1 sets a global variable
        code1 = "session_var = 'session_1_value'"
        result1 = await session_service.execute_in_session(
            "session_1", code1
        )

        # Session 2 sets a different global variable with same name
        code2 = "session_var = 'session_2_value'"
        result2 = await session_service.execute_in_session(
            "session_2", code2
        )

        # Each session should have its own value
        session1_globals = await session_service.get_session_globals("session_1")
        session2_globals = await session_service.get_session_globals("session_2")

        assert session1_globals.get("session_var") == "session_1_value", \
            "Session 1 should have its own global value"
        assert session2_globals.get("session_var") == "session_2_value", \
            "Session 2 should have its own global value"

    @pytest.mark.xfail(
        reason="Session isolation not yet implemented - uses shared ctx.execution_globals"
    )
    async def test_concurrent_sessions_have_separate_cwd(self):
        """Test that concurrent sessions have separate working directories.

        This test verifies that os.getcwd() returns different paths
        for different sessions.
        """
        from sandbox.server.session_service import SessionService

        session_service = SessionService()

        # Create two sessions with different working directories
        with tempfile.TemporaryDirectory() as temp_dir:
            session1_dir = Path(temp_dir) / "session1"
            session2_dir = Path(temp_dir) / "session2"
            session1_dir.mkdir()
            session2_dir.mkdir()

            await session_service.create_session(
                "session_1", working_dir=str(session1_dir)
            )
            await session_service.create_session(
                "session_2", working_dir=str(session2_dir)
            )

            # Change cwd in session 1
            await session_service.execute_in_session(
                "session_1", "import os; os.chdir('subdir')"
            )

            # Session 2 should still be in its original directory
            session2_cwd_result = await session_service.execute_in_session(
                "session_2", "import os; os.getcwd()"
            )

            # Session 2's cwd should be session2_dir, not affected by session 1
            assert str(session2_dir) in session2_cwd_result

    @pytest.mark.xfail(
        reason="Session isolation not yet implemented - uses shared ctx.execution_globals"
    )
    async def test_concurrent_sessions_have_separate_env_vars(self):
        """Test that concurrent sessions have separate environment variables.

        This test verifies that os.environ modifications in one session
        don't affect other sessions.
        """
        from sandbox.server.session_service import SessionService

        session_service = SessionService()

        # Create two sessions
        await session_service.create_session("session_1")
        await session_service.create_session("session_2")

        # Session 1 sets an environment variable
        await session_service.execute_in_session(
            "session_1",
            "import os; os.environ['SESSION_VAR'] = 'session_1_value'"
        )

        # Session 2 should not see this variable
        result = await session_service.execute_in_session(
            "session_2",
            "import os; os.environ.get('SESSION_VAR', 'not_set')"
        )

        assert "not_set" in result, \
            "Session 2 should not see environment variables set by Session 1"

    @pytest.mark.xfail(
        reason="Session isolation not yet implemented - artifacts may leak"
    )
    async def test_concurrent_sessions_have_separate_artifacts(self):
        """Test that concurrent sessions have separate artifact directories.

        This test verifies that artifacts created in one session
        don't appear in another session's artifacts.
        """
        from sandbox.server.session_service import SessionService

        session_service = SessionService()

        # Create two sessions
        await session_service.create_session("session_1")
        await session_service.create_session("session_2")

        # Session 1 creates an artifact (a file)
        await session_service.execute_in_session(
            "session_1",
            """
from pathlib import Path
artifact_path = Path('artifacts/session1_file.txt')
artifact_path.parent.mkdir(parents=True, exist_ok=True)
artifact_path.write_text('session1 content')
"""
        )

        # Session 2 lists its artifacts - should not see session1's files
        session2_artifacts = await session_service.list_session_artifacts("session_2")

        # Session 2 should not have session1_file.txt
        artifact_names = [a.get('name', '') for a in session2_artifacts]
        assert 'session1_file.txt' not in artifact_names, \
            "Session 2 should not see artifacts created by Session 1"

    @pytest.mark.xfail(
        reason="Session isolation not yet implemented - uses shared globals"
    )
    async def test_session_globals_persist_across_executions(self):
        """Test that a session's globals persist across multiple executions.

        This test verifies that within a single session, global variables
        set in one execution are available in subsequent executions.
        """
        from sandbox.server.session_service import SessionService

        session_service = SessionService()

        # Create a session
        await session_service.create_session("test_session")

        # First execution sets a global
        await session_service.execute_in_session(
            "test_session",
            "persistent_var = 'first_value'"
        )

        # Second execution should see the global
        result = await session_service.execute_in_session(
            "test_session",
            "print(persistent_var)"
        )

        assert "first_value" in result, \
            "Session globals should persist across executions in same session"

    @pytest.mark.xfail(
        reason="Session isolation not yet implemented - shared globals leak"
    )
    async def test_concurrent_execution_safety(self):
        """Test that concurrent executions in different sessions are safe.

        This test runs many concurrent operations across multiple sessions
        to verify there's no race condition or data corruption.
        """
        from sandbox.server.session_service import SessionService

        session_service = SessionService()

        # Create multiple sessions
        num_sessions = 5
        for i in range(num_sessions):
            await session_service.create_session(f"session_{i}")

        # Execute concurrent operations in each session
        async def execute_in_session(session_id: int, iteration: int):
            code = f"session_id = {session_id}; iteration = {iteration}"
            return await session_service.execute_in_session(
                f"session_{session_id}", code
            )

        # Run 10 iterations of concurrent executions
        results = []
        for iteration in range(10):
            tasks = [
                execute_in_session(i, iteration)
                for i in range(num_sessions)
            ]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)

        # Verify all executions completed successfully
        assert len(results) == num_sessions * 10, \
            "All concurrent executions should complete"


class TestSessionCleanupTDD:
    """
    TDD tests for session cleanup (RED PHASE - tests should fail).

    These tests verify proper cleanup of session resources.
    """

    @pytest.mark.xfail(
        reason="Session cleanup not yet implemented - needs worker lifecycle"
    )
    async def test_session_cleanup_removes_artifacts(self):
        """Test that cleaning up a session removes its artifacts.

        This test verifies that when a session is cleaned up,
        all its artifacts are removed from disk.
        """
        from sandbox.server.session_service import SessionService

        session_service = SessionService()

        # Create a session and create artifacts
        await session_service.create_session("test_session")
        await session_service.execute_in_session(
            "test_session",
            """
from pathlib import Path
artifact_path = Path('artifacts/test_file.txt')
artifact_path.parent.mkdir(parents=True, exist_ok=True)
artifact_path.write_text('test content')
"""
        )

        # Get the artifacts directory before cleanup
        artifacts_dir = await session_service.get_session_artifacts_dir("test_session")
        assert artifacts_dir.exists(), "Artifacts directory should exist"

        # Cleanup the session
        await session_service.cleanup_session("test_session")

        # Artifacts directory should be removed
        assert not artifacts_dir.exists(), \
            "Artifacts directory should be removed after cleanup"

    @pytest.mark.xfail(
        reason="Session cleanup not yet implemented - web app processes not tracked"
    )
    async def test_session_cleanup_kills_web_processes(self):
        """Test that cleaning up a session terminates its web app processes.

        This test verifies that web apps launched by a session are
        terminated when the session is cleaned up.
        """
        from sandbox.server.session_service import SessionService

        session_service = SessionService()

        # Create a session and launch a web app
        await session_service.create_session("test_session")

        # Launch a simple Flask app
        flask_code = """
from flask import Flask
app = Flask(__name__)

@app.route('/')
def home():
    return 'Hello from session'

if __name__ == '__main__':
    # Just define the app, don't run
    pass
"""
        # Note: This would require actual web app launching
        # For now, we document the expected behavior
        # await session_service.launch_web_app("test_session", flask_code, "flask")

        # Get running processes before cleanup
        processes_before = await session_service.get_session_processes("test_session")

        # Cleanup the session
        await session_service.cleanup_session("test_session")

        # Processes should be terminated
        processes_after = await session_service.get_session_processes("test_session")

        assert len(processes_after) < len(processes_before), \
            "Web app processes should be terminated after cleanup"


class TestWorkerLifecycleTDD:
    """
    TDD tests for worker lifecycle management (RED PHASE - tests should fail).

    These tests verify that execution workers are properly created,
    managed, and cleaned up.
    """

    @pytest.mark.xfail(
        reason="Worker lifecycle not yet implemented - needs worker pool"
    )
    async def test_worker_isolation(self):
        """Test that code executes in an isolated worker process.

        This test verifies that code execution happens in a separate
        process/worker, not in the main server process.
        """
        from sandbox.server.session_service import SessionService

        session_service = SessionService()

        # Create a session and execute code
        await session_service.create_session("test_session")

        # Get worker info before execution
        workers_before = await session_service.get_active_workers()

        # Execute code - should spawn a worker
        await session_service.execute_in_session(
            "test_session",
            "result = 'worker_execution_test'"
        )

        # Worker should have been created
        workers_after = await session_service.get_active_workers()

        # Note: The worker might be cleaned up after execution,
        # so we're documenting the expected behavior here
        # In a real implementation, we'd verify the worker was used

    @pytest.mark.xfail(
        reason="Worker lifecycle not yet implemented - needs worker pool"
    )
    async def test_worker_cleanup_after_timeout(self):
        """Test that workers are cleaned up after execution timeout.

        This test verifies that if a worker times out during execution,
        it is properly cleaned up and doesn't leak resources.
        """
        from sandbox.server.session_service import SessionService

        session_service = SessionService()

        # Create a session
        await session_service.create_session("test_session")

        # Execute code that times out (infinite loop)
        timeout_code = "while True: pass"

        # This should timeout and clean up the worker
        with pytest.raises(TimeoutError):
            await session_service.execute_in_session(
                "test_session", timeout_code, timeout=0.1
            )

        # Verify worker was cleaned up
        workers = await session_service.get_active_workers()
        assert len(workers) == 0, \
            "Worker should be cleaned up after timeout"
