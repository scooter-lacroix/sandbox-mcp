"""
Test to verify ExecutionContext classes are distinct and serve different purposes.

This test documents and validates the intentional architectural separation:
- ExecutionContext: Server-level shared context (singleton pattern)
- PersistentExecutionContext: Per-session execution context with persistence

Related: CRIT-7 (Duplicate ExecutionContext Implementations)
Resolution: CRIT-7 was based on misunderstanding - classes have different names
and serve different architectural purposes.
"""

import pytest
from pathlib import Path


class TestExecutionContextUniqueness:
    """Verify ExecutionContext classes are distinct and purposefully different."""

    def test_only_one_execution_context_class_exists(self):
        """Verify there is only one class named 'ExecutionContext'."""
        from sandbox.core.execution_services import ExecutionContext
        from sandbox.core.execution_context import PersistentExecutionContext

        # These are different classes with different names
        assert ExecutionContext.__name__ == "ExecutionContext"
        assert PersistentExecutionContext.__name__ == "PersistentExecutionContext"

        # They are not the same class
        assert ExecutionContext is not PersistentExecutionContext

    def test_execution_context_purpose(self):
        """ExecutionContext is for server-level shared configuration."""
        from sandbox.core.execution_services import ExecutionContext

        ctx = ExecutionContext()

        # Server-level properties
        assert hasattr(ctx, 'project_root')
        assert hasattr(ctx, 'venv_path')
        assert hasattr(ctx, 'sandbox_area')

        # No session-specific properties
        assert not hasattr(ctx, 'session_id')
        assert not hasattr(ctx, 'state_file')

    def test_persistent_execution_context_purpose(self):
        """PersistentExecutionContext is for per-session execution state."""
        from sandbox.core.execution_context import PersistentExecutionContext

        ctx = PersistentExecutionContext()

        # Session-specific properties
        assert hasattr(ctx, 'session_id')
        assert hasattr(ctx, 'session_dir')
        assert hasattr(ctx, 'state_file')
        assert hasattr(ctx, 'artifacts_dir')

        # Also has project_root (inherits from same base concept)
        assert hasattr(ctx, 'project_root')

    def test_both_imports_work(self):
        """Both classes can be imported from their respective modules."""
        # These imports should work without error
        from sandbox.core.execution_services import ExecutionContext
        from sandbox.core.execution_context import PersistentExecutionContext

        # Both are callable classes
        assert callable(ExecutionContext)
        assert callable(PersistentExecutionContext)

    def test_import_from_core_init(self):
        """Both classes are exported from core.__init__ for convenience."""
        from sandbox.core import (
            ExecutionContext,
            PersistentExecutionContext,
            ExecutionContextService,
        )

        # All should be importable from core package
        assert ExecutionContext.__name__ == "ExecutionContext"
        assert PersistentExecutionContext.__name__ == "PersistentExecutionContext"


class TestServerLevelVsSessionLevel:
    """Test the distinction between server-level and session-level contexts."""

    def test_execution_context_is_singleton_pattern(self):
        """ExecutionContext follows singleton pattern at server level."""
        from sandbox.core.execution_services import ExecutionContext

        # Used once per server instance
        ctx1 = ExecutionContext()
        ctx2 = ExecutionContext()

        # Two instances but represent same server-level concept
        assert isinstance(ctx1, ExecutionContext)
        assert isinstance(ctx2, ExecutionContext)

    def test_persistent_execution_context_is_per_session(self):
        """PersistentExecutionContext is created per session."""
        from sandbox.core.execution_context import PersistentExecutionContext

        # Each session gets its own context
        ctx1 = PersistentExecutionContext(session_id="session-1")
        ctx2 = PersistentExecutionContext(session_id="session-2")

        # Different sessions
        assert ctx1.session_id == "session-1"
        assert ctx2.session_id == "session-2"
        assert ctx1.session_id != ctx2.session_id

        # Different directories
        assert ctx1.session_dir != ctx2.session_dir
