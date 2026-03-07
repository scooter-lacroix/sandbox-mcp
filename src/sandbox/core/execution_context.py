"""
Enhanced execution context with persistence and performance optimizations.

Security:
    This module uses pickle for serializing complex Python objects.
    Pickle deserialization is protected with HMAC-SHA256 verification
    to detect tampering. The HMAC key is generated on first initialization
    and stored in the state database.
"""

from __future__ import annotations

import io
import os
import sys
import json
import uuid
import time
import pickle
import tempfile
import threading
import hmac
import hashlib
import secrets
from pathlib import Path
from typing import Dict, Any, Optional, Set, List
import logging
from contextlib import contextmanager
from collections import OrderedDict
import sqlite3
import base64


logger = logging.getLogger(__name__)

class DirectoryChangeMonitor:
    def __init__(self, default_working_dir: Path, home_dir: Path):
        self.current_dir = default_working_dir
        self.default_dir = default_working_dir
        self.home_dir = home_dir

    def change_directory(self, new_dir: Path):
        if new_dir.resolve() != self.default_dir.resolve() and not new_dir.resolve().is_relative_to(self.home_dir):
            logger.warning(f"Unauthorized attempt to change directory: {new_dir}")
            raise PermissionError(f"Cannot change to directory outside home: {new_dir}")
        logger.info(f"Changing directory from {self.current_dir} to {new_dir}")
        self.current_dir = new_dir

    def reset_to_default(self):
        logger.info(f"Resetting to default directory: {self.default_dir}")
        self.current_dir = self.default_dir




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
        self.session_id = session_id or str(uuid.uuid4())
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

        # HMAC key for state integrity verification
        self._state_hmac_key: Optional[bytes] = None

        # Initialize directories and database
        self._setup_directories()
        self._setup_database()
        self._setup_environment()
        self._load_persistent_state()

        logger.info(f"Initialized persistent execution context for session {self.session_id}")
    
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
        """Initialize SQLite database for state persistence with HMAC support."""
        with sqlite3.connect(self.state_file) as conn:
            # Check if we need to migrate the schema
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='execution_state'"
            )
            table_exists = cursor.fetchone() is not None
            
            # Create execution_state table with HMAC column
            conn.execute('''
                CREATE TABLE IF NOT EXISTS execution_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    type TEXT NOT NULL,
                    hmac TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
            ''')
            
            # Migrate existing rows without HMAC (set HMAC to empty, will be regenerated on next save)
            if table_exists:
                try:
                    conn.execute('ALTER TABLE execution_state ADD COLUMN hmac TEXT NOT NULL DEFAULT ""')
                except sqlite3.OperationalError:
                    # Column already exists
                    pass
            
            # Store/retrieve HMAC key in metadata table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS _metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            ''')
            
            # Get or generate HMAC key
            cursor = conn.execute(
                "SELECT value FROM _metadata WHERE key = 'hmac_key'"
            )
            row = cursor.fetchone()
            
            if row is not None:
                # Load existing key
                self._state_hmac_key = base64.b64decode(row[0])
            else:
                # Generate new key
                self._state_hmac_key = secrets.token_bytes(32)
                conn.execute(
                    "INSERT INTO _metadata (key, value) VALUES (?, ?)",
                    ('hmac_key', base64.b64encode(self._state_hmac_key).decode())
                )
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS execution_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT,
                    result TEXT,
                    execution_time REAL,
                    memory_usage INTEGER,
                    artifacts TEXT,
                    timestamp REAL
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    path TEXT,
                    type TEXT,
                    size INTEGER,
                    metadata TEXT,
                    timestamp REAL
                )
            ''')
    
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

    def _compute_state_hmac(self, data: bytes) -> str:
        """Compute HMAC-SHA256 for state data integrity verification."""
        if self._state_hmac_key is None:
            raise RuntimeError("HMAC key not initialized")
        return hmac.new(
            self._state_hmac_key,
            data,
            hashlib.sha256
        ).hexdigest()

    def _verify_state_hmac(self, data: bytes, stored_hmac: str) -> bool:
        """Verify HMAC for state data. Returns True if valid, False if tampered."""
        if self._state_hmac_key is None:
            raise RuntimeError("HMAC key not initialized")
        computed_hmac = self._compute_state_hmac(data)
        return hmac.compare_digest(computed_hmac, stored_hmac)

    def _load_persistent_state(self):
        """Load persistent execution state from database with HMAC verification."""
        try:
            with sqlite3.connect(self.state_file) as conn:
                cursor = conn.execute(
                    'SELECT key, value, type, hmac FROM execution_state ORDER BY timestamp DESC'
                )

                for key, value_str, type_str, stored_hmac in cursor:
                    try:
                        # Decode the value
                        if type_str == 'pickle':
                            data = base64.b64decode(value_str)
                        else:
                            data = value_str.encode('utf-8')
                        
                        # Verify HMAC before deserializing
                        if not self._verify_state_hmac(data, stored_hmac):
                            logger.error(f"State integrity check failed for {key} - possible tampering")
                            continue
                        
                        # Safe to deserialize after HMAC verification
                        if type_str == 'pickle':
                            value = pickle.loads(data)
                        else:
                            value = json.loads(value_str)

                        self.globals_dict[key] = value
                    except Exception as e:
                        logger.warning(f"Failed to load state for {key}: {e}")

        except Exception as e:
            logger.warning(f"Failed to load persistent state: {e}")

    def save_persistent_state(self):
        """Save current execution state to database with HMAC protection."""
        with self._lock:
            try:
                with sqlite3.connect(self.state_file) as conn:
                    # Clear existing state
                    conn.execute('DELETE FROM execution_state')

                    # Save current state
                    for key, value in self.globals_dict.items():
                        if key.startswith('_'):  # Skip internal variables
                            continue

                        try:
                            # Try JSON serialization first
                            value_str = json.dumps(value)
                            type_str = 'json'
                            data_for_hmac = value_str.encode('utf-8')
                        except (TypeError, ValueError):
                            # Fall back to pickle for complex objects
                            try:
                                pickled = pickle.dumps(value)
                                value_str = base64.b64encode(pickled).decode()
                                type_str = 'pickle'
                                data_for_hmac = pickled
                            except Exception:
                                continue  # Skip non-serializable objects

                        # Compute HMAC for integrity verification
                        state_hmac = self._compute_state_hmac(data_for_hmac)

                        conn.execute(
                            'INSERT OR REPLACE INTO execution_state (key, value, type, hmac, timestamp) VALUES (?, ?, ?, ?, ?)',
                            (key, value_str, type_str, state_hmac, time.time())
                        )

            except Exception as e:
                logger.error(f"Failed to save persistent state: {e}")
    
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
        """Get current set of artifact files."""
        artifacts = set()
        if self.artifacts_dir.exists():
            for file_path in self.artifacts_dir.rglob('*'):
                if file_path.is_file():
                    artifacts.add(str(file_path.relative_to(self.artifacts_dir)))
        return artifacts
    
    def categorize_artifacts(self) -> Dict[str, List[Dict[str, Any]]]:
        """Categorize artifacts by type with detailed metadata."""
        categories = {
            'images': [],
            'videos': [],
            'plots': [],
            'data': [],
            'code': [],
            'documents': [],
            'audio': [],
            'manim': [],
            'other': []
        }
        
        if not self.artifacts_dir.exists():
            return categories
        
        # File type mappings
        type_mappings = {
            'images': {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.svg', '.webp'},
            'videos': {'.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv'},
            'plots': {'.png', '.jpg', '.jpeg', '.pdf', '.svg'},  # When in plots directory
            'data': {'.csv', '.json', '.xml', '.yaml', '.yml', '.pkl', '.pickle', '.h5', '.hdf5'},
            'code': {'.py', '.js', '.html', '.css', '.sql', '.sh', '.bat'},
            'documents': {'.pdf', '.docx', '.doc', '.txt', '.md', '.rtf'},
            'audio': {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a'},
            'manim': {'.mp4', '.png', '.gif'}  # When in manim-related directories
        }
        
        for file_path in self.artifacts_dir.rglob('*'):
            if not file_path.is_file():
                continue
                
            relative_path = file_path.relative_to(self.artifacts_dir)
            suffix = file_path.suffix.lower()
            
            # Get file info
            try:
                stat = file_path.stat()
                file_info = {
                    'path': str(relative_path),
                    'full_path': str(file_path),
                    'size': stat.st_size,
                    'created': stat.st_ctime,
                    'modified': stat.st_mtime,
                    'extension': suffix,
                    'name': file_path.name
                }
            except Exception as e:
                logger.warning(f"Failed to get file info for {file_path}: {e}")
                continue
            
            # Categorize based on location and extension
            categorized = False
            
            # Check if it's in a specific subdirectory
            parts = relative_path.parts
            if len(parts) > 1:
                subdir = parts[0]
                if subdir in categories:
                    categories[subdir].append(file_info)
                    categorized = True
            
            # Enhanced Manim detection - check for various Manim output patterns
            if not categorized:
                path_str = str(relative_path).lower()
                if any(pattern in path_str for pattern in [
                    'manim', 'scene', 'media', 'videos', 'images', 'tex', 'text'
                ]) and any(pattern in path_str for pattern in [
                    'manim_', 'scene_', 'media/', 'videos/', 'images/'
                ]):
                    categories['manim'].append(file_info)
                    categorized = True
            
            # If not categorized by directory, use extension
            if not categorized:
                for category, extensions in type_mappings.items():
                    if suffix in extensions:
                        # Additional Manim detection by content and path patterns
                        if category in ['videos', 'images'] and any(pattern in str(relative_path).lower() for pattern in [
                            'manim', 'scene', 'media/', 'videos/', 'images/', 'tex/', 'text/'
                        ]):
                            categories['manim'].append(file_info)
                        else:
                            categories[category].append(file_info)
                        categorized = True
                        break
            
            # If still not categorized, put in 'other'
            if not categorized:
                categories['other'].append(file_info)
        
        return categories
    
    def get_artifact_report(self) -> Dict[str, Any]:
        """Generate comprehensive artifact report."""
        categorized = self.categorize_artifacts()
        
        report = {
            'total_artifacts': sum(len(files) for files in categorized.values()),
            'categories': {},
            'recent_artifacts': [],
            'largest_artifacts': [],
            'total_size': 0
        }
        
        all_artifacts = []
        
        for category, files in categorized.items():
            if files:
                category_size = sum(f['size'] for f in files)
                report['categories'][category] = {
                    'count': len(files),
                    'size': category_size,
                    'files': files
                }
                report['total_size'] += category_size
                all_artifacts.extend(files)
        
        # Sort by modification time for recent artifacts
        if all_artifacts:
            all_artifacts.sort(key=lambda x: x['modified'], reverse=True)
            report['recent_artifacts'] = all_artifacts[:10]
            
            # Sort by size for largest artifacts
            all_artifacts.sort(key=lambda x: x['size'], reverse=True)
            report['largest_artifacts'] = all_artifacts[:10]
        
        return report
    
    def _store_execution_history(self, code: str, success: bool, error: Optional[str], 
                                execution_time: float, artifacts: List[str]):
        """Store execution in history database."""
        try:
            with sqlite3.connect(self.state_file) as conn:
                conn.execute('''
                    INSERT INTO execution_history 
                    (code, result, execution_time, memory_usage, artifacts, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    code,
                    json.dumps({'success': success, 'error': error}),
                    execution_time,
                    0,  # Memory usage tracking can be added later
                    json.dumps(artifacts),
                    time.time()
                ))
        except Exception as e:
            logger.error(f"Failed to store execution history: {e}")
    
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
        try:
            with sqlite3.connect(self.state_file) as conn:
                cursor = conn.execute('''
                    SELECT code, result, execution_time, artifacts, timestamp
                    FROM execution_history
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (limit,))
                
                history = []
                for row in cursor:
                    code, result_str, exec_time, artifacts_str, timestamp = row
                    try:
                        result = json.loads(result_str)
                        artifacts = json.loads(artifacts_str) if artifacts_str else []
                    except:
                        continue
                    
                    history.append({
                        'code': code,
                        'result': result,
                        'execution_time': exec_time,
                        'artifacts': artifacts,
                        'timestamp': timestamp
                    })
                
                return history
        except Exception as e:
            logger.error(f"Failed to get execution history: {e}")
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
        try:
            error_dir = self.artifacts_dir / "logs"
            error_dir.mkdir(exist_ok=True)
            
            error_file = error_dir / f"error_{int(time.time())}.log"
            with open(error_file, 'w') as f:
                f.write(f"Error occurred at: {time.ctime()}\n")
                f.write(f"Error type: {type(error).__name__}\n")
                f.write(f"Error message: {str(error)}\n")
                f.write(f"Session ID: {self.session_id}\n")
                f.write("\n" + "="*50 + "\n")
                f.write("Code that caused the error:\n")
                f.write("="*50 + "\n")
                f.write(code)
                f.write("\n" + "="*50 + "\n")
                f.write("Full traceback:\n")
                f.write("="*50 + "\n")
                f.write(traceback_str)
                
            logger.info(f"Error details saved to: {error_file}")
        except Exception as e:
            logger.error(f"Failed to save error details: {e}")
    
    def change_working_directory(self, path: str, temporary: bool = False) -> Dict[str, Any]:
        """
        Change the working directory with security checks and logging.
        
        Args:
            path: The new directory path
            temporary: Whether this is a temporary change (returns to default after operation)
            
        Returns:
            Dictionary containing operation result and current directory info
        """
        try:
            new_path = Path(path).resolve()
            
            # Security check through directory monitor
            self.directory_monitor.change_directory(new_path)
            
            # Change actual working directory
            original_cwd = os.getcwd()
            os.chdir(new_path)
            
            logger.info(f"Changed working directory to: {new_path}")
            
            return {
                'success': True,
                'current_directory': str(new_path),
                'previous_directory': original_cwd,
                'is_default': new_path == self.directory_monitor.default_dir,
                'is_temporary': temporary
            }
            
        except PermissionError as e:
            logger.error(f"Permission denied changing directory: {e}")
            return {
                'success': False,
                'error': str(e),
                'current_directory': os.getcwd()
            }
        except Exception as e:
            logger.error(f"Error changing directory: {e}")
            return {
                'success': False,
                'error': str(e),
                'current_directory': os.getcwd()
            }
    
    def list_directory(self, path: Optional[str] = None, include_hidden: bool = False) -> Dict[str, Any]:
        """
        List contents of a directory with security checks.
        
        Args:
            path: Directory to list (defaults to current directory)
            include_hidden: Whether to include hidden files
            
        Returns:
            Dictionary containing directory contents and metadata
        """
        try:
            target_path = Path(path) if path else Path.cwd()
            target_path = target_path.resolve()
            
            # Security check
            if not target_path.is_relative_to(self.home_dir):
                raise PermissionError(f"Cannot access directory outside home: {target_path}")
            
            if not target_path.exists():
                return {
                    'success': False,
                    'error': f"Directory does not exist: {target_path}",
                    'path': str(target_path)
                }
            
            items = []
            for item in target_path.iterdir():
                if not include_hidden and item.name.startswith('.'):
                    continue
                    
                try:
                    stat = item.stat()
                    items.append({
                        'name': item.name,
                        'type': 'directory' if item.is_dir() else 'file',
                        'size': stat.st_size if item.is_file() else None,
                        'modified': stat.st_mtime,
                        'permissions': oct(stat.st_mode)[-3:]
                    })
                except Exception as e:
                    logger.warning(f"Failed to get info for {item}: {e}")
            
            logger.info(f"Listed directory: {target_path} ({len(items)} items)")
            
            return {
                'success': True,
                'path': str(target_path),
                'items': sorted(items, key=lambda x: (x['type'], x['name'])),
                'total_items': len(items)
            }
            
        except PermissionError as e:
            logger.error(f"Permission denied listing directory: {e}")
            return {
                'success': False,
                'error': str(e),
                'path': str(target_path) if 'target_path' in locals() else path
            }
        except Exception as e:
            logger.error(f"Error listing directory: {e}")
            return {
                'success': False,
                'error': str(e),
                'path': str(target_path) if 'target_path' in locals() else path
            }
    
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
        try:
            base_path = Path(search_path) if search_path else Path.cwd()
            base_path = base_path.resolve()
            
            # Security check
            if not base_path.is_relative_to(self.home_dir):
                raise PermissionError(f"Cannot search directory outside home: {base_path}")
            
            matches = []
            for file_path in base_path.glob(pattern):
                if len(matches) >= max_results:
                    break
                    
                try:
                    stat = file_path.stat()
                    matches.append({
                        'path': str(file_path),
                        'relative_path': str(file_path.relative_to(base_path)),
                        'name': file_path.name,
                        'type': 'directory' if file_path.is_dir() else 'file',
                        'size': stat.st_size if file_path.is_file() else None,
                        'modified': stat.st_mtime
                    })
                except Exception as e:
                    logger.warning(f"Failed to get info for {file_path}: {e}")
            
            logger.info(f"Found {len(matches)} files matching pattern '{pattern}' in {base_path}")
            
            return {
                'success': True,
                'pattern': pattern,
                'search_path': str(base_path),
                'matches': matches,
                'total_matches': len(matches),
                'truncated': len(matches) >= max_results
            }
            
        except PermissionError as e:
            logger.error(f"Permission denied searching files: {e}")
            return {
                'success': False,
                'error': str(e),
                'pattern': pattern,
                'search_path': str(base_path) if 'base_path' in locals() else search_path
            }
        except Exception as e:
            logger.error(f"Error searching files: {e}")
            return {
                'success': False,
                'error': str(e),
                'pattern': pattern,
                'search_path': str(base_path) if 'base_path' in locals() else search_path
            }
    
    def reset_to_default_directory(self) -> Dict[str, Any]:
        """
        Reset working directory to the default sandbox area.
        
        Returns:
            Dictionary containing operation result
        """
        try:
            self.directory_monitor.reset_to_default()
            os.chdir(self.directory_monitor.default_dir)
            
            logger.info(f"Reset to default directory: {self.directory_monitor.default_dir}")
            
            return {
                'success': True,
                'current_directory': str(self.directory_monitor.default_dir),
                'message': 'Reset to default sandbox directory'
            }
            
        except Exception as e:
            logger.error(f"Error resetting directory: {e}")
            return {
                'success': False,
                'error': str(e),
                'current_directory': os.getcwd()
            }
    
    def get_current_directory_info(self) -> Dict[str, Any]:
        """
        Get information about the current working directory.
        
        Returns:
            Dictionary containing current directory information
        """
        try:
            current_dir = Path.cwd()
            
            return {
                'current_directory': str(current_dir),
                'default_directory': str(self.directory_monitor.default_dir),
                'home_directory': str(self.home_dir),
                'is_default': current_dir == self.directory_monitor.default_dir,
                'is_in_home': current_dir.is_relative_to(self.home_dir),
                'artifacts_directory': str(self.artifacts_dir)
            }
            
        except Exception as e:
            logger.error(f"Error getting directory info: {e}")
            return {
                'error': str(e),
                'current_directory': os.getcwd()
            }
    
    def cleanup(self):
        """Clean up resources and save state."""
        self.save_persistent_state()
        logger.info(f"Cleaned up execution context for session {self.session_id}")
