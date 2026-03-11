"""
Web Export Service for Sandbox MCP Server.

This module handles web application export orchestration, persistence, and listing.

This is the core orchestration layer. Template generation, Docker operations,
and validation are split into separate modules for maintainability.

Security Features:
- Path traversal prevention via export name sanitization
- Input validation for code and export names
- Symlink attack prevention
- Thread-safe singleton initialization
- Disk space validation to prevent DoS attacks
"""

from __future__ import annotations

import logging
import shutil
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .web_export_validators import (
    ExportResult,
    check_disk_space,
    estimate_export_size,
    sanitize_docker_image_name,
    sanitize_export_name,
    validate_code,
    MAX_EXPORT_SIZE_BYTES,
    MIN_FREE_SPACE_BYTES,
)
from .web_export_templates import (
    get_flask_app_templates,
    get_streamlit_app_templates,
)
from .web_export_docker import (
    DockerManager,
    get_docker_manager,
)

logger = logging.getLogger(__name__)

# Re-export constants for backward compatibility
MAX_CODE_SIZE = 10 * 1024 * 1024  # 10 MB max code size
MAX_EXPORT_NAME_LENGTH = 100
DOCKER_BUILD_TIMEOUT = 1800  # 30 minutes
DOCKER_IMAGE_NAME_MAX_LENGTH = 128

__all__ = [
    'WebExportService',
    'get_web_export_service',
    'ExportResult',
    'MAX_EXPORT_NAME_LENGTH',
    'MAX_CODE_SIZE',
    'DOCKER_BUILD_TIMEOUT',
]


class WebExportService:
    """
    Service for managing web application exports.

    This service provides unified export, listing, and cleanup of web applications.

    Security Features:
    - Path traversal prevention
    - Input validation
    - Symlink attack prevention
    - Thread-safe operations
    """

    SUPPORTED_APP_TYPES = {"flask", "streamlit"}

    def __init__(self, artifacts_dir: Optional[Path] = None):
        """
        Initialize the web export service.

        Args:
            artifacts_dir: Base directory for artifacts. If None, exports will fail.
        """
        self.artifacts_dir = artifacts_dir
        self._lock = threading.RLock()
        self._docker_manager = get_docker_manager()

    def _check_docker_available(self) -> bool:
        """
        Check if Docker is available (wrapper for backward compatibility).

        Returns:
            True if Docker is available, False otherwise.
        """
        return self._docker_manager.check_docker_available()

    def _check_disk_space(self, directory: Path, required_bytes: int) -> tuple[bool, str]:
        """
        Check if sufficient disk space is available (wrapper for backward compatibility).

        Args:
            directory: Directory to check space for
            required_bytes: Required free space in bytes

        Returns:
            Tuple of (success: bool, message: str)
        """
        return check_disk_space(directory, required_bytes)

    def _estimate_export_size(self, code: str, app_type: str) -> int:
        """
        Estimate export size in bytes (wrapper for backward compatibility).

        Args:
            code: Application code
            app_type: Type of application ('flask' or 'streamlit')

        Returns:
            Estimated size in bytes
        """
        return estimate_export_size(code, app_type)

    def _ensure_exports_dir(self) -> Optional[Path]:
        """
        Ensure the exports directory exists.

        Returns:
            Path to exports directory, or None if artifacts_dir is not set.
        """
        if not self.artifacts_dir:
            return None

        exports_dir = self.artifacts_dir / "exports"

        # Security check: ensure exports_dir is not a symlink
        if exports_dir.is_symlink():
            logger.error("Exports directory is a symlink - rejecting for security")
            return None

        exports_dir.mkdir(parents=True, exist_ok=True)
        return exports_dir

    def _export_app(
        self,
        code: str,
        export_name: Optional[str],
        app_type: str,
        file_templates: dict[str, Any]
    ) -> ExportResult:
        """
        Common export logic for all app types.

        Args:
            code: The application code.
            export_name: Optional custom export name.
            app_type: Type of application ('flask' or 'streamlit').
            file_templates: Dictionary of filename -> template function.

        Returns:
            Export result dictionary.
        """
        # Validate inputs
        try:
            validate_code(code)
            sanitized_export_name = sanitize_export_name(export_name) if export_name else None
        except ValueError as e:
            return {
                'success': False,
                'error': str(e)
            }

        exports_dir = self._ensure_exports_dir()
        if not exports_dir:
            return {
                'success': False,
                'error': 'No artifacts directory configured'
            }

        # Check disk space BEFORE creating anything (DoS prevention)
        estimated_size = estimate_export_size(code, app_type)

        # Check if estimated export size exceeds maximum
        if estimated_size > MAX_EXPORT_SIZE_BYTES:
            return {
                'success': False,
                'error': f'Export size exceeds maximum ({MAX_EXPORT_SIZE_BYTES / (1024 * 1024):.0f}MB limit)'
            }

        # Check if we have enough free space (export size + minimum free buffer)
        required_space = estimated_size + MIN_FREE_SPACE_BYTES
        space_ok, space_message = check_disk_space(exports_dir, required_space)
        if not space_ok:
            return {
                'success': False,
                'error': space_message,
                'estimated_size': estimated_size
            }

        # Generate unique export ID and name
        export_id = str(uuid.uuid4())[:8]
        final_export_name = sanitized_export_name or f"{app_type}_app_{export_id}"

        # Handle name collisions with atomic directory creation
        export_dir = exports_dir / final_export_name
        collision_counter = 0

        # Atomic directory creation to prevent race conditions
        while True:
            try:
                export_dir.mkdir(parents=True, exist_ok=False)
                break
            except FileExistsError:
                collision_counter += 1
                export_dir = exports_dir / f"{final_export_name}_{collision_counter}"
                # Safety limit to prevent infinite loops
                if collision_counter > 1000:
                    return {
                        'success': False,
                        'error': 'Unable to create unique export directory'
                    }

        result: ExportResult = {
            'success': False,
            'export_name': export_dir.name,
            'export_dir': str(export_dir),
            'files_created': [],
            'docker_image': None,
            'error': None
        }

        try:
            # Create files using templates
            for filename, template_func in file_templates.items():
                file_path = export_dir / filename
                content = template_func(code, result['export_name'])

                # Security check: ensure we're not writing to a symlink
                if file_path.is_symlink():
                    raise ValueError(f"Security violation: {filename} is a symlink")

                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                result['files_created'].append(str(file_path))

            # Try to build Docker image if available
            docker_image = self._docker_manager.build_docker_image(
                export_dir,
                result['export_name']
            )
            if docker_image:
                result['docker_image'] = docker_image

            result['success'] = True

        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Failed to export {app_type} app: {e}")

            # Cleanup on failure
            if export_dir.exists():
                try:
                    shutil.rmtree(export_dir)
                except Exception as cleanup_error:
                    logger.error(f"Failed to cleanup after error: {cleanup_error}")

        return result

    def export_flask_app(self, code: str, export_name: Optional[str] = None) -> ExportResult:
        """
        Export a Flask application as static files and Docker container.

        Args:
            code: The Flask application code.
            export_name: Optional custom name for the export.

        Returns:
            Export result dictionary.
        """
        return self._export_app(
            code=code,
            export_name=export_name,
            app_type='flask',
            file_templates=get_flask_app_templates()
        )

    def export_streamlit_app(self, code: str, export_name: Optional[str] = None) -> ExportResult:
        """
        Export a Streamlit application as Docker container.

        Args:
            code: The Streamlit application code.
            export_name: Optional custom name for the export.

        Returns:
            Export result dictionary.
        """
        return self._export_app(
            code=code,
            export_name=export_name,
            app_type='streamlit',
            file_templates=get_streamlit_app_templates()
        )

    def export_web_app(
        self,
        code: str,
        app_type: str = 'flask',
        export_name: Optional[str] = None
    ) -> ExportResult:
        """
        Export a web application as Docker container for persistence.

        Args:
            code: The web application code.
            app_type: Type of web app ('flask' or 'streamlit').
            export_name: Optional custom name for the export.

        Returns:
            Export result dictionary.
        """
        if app_type not in self.SUPPORTED_APP_TYPES:
            return {
                'success': False,
                'error': f'Unsupported app type: {app_type}. Use "flask" or "streamlit"'
            }

        if app_type == 'flask':
            return self.export_flask_app(code, export_name)
        else:
            return self.export_streamlit_app(code, export_name)

    def list_web_app_exports(self) -> dict[str, Any]:
        """
        List all exported web applications.

        Returns:
            Dictionary with export listing.
        """
        if not self.artifacts_dir:
            return {
                'status': 'no_exports',
                'message': 'No artifacts directory configured',
                'exports': []
            }

        exports_dir = self.artifacts_dir / "exports"
        if not exports_dir.exists():
            return {
                'status': 'no_exports',
                'message': 'No exports directory found',
                'exports': []
            }

        # Security check: ensure exports_dir is not a symlink
        if exports_dir.is_symlink():
            logger.error("Exports directory is a symlink - rejecting for security")
            return {
                'status': 'error',
                'message': 'Security error: exports directory is a symlink',
                'exports': []
            }

        exports = []
        for export_dir in exports_dir.iterdir():
            if export_dir.is_dir() and not export_dir.is_symlink():
                try:
                    export_info = self._get_export_info(export_dir)
                    if export_info:
                        exports.append(export_info)
                except Exception as e:
                    logger.warning(f"Failed to read export {export_dir}: {e}")

        # Sort by creation time (newest first)
        exports.sort(key=lambda x: x.get('created', 0), reverse=True)

        return {
            'status': 'success',
            'total_exports': len(exports),
            'exports': exports,
            'message': f'Found {len(exports)} exported web applications'
        }

    def _get_export_info(self, export_dir: Path) -> Optional[dict[str, Any]]:
        """
        Get information about a specific export directory.

        Args:
            export_dir: Path to the export directory.

        Returns:
            Dictionary with export information, or None if error.
        """
        try:
            # Determine app type from files (read only first 4KB for efficiency)
            app_type = 'unknown'
            app_file = export_dir / 'app.py'
            if app_file.exists() and not app_file.is_symlink():
                with open(app_file, 'r', encoding='utf-8') as f:
                    content = f.read(4096)  # Read only first 4KB
                    if 'Flask' in content or 'flask' in content:
                        app_type = 'flask'
                    elif 'streamlit' in content or 'st.' in content:
                        app_type = 'streamlit'

            # Get export info
            stat = export_dir.stat()
            files = [f.name for f in export_dir.glob('*') if f.is_file() and not f.is_symlink()]

            return {
                'name': export_dir.name,
                'path': str(export_dir),
                'app_type': app_type,
                'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'files': files,
                'has_dockerfile': (export_dir / 'Dockerfile').exists(),
                'has_compose': (export_dir / 'docker-compose.yml').exists(),
                'has_requirements': (export_dir / 'requirements.txt').exists()
            }
        except Exception as e:
            logger.error(f"Failed to get export info: {e}")
            return None

    def get_export_details(self, export_name: str) -> dict[str, Any]:
        """
        Get detailed information about a specific web app export.

        Args:
            export_name: Name of the export to inspect.

        Returns:
            Dictionary with export details.
        """
        if not self.artifacts_dir:
            return {
                'status': 'error',
                'message': 'No artifacts directory configured'
            }

        try:
            sanitized_name = sanitize_export_name(export_name)
        except ValueError as e:
            return {
                'status': 'error',
                'message': str(e)
            }

        export_dir = self.artifacts_dir / "exports" / sanitized_name

        # Security checks
        if not export_dir.exists():
            return {
                'status': 'error',
                'message': f'Export "{sanitized_name}" not found'
            }

        if export_dir.is_symlink():
            logger.error(f"Export directory is a symlink: {export_dir}")
            return {
                'status': 'error',
                'message': 'Security error: export directory is a symlink'
            }

        try:
            # Read all files in the export (skip symlinks)
            files = {}
            for file_path in export_dir.glob('*'):
                if file_path.is_file() and not file_path.is_symlink():
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            files[file_path.name] = f.read()
                    except Exception as e:
                        files[file_path.name] = f"Error reading file: {str(e)}"

            # Get directory stats
            stat = export_dir.stat()

            # Determine app type
            app_type = 'unknown'
            if 'app.py' in files:
                content = files['app.py']
                if 'Flask' in content or 'flask' in content:
                    app_type = 'flask'
                elif 'streamlit' in content or 'st.' in content:
                    app_type = 'streamlit'

            export_info = {
                'name': sanitized_name,
                'path': str(export_dir),
                'app_type': app_type,
                'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'files': files,
                'total_files': len(files)
            }

            return {
                'status': 'success',
                'export_info': export_info
            }

        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to get export details: {str(e)}'
            }

    def cleanup_web_app_export(self, export_name: str) -> dict[str, Any]:
        """
        Remove an exported web application.

        Args:
            export_name: Name of the export to remove.

        Returns:
            Dictionary with cleanup results.
        """
        if not self.artifacts_dir:
            return {
                'status': 'error',
                'message': 'No artifacts directory configured'
            }

        try:
            sanitized_name = sanitize_export_name(export_name)
        except ValueError as e:
            return {
                'status': 'error',
                'message': str(e)
            }

        export_dir = self.artifacts_dir / "exports" / sanitized_name

        # Security checks
        if not export_dir.exists():
            return {
                'status': 'error',
                'message': f'Export "{sanitized_name}" not found'
            }

        if export_dir.is_symlink():
            logger.error(f"Export directory is a symlink: {export_dir}")
            return {
                'status': 'error',
                'message': 'Security error: export directory is a symlink'
            }

        try:
            # Remove export directory
            shutil.rmtree(export_dir)

            # Try to remove Docker image if it exists
            docker_cleaned = self._docker_manager.remove_docker_image(sanitized_name)

            return {
                'status': 'success',
                'export_name': sanitized_name,
                'docker_image_removed': docker_cleaned,
                'message': f'Export "{sanitized_name}" cleaned up successfully'
            }

        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to cleanup export: {str(e)}'
            }

    def build_docker_image(self, export_name: str) -> dict[str, Any]:
        """
        Build Docker image for an exported web application.

        Args:
            export_name: Name of the export to build.

        Returns:
            Dictionary with build results.
        """
        if not self.artifacts_dir:
            return {
                'status': 'error',
                'message': 'No artifacts directory configured'
            }

        try:
            sanitized_name = sanitize_export_name(export_name)
        except ValueError as e:
            return {
                'status': 'error',
                'message': str(e)
            }

        export_dir = self.artifacts_dir / "exports" / sanitized_name

        # Security checks
        if not export_dir.exists():
            return {
                'status': 'error',
                'message': f'Export "{sanitized_name}" not found'
            }

        if export_dir.is_symlink():
            logger.error(f"Export directory is a symlink: {export_dir}")
            return {
                'status': 'error',
                'message': 'Security error: export directory is a symlink'
            }

        dockerfile_path = export_dir / "Dockerfile"
        if not dockerfile_path.exists():
            return {
                'status': 'error',
                'message': f'No Dockerfile found in export "{sanitized_name}"'
            }

        if not self._docker_manager.check_docker_available():
            return {
                'status': 'error',
                'message': 'Docker not found. Please install Docker to build images.'
            }

        image_name = self._docker_manager.build_docker_image(export_dir, sanitized_name)

        if image_name:
            return {
                'status': 'success',
                'image_name': image_name,
                'export_name': sanitized_name,
                'message': f'Docker image "{image_name}" built successfully'
            }
        else:
            return {
                'status': 'error',
                'message': f'Docker build failed for "{sanitized_name}"'
            }


# Thread-safe singleton instance
_web_export_service: Optional[WebExportService] = None
_singleton_lock = threading.Lock()


def get_web_export_service(artifacts_dir: Optional[Path] = None) -> WebExportService:
    """
    Get the global web export service instance (thread-safe singleton).

    Args:
        artifacts_dir: Optional artifacts directory to initialize with.

    Returns:
        The singleton WebExportService instance.

    Note:
        The artifacts_dir can only be set on first initialization.
        Subsequent calls with different artifacts_dir will log a warning
        but return the existing instance.
    """
    global _web_export_service

    # Double-checked locking for thread safety
    if _web_export_service is None:
        with _singleton_lock:
            if _web_export_service is None:
                _web_export_service = WebExportService(artifacts_dir)
    elif artifacts_dir is not None:
        # artifacts_dir already set - log warning if different
        with _singleton_lock:
            if _web_export_service.artifacts_dir != artifacts_dir:
                logger.warning(
                    "Ignoring artifacts_dir change for singleton WebExportService. "
                    "Use the instance returned by get_web_export_service()."
                )

    return _web_export_service
