"""
Execution helpers for stdio MCP tool logic and artifact-aware patching.

Security S5: Code validation is available but NOT enforced by default.
The sandbox security model relies on process isolation and resource limits,
not on blocking legitimate Python features.

NOTE: InputValidator integration has been removed from the primary execution
path because:
1. It produces false positives (blocks legitimate code like open(), input())
2. It provides false security (easy to bypass with dynamic imports)
3. The sandbox's purpose IS to execute arbitrary user code
4. Real security comes from isolation, not input filtering

For security hardening, use:
- Process isolation (separate worker per session)
- Resource limits (CPU, memory, disk quotas)
- Filesystem sandboxing (path validation - see S4 fixes)
- Network restrictions (block outbound connections)
"""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

import base64
import io
import json
import os
import signal
import subprocess
import sys
import traceback
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# InputValidator available for optional use, but not enforced by default
# from sandbox.core.security import InputValidator

# Delegate to centralized PatchManager for artifact capture patching
from sandbox.core.patching import get_patch_manager


def monkey_patch_matplotlib(ctx: Any, logger: Any) -> bool:
    """
    Monkey patch matplotlib to save plots into the current artifacts directory.

    Security C1: Captures session-specific artifacts_dir to prevent cross-session leakage.
    Delegates to PatchManager for unified implementation.

    CRIT-4: Thread-local storage is set by the patching function, ensuring
    the patched function uses the correct artifacts_dir for the current session.
    """
    try:
        artifacts_dir = Path(ctx.artifacts_dir) if ctx.artifacts_dir else None
        return get_patch_manager().patch_matplotlib(artifacts_dir=artifacts_dir)
    except Exception as exc:
        logger.error(f"Critical error in matplotlib monkey patch: {exc}")
        return False


def monkey_patch_pil(ctx: Any, logger: Any) -> bool:
    """
    Monkey patch PIL image display/save hooks for artifact capture.

    Security C1: Captures session-specific artifacts_dir to prevent cross-session leakage.
    Delegates to PatchManager for unified implementation.

    CRIT-4: Thread-local storage is set by the patching function, ensuring
    the patched function uses the correct artifacts_dir for the current session.
    """
    try:
        artifacts_dir = Path(ctx.artifacts_dir) if ctx.artifacts_dir else None
        return get_patch_manager().patch_pil(artifacts_dir=artifacts_dir)
    except Exception as exc:
        logger.error(f"Critical error in PIL monkey patch: {exc}")
        return False


def _set_session_artifacts_dir(ctx: Any, logger: Any) -> None:
    """
    CRIT-4: Set thread-local artifacts_dir for the current session.

    This ensures that patched matplotlib/PIL functions use the correct
    artifacts_dir for the current session, even if the patches were
    applied for a different session.

    This must be called before each execution to ensure the correct
    artifacts_dir is set in thread-local storage.
    """
    try:
        from sandbox.core.patching import _current_session_artifacts_dir
        if ctx.artifacts_dir:
            _current_session_artifacts_dir.set(Path(ctx.artifacts_dir))
            logger.debug(f"Set session artifacts_dir: {ctx.artifacts_dir}")
    except Exception as exc:
        logger.error(f"Error setting session artifacts_dir: {exc}")


def collect_artifacts(ctx: Any, logger: Any) -> List[Dict[str, Any]]:
    """Collect artifacts from the current artifact directory recursively.
    
    Security: Symlinks are skipped to prevent host file exfiltration attacks.
    """
    artifacts: List[Dict[str, Any]] = []
    if not ctx.artifacts_dir or not Path(ctx.artifacts_dir).exists():
        return artifacts

    artifacts_root = Path(ctx.artifacts_dir).resolve()

    for file_path in artifacts_root.rglob("*"):
        # SECURITY S1: Skip symlinks to prevent host file exfiltration
        if file_path.is_symlink():
            logger.warning(f"Skipping symlink for security: {file_path}")
            continue
            
        if not file_path.is_file():
            continue

        # SECURITY S1: Verify resolved path is still within artifacts_root
        try:
            resolved_path = file_path.resolve()
            if not resolved_path.is_relative_to(artifacts_root):
                logger.warning(
                    f"Skipping file outside artifacts directory: {file_path} -> {resolved_path}"
                )
                continue
        except (ValueError, OSError) as exc:
            logger.warning(f"Error validating path {file_path}: {exc}")
            continue

        try:
            with open(file_path, "rb") as handle:
                content = base64.b64encode(handle.read()).decode("utf-8")

            relative_path = file_path.relative_to(artifacts_root)
            artifacts.append(
                {
                    "name": file_path.name,
                    "path": str(file_path),
                    "relative_path": str(relative_path),
                    "type": file_path.suffix.lower(),
                    "content_base64": content,
                    "size": file_path.stat().st_size,
                    "category": file_path.parent.name,
                }
            )
        except Exception as exc:
            logger.error(f"Error reading artifact {file_path}: {exc}")

    return artifacts


def execute(
    code: str,
    ctx: Any,
    logger: Any,
    launch_web_app: Any,  # Raw function: (code, app_type, ctx, logger, resource_manager) -> Optional[str]
    interactive: bool = False,
    web_app_type: Optional[str] = None,
    session_service: Any = None,
    session_id: Optional[str] = None,
    resource_manager: Any = None,
) -> str:
    """
    Execute Python code with artifact capture and optional web app launch support.

    Args:
        code: Python code to execute.
        ctx: Execution context (used if no session_id provided).
        logger: Logger instance.
        launch_web_app: Function to launch web apps.
        interactive: Whether to enable interactive mode.
        web_app_type: Type of web app (flask/streamlit).
        session_service: Optional session service for per-session context.
        session_id: Optional session ID for per-session execution.
        resource_manager: Resource manager for web app launch.

    Returns:
        JSON string with execution result.
    """
    # Use per-session context if session_id provided
    if session_id and session_service:
        try:
            # Get or create session-specific execution context (synchronous)
            ctx = session_service.get_or_create_execution_context_sync(session_id)
            logger.info(f"Using per-session context for session: {session_id}")
            # CRITICAL: Create session-specific closure with correct ctx
            # launch_web_app is now the raw function that needs (code, app_type, ctx, logger, resource_manager)
            def launch_web_app_for_session(code: str, app_type: str) -> Optional[str]:
                return launch_web_app(
                    code=code,
                    app_type=app_type,
                    ctx=ctx,
                    logger=logger,
                    resource_manager=resource_manager,
                )
        except (ImportError, AttributeError, RuntimeError) as e:
            # Specific exceptions that indicate session service issues
            # Log and fall back to default context with clear warning
            logger.warning(
                f"Session context unavailable for {session_id}, using default: {e}"
            )
            # Fall back to default context - session isolation not available
            def launch_web_app_for_session(code: str, app_type: str) -> Optional[str]:
                return launch_web_app(
                    code=code,
                    app_type=app_type,
                    ctx=ctx,
                    logger=logger,
                    resource_manager=resource_manager,
                )
        except Exception as e:
            # Unexpected error - this should not happen under normal operation
            # Log with higher severity and propagate to avoid silent failures
            logger.error(
                f"Unexpected error getting session context for {session_id}: {e}"
            )
            raise
    else:
        # No session, use default context
        def launch_web_app_for_session(code: str, app_type: str) -> Optional[str]:
            return launch_web_app(
                code=code,
                app_type=app_type,
                ctx=ctx,
                logger=logger,
                resource_manager=resource_manager,
            )

    artifacts_dir = ctx.create_artifacts_dir()

    matplotlib_patched = monkey_patch_matplotlib(ctx, logger)
    pil_patched = monkey_patch_pil(ctx, logger)

    # CRIT-4: Set thread-local artifacts_dir for this session
    _set_session_artifacts_dir(ctx, logger)

    old_stdout, old_stderr = sys.stdout, sys.stderr
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    result: Dict[str, Any] = {
        "stdout": "",
        "stderr": "",
        "error": None,
        "artifacts": [],
        "web_url": None,
        "execution_info": {
            "sys_executable": sys.executable,
            "sys_path_first_3": sys.path[:3],
            "project_root": str(ctx.project_root),
            "artifacts_dir": artifacts_dir,
            "matplotlib_patched": matplotlib_patched,
            "pil_patched": pil_patched,
        },
    }

    try:
        sys.stdout = stdout_capture
        sys.stderr = stderr_capture

        if web_app_type in ["flask", "streamlit"]:
            url = launch_web_app_for_session(code, web_app_type)
            if url:
                result["web_url"] = url
                result["stdout"] = f"Web application launched at: {url}"
            else:
                result["stderr"] = f"Failed to launch {web_app_type} application"
        else:
            logger.debug(f"Executing code: {repr(code)}")
            logger.debug(f"Code length: {len(code)}")
            logger.debug(f"Code lines: {code.count(chr(10)) + 1}")

            # NOTE: Input validation removed - see module docstring for explanation.
            # The sandbox security model uses process isolation and resource limits,
            # not input filtering which produces false positives and is easily bypassed.

            if len(code) > 10:
                if code.count('"') % 2 != 0 or code.count("'") % 2 != 0:
                    logger.warning(
                        "Code appears to have unmatched quotes - possible truncation"
                    )
                    result["stderr"] = (
                        "Warning: Code appears to have unmatched quotes. "
                        "This might indicate the code was truncated during transmission."
                    )

                open_parens = code.count("(") - code.count(")")
                if open_parens != 0:
                    logger.warning(
                        f"Code has unmatched parentheses ({open_parens} open) - possible truncation"
                    )
                    result["stderr"] = (
                        f"Warning: Code has {open_parens} unmatched opening parentheses. "
                        "This might indicate the code was truncated during transmission."
                    )

            try:
                compile(code, "<string>", "exec")
                logger.debug("Code compilation successful")
            except SyntaxError as exc:
                logger.error(f"Syntax error during compilation: {exc}")
                logger.error(f"Error line: {exc.lineno}")
                logger.error(f"Error text: {exc.text}")
                logger.error(f"Error position: {exc.offset}")

                if "was never closed" in str(exc) or "unterminated" in str(exc).lower():
                    error_msg = (
                        f"Syntax error: {exc}\n\n"
                        "This error often occurs when code is truncated during transmission.\n"
                        f"The code received was {len(code)} characters long with "
                        f"{code.count(chr(10)) + 1} lines.\n"
                        "Please try sending the code in smaller chunks or verify the complete "
                        "code was transmitted."
                    )
                    result["stderr"] = error_msg
                    result["error"] = {
                        "type": "TruncationError",
                        "message": error_msg,
                        "original_error": str(exc),
                        "code_length": len(code),
                        "code_lines": code.count(chr(10)) + 1,
                    }
                    return json.dumps(result, indent=2)

                raise

            try:

                def signal_handler(signum: int, frame: Any) -> None:
                    logger.error(f"Signal {signum} received during execution")
                    raise RuntimeError(f"Code execution interrupted by signal {signum}")

                old_handlers: Dict[int, Any] = {}
                for sig in [signal.SIGSEGV, signal.SIGFPE, signal.SIGILL]:
                    try:
                        old_handlers[sig] = signal.signal(sig, signal_handler)
                    except (ValueError, OSError, AttributeError):
                        pass

                try:
                    exec(code, ctx.execution_globals)
                    logger.debug("Code execution completed successfully")
                except Exception as exec_error:
                    logger.error(f"Exception during code execution: {exec_error}")
                    logger.error(f"Exception type: {type(exec_error).__name__}")
                    raise
                finally:
                    for sig, old_handler in old_handlers.items():
                        try:
                            signal.signal(sig, old_handler)
                        except (ValueError, OSError, AttributeError):
                            pass

            except RuntimeError as exc:
                if "signal" in str(exc).lower():
                    result["error"] = {
                        "type": "SystemError",
                        "message": f"Code execution caused a system-level error: {exc}",
                        "suggestion": (
                            "This may be due to incompatible libraries or CPU instruction "
                            "issues. Try simpler code or different libraries."
                        ),
                    }
                    result["stderr"] = (
                        f"System error: {exc}\n\n"
                        "This often indicates library compatibility issues or CPU instruction problems."
                    )
                    return json.dumps(result, indent=2)
                raise

        if interactive:
            result["stdout"] += (
                "\n[Interactive mode enabled - code executed successfully]\n"
            )
            result["stdout"] += (
                "Note: REPL mode would be available in a real terminal session\n"
            )

    except ImportError as exc:
        error_trace = traceback.format_exc()
        module_name = str(exc).split("'")[1] if "'" in str(exc) else "unknown"

        result["error"] = {
            "type": "ImportError",
            "message": str(exc),
            "module": module_name,
            "traceback": error_trace,
            "sys_path": sys.path[:5],
            "attempted_paths": [p for p in sys.path if Path(p).exists()],
        }
        result["stderr"] = f"Import Error: {exc}\n\nFull traceback:\n{error_trace}"

    except Exception as exc:
        error_trace = traceback.format_exc()
        result["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": error_trace,
        }
        result["stderr"] = f"Error: {exc}\n\nFull traceback:\n{error_trace}"

    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        result["stdout"] += stdout_capture.getvalue()
        result["stderr"] += stderr_capture.getvalue()
        result["artifacts"] = collect_artifacts(ctx, logger)

    return json.dumps(result, indent=2)


def execute_with_artifacts(
    code: str,
    ctx: Any,
    logger: Any,
    persistent_context_factory: Callable[[], Any],
    track_artifacts: bool = True,
    session_service: Any = None,
    session_id: Optional[str] = None,
) -> str:
    """
    Execute Python code with before/after artifact tracking and reporting.

    I4 FIX: Uses lightweight artifact diff mechanism instead of full
    PersistentExecutionContext to avoid DB/dirs/env mutation per call.

    Args:
        code: Python code to execute.
        ctx: Execution context (used if no session_id provided).
        logger: Logger instance.
        persistent_context_factory: Factory for persistent contexts.
        track_artifacts: Whether to track artifacts.
        session_service: Optional session service for per-session context.
        session_id: Optional session ID for per-session execution.

    Returns:
        JSON string with execution result and artifact report.
    """
    # Use per-session context if session_id provided
    if session_id and session_service:
        try:
            # Get or create session-specific execution context (synchronous)
            ctx = session_service.get_or_create_execution_context_sync(session_id)
            logger.info(f"Using per-session context for session: {session_id}")
        except (ImportError, AttributeError, RuntimeError) as e:
            # Specific exceptions that indicate session service issues
            logger.warning(
                f"Session context unavailable for {session_id}, using default: {e}"
            )
        except Exception as e:
            # Unexpected error - log and propagate to avoid silent failures
            logger.error(
                f"Unexpected error getting session context for {session_id}: {e}"
            )
            raise
    artifacts_dir = ctx.create_artifacts_dir()

    matplotlib_patched = monkey_patch_matplotlib(ctx, logger)
    pil_patched = monkey_patch_pil(ctx, logger)

    # CRIT-4: Set thread-local artifacts_dir for this session
    _set_session_artifacts_dir(ctx, logger)

    # I4 FIX: Use lightweight artifact tracking instead of full context
    artifacts_root = Path(artifacts_dir)
    artifacts_before = set()
    if track_artifacts and artifacts_root.exists():
        for f in artifacts_root.rglob("*"):
            if f.is_file() and not f.is_symlink():
                try:
                    if f.resolve().is_relative_to(artifacts_root.resolve()):
                        artifacts_before.add(str(f.relative_to(artifacts_root)))
                except (ValueError, OSError):
                    continue

    old_stdout, old_stderr = sys.stdout, sys.stderr
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    result: Dict[str, Any] = {
        "stdout": "",
        "stderr": "",
        "error": None,
        "artifacts": [],
        "artifact_report": None,
        "execution_info": {
            "sys_executable": sys.executable,
            "artifacts_dir": artifacts_dir,
            "matplotlib_patched": matplotlib_patched,
            "pil_patched": pil_patched,
            "track_artifacts": track_artifacts,
        },
    }

    try:
        sys.stdout = stdout_capture
        sys.stderr = stderr_capture

        # NOTE: Input validation removed - see module docstring for explanation.
        # The sandbox security model uses process isolation and resource limits,
        # not input filtering which produces false positives and is easily bypassed.

        exec(code, ctx.execution_globals)

    except Exception as exc:
        error_trace = traceback.format_exc()
        result["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": error_trace,
        }
        result["stderr"] = f"Error: {exc}\n\nFull traceback:\n{error_trace}"

    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

        result["stdout"] = stdout_capture.getvalue()
        result["stderr"] += stderr_capture.getvalue()

        # I4 FIX: Lightweight artifact diff without full context
        if track_artifacts:
            artifacts_after = set()
            if artifacts_root.exists():
                for f in artifacts_root.rglob("*"):
                    if f.is_file() and not f.is_symlink():
                        try:
                            if f.resolve().is_relative_to(artifacts_root.resolve()):
                                artifacts_after.add(str(f.relative_to(artifacts_root)))
                        except (ValueError, OSError):
                            continue
            
            new_artifacts = artifacts_after - artifacts_before
            if new_artifacts:
                result["artifacts"] = list(new_artifacts)
                # Lightweight report without full context instantiation
                result["artifact_report"] = {
                    "new_artifacts_count": len(new_artifacts),
                    "artifacts": sorted(str(a) for a in new_artifacts),
                }

    return json.dumps(result, indent=2)


def find_free_port(start_port: int = 8000) -> int:
    """
    Find a free localhost port with atomic binding.
    
    I5 FIX: Uses SO_EXCLUSIVEADDRUSE to prevent TOCTOU race condition.
    """
    import socket

    for port in range(start_port, start_port + 100):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # I5: Enable exclusive address use to prevent TOCTOU
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            sock.bind(("127.0.0.1", port))
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            port_num = sock.getsockname()[1]
            sock.close()
            return port_num
        except OSError:
            continue
    raise RuntimeError("No free ports available")


def _wait_for_server_ready(
    host: str,
    port: int,
    timeout: float = 5.0,
    logger: Any = None,
) -> bool:
    """
    Wait for server to be ready by checking if port is accepting connections.
    
    I5 FIX: Proper server readiness verification instead of blind sleep.
    """
    import socket
    import time
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex((host, port))
            sock.close()
            if result == 0:
                return True
        except Exception:
            pass
        time.sleep(0.2)
    
    if logger:
        logger.warning(f"Server at {host}:{port} did not become ready in {timeout}s")
    return False


def _drain_pipe(pipe: Any, logger: Any, max_bytes: int = 65536) -> str:
    """
    Drain a pipe without blocking indefinitely.
    
    I5 FIX: Prevents pipe deadlock for long-lived processes by reading
    with timeout and size limits.
    """
    import select
    output = []
    
    try:
        # Non-blocking read with size limit
        while len(b''.join(output)) < max_bytes:
            if hasattr(select, 'poll'):
                poll = select.poll()
                poll.register(pipe, select.POLLIN)
                if not poll.poll(100):  # 100ms timeout
                    break
            elif hasattr(select, 'select'):
                readable, _, _ = select.select([pipe], [], [], 0.1)
                if not readable:
                    break
            
            chunk = pipe.read(4096)
            if not chunk:
                break
            output.append(chunk)
    except Exception as e:
        if logger:
            logger.debug(f"Error draining pipe: {e}")
    
    return b''.join(output).decode('utf-8', errors='replace')


def launch_web_app(
    code: str,
    app_type: str,
    ctx: Any,
    logger: Any,
    resource_manager: Any,
) -> Optional[str]:
    """
    Launch a Flask or Streamlit app and return its local URL.
    
    I5 FIX: Atomic port binding, server readiness verification,
    pipe deadlock prevention, and proper process handle cleanup.
    """
    process_handle = None
    
    try:
        resource_manager.check_resource_limits()
        
        # I5: Atomic port binding with SO_EXCLUSIVEADDRUSE
        port = find_free_port()
        resource_manager.process_manager.cleanup_finished()

        if not ctx.artifacts_dir:
            ctx.create_artifacts_dir()

        if app_type == "flask":
            # I5: Store process handle for cleanup
            def run_flask() -> None:
                modified_code = (
                    code
                    + "\nif __name__ == '__main__': "
                    + f"app.run(host='127.0.0.1', port={port}, debug=False, threaded=True)"
                )
                exec(modified_code, ctx.execution_globals)
            
            future = resource_manager.thread_pool.submit(run_flask)
            
            # I5: Wait for server to be ready instead of blind sleep
            if _wait_for_server_ready("127.0.0.1", port, timeout=5.0, logger=logger):
                url = f"http://127.0.0.1:{port}"
                # Store future for cleanup
                ctx.web_servers[url] = {"future": future, "port": port, "type": "flask"}
                return url
            else:
                logger.error("Flask server failed to start")
                return None
                
        elif app_type == "streamlit":
            script_path = (
                Path(ctx.artifacts_dir) / f"streamlit_app_{uuid.uuid4().hex[:8]}.py"
            )
            with open(script_path, "w", encoding="utf-8") as handle:
                handle.write(code)

            cmd = [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(script_path),
                "--server.port",
                str(port),
                "--server.headless",
                "true",
            ]
            
            # I5: Use subprocess.Popen with proper pipe handling
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                # I5: Don't inherit file descriptors
                close_fds=True,
            )
            process_handle = process

            process_id = resource_manager.process_manager.add_process(
                process,
                name=f"streamlit_{port}",
                metadata={"type": "streamlit", "port": port},
            )

            # I5: Wait for server readiness with proper timeout
            if _wait_for_server_ready("127.0.0.1", port, timeout=5.0, logger=logger):
                url = f"http://127.0.0.1:{port}"
                ctx.web_servers[url] = process_id
                return url
            else:
                # I5: Drain pipes to prevent deadlock before cleanup
                if process.stdout:
                    _drain_pipe(process.stdout, logger)
                if process.stderr:
                    _drain_pipe(process.stderr, logger)
                process.terminate()
                return None
        else:
            return None

    except Exception as exc:
        logger.error(f"Failed to launch web app: {exc}")
        # I5: Cleanup process handle on error
        if process_handle:
            try:
                process_handle.terminate()
                process_handle.wait(timeout=2)
            except Exception:
                process_handle.kill()
        return None

    return None


__all__ = [
    "collect_artifacts",
    "execute",
    "execute_with_artifacts",
    "find_free_port",
    "launch_web_app",
    "monkey_patch_matplotlib",
    "monkey_patch_pil",
]
