"""
Shell helper functions for stdio server tools.
"""

from __future__ import annotations

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
) -> str:
    """
    Execute a shell command safely in a controlled environment.

    Args:
        command: The shell command to execute.
        security_manager: Security manager used to validate commands.
        ctx: Execution context providing sandbox metadata.
        working_directory: Directory to run the command in.
        timeout: Maximum execution time in seconds.

    Returns:
        JSON string containing execution results, stdout, stderr, and metadata.
    """
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
