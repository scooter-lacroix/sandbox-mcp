from __future__ import annotations

from fastmcp import FastMCP
import io
import sys
import os
import traceback
import json
import uuid
import tempfile
import shutil
import subprocess
from .core.resource_manager import get_resource_manager
from .core.security import get_security_manager, SecurityLevel
from .core.execution_services import ExecutionContext
import threading
import time
import socket
import base64
from pathlib import Path
from typing import Dict, List, Any
import logging
from .server.catalog import SERVER_ID, SERVER_INSTRUCTIONS, register_catalog_primitives
from . import __version__

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastMCP server with explicit instructions for discovery-oriented clients.
mcp = FastMCP(
    SERVER_ID,
    instructions=SERVER_INSTRUCTIONS,
    version=__version__,
)

# Create shared execution context using core services
ctx = ExecutionContext()
# Setup environment and log configuration
ctx._setup_environment()
logger.info(f"Project root: {ctx.project_root}")
logger.info(f"Virtual env: {ctx.venv_path if ctx.venv_path.exists() else 'Not found'}")
logger.info(f"sys.executable: {sys.executable}")
logger.info(f"sys.path (first 5): {sys.path[:5]}")
logger.info(f"VIRTUAL_ENV: {os.environ.get('VIRTUAL_ENV', 'Not set')}")

resource_manager = get_resource_manager()
security_manager = get_security_manager(SecurityLevel.MEDIUM)

def monkey_patch_matplotlib():
    """Monkey patch matplotlib to save plots to artifacts directory."""
    try:
        import matplotlib
        matplotlib.use('Agg')  # Use non-interactive backend
        import matplotlib.pyplot as plt
        
        original_show = plt.show
        
        def patched_show(*args, **kwargs):
            if ctx.artifacts_dir:
                figure_path = ctx.artifacts_dir / f"plot_{uuid.uuid4().hex[:8]}.png"
                plt.savefig(figure_path, dpi=150, bbox_inches='tight')
                logger.info(f"Plot saved to: {figure_path}")
            return original_show(*args, **kwargs)
        
        plt.show = patched_show
        return True
    except ImportError:
        return False

def monkey_patch_pil():
    """Monkey patch PIL to save images to artifacts directory."""
    try:
        from PIL import Image
        
        original_show = Image.Image.show
        original_save = Image.Image.save
        
        def patched_show(self, title=None, command=None):
            if ctx.artifacts_dir:
                image_path = ctx.artifacts_dir / f"image_{uuid.uuid4().hex[:8]}.png"
                self.save(image_path)
                logger.info(f"Image saved to: {image_path}")
            return original_show(self, title, command)
        
        def patched_save(self, fp, format=None, **params):
            result = original_save(self, fp, format, **params)
            # If saving to artifacts dir, log it
            if ctx.artifacts_dir and str(fp).startswith(str(ctx.artifacts_dir)):
                logger.info(f"Image saved to artifacts: {fp}")
            return result
        
        Image.Image.show = patched_show
        Image.Image.save = patched_save
        return True
    except ImportError:
        return False

def find_free_port(start_port=8000):
    """Find a free port starting from start_port."""
    for port in range(start_port, start_port + 100):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return port
        except OSError:
            continue
    raise RuntimeError("No free ports available")

def launch_web_app(code: str, app_type: str) -> str | None:
    """Launch a web application and return the URL."""
    try:
        resource_manager.check_resource_limits()
        port = find_free_port()
        resource_manager.process_manager.cleanup_finished()
    
        if app_type == 'flask':
            # Modify Flask code to run on specific port
            modified_code = code + f"\nif __name__ == '__main__': app.run(host='127.0.0.1', port={port}, debug=False)"
        elif app_type == 'streamlit':
            # For Streamlit, we need to create a temporary file and run it
            script_path = ctx.artifacts_dir / f"streamlit_app_{uuid.uuid4().hex[:8]}.py"
            with open(script_path, 'w') as f:
                f.write(code)
            
            # Launch Streamlit in subprocess
            cmd = [sys.executable, '-m', 'streamlit', 'run', str(script_path), '--server.port', str(port), '--server.headless', 'true']
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Register process with resource manager
            process_id = resource_manager.process_manager.add_process(
                process, 
                name=f"streamlit_{port}",
                metadata={'type': 'streamlit', 'port': port}
            )
            
            # Give it time to start
            time.sleep(2)
            
            if process.poll() is None:  # Still running
                url = f"http://127.0.0.1:{port}"
                ctx.web_servers[url] = process_id
                return url
            else:
                return None
        else:
            return None
        
        if app_type == 'flask':
            # Execute the modified Flask code in a separate thread
            def run_flask():
                exec(modified_code, ctx.execution_globals)
            
            # Use resource manager for thread management
            future = resource_manager.thread_pool.submit(run_flask)
            time.sleep(1)  # Give Flask time to start
            
            url = f"http://127.0.0.1:{port}"
            return url
            
    except Exception as e:
        logger.error(f"Failed to launch web app: {e}")
        return None

def collect_artifacts() -> List[Dict[str, Any]]:
    """Collect all artifacts from the artifacts directory."""
    artifacts = []
    if not ctx.artifacts_dir or not ctx.artifacts_dir.exists():
        return artifacts
    
    for file_path in ctx.artifacts_dir.iterdir():
        if file_path.is_file():
            try:
                # Read file as base64 for embedding
                with open(file_path, 'rb') as f:
                    content = base64.b64encode(f.read()).decode('utf-8')
                
                artifacts.append({
                    'name': file_path.name,
                    'path': str(file_path),
                    'type': file_path.suffix.lower(),
                    'content_base64': content,
                    'size': file_path.stat().st_size
                })
            except Exception as e:
                logger.error(f"Error reading artifact {file_path}: {e}")
    
    return artifacts

@mcp.tool
def execute(code: str, interactive: bool = False, web_app_type: str | None = None) -> str:
    """
    Execute Python code with enhanced features:
    - Robust sys.path and venv activation
    - Module import error handling with full traceback
    - Artifact interception and storage
    - Web app launch support
    - Interactive REPL mode
    
    Args:
        code: Python code to execute
        interactive: If True, drop into interactive REPL after execution
        web_app_type: Type of web app to launch ('flask' or 'streamlit')
    
    Returns:
        JSON string containing execution results, artifacts, and metadata
    """
    # Create artifacts directory for this execution
    artifacts_dir = ctx.create_artifacts_dir()
    
    # Set up monkey patches
    matplotlib_patched = monkey_patch_matplotlib()
    pil_patched = monkey_patch_pil()
    
    # Capture stdout and stderr
    old_stdout, old_stderr = sys.stdout, sys.stderr
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    
    result = {
        'stdout': '',
        'stderr': '',
        'error': None,
        'artifacts': [],
        'web_url': None,
        'execution_info': {
            'sys_executable': sys.executable,
            'sys_path_first_3': sys.path[:3],
            'project_root': str(ctx.project_root),
            'artifacts_dir': artifacts_dir,
            'matplotlib_patched': matplotlib_patched,
            'pil_patched': pil_patched
        }
    }
    
    try:
        sys.stdout = stdout_capture
        sys.stderr = stderr_capture
        
        # Check if this is a web app
        if web_app_type in ['flask', 'streamlit']:
            url = launch_web_app(code, web_app_type)
            if url:
                result['web_url'] = url
                result['stdout'] = f"Web application launched at: {url}"
            else:
                result['stderr'] = f"Failed to launch {web_app_type} application"
        else:
            # Regular code execution
            exec(code, ctx.execution_globals)
        
        # Interactive REPL mode
        if interactive:
            result['stdout'] += "\n[Interactive mode enabled - code executed successfully]\n"
            result['stdout'] += "Note: REPL mode would be available in a real terminal session\n"
    
    except ImportError as e:
        # Enhanced import error handling
        error_trace = traceback.format_exc()
        module_name = str(e).split("'")[1] if "'" in str(e) else "unknown"
        
        error_details = {
            'type': 'ImportError',
            'message': str(e),
            'module': module_name,
            'traceback': error_trace,
            'sys_path': sys.path[:5],  # First 5 paths for debugging
            'attempted_paths': [p for p in sys.path if Path(p).exists()]
        }
        result['error'] = error_details
        result['stderr'] = f"Import Error: {e}\n\nFull traceback:\n{error_trace}"
    
    except Exception as e:
        # General exception handling
        error_trace = traceback.format_exc()
        result['error'] = {
            'type': type(e).__name__,
            'message': str(e),
            'traceback': error_trace
        }
        result['stderr'] = f"Error: {e}\n\nFull traceback:\n{error_trace}"
    
    finally:
        # Restore stdout/stderr
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        
        # Capture output
        result['stdout'] += stdout_capture.getvalue()
        result['stderr'] += stderr_capture.getvalue()
        
        # Collect artifacts
        result['artifacts'] = collect_artifacts()
    
    return json.dumps(result, indent=2)

@mcp.tool
def list_artifacts() -> str:
    """List all current artifacts."""
    artifacts = collect_artifacts()
    if not artifacts:
        return "No artifacts found."
    
    result = "Current artifacts:\n"
    for artifact in artifacts:
        result += f"- {artifact['name']} ({artifact['size']} bytes) - {artifact['type']}\n"
    
    return result

@mcp.tool
def cleanup_artifacts() -> str:
    """Clean up all artifacts and temporary files."""
    ctx.cleanup_artifacts()
    # Also cleanup web servers
    for url, process in ctx.web_servers.items():
        try:
            process.terminate()
        except:
            pass
    ctx.web_servers.clear()
    return "Artifacts and web servers cleaned up."

@mcp.tool
def start_repl() -> str:
    """Start an interactive REPL session (simulated for MCP)."""
    # In a real implementation, this would stream stdin/stdout over MCP
    # For now, we provide a simulation
    return json.dumps({
        'status': 'repl_started',
        'message': 'Interactive REPL session started (simulated)',
        'note': 'In a full implementation, this would provide streaming I/O over MCP',
        'globals_available': list(ctx.execution_globals.keys()),
        'sys_path_active': sys.path[:3]
    }, indent=2)

@mcp.tool
def start_web_app(code: str, app_type: str = "flask") -> str:
    """Launch a web application and return connection details."""
    url = launch_web_app(code, app_type)
    if url:
        return json.dumps({
            'status': 'success',
            'url': url,
            'app_type': app_type,
            'message': f'{app_type.title()} application launched successfully'
        }, indent=2)
    else:
        return json.dumps({
            'status': 'error',
            'app_type': app_type,
            'message': f'Failed to launch {app_type} application'
        }, indent=2)

@mcp.tool
def cleanup_temp_artifacts(max_age_hours: int = 24) -> str:
    """Clean up old temporary artifact directories."""
    cleaned = 0
    temp_dir = Path(tempfile.gettempdir())
    
    try:
        for item in temp_dir.glob('sandbox_artifacts_*'):
            if item.is_dir():
                # Check age
                age_hours = (time.time() - item.stat().st_mtime) / 3600
                if age_hours > max_age_hours:
                    shutil.rmtree(item, ignore_errors=True)
                    cleaned += 1
    except Exception as e:
        logger.error(f"Error during temp cleanup: {e}")
    
    return json.dumps({
        'cleaned_directories': cleaned,
        'max_age_hours': max_age_hours,
        'message': f'Cleaned {cleaned} old artifact directories'
    }, indent=2)

@mcp.tool
def shell_execute(command: str, working_directory: str | None = None, timeout: int = 30) -> str:
    """
    Execute a shell command safely in a controlled environment.
    
    Args:
        command: The shell command to execute
        working_directory: Directory to run the command in (defaults to project root)
        timeout: Maximum execution time in seconds
    
    Returns:
        JSON string containing execution results, stdout, stderr, and metadata
    """
    # Set working directory
    if working_directory is None:
        working_directory = str(ctx.project_root)
    
    # Enhanced security checks using security manager
    is_safe, violation = security_manager.check_command_security(command)
    if not is_safe:
        return json.dumps({
            'stdout': '',
            'stderr': f'Command blocked for security: {violation.message}',
            'return_code': -1,
            'error': {
                'type': 'SecurityError',
                'message': violation.message,
                'level': violation.level.value,
                'command': command
            },
            'execution_info': {
                'working_directory': working_directory,
                'timeout': timeout,
                'command_blocked': True,
                'security_violation': True
            }
        }, indent=2)
    
    result = {
        'stdout': '',
        'stderr': '',
        'return_code': 0,
        'error': None,
        'execution_info': {
            'working_directory': working_directory,
            'timeout': timeout,
            'command': command,
            'command_blocked': False
        }
    }
    
    try:
        # Execute the command with timeout
        process = subprocess.run(
            command,
            shell=True,
            cwd=working_directory,
            timeout=timeout,
            capture_output=True,
            text=True,
            env=os.environ.copy()  # Use current environment including VIRTUAL_ENV
        )
        
        result['stdout'] = process.stdout
        result['stderr'] = process.stderr
        result['return_code'] = process.returncode
        
        if process.returncode != 0:
            result['error'] = {
                'type': 'CommandError',
                'message': f'Command failed with return code {process.returncode}',
                'return_code': process.returncode
            }
            
    except subprocess.TimeoutExpired:
        result['error'] = {
            'type': 'TimeoutError',
            'message': f'Command timed out after {timeout} seconds',
            'timeout': timeout
        }
        result['stderr'] = f'Command timed out after {timeout} seconds'
        result['return_code'] = -2
        
    except Exception as e:
        result['error'] = {
            'type': type(e).__name__,
            'message': str(e),
            'traceback': traceback.format_exc()
        }
        result['stderr'] = f'Error executing command: {e}'
        result['return_code'] = -3
    
    return json.dumps(result, indent=2)

@mcp.tool
def get_execution_info() -> str:
    """Get information about the current execution environment."""
    info = {
        'project_root': str(ctx.project_root),
        'venv_path': str(ctx.venv_path),
        'venv_active': ctx.venv_path.exists(),
        'sys_executable': sys.executable,
        'sys_path_length': len(sys.path),
        'sys_path_first_5': sys.path[:5],
        'artifacts_dir': str(ctx.artifacts_dir) if ctx.artifacts_dir else None,
        'web_servers': list(ctx.web_servers.keys()),
        'global_variables': list(ctx.execution_globals.keys()),
        'virtual_env': os.environ.get('VIRTUAL_ENV'),
        'path_contains_venv': str(ctx.venv_path / 'bin') in os.environ.get('PATH', ''),
        'current_working_directory': os.getcwd(),
        'shell_available': True
    }
    return json.dumps(info, indent=2)

@mcp.tool
def get_resource_stats() -> str:
    """Get comprehensive resource usage statistics."""
    stats = resource_manager.get_resource_stats()
    return json.dumps(stats, indent=2)

@mcp.tool
def emergency_cleanup() -> str:
    """Perform emergency cleanup of all resources."""
    try:
        # Clean up finished processes
        finished = resource_manager.process_manager.cleanup_finished()
        
        # Clean up web servers
        for url, process_id in ctx.web_servers.items():
            resource_manager.process_manager.remove_process(process_id)
        ctx.web_servers.clear()
        
        # Clean up artifacts
        ctx.cleanup_artifacts()
        
        # Force garbage collection
        import gc
        gc.collect()
        
        return json.dumps({
            'status': 'success',
            'message': 'Emergency cleanup completed',
            'finished_processes': finished,
            'web_servers_cleaned': len(ctx.web_servers)
        }, indent=2)
    except Exception as e:
        return json.dumps({
            'status': 'error',
            'message': f'Emergency cleanup failed: {str(e)}'
        }, indent=2)


register_catalog_primitives(mcp)

def main():
    """Entry point for the HTTP MCP server."""
    host = os.getenv("SANDBOX_MCP_HOST", "127.0.0.1")
    port = int(os.getenv("SANDBOX_MCP_PORT", "8765"))
    mcp.run(transport="http", host=host, port=port)

if __name__ == "__main__":
    # Run FastMCP server over HTTP (Streamable HTTP transport).
    main()
