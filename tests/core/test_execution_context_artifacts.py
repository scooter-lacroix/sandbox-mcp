"""
Tests for execution_context_artifacts module with security focus.

This module contains tests for artifact management functions,
particularly for symlink exfiltration prevention.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import mock

import pytest

from sandbox.core.execution_context_artifacts import (
    get_current_artifacts,
    categorize_artifacts,
    get_artifact_report,
)


class TestSymlinkExfiltration:
    """Test suite for symlink exfiltration prevention (CRIT-3)."""

    def test_get_current_artifacts_skips_symlinks(self, tmp_path):
        """Test that get_current_artifacts skips symlinks to prevent host file enumeration."""
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()

        # Create a regular file
        regular_file = artifacts_dir / "regular.txt"
        regular_file.write_text("safe content")

        # Create a symlink pointing outside artifacts_dir (simulating attack)
        host_file = tmp_path / "sensitive_host_file.txt"
        host_file.write_text("sensitive content")
        symlink = artifacts_dir / "exfil_symlink"
        symlink.symlink_to(host_file)

        # Get artifacts
        artifacts = get_current_artifacts(artifacts_dir)

        # Assert: Only regular file is included, symlink is skipped
        assert len(artifacts) == 1
        assert "regular.txt" in artifacts
        assert "exfil_symlink" not in artifacts

    def test_categorize_artifacts_skips_symlinks(self, tmp_path):
        """Test that categorize_artifacts skips symlinks to prevent host file enumeration."""
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()

        # Create a regular image file
        image_dir = artifacts_dir / "images"
        image_dir.mkdir()
        regular_image = image_dir / "regular.png"
        regular_image.write_bytes(b"fake png data")

        # Create a symlink pointing to a host file (simulating attack)
        host_sensitive = tmp_path / "sensitive_data.csv"
        host_sensitive.write_text("secret,data,here")
        symlink = artifacts_dir / "data_exfil.csv"
        symlink.symlink_to(host_sensitive)

        # Categorize artifacts
        categories = categorize_artifacts(artifacts_dir)

        # Assert: Regular image is categorized, symlink is NOT in any category
        assert len(categories["images"]) == 1
        assert categories["images"][0]["name"] == "regular.png"

        # Verify symlink is not in any category
        all_artifacts = []
        for category_files in categories.values():
            all_artifacts.extend(category_files)

        artifact_names = [a["name"] for a in all_artifacts]
        assert "data_exfil.csv" not in artifact_names
        assert "sensitive_data.csv" not in artifact_names

    def test_categorize_artifacts_skips_symlink_in_subdirectory(self, tmp_path):
        """Test that symlinks in subdirectories are also skipped."""
        artifacts_dir = tmp_path / "artifacts"
        data_dir = artifacts_dir / "data"
        data_dir.mkdir(parents=True)

        # Create a regular data file
        regular_data = data_dir / "regular.json"
        regular_data.write_text('{"safe": "data"}')

        # Create a symlink in subdirectory pointing outside
        host_secret = tmp_path / "secret.txt"
        host_secret.write_text("secret content")
        symlink = data_dir / "exfil.txt"
        symlink.symlink_to(host_secret)

        categories = categorize_artifacts(artifacts_dir)

        # Assert: Only regular file is included
        assert len(categories["data"]) == 1
        assert categories["data"][0]["name"] == "regular.json"

        # Verify symlink is not included
        all_artifacts = []
        for category_files in categories.values():
            all_artifacts.extend(category_files)

        artifact_names = [a["name"] for a in all_artifacts]
        assert "exfil.txt" not in artifact_names

    def test_get_artifact_report_excludes_symlinks(self, tmp_path):
        """Test that get_artifact_report does not include symlinks in counts."""
        artifacts_dir = tmp_path / "artifacts"
        images_dir = artifacts_dir / "images"
        images_dir.mkdir(parents=True)

        # Create regular files
        (images_dir / "img1.png").write_bytes(b"png1")
        (images_dir / "img2.jpg").write_bytes(b"jpg1")

        # Create a symlink
        host_file = tmp_path / "host.txt"
        host_file.write_text("host data")
        (images_dir / "symlink.png").symlink_to(host_file)

        report = get_artifact_report(artifacts_dir)

        # Assert: Only 2 artifacts counted, symlink is excluded
        assert report["total_artifacts"] == 2
        assert report["categories"]["images"]["count"] == 2


class TestArtifactCategorization:
    """Test suite for general artifact categorization logic."""

    def test_categorize_artifacts_empty_directory(self, tmp_path):
        """Test categorize_artifacts with non-existent directory."""
        result = categorize_artifacts(tmp_path / "nonexistent")
        # Should return empty categories
        assert all(len(v) == 0 for v in result.values())

    def test_categorize_artifacts_by_extension(self, tmp_path):
        """Test that files are categorized by extension."""
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()

        # Create various file types
        (artifacts_dir / "image.png").write_bytes(b"png")
        (artifacts_dir / "video.mp4").write_bytes(b"mp4")
        (artifacts_dir / "data.csv").write_text("csv")
        (artifacts_dir / "script.py").write_text("python")
        (artifacts_dir / "doc.txt").write_text("text")  # Use .txt instead of .pdf

        categories = categorize_artifacts(artifacts_dir)

        assert len(categories["images"]) == 1
        assert categories["images"][0]["name"] == "image.png"
        assert len(categories["videos"]) == 1
        assert categories["videos"][0]["name"] == "video.mp4"
        assert len(categories["data"]) == 1
        assert categories["data"][0]["name"] == "data.csv"
        assert len(categories["code"]) == 1
        assert categories["code"][0]["name"] == "script.py"
        assert len(categories["documents"]) == 1
        assert categories["documents"][0]["name"] == "doc.txt"

    def test_categorize_artifacts_by_directory(self, tmp_path):
        """Test that files in specific subdirectories are categorized by directory."""
        artifacts_dir = tmp_path / "artifacts"
        plots_dir = artifacts_dir / "plots"
        plots_dir.mkdir(parents=True)

        # PNG in plots directory should be categorized as 'plots', not 'images'
        (plots_dir / "plot1.png").write_bytes(b"png")

        categories = categorize_artifacts(artifacts_dir)

        assert len(categories["plots"]) == 1
        assert len(categories["images"]) == 0
        assert categories["plots"][0]["name"] == "plot1.png"


class TestGetCurrentArtifacts:
    """Test suite for get_current_artifacts function."""

    def test_get_current_artifacts_empty_directory(self, tmp_path):
        """Test get_current_artifacts with empty directory."""
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()

        artifacts = get_current_artifacts(artifacts_dir)
        assert len(artifacts) == 0

    def test_get_current_artifacts_recursive(self, tmp_path):
        """Test that get_current_artifacts finds files recursively."""
        artifacts_dir = tmp_path / "artifacts"
        subdir = artifacts_dir / "subdir"
        subdir.mkdir(parents=True)

        (artifacts_dir / "root.txt").write_text("root")
        (subdir / "nested.txt").write_text("nested")

        artifacts = get_current_artifacts(artifacts_dir)

        assert len(artifacts) == 2
        assert "root.txt" in artifacts
        # Nested file uses forward slash as path separator
        assert "subdir/nested.txt" in artifacts or "subdir\\nested.txt" in artifacts
