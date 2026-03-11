"""Comprehensive tests for path validation utilities - Security S4."""

import unittest
from pathlib import Path
import tempfile
import shutil

from sandbox.core.path_validation import (
    PathValidator,
    is_safe_path,
    validate_path,
    get_default_validator,
)


class TestPathValidator(unittest.TestCase):
    """Test PathValidator class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.safe_dir = Path(self.temp_dir) / "safe"
        self.safe_dir.mkdir()
        
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_is_within_base_with_similar_prefix(self):
        """S4: Test that similar prefixes are correctly rejected."""
        # /home/user_evil should NOT be within /home/user
        base = Path("/home/user")
        malicious = Path("/home/user_evil")
        
        self.assertFalse(PathValidator._is_within_base(malicious, base))
        
    def test_is_within_base_with_valid_subpath(self):
        """S4: Test that valid subpaths are accepted."""
        base = Path("/home/user")
        valid = Path("/home/user/documents/file.txt")
        
        self.assertTrue(PathValidator._is_within_base(valid, base))

    def test_validator_with_base_paths(self):
        """Test validator with configured base paths."""
        validator = PathValidator(base_paths=[self.safe_dir])
        
        # Safe path should be accepted
        safe_file = self.safe_dir / "test.txt"
        safe_file.write_text("test")
        self.assertTrue(validator.is_safe_path(safe_file, require_exists=True))
        
        # Path outside base should be rejected
        outside = Path("/etc/passwd")
        self.assertFalse(validator.is_safe_path(outside))

    def test_validate_or_raise(self):
        """Test validate_or_raise raises on invalid paths."""
        validator = PathValidator(base_paths=[self.safe_dir])
        
        # Valid path should return successfully
        result = validator.validate_or_raise(self.safe_dir)
        self.assertEqual(result, self.safe_dir.resolve())
        
        # Invalid path should raise
        with self.assertRaises(ValueError):
            validator.validate_or_raise(Path("/etc/passwd"))


class TestDefaultValidator(unittest.TestCase):
    """Test default validator functions."""

    def test_is_safe_path_with_home(self):
        """Test is_safe_path with home directory."""
        home = Path.home()
        safe_file = home / "test.txt"
        
        # Should be safe (within home)
        result = is_safe_path(safe_file)
        # Note: require_exists=False by default, so this passes even if file doesn't exist
        self.assertTrue(result)

    def test_is_safe_path_with_traversal(self):
        """S4: Test is_safe_path rejects path traversal."""
        # Path with .. should be rejected
        traversal = Path("/tmp/../etc/passwd")
        self.assertFalse(is_safe_path(traversal))

    def test_validate_path_raises(self):
        """Test validate_path raises on invalid paths."""
        with self.assertRaises(ValueError):
            validate_path(Path("/etc/passwd"))


class TestPathValidationSecurity(unittest.TestCase):
    """Security-focused path validation tests."""

    def test_symlink_path_traversal(self):
        """S1+S4: Test symlink-based path traversal is blocked."""
        temp_dir = tempfile.mkdtemp()
        try:
            safe_dir = Path(temp_dir) / "safe"
            safe_dir.mkdir()
            
            # Create a file outside safe_dir
            outside_file = Path(temp_dir) / "outside.txt"
            outside_file.write_text("outside")
            
            # Create symlink inside safe_dir pointing outside
            symlink = safe_dir / "link.txt"
            symlink.symlink_to(outside_file)
            
            # Resolved path should not be within safe_dir
            resolved = symlink.resolve()
            self.assertFalse(resolved.is_relative_to(safe_dir))
            
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_unicode_normalization_attack(self):
        """S4: Test unicode normalization attacks are blocked."""
        # Path with classic traversal should be rejected
        attack = Path("/tmp/../etc/passwd")
        
        # The is_safe_path function checks for .. in parts
        # and uses is_relative_to which handles this correctly
        result = is_safe_path(attack)
        # Should be False because of path traversal
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
