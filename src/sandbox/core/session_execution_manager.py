"""
Session execution context manager for per-session isolation.

This module provides thread-safe management of per-session execution contexts,
ensuring that each session has isolated globals, artifacts, and caches.
"""

from __future__ import annotations

import logging
import shutil
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from .execution_services import ExecutionContext
from .path_validation import PathValidator

logger = logging.getLogger(__name__)


class SessionExecutionContextManager:
    """
    Manages per-session execution contexts with thread-safe access.

    Each session gets its own ExecutionContext with isolated:
    - execution_globals (for variable isolation)
    - artifacts_dir (for file isolation)
    - compilation_cache (for performance isolation)

    NOTE: Process-wide state limitations:
    This is an in-process session isolation implementation. Certain Python
    state is SHARED across all sessions in the same process:
    - sys.path modifications affect all sessions
    - os.environ modifications affect all sessions
    - Imported module caches are shared (import once, available everywhere)
    - Subprocess launches inherit the parent environment

    For full process isolation, consider using:
    - Separate worker processes per session (see RemoteSandbox)
    - Container-based isolation (Docker, microVMs)
    - os.fork() with exec for true process separation
    """
    
    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize the session execution context manager.
        
        Args:
            project_root: Optional project root path for contexts.
        """
        self._contexts: Dict[str, ExecutionContext] = {}
        self._lock = threading.RLock()
        self._project_root = project_root
        
    def get_or_create_context(self, session_id: str) -> ExecutionContext:
        """
        Get or create execution context for a session.
        
        Thread-safe. Creates new context if session doesn't exist.
        
        Args:
            session_id: The session identifier.
            
        Returns:
            ExecutionContext for the session.
        """
        with self._lock:
            if session_id not in self._contexts:
                ctx = ExecutionContext(project_root=self._project_root)
                # Create session-specific artifacts directory
                # CRIT-1: Sanitize session_id to prevent path traversal
                safe_session_id = PathValidator.sanitize_path_component(session_id)
                session_artifacts_dir = ctx.sandbox_area / safe_session_id / "artifacts"
                session_artifacts_dir.mkdir(parents=True, exist_ok=True)
                ctx.artifacts_dir = session_artifacts_dir
                self._contexts[session_id] = ctx
                logger.info(f"Created execution context for session: {session_id}")
            return self._contexts[session_id]
    
    def remove_context(self, session_id: str) -> bool:
        """
        Remove execution context for a session.
        
        Thread-safe. Cleans up artifacts directory.
        
        Args:
            session_id: The session identifier.
            
        Returns:
            True if context was removed, False if not found.
        """
        with self._lock:
            if session_id in self._contexts:
                ctx = self._contexts.pop(session_id)
                ctx.cleanup_artifacts()
                logger.info(f"Removed execution context for session: {session_id}")
                return True
            return False
    
    def get_context(self, session_id: str) -> Optional[ExecutionContext]:
        """
        Get execution context for a session without creating.
        
        Thread-safe.
        
        Args:
            session_id: The session identifier.
            
        Returns:
            ExecutionContext if found, None otherwise.
        """
        with self._lock:
            return self._contexts.get(session_id)
    
    def list_sessions(self) -> list[str]:
        """
        List all session IDs with active contexts.
        
        Thread-safe.
        
        Returns:
            List of session IDs.
        """
        with self._lock:
            return list(self._contexts.keys())
