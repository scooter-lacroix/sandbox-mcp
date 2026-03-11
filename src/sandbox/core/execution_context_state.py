"""
State management module for PersistentExecutionContext.

This module handles all state persistence operations including:
- HMAC computation and verification for state integrity
- Loading and saving persistent state with transaction management
- Execution history tracking and retrieval

Security:
    State serialization uses pickle for complex objects, protected by
    HMAC-SHA256 verification to detect tampering. The HMAC key is
    generated on first initialization and stored in the state database.

Database Transaction Management:
    All database operations use explicit transactions with BEGIN/COMMIT/ROLLBACK
    via the DatabaseTransactionManager for proper resource cleanup.
"""

from __future__ import annotations

import sys
import json
import pickle
import time
import hmac
import hashlib
import secrets
import sqlite3
import base64
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Any as TypingAny

from .execution_context_db import DatabaseTransactionManager

logger = logging.getLogger(__name__)


class StateManager:
    """
    Manages state persistence and integrity verification for execution contexts.

    This class encapsulates all state-related database operations including
    HMAC computation/verification, state loading/saving, and execution history.
    """

    def __init__(
        self,
        state_file: Path,
        db_manager: DatabaseTransactionManager,
        globals_dict: Dict[str, Any]
    ):
        """
        Initialize the StateManager.

        Args:
            state_file: Path to the SQLite state database
            db_manager: DatabaseTransactionManager for transaction handling
            globals_dict: Reference to the globals dictionary to persist
        """
        self.state_file = state_file
        self._db_manager = db_manager
        self._globals_dict = globals_dict
        self._state_hmac_key: Optional[bytes] = None

    def initialize_hmac_key(self, cursor: Optional[sqlite3.Cursor] = None):
        """
        Initialize or load the HMAC key from the database metadata.

        This should be called during database setup to ensure the HMAC key
        is available for state signing/verification operations.

        The key is stored in the _metadata table and generated once per session.

        Args:
            cursor: Optional cursor to use for operations. If not provided,
                   a new transaction will be created. This allows the method
                   to be called within an existing transaction context.
        """
        should_close = False
        if cursor is None:
            # Create a new transaction if no cursor was provided
            context_manager = self._db_manager.transaction()
            cursor = context_manager.__enter__()
            should_close = True
        else:
            context_manager = None

        try:
            # Store/retrieve HMAC key in metadata table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS _metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            ''')

            # Get or generate HMAC key
            cursor.execute(
                "SELECT value FROM _metadata WHERE key = 'hmac_key'"
            )
            row = cursor.fetchone()

            if row is not None:
                # Load existing key
                self._state_hmac_key = base64.b64decode(row[0])
                logger.debug("Loaded existing HMAC key from database")
            else:
                # Generate new key
                self._state_hmac_key = secrets.token_bytes(32)
                cursor.execute(
                    "INSERT INTO _metadata (key, value) VALUES (?, ?)",
                    ('hmac_key', base64.b64encode(self._state_hmac_key).decode())
                )
                logger.debug("Generated new HMAC key for state integrity")
        except Exception as e:
            logger.error(f"Failed to initialize HMAC key: {e}")
            if should_close and context_manager is not None:
                context_manager.__exit__(*sys.exc_info())
            raise
        finally:
            if should_close and context_manager is not None:
                context_manager.__exit__(None, None, None)

    def compute_state_hmac(self, data: bytes) -> str:
        """
        Compute HMAC-SHA256 for state data integrity verification.

        Args:
            data: The serialized state data to sign

        Returns:
            Hexadecimal HMAC-SHA256 digest

        Raises:
            RuntimeError: If HMAC key has not been initialized
        """
        if self._state_hmac_key is None:
            raise RuntimeError("HMAC key not initialized. Call initialize_hmac_key() first.")
        return hmac.new(
            self._state_hmac_key,
            data,
            hashlib.sha256
        ).hexdigest()

    def verify_state_hmac(self, data: bytes, stored_hmac: str) -> bool:
        """
        Verify HMAC for state data to detect tampering.

        Uses constant-time comparison via hmac.compare_digest to prevent
        timing attacks on the HMAC verification.

        Args:
            data: The serialized state data to verify
            stored_hmac: The HMAC digest stored with the state

        Returns:
            True if the HMAC is valid (data integrity verified), False if tampered

        Raises:
            RuntimeError: If HMAC key has not been initialized
        """
        if self._state_hmac_key is None:
            raise RuntimeError("HMAC key not initialized. Call initialize_hmac_key() first.")
        computed_hmac = self.compute_state_hmac(data)
        return hmac.compare_digest(computed_hmac, stored_hmac)

    def load_persistent_state(self) -> None:
        """
        Load persistent execution state from database with HMAC verification.

        This method:
        1. Reads all state entries from the execution_state table
        2. Verifies HMAC for each entry before deserialization
        3. Skips entries with invalid HMAC (possible tampering)
        4. Deserializes and loads valid entries into the globals dictionary

        State entries can be stored as JSON (for simple types) or pickle
        (for complex Python objects). Both formats are HMAC protected.

        Note:
            Loaded values are written directly to the globals_dict reference
            passed during initialization.
        """
        if self._db_manager is None:
            logger.error("Database manager not initialized")
            return

        try:
            with self._db_manager.transaction() as cursor:
                cursor.execute(
                    'SELECT key, value, type, hmac FROM execution_state ORDER BY timestamp DESC'
                )
                rows = cursor.fetchall()

                for key, value_str, type_str, stored_hmac in rows:
                    try:
                        # Decode the value based on type
                        if type_str == 'pickle':
                            data = base64.b64decode(value_str)
                        else:
                            data = value_str.encode('utf-8')

                        # Verify HMAC before deserializing (security check)
                        if not self.verify_state_hmac(data, stored_hmac):
                            logger.error(
                                f"State integrity check failed for {key} - "
                                f"possible tampering detected"
                            )
                            continue

                        # Safe to deserialize after HMAC verification
                        if type_str == 'pickle':
                            value = pickle.loads(data)
                        else:
                            value = json.loads(value_str)

                        self._globals_dict[key] = value
                        logger.debug(f"Loaded state for key: {key}")

                    except Exception as e:
                        logger.warning(f"Failed to load state for {key}: {e}")

        except Exception as e:
            logger.warning(f"Failed to load persistent state: {e}")

    def save_persistent_state(self) -> None:
        """
        Save current execution state to database with HMAC protection.

        This method:
        1. Clears existing state entries
        2. Serializes each global variable (skipping private vars starting with _)
        3. Computes HMAC for each serialized value
        4. Writes all entries atomically in a single transaction

        Serialization strategy:
        - Try JSON first (faster, more secure)
        - Fall back to pickle for complex objects
        - Skip non-serializable objects

        Note:
            The entire operation runs in a single transaction for atomicity.
            Any failure results in automatic rollback via the transaction manager.
        """
        if self._db_manager is None:
            logger.error("Database manager not initialized")
            return

        try:
            # Prepare all operations for atomic execution
            operations = []

            # First operation: clear existing state
            operations.append(('DELETE FROM execution_state', ()))

            # Prepare INSERT operations for each state item
            for key, value in self._globals_dict.items():
                if key.startswith('_'):  # Skip internal variables
                    continue

                try:
                    # Try JSON serialization first
                    value_str = json.dumps(value)
                    type_str = 'json'
                    data_for_hmac = value_str.encode('utf-8')
                except (TypeError, ValueError):
                    # Fall back to pickle for complex objects
                    try:
                        pickled = pickle.dumps(value)
                        value_str = base64.b64encode(pickled).decode()
                        type_str = 'pickle'
                        data_for_hmac = pickled
                    except Exception:
                        continue  # Skip non-serializable objects

                # Compute HMAC for integrity verification
                state_hmac = self.compute_state_hmac(data_for_hmac)

                operations.append((
                    'INSERT OR REPLACE INTO execution_state '
                    '(key, value, type, hmac, timestamp) VALUES (?, ?, ?, ?, ?)',
                    (key, value_str, type_str, state_hmac, time.time())
                ))

            # Execute all operations atomically
            if operations:
                self._db_manager.execute_in_transaction(operations)
                logger.debug(f"Saved {len(operations) - 1} state entries")

        except Exception as e:
            logger.error(f"Failed to save persistent state: {e}")
            # Transaction manager handles rollback automatically

    def store_execution_history(
        self,
        code: str,
        success: bool,
        error: Optional[str],
        execution_time: float,
        artifacts: List[str]
    ) -> None:
        """
        Store execution record in history database.

        Creates an entry in the execution_history table with:
        - The executed code
        - Result (success/error)
        - Execution time
        - Artifacts generated
        - Timestamp

        Args:
            code: The Python code that was executed
            success: Whether execution succeeded
            error: Error message if execution failed
            execution_time: Time taken to execute (seconds)
            artifacts: List of artifact files generated
        """
        try:
            with sqlite3.connect(self.state_file) as conn:
                conn.execute('''
                    INSERT INTO execution_history
                    (code, result, execution_time, memory_usage, artifacts, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    code,
                    json.dumps({'success': success, 'error': error}),
                    execution_time,
                    0,  # Memory usage tracking can be added later
                    json.dumps(artifacts),
                    time.time()
                ))
        except Exception as e:
            logger.error(f"Failed to store execution history: {e}")

    def get_execution_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieve execution history from the database.

        Args:
            limit: Maximum number of history entries to return

        Returns:
            List of execution history entries, each containing:
            - code: The executed code
            - result: Dictionary with success/error status
            - execution_time: Time taken for execution
            - artifacts: List of generated artifacts
            - timestamp: When the execution occurred
        """
        try:
            with sqlite3.connect(self.state_file) as conn:
                cursor = conn.execute('''
                    SELECT code, result, execution_time, artifacts, timestamp
                    FROM execution_history
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (limit,))

                history = []
                for row in cursor:
                    code, result_str, exec_time, artifacts_str, timestamp = row
                    try:
                        result = json.loads(result_str)
                        artifacts = json.loads(artifacts_str) if artifacts_str else []
                    except:
                        continue

                    history.append({
                        'code': code,
                        'result': result,
                        'execution_time': exec_time,
                        'artifacts': artifacts,
                        'timestamp': timestamp
                    })

                return history
        except Exception as e:
            logger.error(f"Failed to get execution history: {e}")
            return []


def create_state_tables(cursor: sqlite3.Cursor) -> None:
    """
    Create database tables for state management.

    This function creates:
    - execution_state: Stores variable state with HMAC protection
    - execution_history: Stores execution records
    - artifacts: Stores artifact metadata

    Args:
        cursor: SQLite cursor to use for table creation
    """
    # Create execution_state table with HMAC column
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS execution_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            type TEXT NOT NULL,
            hmac TEXT NOT NULL,
            timestamp REAL NOT NULL
        )
    ''')

    # Create execution_history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS execution_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT,
            result TEXT,
            execution_time REAL,
            memory_usage INTEGER,
            artifacts TEXT,
            timestamp REAL
        )
    ''')

    # Create artifacts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS artifacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            path TEXT,
            type TEXT,
            size INTEGER,
            metadata TEXT,
            timestamp REAL
        )
    ''')


def migrate_hmac_column(cursor: sqlite3.Cursor) -> None:
    """
    Migrate existing execution_state table to include HMAC column.

    This function attempts to add an HMAC column to existing tables
    that were created before HMAC support was added.

    Args:
        cursor: SQLite cursor to use for migration
    """
    try:
        cursor.execute(
            'ALTER TABLE execution_state ADD COLUMN hmac TEXT NOT NULL DEFAULT ""'
        )
        logger.info("Added HMAC column to execution_state table")
    except sqlite3.OperationalError:
        # Column already exists - this is expected for new installations
        pass
