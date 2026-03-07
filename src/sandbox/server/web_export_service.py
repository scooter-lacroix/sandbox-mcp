"""
Web Export Service for Sandbox MCP Server.

This module handles web application export, persistence, and Docker containerization,
replacing duplicate logic from the stdio server.

Security Features:
- Path traversal prevention via export name sanitization
- Input validation for code and export names
- Symlink attack prevention
- Docker image name sanitization
- Thread-safe singleton initialization
"""

import json
import os
import re
import shutil
import subprocess
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, TypedDict, Callable
import logging

logger = logging.getLogger(__name__)

# Constants
MAX_CODE_SIZE = 10 * 1024 * 1024  # 10 MB max code size
MAX_EXPORT_NAME_LENGTH = 100
DOCKER_BUILD_TIMEOUT = 1800  # 30 minutes
DOCKER_IMAGE_NAME_MAX_LENGTH = 128


class ExportResult(TypedDict, total=False):
    """Type-safe export result dictionary."""
    success: bool
    export_name: str
    export_dir: str
    files_created: List[str]
    docker_image: Optional[str]
    error: Optional[str]
    status: str
    message: str
    exports: List[Dict[str, Any]]
    total_exports: int
    export_info: Dict[str, Any]
    docker_image_removed: bool
    image_name: str
    build_output: str
    build_error: str


class WebExportService:
    """
    Service for managing web application exports.

    This service provides unified export, listing, and cleanup of web applications,
    replacing duplicate logic in the stdio server.

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
        self._docker_available: Optional[bool] = None

    def _sanitize_export_name(self, export_name: str) -> str:
        """
        Sanitize export name to prevent path traversal and other attacks.

        Args:
            export_name: The export name to sanitize.

        Returns:
            Sanitized export name.

        Raises:
            ValueError: If export name is invalid.
        """
        if not export_name or not isinstance(export_name, str):
            raise ValueError("Export name must be a non-empty string")

        # Strip whitespace
        sanitized = export_name.strip()

        # Check length
        if len(sanitized) > MAX_EXPORT_NAME_LENGTH:
            raise ValueError(
                f"Export name exceeds maximum length of {MAX_EXPORT_NAME_LENGTH}"
            )

        # Extract only the final path component to prevent traversal
        sanitized = Path(sanitized).name

        # Reject if empty after sanitization
        if not sanitized:
            raise ValueError("Invalid export name after sanitization")

        # Reject hidden files/directories
        if sanitized.startswith('.'):
            raise ValueError("Export name cannot start with a dot")

        # Reject path separators (should already be handled by .name, but be explicit)
        if os.sep in sanitized or (os.altsep and os.altsep in sanitized):
            raise ValueError("Export name cannot contain path separators")

        # Reject dangerous characters
        dangerous_chars = ['<', '>', ':', '"', '|', '?', '*', '\\', '\x00']
        for char in dangerous_chars:
            if char in sanitized:
                raise ValueError(f"Export name contains invalid character: {char}")

        # Reject reserved names
        if sanitized.lower() in ('.', '..', 'con', 'prn', 'aux', 'nul', 'com1', 'lpt1'):
            raise ValueError(f"Export name '{sanitized}' is reserved")

        return sanitized

    def _sanitize_docker_image_name(self, name: str) -> str:
        """
        Sanitize name for Docker image naming rules.

        Docker names must:
        - Be lowercase
        - Contain only a-z, 0-9, -, _
        - Be <= 128 characters

        Args:
            name: The name to sanitize.

        Returns:
            Sanitized Docker image name.
        """
        # Convert to lowercase
        sanitized = name.lower()

        # Replace underscores and dots with hyphens
        sanitized = sanitized.replace('_', '-').replace('.', '-')

        # Remove invalid characters
        sanitized = re.sub(r'[^a-z0-9-]', '', sanitized)

        # Remove leading/trailing hyphens
        sanitized = sanitized.strip('-')

        # Ensure non-empty
        if not sanitized:
            sanitized = "sandbox-export"

        # Truncate to max length
        if len(sanitized) > DOCKER_IMAGE_NAME_MAX_LENGTH:
            sanitized = sanitized[:DOCKER_IMAGE_NAME_MAX_LENGTH]

        return sanitized

    def _validate_code(self, code: str) -> None:
        """
        Validate code input.

        Args:
            code: The code to validate.

        Raises:
            ValueError: If code is invalid.
        """
        if not code or not isinstance(code, str):
            raise ValueError("Code must be a non-empty string")

        if len(code) > MAX_CODE_SIZE:
            raise ValueError(
                f"Code exceeds maximum size of {MAX_CODE_SIZE / (1024 * 1024):.0f} MB"
            )

        # Check for null bytes
        if '\x00' in code:
            raise ValueError("Code cannot contain null bytes")

        # Check for whitespace-only code
        if not code.strip():
            raise ValueError("Code cannot be whitespace-only")

    def _check_docker_available(self) -> bool:
        """
        Check if Docker is available.

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
            except (FileNotFoundError, subprocess.TimeoutExpired):
                self._docker_available = False

        return self._docker_available

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
        file_templates: Dict[str, Callable]
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
            self._validate_code(code)
            sanitized_export_name = self._sanitize_export_name(export_name) if export_name else None
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

        # Generate unique export ID and name
        export_id = str(uuid.uuid4())[:8]
        final_export_name = sanitized_export_name or f"{app_type}_app_{export_id}"

        # Handle name collisions by adding UUID suffix
        export_dir = exports_dir / final_export_name
        collision_counter = 0
        while export_dir.exists():
            collision_counter += 1
            export_dir = exports_dir / f"{final_export_name}_{collision_counter}"

        export_dir.mkdir(parents=True, exist_ok=True)

        result: ExportResult = {
            'success': False,
            'export_name': export_dir.name,
            'export_dir': str(export_dir),
            'files_created': [],
            'docker_image': None,
            'error': None
        }

        temp_dir: Optional[Path] = None
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
            if self._check_docker_available():
                result['docker_image'] = self._build_docker_image_internal(
                    export_dir,
                    result['export_name']
                )

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

    def _flask_app_templates(self) -> Dict[str, Callable]:
        """Get file templates for Flask app export."""
        def app_template(code: str, name: str) -> str:
            return code

        def requirements_template(code: str, name: str) -> str:
            return "Flask>=2.0.0\ngunicorn>=20.0.0\n"

        def dockerfile_template(code: str, name: str) -> str:
            return '''FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]
'''

        def compose_template(code: str, name: str) -> str:
            return f'''version: '3.8'
services:
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - FLASK_ENV=production
'''

        def readme_template(code: str, name: str) -> str:
            return f'''# {name}

Exported Flask application from sandbox.

## Running with Docker

```bash
docker-compose up --build
```

The application will be available at http://localhost:8000

## Running locally

```bash
pip install -r requirements.txt
python app.py
```

## Files

- `app.py` - Main Flask application
- `requirements.txt` - Python dependencies
- `Dockerfile` - Docker configuration
- `docker-compose.yml` - Docker Compose configuration
'''

        return {
            'app.py': app_template,
            'requirements.txt': requirements_template,
            'Dockerfile': dockerfile_template,
            'docker-compose.yml': compose_template,
            'README.md': readme_template
        }

    def _streamlit_app_templates(self) -> Dict[str, Callable]:
        """Get file templates for Streamlit app export."""
        def app_template(code: str, name: str) -> str:
            return code

        def requirements_template(code: str, name: str) -> str:
            return "streamlit>=1.28.0\npandas>=1.5.0\nnumpy>=1.24.0\n"

        def dockerfile_template(code: str, name: str) -> str:
            return '''FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
'''

        def compose_template(code: str, name: str) -> str:
            return f'''version: '3.8'
services:
  web:
    build: .
    ports:
      - "8501:8501"
    environment:
      - STREAMLIT_SERVER_PORT=8501
      - STREAMLIT_SERVER_ADDRESS=0.0.0.0
'''

        def readme_template(code: str, name: str) -> str:
            return f'''# {name}

Exported Streamlit application from sandbox.

## Running with Docker

```bash
docker-compose up --build
```

The application will be available at http://localhost:8501

## Running locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Files

- `app.py` - Main Streamlit application
- `requirements.txt` - Python dependencies
- `Dockerfile` - Docker configuration
- `docker-compose.yml` - Docker Compose configuration
'''

        return {
            'app.py': app_template,
            'requirements.txt': requirements_template,
            'Dockerfile': dockerfile_template,
            'docker-compose.yml': compose_template,
            'README.md': readme_template
        }

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
            file_templates=self._flask_app_templates()
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
            file_templates=self._streamlit_app_templates()
        )

    def _build_docker_image_internal(
        self,
        export_dir: Path,
        export_name: str
    ) -> Optional[str]:
        """
        Build Docker image for an exported web application.

        Internal method that assumes Docker is available.

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

        try:
            # Sanitize image name for Docker
            image_name = f'sandbox-{self._sanitize_docker_image_name(export_name)}'

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

    def list_web_app_exports(self) -> Dict[str, Any]:
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

    def _get_export_info(self, export_dir: Path) -> Optional[Dict[str, Any]]:
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

    def get_export_details(self, export_name: str) -> Dict[str, Any]:
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
            sanitized_name = self._sanitize_export_name(export_name)
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

    def cleanup_web_app_export(self, export_name: str) -> Dict[str, Any]:
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
            sanitized_name = self._sanitize_export_name(export_name)
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
            docker_cleaned = False
            if self._check_docker_available():
                try:
                    image_name = f'sandbox-{self._sanitize_docker_image_name(sanitized_name)}'
                    remove_result = subprocess.run(
                        ['docker', 'rmi', image_name],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    if remove_result.returncode == 0:
                        docker_cleaned = True
                    else:
                        logger.debug(f"Docker image removal failed: {remove_result.stderr}")
                except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                    logger.debug(f"Docker cleanup error: {e}")

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

    def build_docker_image(self, export_name: str) -> Dict[str, Any]:
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
            sanitized_name = self._sanitize_export_name(export_name)
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

        if not self._check_docker_available():
            return {
                'status': 'error',
                'message': 'Docker not found. Please install Docker to build images.'
            }

        try:
            image_name = f'sandbox-{self._sanitize_docker_image_name(sanitized_name)}'
            build_result = subprocess.run(
                ['docker', 'build', '-t', image_name, str(export_dir)],
                capture_output=True,
                text=True,
                timeout=DOCKER_BUILD_TIMEOUT
            )

            if build_result.returncode == 0:
                return {
                    'status': 'success',
                    'image_name': image_name,
                    'export_name': sanitized_name,
                    'build_output': build_result.stdout,
                    'message': f'Docker image "{image_name}" built successfully'
                }
            else:
                return {
                    'status': 'error',
                    'build_output': build_result.stdout,
                    'build_error': build_result.stderr,
                    'message': f'Docker build failed for "{sanitized_name}"'
                }

        except subprocess.TimeoutExpired:
            return {
                'status': 'error',
                'message': f'Docker build timed out for "{sanitized_name}"'
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to build Docker image: {str(e)}'
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
    """
    global _web_export_service

    # Double-checked locking for thread safety
    if _web_export_service is None:
        with _singleton_lock:
            if _web_export_service is None:
                _web_export_service = WebExportService(artifacts_dir)
    elif artifacts_dir and _web_export_service.artifacts_dir != artifacts_dir:
        # Update artifacts_dir if provided and different
        with _singleton_lock:
            _web_export_service.artifacts_dir = artifacts_dir

    return _web_export_service
