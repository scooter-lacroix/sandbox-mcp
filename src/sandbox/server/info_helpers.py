"""
Info helper functions for stdio server tools.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from typing import Any

from .help_text import get_comprehensive_help, get_sandbox_limitations


def get_execution_info(ctx: Any) -> str:
    """Get information about the current execution environment."""
    info = {
        "project_root": str(ctx.project_root),
        "venv_path": str(ctx.venv_path),
        "venv_active": ctx.venv_path.exists(),
        "sys_executable": sys.executable,
        "sys_path_length": len(sys.path),
        "sys_path_first_5": sys.path[:5],
        "artifacts_dir": str(ctx.artifacts_dir) if ctx.artifacts_dir else None,
        "web_servers": list(ctx.web_servers.keys()),
        "global_variables": list(ctx.execution_globals.keys()),
        "virtual_env": os.environ.get("VIRTUAL_ENV"),
        "path_contains_venv": str(ctx.venv_path / "bin") in os.environ.get("PATH", ""),
        "current_working_directory": os.getcwd(),
        "shell_available": True,
        "manim_available": shutil.which("manim") is not None,
    }
    return json.dumps(info, indent=2)


def get_sandbox_limitations_info(ctx: Any) -> str:
    """Get detailed information about sandbox limitations and restrictions."""
    return get_sandbox_limitations(ctx)


def get_comprehensive_help_info() -> str:
    """Get comprehensive help and usage examples for the sandbox environment."""
    return get_comprehensive_help()


__all__ = [
    "get_comprehensive_help_info",
    "get_execution_info",
    "get_sandbox_limitations_info",
]
