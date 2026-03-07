"""
Tests for HMAC state integrity verification in execution context.

Following Phase 5 quality patterns:
- Type hints with from __future__ import annotations
- Comprehensive error handling
- Tests for both success and tampering detection
"""

from __future__ import annotations

import sqlite3
import tempfile
import shutil
from pathlib import Path

import pytest


class TestHMACStateVerification:
    """Test HMAC verification for execution state integrity."""

    @pytest.fixture
    def temp_session_dir(self) -> Path:
        """Create a temporary session directory for testing."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_hmac_key_generated_on_init(self, temp_session_dir: Path) -> None:
        """Test that HMAC key is generated on first initialization."""
        from sandbox.core.execution_context import PersistentExecutionContext
        
        # Create a mock session
        session_dir = temp_session_dir / "test_session"
        session_dir.mkdir(parents=True)
        
        # Monkey-patch _detect_project_root to use our temp dir
        original_detect = PersistentExecutionContext._detect_project_root
        PersistentExecutionContext._detect_project_root = lambda self: temp_session_dir
        
        try:
            ctx = PersistentExecutionContext()
            assert ctx._state_hmac_key is not None
            assert len(ctx._state_hmac_key) == 32  # 256 bits
        finally:
            PersistentExecutionContext._detect_project_root = original_detect

    def test_hmac_key_persisted_across_instances(self, temp_session_dir: Path) -> None:
        """Test that HMAC key persists across context instances."""
        from sandbox.core.execution_context import PersistentExecutionContext
        
        # Use fixed session_id so both instances use same state file
        session_id = "test_session"
        
        # Monkey-patch for temp dir
        original_detect = PersistentExecutionContext._detect_project_root
        PersistentExecutionContext._detect_project_root = lambda self: temp_session_dir
        
        try:
            # First instance - generates key
            ctx1 = PersistentExecutionContext(session_id=session_id)
            key1 = ctx1._state_hmac_key
            
            # Second instance - should load same key
            ctx2 = PersistentExecutionContext(session_id=session_id)
            key2 = ctx2._state_hmac_key
            
            assert key1 == key2
        finally:
            PersistentExecutionContext._detect_project_root = original_detect

    def test_state_saved_with_hmac(self, temp_session_dir: Path) -> None:
        """Test that state is saved with HMAC."""
        from sandbox.core.execution_context import PersistentExecutionContext
        
        session_id = "test_session"
        original_detect = PersistentExecutionContext._detect_project_root
        PersistentExecutionContext._detect_project_root = lambda self: temp_session_dir
        
        try:
            ctx = PersistentExecutionContext(session_id=session_id)
            
            # Set some state
            ctx.globals_dict['test_var'] = 42
            ctx.save_persistent_state()
            
            # Verify HMAC is stored in database
            with sqlite3.connect(ctx.state_file) as conn:
                cursor = conn.execute(
                    "SELECT key, hmac FROM execution_state WHERE key = 'test_var'"
                )
                row = cursor.fetchone()
                
                assert row is not None
                assert row[0] == 'test_var'
                assert len(row[1]) == 64  # SHA256 hex = 64 chars
        finally:
            PersistentExecutionContext._detect_project_root = original_detect

    def test_hmac_verification_success(self, temp_session_dir: Path) -> None:
        """Test that valid state passes HMAC verification."""
        from sandbox.core.execution_context import PersistentExecutionContext
        
        session_id = "test_session"
        original_detect = PersistentExecutionContext._detect_project_root
        PersistentExecutionContext._detect_project_root = lambda self: temp_session_dir
        
        try:
            # Create and save state
            ctx1 = PersistentExecutionContext(session_id=session_id)
            ctx1.globals_dict['test_data'] = {'key': 'value', 'number': 123}
            ctx1.save_persistent_state()
            
            # Load in new instance - should verify successfully
            ctx2 = PersistentExecutionContext(session_id=session_id)
            
            # State should be loaded
            assert 'test_data' in ctx2.globals_dict
            assert ctx2.globals_dict['test_data'] == {'key': 'value', 'number': 123}
        finally:
            PersistentExecutionContext._detect_project_root = original_detect

    def test_hmac_verification_detects_tampering(self, temp_session_dir: Path) -> None:
        """Test that tampered state is detected and rejected."""
        from sandbox.core.execution_context import PersistentExecutionContext
        
        original_detect = PersistentExecutionContext._detect_project_root
        PersistentExecutionContext._detect_project_root = lambda self: temp_session_dir
        
        try:
            # Create and save state
            ctx1 = PersistentExecutionContext()
            ctx1.globals_dict['sensitive_data'] = 'secret_value'
            ctx1.save_persistent_state()
            
            # Tamper with the database directly
            with sqlite3.connect(ctx1.state_file) as conn:
                # Modify the value without updating HMAC
                conn.execute(
                    "UPDATE execution_state SET value = ? WHERE key = 'sensitive_data'",
                    ('tampered_value',)
                )
            
            # Load in new instance - should detect tampering
            ctx2 = PersistentExecutionContext()
            
            # Tampered data should NOT be loaded
            assert 'sensitive_data' not in ctx2.globals_dict
        finally:
            PersistentExecutionContext._detect_project_root = original_detect

    def test_hmac_verification_pickle_tampering(self, temp_session_dir: Path) -> None:
        """Test that tampered pickle data is detected."""
        from sandbox.core.execution_context import PersistentExecutionContext
        
        original_detect = PersistentExecutionContext._detect_project_root
        PersistentExecutionContext._detect_project_root = lambda self: temp_session_dir
        
        try:
            # Create and save state with complex object (will use pickle)
            ctx1 = PersistentExecutionContext()
            ctx1.globals_dict['complex_obj'] = {'nested': {'data': [1, 2, 3]}}
            ctx1.save_persistent_state()
            
            # Tamper with pickle data
            with sqlite3.connect(ctx1.state_file) as conn:
                conn.execute(
                    "UPDATE execution_state SET value = ? WHERE key = 'complex_obj'",
                    ('dGFtcGVyZWQ=',)  # base64 of 'tampered'
                )
            
            # Load in new instance - should detect tampering
            ctx2 = PersistentExecutionContext()
            
            # Tampered data should NOT be loaded
            assert 'complex_obj' not in ctx2.globals_dict
        finally:
            PersistentExecutionContext._detect_project_root = original_detect

    def test_hmac_verification_type_change_detected(self, temp_session_dir: Path) -> None:
        """Test that changing type (json->pickle) is detected."""
        from sandbox.core.execution_context import PersistentExecutionContext
        
        original_detect = PersistentExecutionContext._detect_project_root
        PersistentExecutionContext._detect_project_root = lambda self: temp_session_dir
        
        try:
            # Create and save state
            ctx1 = PersistentExecutionContext()
            ctx1.globals_dict['data'] = 42  # Simple int, will use JSON
            ctx1.save_persistent_state()
            
            # Tamper by changing type
            with sqlite3.connect(ctx1.state_file) as conn:
                conn.execute(
                    "UPDATE execution_state SET type = 'pickle', value = ? WHERE key = 'data'",
                    ('gASVCAAAAAAAAACMCGJ1aWx0aW5zlIwEZXZhbJSTlIwGJzEnKSBUU4wu',)
                )
            
            # Load in new instance - should detect tampering
            ctx2 = PersistentExecutionContext()
            
            # Tampered data should NOT be loaded
            assert 'data' not in ctx2.globals_dict or ctx2.globals_dict.get('data') == 42
        finally:
            PersistentExecutionContext._detect_project_root = original_detect

    def test_compute_state_hmac_method(self, temp_session_dir: Path) -> None:
        """Test HMAC computation method directly."""
        from sandbox.core.execution_context import PersistentExecutionContext
        
        original_detect = PersistentExecutionContext._detect_project_root
        PersistentExecutionContext._detect_project_root = lambda self: temp_session_dir
        
        try:
            ctx = PersistentExecutionContext()
            
            # Test HMAC computation
            data = b'test data'
            hmac1 = ctx._compute_state_hmac(data)
            hmac2 = ctx._compute_state_hmac(data)
            
            # Same data should produce same HMAC
            assert hmac1 == hmac2
            assert len(hmac1) == 64  # SHA256 hex length
            
            # Different data should produce different HMAC
            hmac3 = ctx._compute_state_hmac(b'different data')
            assert hmac1 != hmac3
        finally:
            PersistentExecutionContext._detect_project_root = original_detect

    def test_verify_state_hmac_method(self, temp_session_dir: Path) -> None:
        """Test HMAC verification method directly."""
        from sandbox.core.execution_context import PersistentExecutionContext
        
        original_detect = PersistentExecutionContext._detect_project_root
        PersistentExecutionContext._detect_project_root = lambda self: temp_session_dir
        
        try:
            ctx = PersistentExecutionContext()
            
            # Test valid HMAC
            data = b'test data'
            valid_hmac = ctx._compute_state_hmac(data)
            assert ctx._verify_state_hmac(data, valid_hmac) is True
            
            # Test invalid HMAC
            invalid_hmac = '0' * 64
            assert ctx._verify_state_hmac(data, invalid_hmac) is False
            
            # Test tampered data
            tampered_data = b'tampered data'
            assert ctx._verify_state_hmac(tampered_data, valid_hmac) is False
        finally:
            PersistentExecutionContext._detect_project_root = original_detect

    def test_migration_adds_hmac_column(self, temp_session_dir: Path) -> None:
        """Test that existing databases are migrated with HMAC column."""
        from sandbox.core.execution_context import PersistentExecutionContext
        
        session_id = "test_session"
        
        # Create a database without HMAC column
        session_dir = temp_session_dir / "sessions" / session_id
        session_dir.mkdir(parents=True)
        state_file = session_dir / "state.db"
        
        with sqlite3.connect(state_file) as conn:
            conn.execute('''
                CREATE TABLE execution_state (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    type TEXT,
                    timestamp REAL
                )
            ''')
            conn.execute(
                "INSERT INTO execution_state VALUES (?, ?, ?, ?)",
                ('test_key', 'test_value', 'json', 1234567890.0)
            )
        
        original_detect = PersistentExecutionContext._detect_project_root
        PersistentExecutionContext._detect_project_root = lambda self: temp_session_dir
        
        try:
            # Initialize context - should migrate schema
            ctx = PersistentExecutionContext(session_id=session_id)
            
            # Verify HMAC column was added
            with sqlite3.connect(state_file) as conn:
                cursor = conn.execute("PRAGMA table_info(execution_state)")
                columns = [row[1] for row in cursor.fetchall()]
                assert 'hmac' in columns
        finally:
            PersistentExecutionContext._detect_project_root = original_detect
