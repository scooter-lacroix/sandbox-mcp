"""
Session Service for Sandbox MCP Server.

This module handles session management, replacing duplicate logic
from the stdio server.
"""

import uuid
from typing import Dict, Any, Optional, List
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class SessionService:
    """
    Service for managing sandbox sessions.
    
    This service provides unified session creation, retrieval, and cleanup,
    replacing duplicate logic in the stdio server.
    """
    
    def __init__(self):
        """Initialize the session service."""
        self._sessions: Dict[str, Dict[str, Any]] = {}
    
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
            'session_id': session_id,
            'created_at': str(uuid.uuid4()),  # Using uuid as timestamp placeholder
            'status': 'active',
            'execution_count': 0,
            'artifacts': [],
        }
        
        self._sessions[session_id] = session
        logger.info(f"Created session: {session_id}")
        
        return session
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get an existing session by ID.
        
        Args:
            session_id: The session identifier.
        
        Returns:
            Session dictionary if found, None otherwise.
        """
        return self._sessions.get(session_id)
    
    async def cleanup_session(self, session_id: str) -> bool:
        """
        Clean up and remove a session.
        
        Args:
            session_id: The session identifier to cleanup.
        
        Returns:
            True if session was cleaned up, False if not found.
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Cleaned up session: {session_id}")
            return True
        
        logger.warning(f"Session not found for cleanup: {session_id}")
        return False
    
    async def list_sessions(self) -> List[Dict[str, Any]]:
        """
        List all active sessions.
        
        Returns:
            List of session dictionaries.
        """
        return list(self._sessions.values())
    
    async def get_active_sessions(self) -> List[Dict[str, Any]]:
        """
        Get all active sessions.
        
        Returns:
            List of active session dictionaries.
        """
        return [s for s in self._sessions.values() if s.get('status') == 'active']
    
    async def update_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update session metadata.
        
        Args:
            session_id: The session identifier.
            updates: Dictionary of fields to update.
        
        Returns:
            True if session was updated, False if not found.
        """
        if session_id not in self._sessions:
            return False
        
        self._sessions[session_id].update(updates)
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
        
        self._sessions[session_id]['execution_count'] += 1
        return self._sessions[session_id]['execution_count']
    
    async def add_artifact(self, session_id: str, artifact_info: Dict[str, Any]) -> bool:
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
        
        if 'artifacts' not in self._sessions[session_id]:
            self._sessions[session_id]['artifacts'] = []
        
        self._sessions[session_id]['artifacts'].append(artifact_info)
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
