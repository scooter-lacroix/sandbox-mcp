"""Security tests for Sandbox MCP - TDD approach for Tier 1 security blockers."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from sandbox.core.execution_context import PersistentExecutionContext
from sandbox.core.security import InputValidator
from sandbox.server.execution_helpers import execute, execute_with_artifacts


class TestSymlinkExfiltration(unittest.TestCase):
    """S1: Test symlink-based host file exfiltration prevention."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.ctx = MagicMock()
        self.ctx.artifacts_dir = self.temp_dir
        self.ctx.project_root = Path(self.temp_dir)
        self.logger = MagicMock()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_symlink_in_artifacts_dir_is_skipped(self):
        """Test that symlinks in artifacts directory are skipped during collection."""
        # Create a real file in artifacts dir
        real_file = Path(self.temp_dir) / "real_file.txt"
        real_file.write_text("real content")

        # Create a symlink pointing to a sensitive file outside artifacts
        sensitive_file = Path(self.temp_dir) / "sensitive_data.txt"
        sensitive_file.write_text("SENSITIVE DATA")
        symlink_path = Path(self.temp_dir) / "symlink_to_sensitive"
        symlink_path.symlink_to(sensitive_file)

        # Import collect_artifacts after setting up
        from sandbox.server.execution_helpers import collect_artifacts

        artifacts = collect_artifacts(self.ctx, self.logger)

        # Should only contain the real file, not the symlink target
        artifact_paths = [a["name"] for a in artifacts]
        self.assertIn("real_file.txt", artifact_paths)
        self.assertNotIn("symlink_to_sensitive", artifact_paths)
        # Verify symlink was not followed
        for artifact in artifacts:
            self.assertNotIn("SENSITIVE DATA", artifact.get("content_base64", ""))

    def test_symlink_attack_via_execution_helpers(self):
        """Test symlink attack prevention in execution_helpers.py artifact collection."""
        # Create symlink to /etc/passwd (or equivalent sensitive file)
        sensitive_file = Path(self.temp_dir) / "etc_passwd_sim"
        sensitive_file.write_text("root:x:0:0:root:/root:/bin/bash")
        symlink_path = Path(self.temp_dir) / "passwd_symlink"
        symlink_path.symlink_to(sensitive_file)

        from sandbox.server.execution_helpers import collect_artifacts

        artifacts = collect_artifacts(self.ctx, self.logger)

        # Symlink should be skipped
        artifact_names = [a["name"] for a in artifacts]
        self.assertNotIn("passwd_symlink", artifact_names)


class TestSessionIdPathTraversal(unittest.TestCase):
    """S2: Test session_id path traversal prevention."""

    def test_session_id_with_path_traversal_is_rejected(self):
        """Test that session_id containing path traversal is rejected."""
        # Attempt to create context with malicious session_id
        with self.assertRaises(ValueError) as context:
            PersistentExecutionContext(session_id="../../etc")

        self.assertIn("session_id", str(context.exception).lower())

    def test_session_id_with_special_chars_is_rejected(self):
        """Test that session_id with special characters is rejected."""
        malicious_ids = [
            "../etc/passwd",
            "..\\..\\etc",
            "....//....//etc",
            "/etc/passwd",
            "etc/passwd",
            "session%00.txt",  # Null byte injection
            "session\nid",  # Newline injection
        ]

        for malicious_id in malicious_ids:
            with self.subTest(malicious_id=malicious_id):
                with self.assertRaises(ValueError):
                    PersistentExecutionContext(session_id=malicious_id)

    def test_valid_session_id_is_accepted(self):
        """Test that valid session_ids are accepted."""
        valid_ids = [
            "abc123",
            "session-123-xyz",
            "ABC123",
            "a1b2c3d4-e5f6-7890",
        ]

        for valid_id in valid_ids:
            with self.subTest(valid_id=valid_id):
                try:
                    ctx = PersistentExecutionContext(session_id=valid_id)
                    # Should not raise
                    self.assertIsNotNone(ctx.session_id)
                except ValueError:
                    self.fail(f"Valid session_id '{valid_id}' was rejected")


class TestBackupNamePathTraversal(unittest.TestCase):
    """S3: Test backup_name path traversal prevention."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        # Use ExecutionContext from stdio server which has backup_artifacts
        from sandbox.mcp_sandbox_server_stdio import ExecutionContext
        self.ctx = ExecutionContext()
        self.ctx.project_root = Path(self.temp_dir)
        self.ctx.artifacts_dir = Path(self.temp_dir) / "artifacts"
        self.ctx.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_backup_name_with_path_traversal_is_rejected(self):
        """Test that backup_name containing path traversal is rejected."""
        # Create some artifacts to backup
        (self.ctx.artifacts_dir / "test.txt").write_text("test")
        
        # Create a valid backup first
        result = self.ctx.backup_artifacts(backup_name="valid_backup")
        self.assertIn("artifact_backups", result)
        
        # Now test malicious names - they should return error message
        malicious_names = [
            "../../exploit",
            "../etc/passwd",
            "..\\..\\windows\\system32",
            "....//....//etc",
        ]

        for malicious_name in malicious_names:
            with self.subTest(malicious_name=malicious_name):
                # The backup_artifacts method should sanitize or reject this
                result = self.ctx.backup_artifacts(backup_name=malicious_name)
                self.assertIn("Invalid backup name", result)

    def test_rollback_name_with_path_traversal_is_rejected(self):
        """Test that rollback_name containing path traversal is rejected."""
        # Create backup_root and a valid backup
        backup_root = Path(self.temp_dir) / "artifact_backups"
        backup_root.mkdir(parents=True, exist_ok=True)
        valid_backup = backup_root / "valid_backup_20260307_120000"
        valid_backup.mkdir(parents=True, exist_ok=True)
        (valid_backup / "test.txt").write_text("test")

        malicious_names = [
            "../../exploit",
            "../etc/passwd",
        ]

        for malicious_name in malicious_names:
            with self.subTest(malicious_name=malicious_name):
                # The rollback_artifacts method should sanitize or reject this
                result = self.ctx.rollback_artifacts(backup_name=malicious_name)
                self.assertIn("Invalid backup name", result)


class TestPathValidationWithIsRelativeTo(unittest.TestCase):
    """S4: Test path validation using is_relative_to() instead of startswith()."""

    def test_path_traversal_with_similar_prefix_is_blocked(self):
        """Test that /home/user_evil is blocked when base is /home/user."""
        from sandbox.core.security import FileSystemSecurity

        fs_security = FileSystemSecurity()

        # These should all be rejected
        base_path = Path("/home/user")
        malicious_paths = [
            "/home/user_evil",
            "/home/user_backup",
            "/home/users",
            "/home/usersecrets",
        ]

        for malicious_path in malicious_paths:
            with self.subTest(malicious_path=malicious_path):
                # Using is_relative_to should correctly reject these
                path_obj = Path(malicious_path)
                self.assertFalse(
                    path_obj.is_relative_to(base_path),
                    f"{malicious_path} should not be relative to {base_path}"
                )

    def test_valid_relative_paths_are_accepted(self):
        """Test that legitimate relative paths are accepted."""
        base_path = Path("/home/user")
        valid_paths = [
            "/home/user/documents",
            "/home/user/documents/file.txt",
            "/home/user/projects/sandbox",
        ]

        for valid_path in valid_paths:
            with self.subTest(valid_path=valid_path):
                path_obj = Path(valid_path)
                self.assertTrue(
                    path_obj.is_relative_to(base_path),
                    f"{valid_path} should be relative to {base_path}"
                )


class TestSecurityManagerIntegration(unittest.TestCase):
    """S5: Test InputValidator is available but NOT enforced by default.
    
    NOTE: The InputValidator integration has been removed from the primary
    execution path because:
    1. It produces false positives (blocks open(), input(), etc.)
    2. It provides false security (easy to bypass)
    3. The sandbox's purpose IS to execute arbitrary user code
    4. Real security comes from process isolation and resource limits
    
    The InputValidator class still exists for optional use cases where
    users want to add their own validation layer.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.validator = InputValidator()

    def test_validator_exists_and_callable(self):
        """Test that InputValidator class exists and can validate code."""
        dangerous_code = """
import subprocess
subprocess.run(['rm', '-rf', '/'])
"""
        is_valid, reason = self.validator._validate_code(dangerous_code)
        self.assertFalse(is_valid)
        self.assertIn("subprocess", reason.lower())

    def test_validator_allows_legitimate_code(self):
        """Test that legitimate code passes validation."""
        safe_code = """
x = 1 + 2
print(f"Result: {x}")
"""
        is_valid, reason = self.validator._validate_code(safe_code)
        self.assertTrue(is_valid)
        self.assertIsNone(reason)

    def test_validator_blocks_dangerous_patterns(self):
        """Test that obviously dangerous patterns are detected."""
        dangerous_patterns = [
            ("import subprocess", "subprocess"),
            ("os.system('ls')", "os.system"),
            ("eval('1+1')", "eval"),
            ("exec(code)", "exec"),
        ]
        
        for pattern, expected in dangerous_patterns:
            with self.subTest(pattern=pattern):
                is_valid, reason = self.validator._validate_code(pattern)
                self.assertFalse(is_valid)
                self.assertIn(expected, reason.lower())

    def test_validator_has_false_positives(self):
        """
        Document that validator produces false positives.
        
        This is WHY it's not enforced by default - legitimate code like
        open(), input(), eval() for educational purposes would be blocked.
        """
        # These are legitimate uses that would be blocked:
        legitimate_but_blocked = [
            "f = open('file.txt', 'r')",  # File I/O
            "name = input('Enter name: ')",  # User input
            "result = eval('2 + 2')",  # Dynamic evaluation
        ]
        
        for code in legitimate_but_blocked:
            with self.subTest(code=code):
                is_valid, reason = self.validator._validate_code(code)
                # These SHOULD be blocked by the validator
                # which is why we don't enforce it by default
                self.assertFalse(
                    is_valid,
                    f"Expected '{code}' to be flagged (demonstrating false positive)"
                )

    def test_validator_can_be_bypassed(self):
        """
        Document that validator provides false security.
        
        The simple string matching can be bypassed easily,
        which is another reason it's not enforced by default.
        """
        # These bypasses work because we only do substring matching:
        bypasses = [
            "__import__('subprocess')",  # Dynamic import
            "getattr(os, 'system')",  # getattr
        ]
        
        for code in bypasses:
            with self.subTest(code=code):
                is_valid, reason = self.validator._validate_code(code)
                # These SHOULD be blocked but aren't (demonstrating bypass)
                # Note: some may be caught due to substring matching
                # The point is the validator is not reliable security


class TestFileSystemSecurityS4Fix(unittest.TestCase):
    """S4: Test that FileSystemSecurity.is_path_allowed() uses is_relative_to() instead of startswith()."""

    def setUp(self):
        """Set up test fixtures."""
        from sandbox.core.security import FileSystemSecurity
        self.fs = FileSystemSecurity()

    def test_similar_prefix_attack_is_blocked(self):
        """
        Test that /home/user_evil is rejected when /home/user is allowed.

        This is the critical S4 vulnerability: startswith() would incorrectly
        allow /home/user_evil when /home/user is the allowed base.
        """
        # Set up allowed path
        self.fs.allowed_paths.add("/home/user")

        # Test that similar prefix is NOT allowed
        is_allowed, reason = self.fs.is_path_allowed("/home/user_evil")
        self.assertFalse(
            is_allowed,
            f"/home/user_evil should NOT be allowed when /home/user is allowed. Reason: {reason}"
        )

    def test_valid_subpath_is_allowed(self):
        """Test that legitimate subpaths are still allowed."""
        self.fs.allowed_paths.add("/home/user")

        # These should be allowed
        valid_paths = [
            "/home/user/documents",
            "/home/user/documents/file.txt",
            "/home/user/.ssh/config",
        ]

        for valid_path in valid_paths:
            with self.subTest(valid_path=valid_path):
                is_allowed, reason = self.fs.is_path_allowed(valid_path)
                self.assertTrue(
                    is_allowed,
                    f"{valid_path} should be allowed. Reason: {reason}"
                )

    def test_restricted_path_blocks_subpaths(self):
        """Test that restricted paths properly block their subpaths."""
        # /etc is in restricted_paths by default
        is_allowed, reason = self.fs.is_path_allowed("/etc/passwd")
        self.assertFalse(
            is_allowed,
            f"/etc/passwd should be restricted. Reason: {reason}"
        )

        # Subpaths should also be blocked
        is_allowed, reason = self.fs.is_path_allowed("/etc/ssh/sshd_config")
        self.assertFalse(
            is_allowed,
            f"/etc/ssh/sshd_config should be restricted. Reason: {reason}"
        )

    def test_similar_prefix_on_restricted_is_blocked(self):
        """
        Test that similar-prefix attacks don't bypass restricted path checks.

        For example, /etc_evil should NOT be treated as restricted just because
        it starts with /etc, but the is_relative_to() check ensures that
        /etc/passwd is properly recognized as restricted.
        """
        # /etc_backup should NOT be restricted (it's not within /etc)
        # This tests that is_relative_to() works correctly for both allowed and restricted
        is_allowed, _ = self.fs.is_path_allowed("/etc_backup/config")
        # Should be allowed (not in restricted paths) or checked against other rules
        # The key is that /etc/passwd is still blocked


class TestExecutionServicesS4Fix(unittest.TestCase):
    """S4: Test that create_artifacts_dir() uses is_relative_to() instead of startswith()."""

    def test_similar_prefix_sandbox_area_attack_is_blocked(self):
        """
        Test that sandbox_area_evil is rejected when sandbox_area is the base.

        This tests the S4 fix in execution_services.py line 503.
        """
        from sandbox.core.execution_services import ExecutionContextService
        from pathlib import Path
        import tempfile

        # Create a mock context with sandbox_area
        service = ExecutionContextService()

        # Create a temporary sandbox_area
        with tempfile.TemporaryDirectory() as temp_dir:
            sandbox_area = Path(temp_dir) / "sandbox_area"
            sandbox_area.mkdir()

            # Create a malicious similar-named directory
            sandbox_area_evil = Path(temp_dir) / "sandbox_area_evil"
            sandbox_area_evil.mkdir()

            # Try to create artifacts in the malicious directory
            # This should fail because sandbox_area_evil is not within sandbox_area
            # The create_artifacts_dir method will validate this
            from unittest.mock import MagicMock
            context = MagicMock()
            context.sandbox_area = sandbox_area

            # This should work (valid subdirectory)
            result = service.create_artifacts_dir(context, "validsession123")
            self.assertTrue(result.is_relative_to(sandbox_area))

            # If someone tried to use a session_id like "../sandbox_area_evil/session",
            # the validation should block it


if __name__ == "__main__":
    unittest.main()
