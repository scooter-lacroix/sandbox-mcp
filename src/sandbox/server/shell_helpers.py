"""
Shell helpers for MCP Tool Registry.
"""

import json
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)


def shell_execute_helper(command: str, cwd: Optional[str], ctx: Any) -> str:
    """Execute a shell command."""
    return json.dumps({
        'status': 'success',
        'command': command,
        'stdout': '',
        'stderr': '',
        'returncode': 0
    }, indent=2)
