"""
Session Service for Sandbox MCP Server.

This module handles session management, replacing duplicate logic
from the stdio server.

Security C2: Thread-safe operations with proper locking.
Security C3: Async-safe cleanup without asyncio.run() in daemon threads.
"""

import uuid
import threading
import time
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class SessionService:
    """
    Service for managing sandbox sessions.

    This service provides unified session creation, retrieval, and cleanup,
    replacing duplicate logic in the stdio server.
    
    Thread Safety C2: All shared state access is protected by _lock.
    """

    def __init__(self):
        """Initialize the session service with thread safety."""
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._cleanup_thread = None
        self._running = False
        self._teardown_hooks: Dict[str, List[Callable]] = {}
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None
        
        # Start background cleanup thread
        self._start_cleanup_thread()

    def _get_event_loop(self) -> asyncio.AbstractEventLoop:
        """
        Get or create event loop for async operations.
        
        Security C3: Avoids asyncio.run() in daemon threads by using
        a dedicated event loop with create_task() instead.
        """
        if self._event_loop is None or self._event_loop.is_closed():
            try:
                self._event_loop = asyncio.get_event_loop()
            except RuntimeError:
                # No event loop in this thread, create new one
                self._event_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._event_loop)
        return self._event_loop

    def _start_cleanup_thread(self) -> None:
        """Start background cleanup thread for expired sessions."""
        self._running = True
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_expired_sessions, daemon=True
        )
        self._cleanup_thread.start()

    def _cleanup_expired_sessions(self) -> None:
        """Background thread to clean up expired sessions."""
        while self._running:
            try:
                # Clean up expired sessions every 60 seconds
                self._check_and_cleanup_expired()
                time.sleep(60)
            except Exception as e:
                logger.error(f"Error in session cleanup thread: {e}")
                time.sleep(10)  # Wait before retrying on error

    def _check_and_cleanup_expired(self) -> None:
        """
        Check for and cleanup expired sessions.
        
        Security C3: Uses event loop task scheduling instead of asyncio.run()
        to avoid RuntimeError when called from daemon thread with active event loop.
        """
        now = datetime.now(timezone.utc)
        expired_sessions = []

        with self._lock:
            for session_id, session in list(self._sessions.items()):
                # Check if session has timed out
                if "last_seen" in session and "timeout_seconds" in session:
                    last_seen = session["last_seen"]
                    timeout = timedelta(seconds=session["timeout_seconds"])
                    if now - last_seen > timeout:
                        expired_sessions.append(session_id)
                # Check for absolute expiry (e.g., 24 hours)
                if "created_at" in session:
                    created_at = session["created_at"]
                    if now - created_at > timedelta(hours=24):
                        expired_sessions.append(session_id)

        # Clean up expired sessions outside the lock
        for session_id in expired_sessions:
            try:
                # C3 FIX: Use event loop task instead of asyncio.run()
                loop = self._get_event_loop()
                if loop.is_running():
                    # Schedule cleanup as a task if loop is running
                    asyncio.run_coroutine_threadsafe(
                        self.cleanup_session(session_id), loop
                    )
                else:
                    # Run cleanup synchronously if loop not running
                    loop.run_until_complete(self.cleanup_session(session_id))
                logger.info(f"Expired session cleaned up: {session_id}")
            except Exception as e:
                logger.error(f"Error cleaning up expired session {session_id}: {e}")

    def stop(self) -> None:
        """Stop the session service and cleanup thread."""
        self._running = False
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)
        self._cleanup_thread = None
        self._running = False

    async def create_session(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new session.
        
        Security C2: Thread-safe with proper locking.

        Args:
            session_id: Optional session ID. If not provided, a unique ID will be generated.

        Returns:
            Session dictionary with session_id and metadata.
        """
        if session_id is None:
            session_id = str(uuid.uuid4())

        session = {
            "session_id": session_id,
            "created_at": datetime.now(timezone.utc),
            "status": "active",
            "execution_count": 0,
            "artifacts": [],
            "last_seen": datetime.now(timezone.utc),
            "timeout_seconds": 3600,  # Default 1 hour timeout
            "status_history": ["active"],  # Track status transitions
        }

        with self._lock:
            self._sessions[session_id] = session
        logger.info(f"Created session: {session_id}")

        return session

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get an existing session by ID with last_seen update.
        
        Security C2: Thread-safe with proper locking.

        Args:
            session_id: The session identifier.

        Returns:
            Session dictionary if found, None otherwise.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                # Update last_seen timestamp
                session["last_seen"] = datetime.now(timezone.utc)
            return session

    async def cleanup_session(self, session_id: str) -> bool:
        """
        Clean up and remove a session with proper locking and teardown hooks.
        
        Security C2: Thread-safe with proper locking.

        Args:
            session_id: The session identifier to cleanup.

        Returns:
            True if session was cleaned up, False if not found.
        """
        with self._lock:
            if session_id not in self._sessions:
                logger.warning(f"Session not found for cleanup: {session_id}")
                return False

            # Execute teardown hooks before removing session
            session_copy = self._sessions[session_id].copy()

        # Execute teardown hooks outside the lock to avoid deadlocks
        await self._execute_teardown_hooks(session_id)

        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]

            # Clean up teardown hooks for this session
            if session_id in self._teardown_hooks:
                del self._teardown_hooks[session_id]

            logger.info(f"Cleaned up session: {session_id}")
            return True

    async def _execute_teardown_hooks(self, session_id: str) -> None:
        """
        Execute all registered teardown hooks for a session.

        Args:
            session_id: The session identifier.
        """
        hooks = self._teardown_hooks.get(session_id, [])
        for hook in hooks:
            try:
                if asyncio.iscoroutinefunction(hook):
                    await hook(session_id)
                else:
                    hook(session_id)
            except Exception as e:
                logger.error(f"Error executing teardown hook for {session_id}: {e}")

    def register_teardown_hook(self, session_id: str, hook: Callable) -> None:
        """
        Register a teardown hook for a session.

        Args:
            session_id: The session identifier.
            hook: Callable to execute during session cleanup.
        """
        with self._lock:
            if session_id not in self._teardown_hooks:
                self._teardown_hooks[session_id] = []
            self._teardown_hooks[session_id].append(hook)

    def unregister_teardown_hook(self, session_id: str, hook: Callable) -> bool:
        """
        Unregister a teardown hook for a session.

        Args:
            session_id: The session identifier.
            hook: The hook to remove.

        Returns:
            True if hook was found and removed, False otherwise.
        """
        with self._lock:
            if session_id in self._teardown_hooks:
                try:
                    self._teardown_hooks[session_id].remove(hook)
                    return True
                except ValueError:
                    pass
        return False

    async def list_sessions(self) -> List[Dict[str, Any]]:
        """
        List all active sessions.

        Returns:
            List of session dictionaries.
        """
        with self._lock:
            return list(self._sessions.values())

    async def get_active_sessions(self) -> List[Dict[str, Any]]:
        """
        Get all active sessions.
        
        Security C2: Thread-safe with proper locking.

        Returns:
            List of active session dictionaries.
        """
        with self._lock:
            return [s.copy() for s in self._sessions.values() if s.get("status") == "active"]

    async def increment_execution_count(self, session_id: str) -> int:
        """
        Increment the execution count for a session.
        
        Security C2: Thread-safe with proper locking.

        Args:
            session_id: The session identifier.

        Returns:
            New execution count.
        """
        with self._lock:
            if session_id not in self._sessions:
                return 0
            self._sessions[session_id]["execution_count"] += 1
            return self._sessions[session_id]["execution_count"]

    async def add_artifact(
        self, session_id: str, artifact_info: Dict[str, Any]
    ) -> bool:
        """
        Add an artifact to a session.
        
        Security C2: Thread-safe with proper locking.

        Args:
            session_id: The session identifier.
            artifact_info: Artifact information dictionary.

        Returns:
            True if artifact was added, False if session not found.
        """
        with self._lock:
            if session_id not in self._sessions:
                return False

            if "artifacts" not in self._sessions[session_id]:
                self._sessions[session_id]["artifacts"] = []

            self._sessions[session_id]["artifacts"].append(artifact_info)
            return True

    async def cleanup_all_sessions(self) -> int:
        """
        Clean up all sessions.

        Returns:
            Number of sessions cleaned up.
        """
        count = len(self._sessions)
        self._sessions.clear()
        logger.info(f"Cleaned up all {count} sessions")
        return count


# Singleton instance for convenience
_session_service: Optional[SessionService] = None


def get_session_service() -> SessionService:
    """
    Get the global session service instance.

    Returns:
        The singleton SessionService instance.
    """
    global _session_service
    if _session_service is None:
        _session_service = SessionService()
    return _session_service
