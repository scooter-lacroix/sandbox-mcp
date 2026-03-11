"""
Database transaction management for persistent execution context.

This module provides SQLite database connection pooling and transaction
management with proper resource cleanup. Extracted from execution_context.py
to reduce module size and improve maintainability.

Features:
- Explicit transaction management (BEGIN/COMMIT/ROLLBACK)
- Connection pooling with thread-local storage
- Automatic rollback on exceptions
- Proper resource cleanup in finally blocks
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import ContextManager, List, Any, Tuple

logger = logging.getLogger(__name__)


class DatabaseTransactionManager:
    """
    Manages SQLite database connections and transactions with proper resource cleanup.

    Features:
    - Explicit transaction management (BEGIN/COMMIT/ROLLBACK)
    - Connection pooling with thread-local storage
    - Automatic rollback on exceptions
    - Proper resource cleanup in finally blocks
    """

    def __init__(self, db_path: Path, timeout: float = 30.0) -> None:
        """
        Initialize database transaction manager.

        Args:
            db_path: Path to SQLite database file
            timeout: Connection timeout in seconds
        """
        self.db_path = db_path
        self.timeout = timeout
        self._local = threading.local()
        self._lock = threading.Lock()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                str(self.db_path),
                timeout=self.timeout,
                isolation_level=None  # Autocommit mode, we manage transactions manually
            )
            self._local.conn.execute('PRAGMA journal_mode=WAL')
            self._local.conn.execute('PRAGMA synchronous=NORMAL')
        return self._local.conn

    def _close_connection(self) -> None:
        """Close thread-local database connection."""
        if hasattr(self._local, 'conn') and self._local.conn is not None:
            try:
                self._local.conn.close()
            except Exception as e:
                logger.warning(f"Error closing database connection: {e}")
            self._local.conn = None

    @contextmanager
    def transaction(self) -> ContextManager[sqlite3.Cursor]:
        """
        Context manager for database transactions with automatic rollback on failure.

        Usage:
            with db_manager.transaction() as cursor:
                cursor.execute('INSERT INTO ...')
                cursor.execute('UPDATE ...')
            # Commits automatically on success
            # Rolls back automatically on exception

        Yields:
            sqlite3.Cursor for executing queries within the transaction
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Begin explicit transaction
            cursor.execute('BEGIN IMMEDIATE')
            yield cursor
            # Commit on success
            cursor.execute('COMMIT')
        except Exception as e:
            # Rollback on any exception
            try:
                cursor.execute('ROLLBACK')
            except Exception as rollback_error:
                logger.error(f"Rollback failed: {rollback_error}")
            logger.error(f"Transaction failed, rolled back: {e}")
            raise
        finally:
            # Always clean up cursor
            cursor.close()

    def execute_in_transaction(
        self,
        operations: List[tuple[str, tuple[Any, ...]]]
    ) -> List[Any]:
        """
        Execute multiple operations in a single transaction.

        Args:
            operations: List of (sql, params) tuples to execute atomically

        Returns:
            List of results from each operation

        Raises:
            sqlite3.Error: If any operation fails, entire transaction is rolled back
        """
        results = []

        with self.transaction() as cursor:
            for sql, params in operations:
                cursor.execute(sql, params)
                results.append(cursor.fetchall() if cursor.description else cursor.rowcount)

        return results

    def close_all(self) -> None:
        """Close all database connections (for cleanup)."""
        self._close_connection()
