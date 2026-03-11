"""
Comprehensive tests for artifact_helpers.py security-critical paths.

Priority Coverage Areas:
- List artifacts with various states (empty, categorized, missing fields)
- Cache clearing (full and important_only modes)
- Artifact cleanup with web servers
- Temp artifact cleanup with age thresholds
- Artifact report and categorization
- Cleanup by artifact type with error handling
- Backup operations (create, list, rollback, details)
- Old backup cleanup with sorting

Google Python Style Guide compliance.
"""

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch, call

from sandbox.server.artifact_helpers import (
    backup_current_artifacts,
    categorize_artifacts,
    cleanup_artifacts,
    cleanup_artifacts_by_type,
    cleanup_old_backups,
    cleanup_temp_artifacts,
    clear_cache,
    get_artifact_report,
    get_backup_details,
    list_artifact_backups,
    list_artifacts,
    rollback_to_backup,
)


class TestListArtifacts(unittest.TestCase):
    """Test list_artifacts function with various states."""

    def test_list_artifacts_empty_collection(self):
        """Test listing when no artifacts exist."""
        collect_mock = Mock(return_value=[])
        result = list_artifacts(collect_mock)
        self.assertEqual(result, "No artifacts found.")

    def test_list_artifacts_with_single_artifact(self):
        """Test listing a single artifact."""
        collect_mock = Mock(
            return_value=[
                {
                    "name": "plot.png",
                    "size": 2048,
                    "type": "image",
                    "category": "plots",
                    "relative_path": "plots/plot.png",
                }
            ]
        )
        result = list_artifacts(collect_mock)
        self.assertIn("plot.png", result)
        self.assertIn("2.0 KB", result)
        self.assertIn("PLOTS:", result)
        self.assertIn("Total: 1 artifacts", result)

    def test_list_artifacts_with_multiple_categories(self):
        """Test listing artifacts grouped by category."""
        collect_mock = Mock(
            return_value=[
                {
                    "name": "plot1.png",
                    "size": 1024,
                    "type": "image",
                    "category": "plots",
                    "relative_path": "plots/plot1.png",
                },
                {
                    "name": "data.csv",
                    "size": 5120,
                    "type": "data",
                    "category": "data",
                    "relative_path": "data/data.csv",
                },
            ]
        )
        result = list_artifacts(collect_mock)
        self.assertIn("PLOTS:", result)
        self.assertIn("DATA:", result)
        self.assertIn("Total: 2 artifacts", result)

    def test_list_artifacts_fallback_to_path(self):
        """Test listing artifact without relative_path."""
        collect_mock = Mock(
            return_value=[
                {
                    "name": "artifact.txt",
                    "size": 1024,
                    "type": "text",
                    "category": "root",
                    "path": "/tmp/artifact.txt",
                }
            ]
        )
        result = list_artifacts(collect_mock)
        self.assertIn("/tmp/artifact.txt", result)

    def test_list_artifacts_missing_optional_fields(self):
        """Test listing artifact with missing optional fields."""
        collect_mock = Mock(return_value=[{"category": "misc"}])
        result = list_artifacts(collect_mock)
        self.assertIn("unknown", result)  # name defaults to unknown
        self.assertIn("MISC:", result)

    def test_list_artifacts_without_category(self):
        """Test listing artifact without category defaults to root."""
        collect_mock = Mock(return_value=[{"name": "test.bin"}])
        result = list_artifacts(collect_mock)
        self.assertIn("ROOT:", result)


class TestClearCache(unittest.TestCase):
    """Test clear_cache function with different modes."""

    def setUp(self):
        """Set up test fixtures."""
        self.ctx = MagicMock()
        self.ctx.compilation_cache = {
            "import math": b"code1",
            "def foo": b"code2",
            "class Bar": b"code3",
            "temp_var": b"code4",
        }
        self.ctx.cache_hits = 10
        self.ctx.cache_misses = 5

    def test_clear_cache_full_clear(self):
        """Test full cache clear when important_only is False."""
        result = clear_cache(self.ctx, important_only=False)
        self.assertEqual(len(self.ctx.compilation_cache), 0)
        self.assertEqual(self.ctx.cache_hits, 0)
        self.assertEqual(self.ctx.cache_misses, 0)
        self.assertEqual(result, "Cache cleared successfully.")

    def test_clear_cache_preserve_important(self):
        """Test cache clear preserving import/def/class entries."""
        result = clear_cache(self.ctx, important_only=True)
        self.assertIn("import math", self.ctx.compilation_cache)
        self.assertIn("def foo", self.ctx.compilation_cache)
        self.assertIn("class Bar", self.ctx.compilation_cache)
        self.assertNotIn("temp_var", self.ctx.compilation_cache)
        self.assertEqual(len(self.ctx.compilation_cache), 3)

    def test_clear_cache_empty_cache(self):
        """Test clearing an already empty cache."""
        self.ctx.compilation_cache = {}
        result = clear_cache(self.ctx, important_only=False)
        self.assertEqual(result, "Cache cleared successfully.")

    def test_clear_cache_partial_match_preservation(self):
        """Test that substring matching preserves entries (e.g., 'import' in 'myimport')."""
        self.ctx.compilation_cache = {
            "import_module_x": b"code1",
            "myimport": b"code2",  # 'import' is a substring, so preserved
            "def_function_y": b"code3",
            "myclass": b"code4",  # 'class' is a substring, so preserved
            "temp_var": b"code5",  # Not preserved
        }
        clear_cache(self.ctx, important_only=True)
        # All entries containing "import", "def", or "class" as substrings remain
        self.assertIn("import_module_x", self.ctx.compilation_cache)
        self.assertIn("myimport", self.ctx.compilation_cache)
        self.assertIn("def_function_y", self.ctx.compilation_cache)
        self.assertIn("myclass", self.ctx.compilation_cache)
        self.assertNotIn("temp_var", self.ctx.compilation_cache)
        self.assertEqual(len(self.ctx.compilation_cache), 4)


class TestCleanupArtifacts(unittest.TestCase):
    """Test cleanup_artifacts function."""

    def setUp(self):
        """Set up test fixtures."""
        self.ctx = MagicMock()
        self.process = MagicMock()
        self.ctx.web_servers = {"server1": self.process}

    def test_cleanup_artifacts_calls_cleanup(self):
        """Test that cleanup_artifacts calls context cleanup."""
        result = cleanup_artifacts(self.ctx)
        self.ctx.cleanup_artifacts.assert_called_once()
        self.assertIn("cleaned up", result.lower())

    def test_cleanup_artifacts_terminates_web_servers(self):
        """Test that cleanup terminates web servers."""
        result = cleanup_artifacts(self.ctx)
        self.process.terminate.assert_called_once()
        self.assertEqual(len(self.ctx.web_servers), 0)

    def test_cleanup_artifacts_handles_terminate_exception(self):
        """Test graceful handling of terminate exceptions."""
        self.process.terminate.side_effect = RuntimeError("Process dead")
        result = cleanup_artifacts(self.ctx)
        # Should not raise, should clear web_servers
        self.assertEqual(len(self.ctx.web_servers), 0)
        self.assertIn("cleaned up", result.lower())

    def test_cleanup_artifacts_empty_web_servers(self):
        """Test cleanup with no web servers."""
        self.ctx.web_servers = {}
        result = cleanup_artifacts(self.ctx)
        self.assertIn("cleaned up", result.lower())


class TestCleanupTempArtifacts(unittest.TestCase):
    """Test cleanup_temp_artifacts function."""

    def setUp(self):
        """Set up test fixtures."""
        self.logger = MagicMock()
        self.temp_base = tempfile.gettempdir()

    def test_cleanup_temp_artifacts_no_matching_dirs(self):
        """Test cleanup when no matching directories exist."""
        result = cleanup_temp_artifacts(self.logger, max_age_hours=24)
        data = json.loads(result)
        self.assertEqual(data["cleaned_directories"], 0)

    def test_cleanup_temp_artifacts_with_old_dir(self):
        """Test cleanup removes old directories."""
        # Create an old temp directory
        old_dir = Path(self.temp_base) / "sandbox_artifacts_old_test"
        old_dir.mkdir(exist_ok=True)
        # Set old modification time
        old_time = time.time() - (25 * 3600)  # 25 hours ago
        os.utime(old_dir, (old_time, old_time))

        try:
            result = cleanup_temp_artifacts(self.logger, max_age_hours=24)
            data = json.loads(result)
            self.assertEqual(data["cleaned_directories"], 1)
        finally:
            # Clean up in case test fails
            if old_dir.exists():
                old_dir.rmdir()

    def test_cleanup_temp_artifacts_preserves_recent_dirs(self):
        """Test cleanup preserves recent directories."""
        # Create a recent temp directory
        recent_dir = Path(self.temp_base) / "sandbox_artifacts_recent_test"
        recent_dir.mkdir(exist_ok=True)

        try:
            result = cleanup_temp_artifacts(self.logger, max_age_hours=24)
            data = json.loads(result)
            self.assertEqual(data["cleaned_directories"], 0)
            self.assertTrue(recent_dir.exists())
        finally:
            if recent_dir.exists():
                recent_dir.rmdir()

    def test_cleanup_temp_artifacts_custom_age_threshold(self):
        """Test cleanup with custom max_age_hours."""
        old_dir = Path(self.temp_base) / "sandbox_artifacts_age_test"
        old_dir.mkdir(exist_ok=True)
        # Set to 2 hours old
        old_time = time.time() - (2 * 3600)
        os.utime(old_dir, (old_time, old_time))

        try:
            # With 1 hour threshold, should delete
            result = cleanup_temp_artifacts(self.logger, max_age_hours=1)
            data = json.loads(result)
            self.assertEqual(data["cleaned_directories"], 1)
        finally:
            if old_dir.exists():
                old_dir.rmdir()

    def test_cleanup_temp_artifacts_handles_exceptions(self):
        """Test cleanup handles exceptions gracefully."""
        logger = MagicMock()
        with patch("sandbox.server.artifact_helpers.Path") as mock_path:
            mock_path.return_value.glob.side_effect = OSError("Permission denied")
            result = cleanup_temp_artifacts(logger, max_age_hours=24)
            logger.error.assert_called()
            data = json.loads(result)
            self.assertEqual(data["cleaned_directories"], 0)


class TestGetArtifactReport(unittest.TestCase):
    """Test get_artifact_report function."""

    def setUp(self):
        """Set up test fixtures."""
        self.ctx = MagicMock()
        self.persistent_context_factory = MagicMock()

    def test_get_report_no_artifacts_dir(self):
        """Test report when artifacts_dir is None."""
        self.ctx.artifacts_dir = None
        result = get_artifact_report(self.ctx, self.persistent_context_factory)
        data = json.loads(result)
        self.assertEqual(data["status"], "no_artifacts")

    def test_get_report_nonexistent_artifacts_dir(self):
        """Test report when artifacts_dir does not exist."""
        self.ctx.artifacts_dir = "/nonexistent/path"
        result = get_artifact_report(self.ctx, self.persistent_context_factory)
        data = json.loads(result)
        self.assertEqual(data["status"], "no_artifacts")

    def test_get_report_success(self):
        """Test successful report generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            self.ctx.artifacts_dir = temp_dir
            mock_temp_ctx = MagicMock()
            mock_temp_ctx.get_artifact_report.return_value = {
                "total_artifacts": 5,
                "categories": ["plots", "images"],
            }
            self.persistent_context_factory.return_value = mock_temp_ctx

            result = get_artifact_report(self.ctx, self.persistent_context_factory)
            data = json.loads(result)
            self.assertEqual(data["total_artifacts"], 5)
            self.assertIn("categories", data)

    def test_get_report_handles_exception(self):
        """Test report handles exceptions gracefully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            self.ctx.artifacts_dir = temp_dir
            mock_temp_ctx = MagicMock()
            mock_temp_ctx.get_artifact_report.side_effect = RuntimeError("DB error")
            self.persistent_context_factory.return_value = mock_temp_ctx

            result = get_artifact_report(self.ctx, self.persistent_context_factory)
            data = json.loads(result)
            self.assertEqual(data["status"], "error")
            self.assertIn("Failed to generate", data["message"])


class TestCategorizeArtifacts(unittest.TestCase):
    """Test categorize_artifacts function."""

    def setUp(self):
        """Set up test fixtures."""
        self.ctx = MagicMock()
        self.persistent_context_factory = MagicMock()

    def test_categorize_no_artifacts_dir(self):
        """Test categorization when artifacts_dir is None."""
        self.ctx.artifacts_dir = None
        result = categorize_artifacts(self.ctx, self.persistent_context_factory)
        data = json.loads(result)
        self.assertEqual(data["status"], "no_artifacts")

    def test_categorize_nonexistent_artifacts_dir(self):
        """Test categorization when artifacts_dir does not exist."""
        self.ctx.artifacts_dir = "/nonexistent/path"
        result = categorize_artifacts(self.ctx, self.persistent_context_factory)
        data = json.loads(result)
        self.assertEqual(data["status"], "no_artifacts")

    def test_categorize_success(self):
        """Test successful categorization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            self.ctx.artifacts_dir = temp_dir
            mock_temp_ctx = MagicMock()
            mock_temp_ctx.categorize_artifacts.return_value = {
                "plots": [{"name": "plot.png"}],
                "images": [{"name": "img.jpg"}],
            }
            self.persistent_context_factory.return_value = mock_temp_ctx

            result = categorize_artifacts(self.ctx, self.persistent_context_factory)
            data = json.loads(result)
            self.assertIn("plots", data)
            self.assertIn("images", data)

    def test_categorize_handles_exception(self):
        """Test categorization handles exceptions gracefully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            self.ctx.artifacts_dir = temp_dir
            mock_temp_ctx = MagicMock()
            mock_temp_ctx.categorize_artifacts.side_effect = ValueError("Invalid path")
            self.persistent_context_factory.return_value = mock_temp_ctx

            result = categorize_artifacts(self.ctx, self.persistent_context_factory)
            data = json.loads(result)
            self.assertEqual(data["status"], "error")
            self.assertIn("Failed to categorize", data["message"])


class TestCleanupArtifactsByType(unittest.TestCase):
    """Test cleanup_artifacts_by_type function."""

    def setUp(self):
        """Set up test fixtures."""
        self.ctx = MagicMock()
        self.logger = MagicMock()
        self.persistent_context_factory = MagicMock()

    def test_cleanup_by_type_no_artifacts_dir(self):
        """Test cleanup when artifacts_dir is None."""
        self.ctx.artifacts_dir = None
        result = cleanup_artifacts_by_type(
            "plots", self.ctx, self.logger, self.persistent_context_factory
        )
        data = json.loads(result)
        self.assertEqual(data["status"], "no_artifacts")

    def test_cleanup_by_type_nonexistent_dir(self):
        """Test cleanup when artifacts_dir does not exist."""
        self.ctx.artifacts_dir = "/nonexistent"
        result = cleanup_artifacts_by_type(
            "plots", self.ctx, self.logger, self.persistent_context_factory
        )
        data = json.loads(result)
        self.assertEqual(data["status"], "no_artifacts")

    def test_cleanup_by_type_invalid_type(self):
        """Test cleanup with invalid artifact type."""
        with tempfile.TemporaryDirectory() as temp_dir:
            self.ctx.artifacts_dir = temp_dir
            mock_temp_ctx = MagicMock()
            mock_temp_ctx.categorize_artifacts.return_value = {
                "plots": [],
                "images": [],
            }
            self.persistent_context_factory.return_value = mock_temp_ctx

            result = cleanup_artifacts_by_type(
                "videos", self.ctx, self.logger, self.persistent_context_factory
            )
            data = json.loads(result)
            self.assertEqual(data["status"], "error")
            self.assertIn("not found", data["message"])
            self.assertIn("available_types", data)

    def test_cleanup_by_type_success(self):
        """Test successful cleanup by type."""
        with tempfile.TemporaryDirectory() as temp_dir:
            self.ctx.artifacts_dir = temp_dir
            test_file = Path(temp_dir) / "test_plot.png"
            test_file.write_text("test")

            mock_temp_ctx = MagicMock()
            mock_temp_ctx.categorize_artifacts.return_value = {
                "plots": [{"full_path": str(test_file), "path": "test_plot.png"}]
            }
            self.persistent_context_factory.return_value = mock_temp_ctx

            result = cleanup_artifacts_by_type(
                "plots", self.ctx, self.logger, self.persistent_context_factory
            )
            data = json.loads(result)
            self.assertEqual(data["status"], "success")
            self.assertEqual(data["cleaned_count"], 1)
            self.assertFalse(test_file.exists())

    def test_cleanup_by_type_handles_delete_error(self):
        """Test cleanup handles file deletion errors gracefully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            self.ctx.artifacts_dir = temp_dir
            # Create a test file
            test_file = Path(temp_dir) / "test.png"
            test_file.write_text("test")

            mock_temp_ctx = MagicMock()
            mock_temp_ctx.categorize_artifacts.return_value = {
                "plots": [
                    {"full_path": str(test_file), "path": "test.png"}
                ]
            }
            self.persistent_context_factory.return_value = mock_temp_ctx

            # Mock Path.unlink to raise an exception
            with patch.object(Path, "unlink") as mock_unlink:
                mock_unlink.side_effect = PermissionError("Cannot delete")
                result = cleanup_artifacts_by_type(
                    "plots", self.ctx, self.logger, self.persistent_context_factory
                )
                data = json.loads(result)
                self.assertEqual(data["status"], "success")
                self.assertEqual(data["cleaned_count"], 0)
                self.logger.warning.assert_called()

    def test_cleanup_by_type_exception_in_categorize(self):
        """Test cleanup handles categorize exception."""
        with tempfile.TemporaryDirectory() as temp_dir:
            self.ctx.artifacts_dir = temp_dir
            mock_temp_ctx = MagicMock()
            mock_temp_ctx.categorize_artifacts.side_effect = RuntimeError("DB error")
            self.persistent_context_factory.return_value = mock_temp_ctx

            result = cleanup_artifacts_by_type(
                "plots", self.ctx, self.logger, self.persistent_context_factory
            )
            data = json.loads(result)
            self.assertEqual(data["status"], "error")


class TestBackupCurrentArtifacts(unittest.TestCase):
    """Test backup_current_artifacts function."""

    def setUp(self):
        """Set up test fixtures."""
        self.ctx = MagicMock()

    def test_backup_success(self):
        """Test successful artifact backup."""
        self.ctx.backup_artifacts.return_value = "/backups/backup_123"
        result = backup_current_artifacts(self.ctx, "test_backup")
        data = json.loads(result)
        self.assertEqual(data["status"], "success")
        self.assertIn("backup_123", data["backup_name"])

    def test_backup_with_auto_name(self):
        """Test backup with None name uses auto-generated name."""
        self.ctx.backup_artifacts.return_value = "/backups/auto_456"
        result = backup_current_artifacts(self.ctx, None)
        data = json.loads(result)
        self.assertEqual(data["status"], "success")

    def test_backup_no_artifacts(self):
        """Test backup when no artifacts directory exists."""
        self.ctx.backup_artifacts.return_value = "No artifacts directory to backup"
        result = backup_current_artifacts(self.ctx)
        data = json.loads(result)
        self.assertEqual(data["status"], "error")

    def test_backup_returns_none(self):
        """Test backup when backup_artifacts returns None."""
        self.ctx.backup_artifacts.return_value = None
        result = backup_current_artifacts(self.ctx)
        data = json.loads(result)
        self.assertEqual(data["status"], "error")


class TestListArtifactBackups(unittest.TestCase):
    """Test list_artifact_backups function."""

    def setUp(self):
        """Set up test fixtures."""
        self.ctx = MagicMock()

    def test_list_backups_empty(self):
        """Test listing when no backups exist."""
        self.ctx.list_artifact_backups.return_value = []
        result = list_artifact_backups(self.ctx)
        data = json.loads(result)
        self.assertEqual(data["status"], "no_backups")
        self.assertIn("No artifact backups found", data["message"])
        # Empty backups list included
        self.assertEqual(data["backups"], [])

    def test_list_backups_with_entries(self):
        """Test listing existing backups."""
        self.ctx.list_artifact_backups.return_value = [
            {
                "name": "backup1",
                "path": "/backups/backup1",
                "created": 1672531200.0,  # 2023-01-01 00:00:00
                "modified": 1672531200.0,
                "size": 1024,
            }
        ]
        result = list_artifact_backups(self.ctx)
        data = json.loads(result)
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["total_backups"], 1)
        self.assertIn("created_formatted", data["backups"][0])
        self.assertIn("modified_formatted", data["backups"][0])

    def test_list_backups_multiple_entries(self):
        """Test listing multiple backups."""
        backups = [
            {
                "name": f"backup{i}",
                "path": f"/backups/backup{i}",
                "created": 1672531200.0 + i * 3600,
                "modified": 1672531200.0 + i * 3600,
                "size": 1024 * i,
            }
            for i in range(3)
        ]
        self.ctx.list_artifact_backups.return_value = backups
        result = list_artifact_backups(self.ctx)
        data = json.loads(result)
        self.assertEqual(data["total_backups"], 3)
        for backup in data["backups"]:
            self.assertIn("created_formatted", backup)


class TestRollbackToBackup(unittest.TestCase):
    """Test rollback_to_backup function."""

    def setUp(self):
        """Set up test fixtures."""
        self.ctx = MagicMock()

    def test_rollback_success(self):
        """Test successful rollback."""
        self.ctx.rollback_artifacts.return_value = (
            "Successfully rolled back to backup1"
        )
        result = rollback_to_backup(self.ctx, "backup1")
        data = json.loads(result)
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["backup_name"], "backup1")

    def test_rollback_failure(self):
        """Test rollback when operation fails."""
        self.ctx.rollback_artifacts.return_value = "Backup not found"
        result = rollback_to_backup(self.ctx, "nonexistent")
        data = json.loads(result)
        self.assertEqual(data["status"], "error")

    def test_rollback_partial_success_message(self):
        """Test rollback with partial success message."""
        self.ctx.rollback_artifacts.return_value = (
            "Successfully rolled back to backup2 with warnings"
        )
        result = rollback_to_backup(self.ctx, "backup2")
        data = json.loads(result)
        self.assertEqual(data["status"], "success")


class TestGetBackupDetails(unittest.TestCase):
    """Test get_backup_details function."""

    def setUp(self):
        """Set up test fixtures."""
        self.ctx = MagicMock()

    def test_get_details_success(self):
        """Test getting backup details successfully."""
        self.ctx.get_backup_info.return_value = {
            "name": "backup1",
            "created": 1672531200.0,
            "modified": 1672617600.0,
            "total_size_bytes": 2097152,  # 2 MB
            "files": 10,
        }
        result = get_backup_details(self.ctx, "backup1")
        data = json.loads(result)
        self.assertEqual(data["status"], "success")
        self.assertIn("created_formatted", data["backup_info"])
        self.assertIn("modified_formatted", data["backup_info"])
        self.assertEqual(data["backup_info"]["total_size_mb"], 2.0)

    def test_get_details_error(self):
        """Test getting details for non-existent backup."""
        self.ctx.get_backup_info.return_value = {
            "error": "Backup not found"
        }
        result = get_backup_details(self.ctx, "nonexistent")
        data = json.loads(result)
        self.assertEqual(data["status"], "error")
        self.assertIn("not found", data["message"].lower())

    def test_get_details_size_conversion(self):
        """Test size conversion to megabytes."""
        self.ctx.get_backup_info.return_value = {
            "name": "backup1",
            "created": 1672531200.0,
            "modified": 1672531200.0,
            "total_size_bytes": 10485760,  # 10 MB
        }
        result = get_backup_details(self.ctx, "backup1")
        data = json.loads(result)
        self.assertAlmostEqual(data["backup_info"]["total_size_mb"], 10.0)


class TestCleanupOldBackups(unittest.TestCase):
    """Test cleanup_old_backups function."""

    def setUp(self):
        """Set up test fixtures."""
        self.ctx = MagicMock()
        self.logger = MagicMock()
        self.temp_dir = tempfile.mkdtemp()
        self.ctx.project_root = self.temp_dir

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_cleanup_no_backup_directory(self):
        """Test cleanup when backup directory does not exist."""
        result = cleanup_old_backups(self.ctx, self.logger, max_backups=10)
        data = json.loads(result)
        self.assertEqual(data["status"], "no_backups")
        self.assertEqual(data["cleaned_count"], 0)

    def test_cleanup_keeps_recent_backups(self):
        """Test cleanup keeps max_backups most recent."""
        backup_root = Path(self.temp_dir) / "artifact_backups"
        backup_root.mkdir()

        # Create 5 backups with different timestamps
        for i in range(5):
            backup_dir = backup_root / f"backup_{i}"
            backup_dir.mkdir()
            # Set different modification times
            old_time = time.time() - (5 - i) * 3600  # i=0 is oldest
            os.utime(backup_dir, (old_time, old_time))

        result = cleanup_old_backups(self.ctx, self.logger, max_backups=3)
        data = json.loads(result)
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["cleaned_count"], 2)  # Should delete 2 oldest
        self.assertEqual(data["remaining_backups"], 3)

    def test_cleanup_no_excess_backups(self):
        """Test cleanup when backups <= max_backups."""
        backup_root = Path(self.temp_dir) / "artifact_backups"
        backup_root.mkdir()

        # Create only 2 backups
        for i in range(2):
            backup_dir = backup_root / f"backup_{i}"
            backup_dir.mkdir()

        result = cleanup_old_backups(self.ctx, self.logger, max_backups=5)
        data = json.loads(result)
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["cleaned_count"], 0)
        self.assertEqual(data["remaining_backups"], 2)

    def test_cleanup_handles_file_in_backup_dir(self):
        """Test cleanup ignores files in backup directory."""
        backup_root = Path(self.temp_dir) / "artifact_backups"
        backup_root.mkdir()

        # Create some directories and a file
        (backup_root / "backup_1").mkdir()
        (backup_root / "backup_2").mkdir()
        (backup_root / "readme.txt").write_text("readme")

        result = cleanup_old_backups(self.ctx, self.logger, max_backups=1)
        data = json.loads(result)
        self.assertEqual(data["status"], "success")
        # File should not count as a backup
        self.assertEqual(data["remaining_backups"], 1)

    def test_cleanup_handles_delete_exception(self):
        """Test cleanup handles delete exceptions gracefully."""
        backup_root = Path(self.temp_dir) / "artifact_backups"
        backup_root.mkdir()

        # Create backups
        for i in range(5):
            (backup_root / f"backup_{i}").mkdir()

        with patch("sandbox.server.artifact_helpers.shutil.rmtree") as mock_rmtree:
            mock_rmtree.side_effect = OSError("Permission denied")
            result = cleanup_old_backups(self.ctx, self.logger, max_backups=2)
            data = json.loads(result)
            self.assertEqual(data["status"], "success")
            self.logger.warning.assert_called()

    def test_cleanup_sorts_by_mtime(self):
        """Test cleanup correctly sorts by modification time."""
        backup_root = Path(self.temp_dir) / "artifact_backups"
        backup_root.mkdir()

        # Create backups with non-sequential names
        backups = {"zebra": 3, "alpha": 1, "beta": 2, "gamma": 4}
        for name, hours_ago in backups.items():
            backup_dir = backup_root / name
            backup_dir.mkdir()
            old_time = time.time() - hours_ago * 3600
            os.utime(backup_dir, (old_time, old_time))

        result = cleanup_old_backups(self.ctx, self.logger, max_backups=2)
        data = json.loads(result)
        # Should keep the 2 most recently modified (gamma=4h ago, zebra=3h ago)
        self.assertEqual(data["remaining_backups"], 2)
        self.assertEqual(data["cleaned_count"], 2)

    def test_cleanup_handles_iterdir_exception(self):
        """Test cleanup handles iterdir exceptions."""
        backup_root = Path(self.temp_dir) / "artifact_backups"
        backup_root.mkdir()

        with patch.object(Path, "iterdir") as mock_iterdir:
            mock_iterdir.side_effect = OSError("Permission denied")
            result = cleanup_old_backups(self.ctx, self.logger, max_backups=5)
            data = json.loads(result)
            self.assertEqual(data["status"], "error")


if __name__ == "__main__":
    unittest.main()
