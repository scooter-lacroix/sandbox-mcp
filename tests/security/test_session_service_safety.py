"""Tests for SessionService thread safety and async fixes - C2, C3."""

import unittest
import threading
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

from sandbox.server.session_service import SessionService


class TestSessionServiceThreadSafety(unittest.TestCase):
    """C2: Test SessionService thread safety."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = SessionService()
        
    def tearDown(self):
        """Clean up."""
        self.service.stop()

    def test_concurrent_session_creation(self):
        """C2: Test thread-safe concurrent session creation."""
        created_sessions = []
        errors = []
        
        def create_session():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                session = loop.run_until_complete(self.service.create_session())
                created_sessions.append(session["session_id"])
                loop.close()
            except Exception as e:
                errors.append(e)
        
        # Create sessions concurrently from multiple threads
        threads = []
        for _ in range(10):
            t = threading.Thread(target=create_session)
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # All sessions should be created without errors
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(created_sessions), 10)
        # All session IDs should be unique
        self.assertEqual(len(set(created_sessions)), 10)

    def test_concurrent_execution_count_increment(self):
        """C2: Test thread-safe execution count increment."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        session = loop.run_until_complete(self.service.create_session())
        session_id = session["session_id"]
        
        increments = []
        errors = []
        
        def increment():
            try:
                result = loop.run_until_complete(
                    self.service.increment_execution_count(session_id)
                )
                increments.append(result)
            except Exception as e:
                errors.append(e)
        
        # Increment from multiple threads
        threads = []
        for _ in range(10):
            t = threading.Thread(target=increment)
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(increments), 10)
        # Final count should be 10
        self.assertEqual(increments[-1], 10)

    def test_concurrent_artifact_addition(self):
        """C2: Test thread-safe artifact addition."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        session = loop.run_until_complete(self.service.create_session())
        session_id = session["session_id"]
        
        errors = []
        lock = threading.Lock()
        
        def add_artifact(idx):
            try:
                artifact = {"name": f"artifact_{idx}", "type": "test"}
                # Each thread needs its own event loop context
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    new_loop.run_until_complete(
                        self.service.add_artifact(session_id, artifact)
                    )
                finally:
                    new_loop.close()
            except Exception as e:
                with lock:
                    errors.append(e)
        
        # Add artifacts from multiple threads
        threads = []
        for i in range(10):
            t = threading.Thread(target=add_artifact, args=(i,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        self.assertEqual(len(errors), 0)
        
        # Verify all artifacts were added
        session_data = loop.run_until_complete(self.service.get_session(session_id))
        self.assertEqual(len(session_data["artifacts"]), 10)

    def test_get_active_sessions_returns_copy(self):
        """C2: Test get_active_sessions returns copies not references."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        session = loop.run_until_complete(self.service.create_session())
        
        # Get sessions and modify
        sessions = loop.run_until_complete(self.service.get_active_sessions())
        original_count = len(sessions)
        
        # Modify returned list
        sessions.append({"fake": "session"})
        sessions[0]["modified"] = True
        
        # Get sessions again - should not have modifications
        sessions2 = loop.run_until_complete(self.service.get_active_sessions())
        self.assertEqual(len(sessions2), original_count)
        self.assertNotIn("modified", sessions2[0])


class TestSessionServiceAsyncSafety(unittest.TestCase):
    """C3: Test asyncio.run() fix in daemon thread."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = SessionService()
        
    def tearDown(self):
        """Clean up."""
        self.service.stop()

    def test_cleanup_with_active_event_loop(self):
        """C3: Test cleanup doesn't fail with active event loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Create a session
        session = loop.run_until_complete(self.service.create_session())
        session_id = session["session_id"]
        
        # Manually set short timeout by accessing internal state
        with self.service._lock:
            self.service._sessions[session_id]["timeout_seconds"] = 1
            self.service._sessions[session_id]["last_seen"] = \
                self.service._sessions[session_id]["created_at"]
        
        # Wait for session to expire and be cleaned up by daemon thread
        # This should NOT raise RuntimeError about asyncio.run()
        time.sleep(3)
        
        # Service should still be running
        self.assertTrue(self.service._running)

    def test_event_loop_reuse(self):
        """C3: Test event loop is properly reused."""
        # Get event loop twice
        loop1 = self.service._get_event_loop()
        loop2 = self.service._get_event_loop()
        
        # Should be same loop
        self.assertIs(loop1, loop2)

    def test_run_coroutine_threadsafe(self):
        """C3: Test asyncio.run_coroutine_threadsafe usage."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Start loop in background thread
        def run_loop():
            asyncio.set_event_loop(loop)
            loop.run_forever()
        
        thread = threading.Thread(target=run_loop)
        thread.start()
        
        try:
            # Schedule coroutine from different thread
            future = asyncio.run_coroutine_threadsafe(
                self.service.create_session(),
                loop
            )
            session = future.result(timeout=5)
            
            self.assertIn("session_id", session)
        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join()


class TestSessionServiceTeardownHooks(unittest.TestCase):
    """Test teardown hooks thread safety."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = SessionService()
        
    def tearDown(self):
        """Clean up."""
        self.service.stop()

    def test_register_teardown_hook_thread_safe(self):
        """C2: Test register_teardown_hook is thread-safe."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        session = loop.run_until_complete(self.service.create_session())
        session_id = session["session_id"]
        
        errors = []
        
        def register_hook(idx):
            try:
                def hook(sid):
                    pass
                self.service.register_teardown_hook(session_id, hook)
            except Exception as e:
                errors.append(e)
        
        # Register hooks from multiple threads
        threads = []
        for i in range(10):
            t = threading.Thread(target=register_hook, args=(i,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        self.assertEqual(len(errors), 0)


if __name__ == "__main__":
    unittest.main()
