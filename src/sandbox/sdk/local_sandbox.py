"""
Local sandbox implementation for the enhanced Sandbox SDK.
"""

import io
import sys
import os
import traceback
import uuid
import tempfile
import shutil
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_sandbox import BaseSandbox
from .execution import Execution
from ..core.execution_context import PersistentExecutionContext
from ..core.patching import get_patch_manager

logger = logging.getLogger(__name__)


class LocalSandbox(BaseSandbox):
    """
    Local sandbox implementation that uses the existing MCP server functionality.

    This provides secure local execution with artifact capture and virtual environment support.
    """

    def __init__(self, **kwargs):
        """
        Initialize a local sandbox instance.
        """
        # Force remote=False for local sandboxes
        kwargs["remote"] = False
        super().__init__(**kwargs)

        # Initialize local execution context with persistence
        self._execution_context = PersistentExecutionContext()
        self._execution_globals = self._execution_context.globals_dict

        # Apply monkey patches for artifact capture using core service
        patch_manager = get_patch_manager()
        patch_manager.patch_matplotlib()
        patch_manager.patch_pil()

    async def get_default_image(self) -> str:
        """
        Get the default Docker image for local sandbox (not used in local execution).
        """
        return "local-python"

    async def start(
        self,
        image: Optional[str] = None,
        memory: int = 512,
        cpus: float = 1.0,
        timeout: float = 180.0,
    ) -> None:
        """
        Start the local sandbox.
        
        For local sandboxes, this primarily sets up the execution environment.
        """
        if self._is_started:
            return
            
        # Already set up in PersistentExecutionContext
        # No additional setup needed for persistent context
        
        self._is_started = True

    async def stop(self) -> None:
        """
        Stop the local sandbox and clean up resources.
        """
        if not self._is_started:
            return
            
        # Clean up artifacts if needed
        # Note: We might want to preserve artifacts for user access
        # self._execution_context.cleanup_artifacts()
        
        self._is_started = False

    async def run(self, code: str, validate: bool = True) -> Execution:
        """
        Execute Python code in the local sandbox with enhanced error handling.

        Args:
            code: Python code to execute
            validate: Whether to validate code before execution

        Returns:
            An Execution object representing the executed code

        Raises:
            RuntimeError: If the sandbox is not started or execution fails
        """
        if not self._is_started:
            raise RuntimeError("Sandbox is not started. Call start() first.")

        # Use the enhanced persistent execution context with validation
        import hashlib
        cache_key = hashlib.md5(code.encode()).hexdigest()
        
        result = self._execution_context.execute_code(
            code, 
            cache_key=cache_key, 
            validate=validate
        )
        
        # Create and return execution result with enhanced information
        execution = Execution(
            stdout=result.get('stdout', ''),
            stderr=result.get('stderr', ''),
            return_value=None,  # Will be enhanced in future versions
            exception=Exception(result['error']) if result.get('error') else None,
            artifacts=result.get('artifacts', []),
        )
        
        # Add validation result to execution if available
        if result.get('validation_result'):
            execution._validation_result = result['validation_result']
        
        return execution

    @property
    def artifacts_dir(self) -> Optional[str]:
        """
        Get the artifacts directory path.
        """
        return str(self._execution_context.artifacts_dir) if self._execution_context.artifacts_dir else None

    def list_artifacts(self, format_type: str = 'list', recursive: bool = True) -> Any:
        """
        List all artifacts created during execution with recursive scanning.
        
        Args:
            format_type: Output format ('list', 'json', 'csv', 'detailed')
            recursive: Whether to scan subdirectories recursively
            
        Returns:
            Artifacts in the requested format
        """
        if not self._execution_context.artifacts_dir:
            return [] if format_type == 'list' else self._format_empty_artifacts(format_type)
            
        artifacts_dir = Path(self._execution_context.artifacts_dir)
        if not artifacts_dir.exists():
            return [] if format_type == 'list' else self._format_empty_artifacts(format_type)
        
        # Get artifacts with full details
        artifacts = []
        pattern = "**/*" if recursive else "*"
        
        for file_path in artifacts_dir.glob(pattern):
            if file_path.is_file():
                try:
                    stat = file_path.stat()
                    artifact_info = {
                        'name': file_path.name,
                        'path': str(file_path.relative_to(artifacts_dir)),
                        'full_path': str(file_path),
                        'size': stat.st_size,
                        'created': stat.st_ctime,
                        'modified': stat.st_mtime,
                        'extension': file_path.suffix.lower(),
                        'type': self._categorize_file(file_path)
                    }
                    artifacts.append(artifact_info)
                except Exception as e:
                    logger.warning(f"Failed to get info for {file_path}: {e}")
        
        return self._format_artifacts_output(artifacts, format_type)
    
    def _categorize_file(self, file_path: Path) -> str:
        """Categorize a file based on its extension and path."""
        suffix = file_path.suffix.lower()
        path_str = str(file_path).lower()
        
        # Check for Manim files
        if any(pattern in path_str for pattern in ['manim', 'media', 'videos', 'images']):
            return 'manim'
        
        # Extension-based categorization
        type_mappings = {
            'images': {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.svg', '.webp'},
            'videos': {'.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv'},
            'data': {'.csv', '.json', '.xml', '.yaml', '.yml', '.pkl', '.pickle', '.h5', '.hdf5'},
            'code': {'.py', '.js', '.html', '.css', '.sql', '.sh', '.bat'},
            'documents': {'.pdf', '.docx', '.doc', '.txt', '.md', '.rtf'},
            'audio': {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a'}
        }
        
        for category, extensions in type_mappings.items():
            if suffix in extensions:
                return category
        
        return 'other'
    
    def _format_empty_artifacts(self, format_type: str) -> Any:
        """Format empty artifacts response."""
        if format_type == 'json':
            return json.dumps([])
        elif format_type == 'csv':
            return 'name,path,size,created,modified,extension,type\n'
        elif format_type == 'detailed':
            return {'total': 0, 'files': [], 'categories': {}}
        else:
            return []
    
    def _format_artifacts_output(self, artifacts: List[Dict], format_type: str) -> Any:
        """Format artifacts output in the requested format."""
        if format_type == 'list':
            return [artifact['path'] for artifact in artifacts]
        
        elif format_type == 'json':
            import json
            return json.dumps(artifacts, indent=2)
        
        elif format_type == 'csv':
            import csv
            import io
            output = io.StringIO()
            if artifacts:
                writer = csv.DictWriter(output, fieldnames=artifacts[0].keys())
                writer.writeheader()
                writer.writerows(artifacts)
            return output.getvalue()
        
        elif format_type == 'detailed':
            # Group by category
            categories = {}
            for artifact in artifacts:
                category = artifact['type']
                if category not in categories:
                    categories[category] = []
                categories[category].append(artifact)
            
            return {
                'total': len(artifacts),
                'files': artifacts,
                'categories': categories,
                'summary': {
                    cat: {'count': len(files), 'total_size': sum(f['size'] for f in files)}
                    for cat, files in categories.items()
                }
            }
        
        else:
            return artifacts

    def cleanup_artifacts(self) -> None:
        """
        Clean up all artifacts.
        """
        self._execution_context.cleanup_artifacts()

    def get_execution_info(self) -> Dict[str, Any]:
        """
        Get information about the execution environment.
        """
        return {
            "python_version": sys.version,
            "executable": sys.executable,
            "virtual_env": os.environ.get("VIRTUAL_ENV"),
            "project_root": str(self._execution_context.project_root),
            "artifacts_dir": self.artifacts_dir,
            "sys_path": sys.path[:10],  # First 10 entries
        }
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get performance statistics from the execution context.
        """
        return self._execution_context.get_execution_stats()
    
    def get_execution_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get execution history.
        """
        return self._execution_context.get_execution_history(limit=limit)
    
    def clear_cache(self) -> None:
        """
        Clear compilation and execution cache.
        """
        self._execution_context.clear_cache()
    
    def save_session(self) -> None:
        """
        Manually save the current execution session state.
        """
        self._execution_context.save_persistent_state()
    
    @property
    def session_id(self) -> str:
        """
        Get the current session ID.
        """
        return self._execution_context.session_id
    
    def cleanup_session(self) -> None:
        """
        Cleanup the current session.
        """
        self._execution_context.cleanup()
    
    def get_artifact_report(self) -> Dict[str, Any]:
        """
        Get comprehensive artifact report with categorization.
        """
        return self._execution_context.get_artifact_report()
    
    def categorize_artifacts(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Categorize artifacts by type with detailed metadata.
        """
        return self._execution_context.categorize_artifacts()
    
    def cleanup_artifacts_by_type(self, artifact_type: str) -> int:
        """
        Clean up artifacts of a specific type.
        
        Args:
            artifact_type: Type of artifacts to clean (e.g., 'images', 'videos', 'plots')
            
        Returns:
            Number of artifacts cleaned up
        """
        if not self._execution_context.artifacts_dir:
            return 0
            
        categorized = self.categorize_artifacts()
        if artifact_type not in categorized:
            return 0
            
        cleaned_count = 0
        for file_info in categorized[artifact_type]:
            try:
                file_path = Path(file_info['full_path'])
                if file_path.exists():
                    file_path.unlink()
                    cleaned_count += 1
            except Exception as e:
                logger.warning(f"Failed to delete {file_info['path']}: {e}")
        
        return cleaned_count
    
    def get_manim_artifacts(self) -> List[Dict[str, Any]]:
        """
        Get all Manim-related artifacts.
        """
        categorized = self.categorize_artifacts()
        return categorized.get('manim', [])
    
    def get_artifact_summary(self) -> str:
        """
        Get a human-readable summary of artifacts.
        """
        report = self.get_artifact_report()
        
        if report['total_artifacts'] == 0:
            return "No artifacts found."
        
        def format_size(bytes_size):
            for unit in ['B', 'KB', 'MB', 'GB']:
                if bytes_size < 1024.0:
                    return f"{bytes_size:.1f} {unit}"
                bytes_size /= 1024.0
            return f"{bytes_size:.1f} TB"
        
        lines = [
            f"Total Artifacts: {report['total_artifacts']}",
            f"Total Size: {format_size(report['total_size'])}",
            "",
            "Categories:"
        ]
        
        for category, info in report['categories'].items():
            lines.append(f"  {category}: {info['count']} files ({format_size(info['size'])})")
        
        if report['recent_artifacts']:
            lines.extend([
                "",
                "Recent Artifacts:"
            ])
            for artifact in report['recent_artifacts'][:5]:
                lines.append(f"  {artifact['name']} ({format_size(artifact['size'])})")
        
        return "\n".join(lines)
    
    def start_interactive_repl(self) -> None:
        """Start an enhanced interactive REPL session."""
        from ..core.interactive_repl import EnhancedREPL
        
        repl = EnhancedREPL(self._execution_context)
        repl.start_interactive_session()
    
    def get_code_template(self, template_type: str) -> str:
        """Get code templates for common tasks."""
        from ..core.code_validator import CodeValidator
        
        validator = CodeValidator()
        return validator.get_code_template(template_type)
    
    def get_available_templates(self) -> List[str]:
        """Get list of available code templates."""
        from ..core.code_validator import CodeValidator
        
        validator = CodeValidator()
        return validator.get_available_templates()
    
    def validate_code(self, code: str) -> Dict[str, Any]:
        """Validate code before execution."""
        from ..core.code_validator import CodeValidator
        
        validator = CodeValidator()
        return validator.validate_and_format(code)
    
    def get_manim_helper(self):
        """Get Manim helper for animation support."""
        from ..core.manim_support import ManIMHelper
        
        return ManIMHelper(self._execution_context.artifacts_dir)
