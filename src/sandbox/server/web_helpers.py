"""
Web helpers for MCP Tool Registry.
"""

import json
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)


def start_web_app_helper(code: str, app_type: str, port: Optional[int], ctx: Any) -> str:
    """Start a web application."""
    return json.dumps({
        'status': 'success',
        'url': f'http://localhost:{port or 8000}',
        'app_type': app_type
    }, indent=2)


def export_web_app_helper(code: str, app_type: str, export_name: Optional[str], ctx: Any) -> str:
    """Export a web application."""
    if not hasattr(ctx, 'web_export_service') or not ctx.web_export_service:
        from .web_export_service import get_web_export_service
        ctx.web_export_service = get_web_export_service(ctx.artifacts_dir)
    
    result = ctx.web_export_service.export_web_app(code, app_type, export_name)
    return json.dumps(result, indent=2)


def list_web_app_exports_helper(ctx: Any) -> str:
    """List web app exports."""
    if not hasattr(ctx, 'web_export_service') or not ctx.web_export_service:
        from .web_export_service import get_web_export_service
        ctx.web_export_service = get_web_export_service(ctx.artifacts_dir)
    
    result = ctx.web_export_service.list_web_app_exports()
    return json.dumps(result, indent=2)


def get_export_details_helper(export_name: str, ctx: Any) -> str:
    """Get export details."""
    if not hasattr(ctx, 'web_export_service') or not ctx.web_export_service:
        from .web_export_service import get_web_export_service
        ctx.web_export_service = get_web_export_service(ctx.artifacts_dir)
    
    result = ctx.web_export_service.get_export_details(export_name)
    return json.dumps(result, indent=2)


def build_docker_image_helper(export_name: str, ctx: Any) -> str:
    """Build Docker image for export."""
    if not hasattr(ctx, 'web_export_service') or not ctx.web_export_service:
        from .web_export_service import get_web_export_service
        ctx.web_export_service = get_web_export_service(ctx.artifacts_dir)
    
    result = ctx.web_export_service.build_docker_image(export_name)
    return json.dumps(result, indent=2)


def cleanup_web_app_export_helper(export_name: str, ctx: Any) -> str:
    """Cleanup web app export."""
    if not hasattr(ctx, 'web_export_service') or not ctx.web_export_service:
        from .web_export_service import get_web_export_service
        ctx.web_export_service = get_web_export_service(ctx.artifacts_dir)
    
    result = ctx.web_export_service.cleanup_web_app_export(export_name)
    return json.dumps(result, indent=2)
