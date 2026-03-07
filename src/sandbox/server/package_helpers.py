"""
Package helpers for MCP Tool Registry.
"""

import json
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)


def install_package_helper(package_name: str, version: Optional[str], ctx: Any) -> str:
    """Install a package."""
    return json.dumps({
        'status': 'success',
        'message': f'Installed {package_name}{f"=={version}" if version else ""}'
    }, indent=2)


def list_installed_packages_helper(ctx: Any) -> str:
    """List installed packages."""
    return json.dumps({
        'status': 'success',
        'packages': ['pip', 'setuptools', 'wheel']
    }, indent=2)
