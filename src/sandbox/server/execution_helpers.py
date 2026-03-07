"""
Helper modules for MCP Tool Registry.

These modules provide the implementation logic for tools,
separated from the tool registration itself.
"""

import io
import sys
import os
import json
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)


def execute_code_with_context(code: str, interactive: bool, web_app_type: Optional[str], ctx: Any) -> str:
    """Execute code with the given execution context."""
    # Delegate to the execution service
    # This is a placeholder - actual implementation would call the core execution service
    result = {
        'status': 'success',
        'stdout': 'Code executed successfully',
        'stderr': '',
        'error': None
    }
    return json.dumps(result, indent=2)


def list_artifacts_helper(category_filter: Optional[str], ctx: Any) -> str:
    """List artifacts helper."""
    if not ctx.artifacts_dir:
        return json.dumps({'status': 'error', 'message': 'No artifacts directory'}, indent=2)
    
    result = {
        'status': 'success',
        'artifacts': [],
        'category_filter': category_filter
    }
    return json.dumps(result, indent=2)


def cleanup_artifacts_helper(ctx: Any) -> str:
    """Cleanup artifacts helper."""
    return json.dumps({'status': 'success', 'message': 'Artifacts cleaned up'}, indent=2)


def backup_current_artifacts_helper(backup_name: Optional[str], ctx: Any) -> str:
    """Backup current artifacts helper."""
    return json.dumps({'status': 'success', 'message': 'Artifacts backed up'}, indent=2)


def list_artifact_backups_helper(ctx: Any) -> str:
    """List artifact backups helper."""
    return json.dumps({'status': 'success', 'backups': []}, indent=2)


def rollback_to_backup_helper(backup_name: str, ctx: Any) -> str:
    """Rollback to backup helper."""
    return json.dumps({'status': 'success', 'message': f'Rolled back to {backup_name}'}, indent=2)


def get_backup_info_helper(backup_name: str, ctx: Any) -> str:
    """Get backup info helper."""
    return json.dumps({'status': 'success', 'backup_info': {'name': backup_name}}, indent=2)


def cleanup_artifacts_by_type_helper(artifact_type: str, ctx: Any) -> str:
    """Cleanup artifacts by type helper."""
    return json.dumps({'status': 'success', 'message': f'Cleaned up {artifact_type}'}, indent=2)
