"""
Session Service for Sandbox MCP Server.

This module handles session management, replacing duplicate logic
from the stdio server.
"""

import uuid
import threading
import time
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path
import logging
import time

logger = logging.getLogger(__name__)


class SessionService:
    """
    Service for managing sandbox sessions.

    This service provides unified session creation, retrieval, and cleanup,
    replacing duplicate logic in the stdio server.
    """

    def __init__(self):
        """Initialize the session service with thread safety."""
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._cleanup_thread = None
        self._running = False
        self._teardown_hooks: Dict[str, List[Callable]] = {}

        # Start background cleanup thread
        self._start_cleanup_thread()

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
        """Check for and cleanup expired sessions."""
        now = datetime.now(timezone.utc)
        expired_sessions = []

        with self._lock:
            for session_id, session in self._sessions.items():
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

                # Remove expired sessions
        for session_id in expired_sessions:
            try:
                asyncio.run(self.cleanup_session(session_id))
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

        self._sessions[session_id] = session
        logger.info(f"Created session: {session_id}")

        return session

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get an existing session by ID with last_seen update.

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
            await self._execute_teardown_hooks(session_id)

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

        Returns:
            List of active session dictionaries.
        """
        return [s for s in self._sessions.values() if s.get("status") == "active"]

    async def update_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update session metadata with validation.

        Args:
            session_id: The session identifier.
            updates: Dictionary of fields to update.

        Returns:
            True if session was updated, False if not found.
        """
        if session_id not in self._sessions:
            return False

        with self._lock:
            session = self._sessions[session_id]

            # Validate updates
            valid_updates = {}
            for key, value in updates.items():
                if key == "status":
                    # Validate status transition
                    if value not in ["active", "inactive", "expired"]:
                        logger.warning(f"Invalid status update: {value}")
                        continue
                    # Track status history
                    if "status_history" not in session:
                        session["status_history"] = []
                    session["status_history"].append(value)
                elif key == "timeout_seconds":
                    # Validate timeout is positive integer
                    if not isinstance(value, int) or value <= 0:
                        logger.warning(f"Invalid timeout value: {value}")
                        continue
                elif key == "created_at" or key == "last_seen":
                    # Validate datetime objects
                    if not isinstance(value, datetime):
                        logger.warning(f"Invalid datetime for {key}")
                        continue

                valid_updates[key] = value

            # Apply valid updates
            session.update(valid_updates)

            # Update last_seen if any changes were made
            if valid_updates:
                session["last_seen"] = datetime.now(timezone.utc)

        return True

    async def increment_execution_count(self, session_id: str) -> int:
        """
        Increment the execution count for a session.

        Args:
            session_id: The session identifier.

        Returns:
            New execution count.
        """
        if session_id not in self._sessions:
            return 0

        self._sessions[session_id]["execution_count"] += 1
        return self._sessions[session_id]["execution_count"]

    async def add_artifact(
        self, session_id: str, artifact_info: Dict[str, Any]
    ) -> bool:
        """
        Add an artifact to a session.

        Args:
            session_id: The session identifier.
            artifact_info: Artifact information dictionary.

        Returns:
            True if artifact was added, False if session not found.
        """
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
