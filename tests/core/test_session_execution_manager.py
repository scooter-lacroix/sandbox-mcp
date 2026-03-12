"""
Tests for SessionExecutionContextManager with path traversal protection.

CRIT-1: Session ID must be sanitized to prevent path traversal attacks.
TDD: Write failing tests first, then implement fix.
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from sandbox.core.session_execution_manager import SessionExecutionContextManager
from sandbox.core.path_validation import PathValidator


class TestPathValidatorSanitizePathComponent:
    """Test sanitize_path_component static method for CRIT-1 fix."""

    def test_reject_double_dot_path_traversal(self):
        """Path traversal with '..' should be rejected."""
        with pytest.raises(ValueError, match="path traversal"):
            PathValidator.sanitize_path_component("../escape")

    def test_reject_forward_slash(self):
        """Path components containing '/' should be rejected."""
        with pytest.raises(ValueError, match="path separators"):
            PathValidator.sanitize_path_component("session/with/slash")

    def test_reject_backslash(self):
        """Path components containing '\\' should be rejected."""
        with pytest.raises(ValueError, match="path separators"):
            PathValidator.sanitize_path_component("session\\with\\backslash")

    def test_reject_empty_string(self):
        """Empty string should be rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            PathValidator.sanitize_path_component("")

    def test_accept_valid_session_id(self):
        """Valid session IDs should be accepted."""
        assert PathValidator.sanitize_path_component("valid_session") == "valid_session"
        assert PathValidator.sanitize_path_component("session-123") == "session-123"
        assert PathValidator.sanitize_path_component("session_abc") == "session_abc"
        assert PathValidator.sanitize_path_component("Session123") == "Session123"

    def test_accept_session_with_dots_inside(self):
        """Session IDs with dots inside (not leading) are valid."""
        assert PathValidator.sanitize_path_component("session.v1") == "session.v1"
        assert PathValidator.sanitize_path_component("my.session.txt") == "my.session.txt"

    def test_reject_leading_dot(self):
        """Session IDs starting with dot (hidden files) should be rejected."""
        with pytest.raises(ValueError, match="cannot start with"):
            PathValidator.sanitize_path_component(".hidden")

    def test_reject_dot_dot_sequence(self):
        """Session IDs containing '..' anywhere should be rejected."""
        with pytest.raises(ValueError, match="path traversal"):
            PathValidator.sanitize_path_component("session..other")
        with pytest.raises(ValueError, match="path traversal"):
            PathValidator.sanitize_path_component("..test")

    def test_reject_absolute_path_unix(self):
        """Unix absolute paths should be rejected."""
        with pytest.raises(ValueError, match="absolute path"):
            PathValidator.sanitize_path_component("/etc/passwd")

    def test_reject_absolute_path_windows(self):
        """Windows absolute paths should be rejected."""
        with pytest.raises(ValueError, match="absolute path"):
            PathValidator.sanitize_path_component("C:\\Windows\\System32")

    def test_whitespace_only_rejected(self):
        """Whitespace-only strings should be rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            PathValidator.sanitize_path_component("   ")


class TestSessionExecutionContextManagerPathTraversal:
    """Test SessionExecutionContextManager resists path traversal via session_id."""

    def setup_method(self):
        """Create a temporary directory for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def teardown_method(self):
        """Clean up temporary directory."""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_session_id_with_double_dot_is_rejected(self):
        """Session IDs containing '..' should be rejected."""
        mgr = SessionExecutionContextManager(project_root=self.temp_path)

        with pytest.raises(ValueError, match="path traversal"):
            mgr.get_or_create_context("../escape")

        # Verify no context was created for the malicious session
        assert "../escape" not in mgr.list_sessions()

    def test_session_id_with_slash_is_rejected(self):
        """Session IDs containing '/' should be rejected."""
        mgr = SessionExecutionContextManager(project_root=self.temp_path)

        with pytest.raises(ValueError, match="path separators"):
            mgr.get_or_create_context("session/with/slash")

        assert "session/with/slash" not in mgr.list_sessions()

    def test_valid_session_id_works(self):
        """Valid session IDs should work correctly."""
        mgr = SessionExecutionContextManager(project_root=self.temp_path)

        ctx = mgr.get_or_create_context("valid_session_123")

        assert ctx is not None
        assert "valid_session_123" in mgr.list_sessions()
        # Verify artifacts directory is within sandbox_area
        assert ctx.artifacts_dir.is_relative_to(ctx.sandbox_area)

    def test_session_id_with_backslash_is_rejected(self):
        """Session IDs containing backslash should be rejected."""
        mgr = SessionExecutionContextManager(project_root=self.temp_path)

        with pytest.raises(ValueError, match="path separators"):
            mgr.get_or_create_context("session\\backslash")

    def test_cannot_escape_sandbox_area(self):
        """Verify that even with crafted session_id, cannot escape sandbox_area."""
        mgr = SessionExecutionContextManager(project_root=self.temp_path)

        # Try various path traversal attempts
        malicious_ids = [
            "../escape",
            "..",
            "../../etc",
            "session/../../../escape",
            "session\\..\\..\\escape",
        ]

        for bad_id in malicious_ids:
            with pytest.raises(ValueError):
                mgr.get_or_create_context(bad_id)

        # Verify sandbox_area is not escaped
        sessions = mgr.list_sessions()
        assert len(sessions) == 0  # All malicious IDs were rejected

    def test_artifacts_dir_remains_within_sandbox(self):
        """Verify artifacts directory is always within sandbox_area."""
        mgr = SessionExecutionContextManager(project_root=self.temp_path)

        valid_ids = ["session1", "my-session", "test_session_123"]

        for session_id in valid_ids:
            ctx = mgr.get_or_create_context(session_id)
            # Verify artifacts_dir is a subdirectory of sandbox_area
            assert ctx.artifacts_dir.is_relative_to(ctx.sandbox_area)
            # Verify session_id is in the path
            assert session_id in str(ctx.artifacts_dir)
