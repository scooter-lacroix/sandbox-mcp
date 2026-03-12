"""
Shell helper functions for stdio server tools.
"""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

import json
import os
import subprocess
import traceback
from typing import Any, Optional


def shell_execute(
    command: str,
    security_manager: Any,
    ctx: Any,
    working_directory: Optional[str] = None,
    timeout: int = 30,
    session_service: Any = None,
    session_id: Optional[str] = None,
) -> str:
    """
    Execute a shell command safely in a controlled environment.

    Args:
        command: The shell command to execute.
        security_manager: Security manager used to validate commands.
        ctx: Execution context providing sandbox metadata (used if no session_id provided).
        working_directory: Directory to run the command in.
        timeout: Maximum execution time in seconds.
        session_service: Optional session service for per-session context.
        session_id: Optional session ID for per-session execution.

    Returns:
        JSON string containing execution results, stdout, stderr, and metadata.
    """
    # Use per-session context if session_id provided
    if session_id and session_service:
        try:
            # Get or create session-specific execution context (synchronous)
            ctx = session_service.get_or_create_execution_context_sync(session_id)
        except (ImportError, AttributeError, RuntimeError) as e:
            # Specific exceptions that indicate session service issues
            # Log and fall back to default context with clear warning
            logger.warning(
                f"Session context unavailable for {session_id}, using default: {e}"
            )
        except Exception as e:
            # Unexpected error - log with higher severity and still fail closed
            logger.error(
                f"Unexpected error getting session context for {session_id}: {e}"
            )
            # For unexpected errors, don't silently fail - let the error propagate
            # This prevents silent fallback that could mask serious issues
            raise
    if working_directory is None:
        working_directory = str(ctx.sandbox_area)

    is_safe, violation = security_manager.check_command_security(command)
    if not is_safe:
        return json.dumps(
            {
                "stdout": "",
                "stderr": f"Command blocked for security: {violation.message}",
                "return_code": -1,
                "error": {
                    "type": "SecurityError",
                    "message": violation.message,
                    "level": violation.level.value,
                    "command": command,
                },
                "execution_info": {
                    "working_directory": working_directory,
                    "timeout": timeout,
                    "command": command,
                    "command_blocked": True,
                    "security_violation": True,
                },
            },
            indent=2,
        )

    result = {
        "stdout": "",
        "stderr": "",
        "return_code": 0,
        "error": None,
        "execution_info": {
            "working_directory": working_directory,
            "timeout": timeout,
            "command": command,
            "command_blocked": False,
        },
    }

    try:
        process = subprocess.run(
            command,
            shell=True,
            cwd=working_directory,
            timeout=timeout,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

        result["stdout"] = process.stdout
        result["stderr"] = process.stderr
        result["return_code"] = process.returncode

        if process.returncode != 0:
            result["error"] = {
                "type": "CommandError",
                "message": f"Command failed with return code {process.returncode}",
                "return_code": process.returncode,
            }

    except subprocess.TimeoutExpired:
        result["error"] = {
            "type": "TimeoutError",
            "message": f"Command timed out after {timeout} seconds",
            "timeout": timeout,
        }
        result["stderr"] = f"Command timed out after {timeout} seconds"
        result["return_code"] = -2

    except Exception as exc:
        result["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        result["stderr"] = f"Error executing command: {exc}"
        result["return_code"] = -3

    return json.dumps(result, indent=2)


__all__ = ["shell_execute"]
