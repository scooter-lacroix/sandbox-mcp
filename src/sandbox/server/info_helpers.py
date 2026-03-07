"""
Info helpers for MCP Tool Registry.
"""

import json
import logging
import sys
from typing import Any

logger = logging.getLogger(__name__)


def get_execution_info_helper(ctx: Any) -> str:
    """Get execution environment info."""
    info = {
        'status': 'success',
        'execution_info': {
            'sys_executable': sys.executable,
            'sys_path': sys.path[:5],
            'project_root': str(ctx.project_root) if hasattr(ctx, 'project_root') else 'unknown',
            'artifacts_dir': str(ctx.artifacts_dir) if hasattr(ctx, 'artifacts_dir') else None
        }
    }
    return json.dumps(info, indent=2)


def get_comprehensive_help_helper() -> str:
    """Get comprehensive help."""
    help_info = {
        'status': 'success',
        'help': {
            'getting_started': 'Use execute() to run Python code',
            'artifacts': 'Use list_artifacts() to see generated files',
            'web_apps': 'Use start_web_app() or export_web_app() for web applications'
        }
    }
    return json.dumps(help_info, indent=2)


def get_sandbox_recommendations_helper() -> str:
    """Get sandbox recommendations."""
    recommendations = {
        'status': 'success',
        'recommendations': [
            'Use artifact management for persistent storage',
            'Export web applications for deployment',
            'Use shell_execute() for safe command execution'
        ]
    }
    return json.dumps(recommendations, indent=2)
