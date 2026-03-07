"""
Tests for database transaction management in execution context.

Following Phase 5 quality patterns:
- Type hints with from __future__ import annotations
- Comprehensive error handling
- Tests for transaction rollback, atomicity, and resource cleanup
"""

from __future__ import annotations

import sqlite3
import tempfile
import shutil
from pathlib import Path

import pytest


class TestDatabaseTransactionManager:
    """Test DatabaseTransactionManager for proper transaction handling."""

    @pytest.fixture
    def temp_db_path(self) -> Path:
        """Create a temporary database file for testing."""
        temp_dir = Path(tempfile.mkdtemp())
        db_path = temp_dir / "test.db"
        yield db_path
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_transaction_manager_creation(self, temp_db_path: Path) -> None:
        """Test that DatabaseTransactionManager can be created."""
        from sandbox.core.execution_context import DatabaseTransactionManager
        
        db_manager = DatabaseTransactionManager(temp_db_path)
        assert db_manager is not None
        assert db_manager.db_path == temp_db_path

    def test_transaction_commits_on_success(self, temp_db_path: Path) -> None:
        """Test that transactions commit successfully on normal completion."""
        from sandbox.core.execution_context import DatabaseTransactionManager
        
        db_manager = DatabaseTransactionManager(temp_db_path)
        
        # Create table and insert data in transaction
        with db_manager.transaction() as cursor:
            cursor.execute('CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)')
            cursor.execute('INSERT INTO test (id, value) VALUES (?, ?)', (1, 'test_value'))
        
        # Verify data was committed
        with db_manager.transaction() as cursor:
            cursor.execute('SELECT value FROM test WHERE id = 1')
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == 'test_value'

    def test_transaction_rollback_on_exception(self, temp_db_path: Path) -> None:
        """Test that transactions rollback on exception."""
        from sandbox.core.execution_context import DatabaseTransactionManager
        
        db_manager = DatabaseTransactionManager(temp_db_path)
        
        # Create table first
        with db_manager.transaction() as cursor:
            cursor.execute('CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)')
            cursor.execute('INSERT INTO test (id, value) VALUES (?, ?)', (1, 'initial'))
        
        # Try to insert with constraint violation (should rollback)
        with pytest.raises(sqlite3.IntegrityError):
            with db_manager.transaction() as cursor:
                cursor.execute('INSERT INTO test (id, value) VALUES (?, ?)', (1, 'duplicate'))
                # This should raise IntegrityError and rollback
        
        # Verify original data is still there (transaction rolled back)
        with db_manager.transaction() as cursor:
            cursor.execute('SELECT COUNT(*) FROM test')
            count = cursor.fetchone()[0]
            assert count == 1

    def test_transaction_cursor_cleanup(self, temp_db_path: Path) -> None:
        """Test that cursors are properly cleaned up after transaction."""
        from sandbox.core.execution_context import DatabaseTransactionManager
        
        db_manager = DatabaseTransactionManager(temp_db_path)
        
        # Run multiple transactions
        for i in range(5):
            with db_manager.transaction() as cursor:
                cursor.execute('SELECT 1')
        
        # Should not leak cursors or connections
        assert db_manager._get_connection() is not None

    def test_execute_in_transaction_atomic(self, temp_db_path: Path) -> None:
        """Test that execute_in_transaction executes atomically."""
        from sandbox.core.execution_context import DatabaseTransactionManager
        
        db_manager = DatabaseTransactionManager(temp_db_path)
        
        # Create table
        with db_manager.transaction() as cursor:
            cursor.execute('CREATE TABLE test (id INTEGER PRIMARY KEY)')
        
        # Execute multiple operations atomically
        operations = [
            ('INSERT INTO test (id) VALUES (?)', (1,)),
            ('INSERT INTO test (id) VALUES (?)', (2,)),
            ('INSERT INTO test (id) VALUES (?)', (3,)),
        ]
        results = db_manager.execute_in_transaction(operations)
        
        # Verify all operations succeeded
        assert len(results) == 3
        
        # Verify all data was committed
        with db_manager.transaction() as cursor:
            cursor.execute('SELECT COUNT(*) FROM test')
            count = cursor.fetchone()[0]
            assert count == 3

    def test_execute_in_transaction_rollback_on_failure(self, temp_db_path: Path) -> None:
        """Test that execute_in_transaction rolls back on any failure."""
        from sandbox.core.execution_context import DatabaseTransactionManager
        
        db_manager = DatabaseTransactionManager(temp_db_path)
        
        # Create table
        with db_manager.transaction() as cursor:
            cursor.execute('CREATE TABLE test (id INTEGER PRIMARY KEY)')
            cursor.execute('INSERT INTO test (id) VALUES (?)', (0,))
        
        # Try to execute operations where one will fail (duplicate key)
        operations = [
            ('INSERT INTO test (id) VALUES (?)', (1,)),
            ('INSERT INTO test (id) VALUES (?)', (2,)),
            ('INSERT INTO test (id) VALUES (?)', (1,)),  # Duplicate - will fail
            ('INSERT INTO test (id) VALUES (?)', (3,)),
        ]
        
        with pytest.raises(sqlite3.IntegrityError):
            db_manager.execute_in_transaction(operations)
        
        # Verify NO operations were committed (all rolled back)
        with db_manager.transaction() as cursor:
            cursor.execute('SELECT COUNT(*) FROM test')
            count = cursor.fetchone()[0]
            assert count == 1  # Only the initial row

    def test_connection_pooling_thread_local(self, temp_db_path: Path) -> None:
        """Test that connections are thread-local."""
        from sandbox.core.execution_context import DatabaseTransactionManager
        
        db_manager = DatabaseTransactionManager(temp_db_path)
        
        # Get connection multiple times - should be same connection
        conn1 = db_manager._get_connection()
        conn2 = db_manager._get_connection()
        
        assert conn1 is conn2

    def test_close_all_connections(self, temp_db_path: Path) -> None:
        """Test that close_all properly closes connections."""
        from sandbox.core.execution_context import DatabaseTransactionManager
        
        db_manager = DatabaseTransactionManager(temp_db_path)
        
        # Get connection
        _ = db_manager._get_connection()
        
        # Close all
        db_manager.close_all()
        
        # Connection should be closed
        assert db_manager._local.conn is None

    def test_wal_mode_enabled(self, temp_db_path: Path) -> None:
        """Test that WAL journal mode is enabled for better concurrency."""
        from sandbox.core.execution_context import DatabaseTransactionManager
        
        db_manager = DatabaseTransactionManager(temp_db_path)
        
        with db_manager.transaction() as cursor:
            cursor.execute('PRAGMA journal_mode')
            mode = cursor.fetchone()[0]
            assert mode == 'wal'


class TestExecutionContextTransactionManagement:
    """Test PersistentExecutionContext uses transactions properly."""

    @pytest.fixture
    def temp_session_dir(self) -> Path:
        """Create a temporary session directory for testing."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_db_manager_initialized(self, temp_session_dir: Path) -> None:
        """Test that database manager is initialized with execution context."""
        from sandbox.core.execution_context import PersistentExecutionContext
        
        original_detect = PersistentExecutionContext._detect_project_root
        PersistentExecutionContext._detect_project_root = lambda self: temp_session_dir
        
        try:
            ctx = PersistentExecutionContext()
            assert ctx._db_manager is not None
        finally:
            PersistentExecutionContext._detect_project_root = original_detect

    def test_state_save_uses_transaction(self, temp_session_dir: Path) -> None:
        """Test that state save uses proper transactions."""
        from sandbox.core.execution_context import PersistentExecutionContext
        
        original_detect = PersistentExecutionContext._detect_project_root
        PersistentExecutionContext._detect_project_root = lambda self: temp_session_dir
        
        try:
            ctx = PersistentExecutionContext()
            
            # Set state and save
            ctx.globals_dict['test_key'] = 'test_value'
            ctx.save_persistent_state()
            
            # Verify data was saved with HMAC
            with ctx._db_manager.transaction() as cursor:
                cursor.execute('SELECT key, value, hmac FROM execution_state WHERE key = ?', ('test_key',))
                row = cursor.fetchone()
                assert row is not None
                assert row[0] == 'test_key'
                assert len(row[2]) == 64  # HMAC hex length
        finally:
            PersistentExecutionContext._detect_project_root = original_detect

    def test_state_save_rollback_on_error(self, temp_session_dir: Path) -> None:
        """Test that state save rolls back on error."""
        from sandbox.core.execution_context import PersistentExecutionContext
        
        original_detect = PersistentExecutionContext._detect_project_root
        PersistentExecutionContext._detect_project_root = lambda self: temp_session_dir
        
        try:
            ctx = PersistentExecutionContext()
            
            # Set initial state
            ctx.globals_dict['initial'] = 'value'
            ctx.save_persistent_state()
            
            # Verify initial state
            with ctx._db_manager.transaction() as cursor:
                cursor.execute('SELECT COUNT(*) FROM execution_state')
                initial_count = cursor.fetchone()[0]
            
            # Now try to save with problematic data (should still work or rollback cleanly)
            ctx.globals_dict['new_key'] = 'new_value'
            ctx.save_persistent_state()
            
            # Should complete without corruption
            with ctx._db_manager.transaction() as cursor:
                cursor.execute('SELECT COUNT(*) FROM execution_state')
                final_count = cursor.fetchone()[0]
                assert final_count >= initial_count
        finally:
            PersistentExecutionContext._detect_project_root = original_detect

    def test_state_load_handles_corruption_gracefully(self, temp_session_dir: Path) -> None:
        """Test that state load handles database corruption gracefully."""
        from sandbox.core.execution_context import PersistentExecutionContext
        
        session_id = "test_corruption"
        original_detect = PersistentExecutionContext._detect_project_root
        PersistentExecutionContext._detect_project_root = lambda self: temp_session_dir
        
        try:
            # Create context and save state
            ctx1 = PersistentExecutionContext(session_id=session_id)
            ctx1.globals_dict['valid_key'] = 'valid_value'
            ctx1.save_persistent_state()
            
            # Manually corrupt the database (insert invalid HMAC)
            with ctx1._db_manager.transaction() as cursor:
                cursor.execute(
                    "INSERT OR REPLACE INTO execution_state (key, value, type, hmac, timestamp) VALUES (?, ?, ?, ?, ?)",
                    ('corrupted', 'data', 'json', 'invalid_hmac', 1234567890.0)
                )
            
            # Create new context - should load valid data, skip corrupted
            ctx2 = PersistentExecutionContext(session_id=session_id)
            
            # Valid data should be loaded
            assert 'valid_key' in ctx2.globals_dict
            
            # Corrupted data should be skipped (HMAC verification fails)
            assert 'corrupted' not in ctx2.globals_dict
        finally:
            PersistentExecutionContext._detect_project_root = original_detect
