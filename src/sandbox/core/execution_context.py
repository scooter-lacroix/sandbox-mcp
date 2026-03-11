"""
Enhanced execution context with persistence and performance optimizations.

Security:
    State persistence uses pickle for complex objects, protected by HMAC-SHA256
    verification to detect tampering. HMAC and state management are handled by
    the StateManager in execution_context_state.py.

Database Transaction Management:
    All database operations use explicit transactions with BEGIN/COMMIT/ROLLBACK.
    Connection pooling via DatabaseTransactionManager ensures proper resource cleanup.
    Failed operations are automatically rolled back to prevent partial state corruption.
"""

from __future__ import annotations

import io
import os
import sys
import uuid
import time
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Set, List, ContextManager
import logging
from contextlib import contextmanager
from collections import OrderedDict


logger = logging.getLogger(__name__)


# Import DatabaseTransactionManager from dedicated module
from .execution_context_db import DatabaseTransactionManager

# Import DirectoryChangeMonitor from dedicated module
from .execution_context_monitor import DirectoryChangeMonitor

# Import artifact management functions from dedicated module
from .execution_context_artifacts import (
    get_current_artifacts,
    categorize_artifacts,
    get_artifact_report
)

# Import file operation functions from dedicated module
from .execution_context_files import (
    save_error_details,
    change_working_directory as change_working_directory_fn,
    list_directory as list_directory_fn,
    find_files as find_files_fn,
    reset_to_default_directory as reset_to_default_directory_fn,
    get_current_directory_info as get_current_directory_info_fn
)

# Import state management functions and classes from dedicated module
from .execution_context_state import (
    StateManager,
    create_state_tables,
    migrate_hmac_column
)

class PersistentExecutionContext:
    """
    Enhanced execution context with state persistence and performance optimizations.
    
    Features:
    - Persistent variable storage across sessions
    - Optimized execution with caching
    - Complete rendering support for AI viewing
    - Enhanced artifact management
    - Performance monitoring
    """
    
    def __init__(self, session_id: Optional[str] = None):
        # SECURITY S2: Validate session_id before use to prevent path traversal
        raw_session_id = session_id or str(uuid.uuid4())
        self.session_id = self._validate_session_id(raw_session_id)
        
        self.project_root = self._detect_project_root()
        self.venv_path = self.project_root / ".venv"
        self.session_dir = self.project_root / "sessions" / self.session_id
        self.artifacts_dir = self.session_dir / "artifacts"
        self.state_file = self.session_dir / "state.db"

        # Directory monitoring and security
        self.home_dir = Path.home()
        self.directory_monitor = DirectoryChangeMonitor(
            default_working_dir=self.artifacts_dir,
            home_dir=self.home_dir
        )

        # Performance tracking
        self.execution_times = []
        self.memory_usage = []
        self.cache_hits = 0
        self.cache_misses = 0

        # Execution state
        self.globals_dict = {}
        self.imports_cache = {}
        self.compilation_cache = {}
        self._lock = threading.RLock()

        # Database transaction manager
        self._db_manager: Optional[DatabaseTransactionManager] = None
        # State manager for persistence operations
        self._state_manager: Optional[StateManager] = None

        # Initialize directories and database
        self._setup_directories()
        self._setup_database()
        self._setup_environment()
        self._load_persistent_state()

        logger.info(f"Initialized persistent execution context for session {self.session_id}")

    @staticmethod
    def _validate_session_id(session_id: str) -> str:
        """
        Validate session_id to prevent path traversal and injection attacks.
        
        Security S2: Only alphanumeric characters, hyphens, and underscores are allowed.
        Path traversal sequences, special characters, and null bytes are rejected.
        
        Args:
            session_id: The session identifier to validate
            
        Returns:
            The validated session_id
            
        Raises:
            ValueError: If session_id contains invalid characters or patterns
        """
        if not session_id:
            raise ValueError("session_id cannot be empty")
            
        # Check for null bytes
        if '\x00' in session_id:
            raise ValueError("session_id cannot contain null bytes")
            
        # Check for newlines or whitespace
        if any(c in session_id for c in '\n\r\t '):
            raise ValueError("session_id cannot contain whitespace")
            
        # Check for path traversal patterns
        if '..' in session_id:
            raise ValueError("session_id cannot contain '..' (path traversal)")
            
        # Check for path separators
        if '/' in session_id or '\\' in session_id:
            raise ValueError("session_id cannot contain path separators")
            
        # Only allow alphanumeric characters, hyphens, and underscores
        safe_id = session_id.replace('-', '').replace('_', '')
        if not safe_id.isalnum():
            raise ValueError(
                f"session_id must be alphanumeric with hyphens/underscores: {session_id!r}"
            )
            
        # Limit length to prevent DoS
        if len(session_id) > 128:
            raise ValueError(f"session_id too long: {len(session_id)} > 128")
            
        return session_id
    
    def _detect_project_root(self) -> Path:
        """Detect project root with improved logic."""
        current_file = Path(__file__).resolve()
        
        # Walk up the directory tree to find project root
        for parent in current_file.parents:
            if any((parent / marker).exists() for marker in [
                'pyproject.toml', 'setup.py', '.git', 'README.md'
            ]):
                return parent
        
        # Fallback to current directory
        return Path.cwd()
    
    def _setup_directories(self):
        """Create necessary directories with proper permissions."""
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories for organized artifacts
        for subdir in ['plots', 'images', 'videos', 'data', 'code', 'logs', 'manim']:
            (self.artifacts_dir / subdir).mkdir(exist_ok=True)
    
    def _setup_database(self):
        """Initialize SQLite database for state persistence with HMAC support and transaction management."""
        # Initialize database transaction manager
        self._db_manager = DatabaseTransactionManager(self.state_file)

        # Initialize state manager with globals_dict reference
        self._state_manager = StateManager(
            state_file=self.state_file,
            db_manager=self._db_manager,
            globals_dict=self.globals_dict
        )

        try:
            with self._db_manager.transaction() as cursor:
                # Check if we need to migrate the schema
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='execution_state'"
                )
                table_exists = cursor.fetchone() is not None

                # Create state management tables using helper function
                create_state_tables(cursor)

                # Migrate existing tables if needed
                if table_exists:
                    migrate_hmac_column(cursor)

                # Initialize HMAC key via StateManager (pass cursor to avoid nested transaction)
                self._state_manager.initialize_hmac_key(cursor=cursor)

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    def _setup_environment(self):
        """Enhanced environment setup with performance optimizations."""
        # Compute absolute paths
        project_root_str = str(self.project_root)
        project_parent_str = str(self.project_root.parent)
        
        # Detect virtual environment
        venv_site_packages = None
        if self.venv_path.exists():
            for py_version in ['python3.12', 'python3.11', 'python3.10', 'python3.9']:
                candidate = self.venv_path / "lib" / py_version / "site-packages"
                if candidate.exists():
                    venv_site_packages = candidate
                    break
        
        # Optimize sys.path with deduplication
        current_paths = OrderedDict.fromkeys(sys.path)
        paths_to_add = [project_parent_str, project_root_str]
        
        if venv_site_packages:
            paths_to_add.append(str(venv_site_packages))
        
        # Add new paths at the beginning
        new_sys_path = []
        for path in paths_to_add:
            if path not in current_paths:
                new_sys_path.append(path)
                current_paths[path] = None
        
        sys.path[:] = new_sys_path + list(current_paths.keys())
        
        # Virtual environment activation
        if self.venv_path.exists():
            venv_python = self.venv_path / "bin" / "python"
            venv_bin = self.venv_path / "bin"
            
            if venv_python.exists():
                os.environ['VIRTUAL_ENV'] = str(self.venv_path)
                current_path = os.environ.get('PATH', '')
                venv_bin_str = str(venv_bin)
                
                if venv_bin_str not in current_path.split(os.pathsep):
                    os.environ['PATH'] = f"{venv_bin_str}{os.pathsep}{current_path}"
                
                sys.executable = str(venv_python)
        
        logger.info(f"Environment setup complete: {self.project_root}")

    def _load_persistent_state(self):
        """Load persistent execution state from database with HMAC verification."""
        if self._state_manager is not None:
            self._state_manager.load_persistent_state()
        else:
            logger.error("State manager not initialized")

    def save_persistent_state(self):
        """Save current execution state to database with HMAC protection."""
        if self._state_manager is not None:
            with self._lock:
                self._state_manager.save_persistent_state()
        else:
            logger.error("State manager not initialized")

    # Backward-compatible properties for accessing HMAC key via StateManager
    @property
    def _state_hmac_key(self) -> Optional[bytes]:
        """Access the HMAC key from StateManager for backward compatibility."""
        if self._state_manager is not None:
            return self._state_manager._state_hmac_key
        return None

    # Backward-compatible wrappers for HMAC operations
    def _compute_state_hmac(self, data: bytes) -> str:
        """Compute HMAC-SHA256 for state data integrity verification."""
        if self._state_manager is not None:
            return self._state_manager.compute_state_hmac(data)
        raise RuntimeError("State manager not initialized")

    def _verify_state_hmac(self, data: bytes, stored_hmac: str) -> bool:
        """Verify HMAC for state data. Returns True if valid, False if tampered."""
        if self._state_manager is not None:
            return self._state_manager.verify_state_hmac(data, stored_hmac)
        raise RuntimeError("State manager not initialized")

    @contextmanager
    def capture_output(self):
        """Context manager for capturing stdout/stderr with performance tracking."""
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        start_time = time.time()
        
        try:
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture
            yield stdout_capture, stderr_capture
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            
            execution_time = time.time() - start_time
            self.execution_times.append(execution_time)
            
            # Keep only last 1000 execution times for memory efficiency
            if len(self.execution_times) > 1000:
                self.execution_times = self.execution_times[-1000:]
    
    def execute_code(self, code: str, cache_key: Optional[str] = None, validate: bool = True) -> Dict[str, Any]:
        """
        Execute code with enhanced performance, caching, and validation.
        
        Args:
            code: Python code to execute
            cache_key: Optional cache key for compilation caching
            validate: Whether to validate code before execution
            
        Returns:
            Dictionary containing execution results
        """
        with self._lock:
            start_time = time.time()
            result = {
                'success': False,
                'error': None,
                'error_type': None,
                'stdout': '',
                'stderr': '',
                'execution_time': 0,
                'artifacts': [],
                'cache_hit': False,
                'validation_result': None,
                'formatted_code': code
            }
            
            # Step 1: Validate code if requested
            if validate:
                from .code_validator import CodeValidator
                validator = CodeValidator()
                validation_result = validator.validate_and_format(code)
                result['validation_result'] = validation_result
                
                if not validation_result['valid']:
                    result['error'] = '; '.join(validation_result['issues'])
                    result['error_type'] = 'ValidationError'
                    result['execution_time'] = time.time() - start_time
                    return result
                
                # Use formatted code if validation passed
                code = validation_result['formatted_code']
                result['formatted_code'] = code
            
            # Step 2: Check compilation cache
            if cache_key and cache_key in self.compilation_cache:
                compiled_code = self.compilation_cache[cache_key]
                self.cache_hits += 1
                result['cache_hit'] = True
            else:
                try:
                    compiled_code = compile(code, '<sandbox>', 'exec')
                    if cache_key:
                        self.compilation_cache[cache_key] = compiled_code
                    self.cache_misses += 1
                except SyntaxError as e:
                    result.update({
                        'error': f"Syntax error at line {e.lineno}: {e.msg}",
                        'error_type': 'SyntaxError',
                        'stderr': str(e),
                        'execution_time': time.time() - start_time
                    })
                    return result
                except Exception as e:
                    result.update({
                        'error': f"Compilation error: {str(e)}",
                        'error_type': type(e).__name__,
                        'stderr': str(e),
                        'execution_time': time.time() - start_time
                    })
                    return result
            
            # Step 3: Track artifacts before execution
            artifacts_before = self._get_current_artifacts()
            
            # Step 4: Execute with output capture and enhanced error reporting
            with self.capture_output() as (stdout, stderr):
                try:
                    # Print execution info
                    print(f"🚀 Executing code (session: {self.session_id[:8]}...)")
                    print(f"📁 Artifacts directory: {self.artifacts_dir}")
                    print("-" * 50)
                    
                    exec(compiled_code, self.globals_dict)
                    
                    print("-" * 50)
                    print("✅ Execution completed successfully!")
                    
                    result['success'] = True
                    
                except KeyboardInterrupt:
                    result.update({
                        'error': "Execution interrupted by user",
                        'error_type': 'KeyboardInterrupt'
                    })
                    print("\n⚠️ Execution interrupted!")
                    
                except MemoryError:
                    result.update({
                        'error': "Memory limit exceeded",
                        'error_type': 'MemoryError'
                    })
                    print("\n💾 Memory limit exceeded!")
                    
                except Exception as e:
                    result.update({
                        'error': str(e),
                        'error_type': type(e).__name__
                    })
                    print(f"\n❌ Execution failed: {str(e)}")
                    
                    # Print enhanced traceback
                    import traceback
                    traceback.print_exc()
                    
                    # Save error details for debugging
                    self._save_error_details(e, code, traceback.format_exc())
            
            # Step 5: Track artifacts after execution
            artifacts_after = self._get_current_artifacts()
            new_artifacts = artifacts_after - artifacts_before
            
            execution_time = time.time() - start_time
            result['execution_time'] = execution_time
            
            # Step 6: Process artifacts
            result['artifacts'] = list(new_artifacts)
            if new_artifacts:
                print(f"📁 Generated {len(new_artifacts)} artifacts:")
                for artifact in sorted(new_artifacts)[:5]:  # Show first 5
                    print(f"  - {artifact}")
                if len(new_artifacts) > 5:
                    print(f"  ... and {len(new_artifacts) - 5} more")
            
            # Step 7: Capture output
            result['stdout'] = stdout.getvalue()
            result['stderr'] = stderr.getvalue()
            
            # Step 8: Store execution in history
            self._store_execution_history(
                code=code,
                success=result['success'],
                error=result['error'],
                execution_time=execution_time,
                artifacts=list(new_artifacts)
            )
            
            # Step 9: Save state periodically
            if len(self.execution_times) % 10 == 0:  # Every 10 executions
                self.save_persistent_state()
            
            return result
    
    def _get_current_artifacts(self) -> Set[str]:
        """Get current set of artifact files.

        Security: Symlinks are skipped to prevent host file exfiltration attacks.
        """
        return get_current_artifacts(self.artifacts_dir)
    
    def categorize_artifacts(self) -> Dict[str, List[Dict[str, Any]]]:
        """Categorize artifacts by type with detailed metadata."""
        return categorize_artifacts(self.artifacts_dir)
    
    def get_artifact_report(self) -> Dict[str, Any]:
        """Generate comprehensive artifact report."""
        return get_artifact_report(self.artifacts_dir)
    
    def _store_execution_history(self, code: str, success: bool, error: Optional[str],
                                execution_time: float, artifacts: List[str]):
        """Store execution in history database."""
        if self._state_manager is not None:
            self._state_manager.store_execution_history(
                code=code,
                success=success,
                error=error,
                execution_time=execution_time,
                artifacts=artifacts
            )
        else:
            logger.error("State manager not initialized")
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        return {
            'total_executions': len(self.execution_times),
            'average_execution_time': sum(self.execution_times) / len(self.execution_times) if self.execution_times else 0,
            'cache_hit_ratio': self.cache_hits / (self.cache_hits + self.cache_misses) if (self.cache_hits + self.cache_misses) > 0 else 0,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'cached_compilations': len(self.compilation_cache),
            'session_id': self.session_id,
            'artifacts_count': len(self._get_current_artifacts())
        }
    
    def get_execution_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get execution history."""
        if self._state_manager is not None:
            return self._state_manager.get_execution_history(limit=limit)
        else:
            logger.error("State manager not initialized")
            return []
    
    def clear_cache(self):
        """Clear compilation cache."""
        with self._lock:
            self.compilation_cache.clear()
            self.cache_hits = 0
            self.cache_misses = 0
    
    def cleanup_artifacts(self):
        """Clean up artifacts directory and all its contents."""
        if self.artifacts_dir and self.artifacts_dir.exists():
            import shutil
            shutil.rmtree(self.artifacts_dir, ignore_errors=True)
            logger.info(f"Cleaned up artifacts directory: {self.artifacts_dir}")
    
    def _save_error_details(self, error: Exception, code: str, traceback_str: str):
        """Save detailed error information for debugging."""
        save_error_details(
            artifacts_dir=self.artifacts_dir,
            error=error,
            code=code,
            traceback_str=traceback_str,
            session_id=self.session_id
        )
    
    def change_working_directory(self, path: str, temporary: bool = False) -> Dict[str, Any]:
        """
        Change the working directory with security checks and logging.

        Args:
            path: The new directory path
            temporary: Whether this is a temporary change (returns to default after operation)

        Returns:
            Dictionary containing operation result and current directory info
        """
        return change_working_directory_fn(
            path=path,
            temporary=temporary,
            directory_monitor=self.directory_monitor,
            home_dir=self.home_dir
        )
    
    def list_directory(self, path: Optional[str] = None, include_hidden: bool = False) -> Dict[str, Any]:
        """
        List contents of a directory with security checks.

        Args:
            path: Directory to list (defaults to current directory)
            include_hidden: Whether to include hidden files

        Returns:
            Dictionary containing directory contents and metadata
        """
        return list_directory_fn(
            path=path,
            include_hidden=include_hidden,
            home_dir=self.home_dir
        )
    
    def find_files(self, pattern: str, search_path: Optional[str] = None, max_results: int = 100) -> Dict[str, Any]:
        """
        Find files matching a pattern with security checks.

        Args:
            pattern: Glob pattern to search for
            search_path: Directory to search in (defaults to current directory)
            max_results: Maximum number of results to return

        Returns:
            Dictionary containing search results
        """
        return find_files_fn(
            pattern=pattern,
            search_path=search_path,
            max_results=max_results,
            home_dir=self.home_dir
        )
    
    def reset_to_default_directory(self) -> Dict[str, Any]:
        """
        Reset working directory to the default sandbox area.

        Returns:
            Dictionary containing operation result
        """
        return reset_to_default_directory_fn(directory_monitor=self.directory_monitor)
    
    def get_current_directory_info(self) -> Dict[str, Any]:
        """
        Get information about the current working directory.

        Returns:
            Dictionary containing current directory information
        """
        return get_current_directory_info_fn(
            directory_monitor=self.directory_monitor,
            home_dir=self.home_dir,
            artifacts_dir=self.artifacts_dir
        )
    
    def cleanup(self):
        """Clean up resources and save state."""
        self.save_persistent_state()
        logger.info(f"Cleaned up execution context for session {self.session_id}")
