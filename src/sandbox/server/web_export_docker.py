"""
Docker operations for web application exports.

This module provides Docker-related functionality:
- Docker availability checking
- Docker image building for exported applications
- Docker image cleanup

The module caches Docker availability checks for performance.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Optional

from .web_export_validators import sanitize_docker_image_name

logger = logging.getLogger(__name__)

# Constants
DOCKER_BUILD_TIMEOUT = 1800  # 30 minutes


class DockerManager:
    """
    Manages Docker operations for web application exports.

    This class handles:
    - Checking Docker availability
    - Building Docker images from export directories
    - Removing Docker images
    """

    def __init__(self):
        """Initialize the Docker manager."""
        self._docker_available: Optional[bool] = None

    def check_docker_available(self) -> bool:
        """
        Check if Docker is available.

        Results are cached for performance.

        Returns:
            True if Docker is available, False otherwise.
        """
        if self._docker_available is None:
            try:
                result = subprocess.run(
                    ['docker', '--version'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                self._docker_available = (result.returncode == 0)
                if self._docker_available:
                    logger.debug("Docker is available")
                else:
                    logger.warning("Docker command failed")
            except (FileNotFoundError, subprocess.TimeoutExpired) as e:
                logger.debug(f"Docker not available: {e}")
                self._docker_available = False

        return self._docker_available

    def build_docker_image(
        self,
        export_dir: Path,
        export_name: str
    ) -> Optional[str]:
        """
        Build Docker image for an exported web application.

        Args:
            export_dir: Path to the export directory.
            export_name: Name of the export.

        Returns:
            Docker image name if successful, None otherwise.
        """
        dockerfile_path = export_dir / "Dockerfile"
        if not dockerfile_path.exists():
            logger.warning(f"No Dockerfile found in export {export_name}")
            return None

        if not self.check_docker_available():
            logger.warning("Docker is not available")
            return None

        try:
            # Sanitize image name for Docker
            image_name = f'sandbox-{sanitize_docker_image_name(export_name)}'

            logger.info(f"Building Docker image {image_name} for {export_name}")
            result = subprocess.run(
                ['docker', 'build', '-t', image_name, str(export_dir)],
                capture_output=True,
                text=True,
                timeout=DOCKER_BUILD_TIMEOUT
            )

            if result.returncode == 0:
                logger.info(f"Docker image built successfully: {image_name}")
                return image_name
            else:
                logger.warning(f"Docker build failed for {export_name}: {result.stderr}")
                return None

        except subprocess.TimeoutExpired:
            logger.warning(f"Docker build timed out for {export_name}")
            return None
        except Exception as e:
            logger.error(f"Failed to build Docker image: {e}")
            return None

    def remove_docker_image(self, export_name: str) -> bool:
        """
        Remove Docker image for an export.

        Args:
            export_name: Name of the export.

        Returns:
            True if image was removed successfully, False otherwise.
        """
        if not self.check_docker_available():
            return False

        try:
            image_name = f'sandbox-{sanitize_docker_image_name(export_name)}'
            result = subprocess.run(
                ['docker', 'rmi', image_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                logger.info(f"Removed Docker image: {image_name}")
                return True
            else:
                logger.debug(f"Docker image removal failed: {result.stderr}")
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.debug(f"Docker cleanup error: {e}")
            return False


# Global singleton instance for reuse
_docker_manager: Optional[DockerManager] = None


def get_docker_manager() -> DockerManager:
    """
    Get the global Docker manager instance (singleton).

    Returns:
        The DockerManager singleton instance.
    """
    global _docker_manager
    if _docker_manager is None:
        _docker_manager = DockerManager()
    return _docker_manager
