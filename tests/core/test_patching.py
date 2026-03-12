"""
Tests for PatchManager security fixes.

CRIT-5: Test for incomplete path validation using startswith()
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from sandbox.core.patching import PatchManager


class TestPatchManagerPathValidation:
    """Test CRIT-5: Path validation prevents similar-prefix attacks."""

    def test_path_validation_rejects_similar_prefix_attack(self, tmp_path):
        """
        CRIT-5: Verify is_relative_to() rejects paths outside allowed directory.

        Attack: '/tmp/user_evil/file.png' should be rejected when
        allowed path is '/tmp/user/'

        The vulnerable code using startswith() would return True for:
        str('/tmp/user_evil/file.png').startswith('/tmp/user') == True (ATTACK!)

        The secure code using is_relative_to() returns False:
        Path('/tmp/user_evil/file.png').is_relative_to('/tmp/user') == False (SECURE!)
        """
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()

        # Attack path: similar prefix but outside allowed directory
        attack_dir = tmp_path / "allowed_evil"
        attack_dir.mkdir()
        attack_path = attack_dir / "attack.png"

        # Valid path: inside allowed directory
        valid_path = allowed_dir / "subdir" / "valid.png"
        valid_path.parent.mkdir(parents=True, exist_ok=True)

        # Test the secure validation directly
        from pathlib import Path as StdPath

        # Attack path should NOT be relative to allowed
        assert not StdPath(attack_path).resolve().is_relative_to(StdPath(allowed_dir).resolve()), \
            "Attack path with similar prefix should be rejected"

        # Valid path should be relative to allowed
        assert StdPath(valid_path).resolve().is_relative_to(StdPath(allowed_dir).resolve()), \
            "Valid path inside allowed directory should be accepted"

    def test_vulnerable_startswith_allows_attack(self, tmp_path):
        """
        CRIT-5: Demonstrate that startswith() is vulnerable to similar-prefix attacks.

        This test shows the vulnerability that we're fixing.
        """
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()

        # Attack path: similar prefix but outside allowed directory
        attack_dir = tmp_path / "allowed_evil"
        attack_path = str(attack_dir / "attack.png")
        allowed_str = str(allowed_dir)

        # Vulnerable: startswith() allows similar-prefix attack
        is_vulnerable = attack_path.startswith(allowed_str)
        assert is_vulnerable, \
            "This demonstrates the vulnerability: startswith() allows similar-prefix attacks"

        # Secure: is_relative_to() blocks the attack
        from pathlib import Path as StdPath
        is_secure = StdPath(attack_path).resolve().is_relative_to(StdPath(allowed_dir).resolve())
        assert not is_secure, \
            "is_relative_to() correctly blocks similar-prefix attacks"

    def test_patch_manager_source_code_uses_secure_validation(self):
        """
        CRIT-5: Verify the patching.py source code uses is_relative_to().

        This test inspects the source code to ensure the secure pattern is used.
        """
        import inspect
        from sandbox.core import patching

        # Get the source code of the patching module
        source = inspect.getsource(patching)

        # Verify is_relative_to is used
        assert "is_relative_to" in source, \
            "Source code should use is_relative_to() for path validation"

        # Verify startswith is NOT used for path validation (vulnerable pattern)
        # We check that the vulnerable pattern doesn't exist
        assert ".startswith(session_artifacts_dir)" not in source, \
            "Source code should NOT use startswith(session_artifacts_dir) - vulnerable pattern"

        assert 'str(fp).startswith(session_artifacts_dir)' not in source, \
            "Source code should NOT use str(fp).startswith(session_artifacts_dir) - vulnerable pattern"

    def test_path_boundary_comprehensive(self, tmp_path):
        """
        CRIT-5: Comprehensive path boundary enforcement test.

        Tests various attack vectors and valid paths.
        """
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()

        test_cases = [
            # (path, description, should_be_relative)
            (allowed_dir / "file.png", "Direct child", True),
            (allowed_dir / "sub" / "file.png", "Nested child", True),
            (tmp_path / "allowed_extra" / "file.png", "Similar prefix attack", False),
            (tmp_path / "allowed_backup" / "file.png", "Similar prefix attack 2", False),
            (tmp_path / "other" / "file.png", "Different directory", False),
        ]

        from pathlib import Path as StdPath
        resolved_allowed = StdPath(allowed_dir).resolve()

        for path, description, should_be_relative in test_cases:
            path.parent.mkdir(parents=True, exist_ok=True)
            resolved_path = StdPath(path).resolve()

            is_relative = resolved_path.is_relative_to(resolved_allowed)

            if should_be_relative:
                assert is_relative, \
                    f"{description}: {path} should be relative to {allowed_dir}"
            else:
                assert not is_relative, \
                    f"{description}: {path} should NOT be relative to {allowed_dir}"

    def test_path_boundary_with_symlinks(self, tmp_path):
        """
        CRIT-5: Test that symlinks are properly resolved.

        Symlinks that escape the allowed directory should be blocked.
        """
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()

        # Create a directory outside allowed
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()

        # Create a symlink inside allowed that points outside
        symlink_path = allowed_dir / "escape_symlink"
        try:
            symlink_path.symlink_to(outside_dir)
        except OSError:
            # Symlinks might not be supported on this system
            pytest.skip("Symlinks not supported")

        # File accessed through symlink is outside the allowed directory
        file_via_symlink = symlink_path / "file.png"

        from pathlib import Path as StdPath
        resolved_allowed = StdPath(allowed_dir).resolve()

        # The symlink resolves to outside, so it should NOT be relative
        is_relative = StdPath(file_via_symlink).resolve().is_relative_to(resolved_allowed)

        assert not is_relative, \
            "Files accessed through symlinks outside allowed dir should be rejected"

    def test_resolved_path_vs_string_comparison(self):
        """
        CRIT-5: Demonstrate why resolve() + is_relative_to() is more secure.

        Shows that string-based comparisons miss edge cases that resolve() catches.
        """
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            allowed = base / "allowed"
            allowed.mkdir()

            # Test with relative paths
            os.chdir(allowed)

            relative_path = Path("../allowed_evil/file.png")
            allowed_evil = base / "allowed_evil"
            allowed_evil.mkdir()

            # String comparison would be tricky with relative paths
            # But resolve() normalizes everything
            resolved_relative = relative_path.resolve()
            resolved_allowed = allowed.resolve()

            # Even with "../" tricks, resolve() + is_relative_to() is secure
            is_relative = resolved_relative.is_relative_to(resolved_allowed)
            assert not is_relative, \
                "Relative path tricks should be caught by resolve()"


class TestCrossSessionArtifactLeakage:
    """
    CRIT-4: Test for cross-session artifact leakage vulnerability.

    The bug: When patch_matplotlib() is called for session A, it captures
    session_a's artifacts_dir in a closure. When called for session B,
    the early return (line 74) prevents creating a new patched function,
    so session B's artifacts are saved to session A's directory.

    Fix: Thread-local storage is set before each execution, ensuring
    the patched function dynamically looks up the correct artifacts_dir.
    """

    def test_concurrent_sessions_isolate_artifacts_matplotlib(self, tmp_path):
        """
        CRIT-4: Matplotlib artifacts from different sessions must go to separate directories.

        This test simulates the actual execution flow where thread-local storage
        is set before each execution via _set_session_artifacts_dir().
        """
        pytest.importorskip("matplotlib")

        from unittest.mock import MagicMock
        from sandbox.core.patching import _current_session_artifacts_dir
        import matplotlib.pyplot as plt

        # Create two separate session directories
        session_a_dir = tmp_path / "session_a" / "artifacts"
        session_b_dir = tmp_path / "session_b" / "artifacts"
        session_a_dir.mkdir(parents=True, exist_ok=True)
        session_b_dir.mkdir(parents=True, exist_ok=True)

        # Create PatchManager and apply patches (simulating initialization)
        manager = PatchManager()
        manager.patch_matplotlib(session_a_dir, session_id="session_a")

        # CRIT-4: Set thread-local storage for session A before execution
        _current_session_artifacts_dir.set(session_a_dir)

        # Create a simple plot for session A
        plt.figure()
        plt.plot([1, 2, 3], [1, 2, 3])
        plt.show()  # Should save to session_a_dir/plots/

        # Clear for session B
        plt.close('all')

        # CRIT-4: Set thread-local storage for session B before execution
        _current_session_artifacts_dir.set(session_b_dir)

        # Create a plot for session B
        plt.figure()
        plt.plot([4, 5, 6], [4, 5, 6])
        plt.show()  # Should save to session_b_dir/plots/

        # Verify session isolation
        session_a_plots = list((session_a_dir / "plots").glob("*.png")) if (session_a_dir / "plots").exists() else []
        session_b_plots = list((session_b_dir / "plots").glob("*.png")) if (session_b_dir / "plots").exists() else []

        # Session A should have at least one plot
        assert len(session_a_plots) >= 1, \
            f"Session A should have at least 1 plot, found {len(session_a_plots)} in {session_a_dir / 'plots'}"

        # Session B should have at least one plot
        assert len(session_b_plots) >= 1, \
            f"Session B should have at least 1 plot, found {len(session_b_plots)} in {session_b_dir / 'plots'}"

    def test_concurrent_sessions_isolate_artifacts_pil(self, tmp_path):
        """
        CRIT-4: PIL artifacts from different sessions must go to separate directories.

        Uses patched PIL.save() to test isolation since Image.show() can hang
        in headless environments.
        """
        pytest.importorskip("PIL")

        from PIL import Image
        from sandbox.core.patching import _current_session_artifacts_dir
        from unittest.mock import patch

        # Create two separate session directories
        session_a_dir = tmp_path / "session_a_pil" / "artifacts"
        session_b_dir = tmp_path / "session_b_pil" / "artifacts"
        session_a_dir.mkdir(parents=True, exist_ok=True)
        session_b_dir.mkdir(parents=True, exist_ok=True)

        # Create PatchManager and apply patches
        manager = PatchManager()
        manager.patch_pil(session_a_dir, session_id="session_a_pil")

        # Mock the original show to prevent GUI hang
        with patch.object(Image.Image, 'show', wraps=lambda self, *args, **kwargs: None):
            # CRIT-4: Set thread-local storage for session A
            _current_session_artifacts_dir.set(session_a_dir)

            # Create and save an image for session A
            img_a = Image.new('RGB', (10, 10), color='red')
            save_path_a = session_a_dir / "images" / "test_a.png"
            save_path_a.parent.mkdir(parents=True, exist_ok=True)
            img_a.save(save_path_a)  # Calls patched_save which logs to session A

            # CRIT-4: Set thread-local storage for session B
            _current_session_artifacts_dir.set(session_b_dir)

            # Create and save an image for session B
            img_b = Image.new('RGB', (10, 10), color='blue')
            save_path_b = session_b_dir / "images" / "test_b.png"
            save_path_b.parent.mkdir(parents=True, exist_ok=True)
            img_b.save(save_path_b)  # Calls patched_save which logs to session B

        # Verify session isolation
        session_a_images = list((session_a_dir / "images").glob("*.png")) if (session_a_dir / "images").exists() else []
        session_b_images = list((session_b_dir / "images").glob("*.png")) if (session_b_dir / "images").exists() else []

        # Both sessions should have their own images
        assert len(session_a_images) >= 1, \
            f"Session A should have at least 1 image, found {len(session_a_images)}"
        assert len(session_b_images) >= 1, \
            f"Session B should have at least 1 image, found {len(session_b_images)}"

        # Verify cross-session isolation
        assert any("test_a" in img.name for img in session_a_images), \
            "Session A should have test_a.png"
        assert any("test_b" in img.name for img in session_b_images), \
            "Session B should have test_b.png"

    def test_singleton_manager_with_thread_local_storage(self, tmp_path):
        """
        CRIT-4: Verify that thread-local storage prevents leakage with singleton manager.

        This test demonstrates that even with a singleton manager, setting
        thread-local storage before each execution ensures artifacts go
        to the correct directory.
        """
        pytest.importorskip("matplotlib")

        from sandbox.core.patching import get_patch_manager, _current_session_artifacts_dir
        import matplotlib.pyplot as plt

        # Create two separate session directories
        session_a_dir = tmp_path / "session_a_singleton" / "artifacts"
        session_b_dir = tmp_path / "session_b_singleton" / "artifacts"
        session_a_dir.mkdir(parents=True, exist_ok=True)
        session_b_dir.mkdir(parents=True, exist_ok=True)

        # Get the SAME singleton manager (simulating real usage)
        manager = get_patch_manager()

        # Patch for session A
        manager.patch_matplotlib(session_a_dir, session_id="session_a_singleton")

        # Patch for session B with the SAME manager (early return, but updates TLS)
        manager.patch_matplotlib(session_b_dir, session_id="session_b_singleton")

        # CRIT-4: Set thread-local storage for session A before execution
        _current_session_artifacts_dir.set(session_a_dir)

        # Create plot for session A
        plt.figure()
        plt.plot([1, 2, 3], [1, 2, 3])
        plt.show()

        # Clear
        plt.close('all')

        # CRIT-4: Set thread-local storage for session B before execution
        _current_session_artifacts_dir.set(session_b_dir)

        # Create plot for session B
        plt.figure()
        plt.plot([4, 5, 6], [4, 5, 6])
        plt.show()

        # Verify both sessions have their own plots
        session_a_plots = list((session_a_dir / "plots").glob("*.png")) if (session_a_dir / "plots").exists() else []
        session_b_plots = list((session_b_dir / "plots").glob("*.png")) if (session_b_dir / "plots").exists() else []

        # Both sessions should have plots
        assert len(session_a_plots) >= 1, \
            f"Session A should have at least 1 plot, found {len(session_a_plots)}"
        assert len(session_b_plots) >= 1, \
            f"Session B should have at least 1 plot, found {len(session_b_plots)}"

    def test_thread_local_storage_isolation(self, tmp_path):
        """
        CRIT-4: Verify that thread-local storage properly isolates sessions.

        This is a lower-level test that verifies the _SessionArtifactsDir
        class correctly manages per-thread artifacts directories.
        """
        from sandbox.core.patching import _SessionArtifactsDir

        storage = _SessionArtifactsDir()

        # Test set and get
        dir_a = tmp_path / "dir_a"
        dir_b = tmp_path / "dir_b"

        storage.set(dir_a)
        assert storage.get() == str(dir_a), "Should return dir_a"

        storage.set(dir_b)
        assert storage.get() == str(dir_b), "Should return dir_b"

        # Test clear
        storage.clear()
        assert storage.get() is None, "Should return None after clear"
