"""
MCP Tool Registry for Sandbox MCP Server.

This module handles MCP tool registration and definitions,
replacing duplicate logic from the stdio server.
"""

import io
import sys
import os
import json
import uuid
import tempfile
import shutil
import subprocess
import threading
import time
import socket
import base64
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from fastmcp import FastMCP

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Registry for MCP tools.

    This class provides centralized tool registration and management,
    replacing duplicate logic in the stdio server.
    """

    def __init__(self, mcp_server: FastMCP, execution_context: Any):
        """
        Initialize the tool registry.

        Args:
            mcp_server: FastMCP server instance.
            execution_context: ExecutionContext instance for tool operations.
        """
        self.mcp = mcp_server
        self.ctx = execution_context
        self._register_all_tools()

    def _register_all_tools(self) -> None:
        """Register all MCP tools with the server."""
        # Execution tools
        self._register_execute_tool()
        
        # Artifact management tools
        self._register_list_artifacts_tool()
        self._register_cleanup_artifacts_tool()
        self._register_backup_current_artifacts_tool()
        self._register_list_artifact_backups_tool()
        self._register_rollback_to_backup_tool()
        self._register_get_backup_info_tool()
        self._register_cleanup_artifacts_by_type_tool()
        
        # Web application tools
        self._register_start_web_app_tool()
        self._register_export_web_app_tool()
        self._register_list_web_app_exports_tool()
        self._register_get_export_details_tool()
        self._register_build_docker_image_tool()
        self._register_cleanup_web_app_export_tool()
        
        # Manim tools
        self._register_get_manim_examples_tool()
        self._register_create_manim_animation_tool()
        self._register_list_manim_animations_tool()
        self._register_cleanup_manim_animation_tool()
        
        # Package management tools
        self._register_install_package_tool()
        self._register_list_installed_packages_tool()
        
        # Shell execution tools
        self._register_shell_execute_tool()
        
        # Help and info tools
        self._register_get_execution_info_tool()
        self._register_get_comprehensive_help_tool()
        self._register_get_sandbox_recommendations_tool()

    def _register_execute_tool(self) -> None:
        """Register the execute tool."""
        @self.mcp.tool
        def execute(code: str, interactive: bool = False, web_app_type: Optional[str] = None) -> str:
            """
            Execute Python code with enhanced features.

            Args:
                code: Python code to execute
                interactive: If True, drop into interactive REPL after execution
                web_app_type: Type of web app to launch ('flask' or 'streamlit')

            Returns:
                JSON string containing execution results, artifacts, and metadata
            """
            # Delegate to execution service
            from .server.execution_helpers import execute_code_with_context
            return execute_code_with_context(
                code=code,
                interactive=interactive,
                web_app_type=web_app_type,
                ctx=self.ctx
            )

    def _register_list_artifacts_tool(self) -> None:
        """Register the list_artifacts tool."""
        @self.mcp.tool
        def list_artifacts(category_filter: Optional[str] = None) -> str:
            """
            List all artifacts in the artifacts directory.

            Args:
                category_filter: Optional filter by category (images, plots, data, etc.)

            Returns:
                JSON string with artifact listing
            """
            from .server.artifact_helpers import list_artifacts_helper
            return list_artifacts_helper(category_filter, self.ctx)

    def _register_cleanup_artifacts_tool(self) -> None:
        """Register the cleanup_artifacts tool."""
        @self.mcp.tool
        def cleanup_artifacts() -> str:
            """
            Clean up all artifacts in the current artifacts directory.

            Returns:
                JSON string with cleanup results
            """
            from .server.artifact_helpers import cleanup_artifacts_helper
            return cleanup_artifacts_helper(self.ctx)

    def _register_backup_current_artifacts_tool(self) -> None:
        """Register the backup_current_artifacts tool."""
        @self.mcp.tool
        def backup_current_artifacts(backup_name: Optional[str] = None) -> str:
            """
            Create a backup of current artifacts.

            Args:
                backup_name: Optional custom backup name

            Returns:
                JSON string with backup results
            """
            from .server.artifact_helpers import backup_current_artifacts_helper
            return backup_current_artifacts_helper(backup_name, self.ctx)

    def _register_list_artifact_backups_tool(self) -> None:
        """Register the list_artifact_backups tool."""
        @self.mcp.tool
        def list_artifact_backups() -> str:
            """
            List all artifact backups.

            Returns:
                JSON string with backup listing
            """
            from .server.artifact_helpers import list_artifact_backups_helper
            return list_artifact_backups_helper(self.ctx)

    def _register_rollback_to_backup_tool(self) -> None:
        """Register the rollback_to_backup tool."""
        @self.mcp.tool
        def rollback_to_backup(backup_name: str) -> str:
            """
            Rollback to a previous artifact backup.

            Args:
                backup_name: Name of the backup to restore

            Returns:
                JSON string with rollback results
            """
            from .server.artifact_helpers import rollback_to_backup_helper
            return rollback_to_backup_helper(backup_name, self.ctx)

    def _register_get_backup_info_tool(self) -> None:
        """Register the get_backup_info tool."""
        @self.mcp.tool
        def get_backup_info(backup_name: str) -> str:
            """
            Get detailed information about a backup.

            Args:
                backup_name: Name of the backup

            Returns:
                JSON string with backup information
            """
            from .server.artifact_helpers import get_backup_info_helper
            return get_backup_info_helper(backup_name, self.ctx)

    def _register_cleanup_artifacts_by_type_tool(self) -> None:
        """Register the cleanup_artifacts_by_type tool."""
        @self.mcp.tool
        def cleanup_artifacts_by_type(artifact_type: str) -> str:
            """
            Clean up artifacts of a specific type.

            Args:
                artifact_type: Type of artifacts to clean (images, plots, data, etc.)

            Returns:
                JSON string with cleanup results
            """
            from .server.artifact_helpers import cleanup_artifacts_by_type_helper
            return cleanup_artifacts_by_type_helper(artifact_type, self.ctx)

    def _register_start_web_app_tool(self) -> None:
        """Register the start_web_app tool."""
        @self.mcp.tool
        def start_web_app(code: str, app_type: str, port: Optional[int] = None) -> str:
            """
            Start a web application from code.

            Args:
                code: Web application code (Flask or Streamlit)
                app_type: Type of web app ('flask' or 'streamlit')
                port: Optional custom port

            Returns:
                JSON string with web app URL
            """
            from .server.web_helpers import start_web_app_helper
            return start_web_app_helper(code, app_type, port, self.ctx)

    def _register_export_web_app_tool(self) -> None:
        """Register the export_web_app tool."""
        @self.mcp.tool
        def export_web_app(code: str, app_type: str = 'flask', export_name: Optional[str] = None) -> str:
            """
            Export a web application as Docker container for persistence.

            Args:
                code: The web application code
                app_type: Type of web app ('flask' or 'streamlit')
                export_name: Optional custom name for the export

            Returns:
                JSON string with export results
            """
            from .server.web_helpers import export_web_app_helper
            return export_web_app_helper(code, app_type, export_name, self.ctx)

    def _register_list_web_app_exports_tool(self) -> None:
        """Register the list_web_app_exports tool."""
        @self.mcp.tool
        def list_web_app_exports() -> str:
            """
            List all exported web applications.

            Returns:
                JSON string with export listing
            """
            from .server.web_helpers import list_web_app_exports_helper
            return list_web_app_exports_helper(self.ctx)

    def _register_get_export_details_tool(self) -> None:
        """Register the get_export_details tool."""
        @self.mcp.tool
        def get_export_details(export_name: str) -> str:
            """
            Get detailed information about a specific web app export.

            Args:
                export_name: Name of the export to inspect

            Returns:
                JSON string with export details
            """
            from .server.web_helpers import get_export_details_helper
            return get_export_details_helper(export_name, self.ctx)

    def _register_build_docker_image_tool(self) -> None:
        """Register the build_docker_image tool."""
        @self.mcp.tool
        def build_docker_image(export_name: str) -> str:
            """
            Build Docker image for an exported web application.

            Args:
                export_name: Name of the export to build

            Returns:
                JSON string with build results
            """
            from .server.web_helpers import build_docker_image_helper
            return build_docker_image_helper(export_name, self.ctx)

    def _register_cleanup_web_app_export_tool(self) -> None:
        """Register the cleanup_web_app_export tool."""
        @self.mcp.tool
        def cleanup_web_app_export(export_name: str) -> str:
            """
            Remove an exported web application.

            Args:
                export_name: Name of the export to remove

            Returns:
                JSON string with cleanup results
            """
            from .server.web_helpers import cleanup_web_app_export_helper
            return cleanup_web_app_export_helper(export_name, self.ctx)

    def _register_get_manim_examples_tool(self) -> None:
        """Register the get_manim_examples tool."""
        @self.mcp.tool
        def get_manim_examples() -> str:
            """
            Get example Manim animation code.

            Returns:
                JSON string with example code
            """
            from .server.manim_helpers import get_manim_examples_helper
            return get_manim_examples_helper()

    def _register_create_manim_animation_tool(self) -> None:
        """Register the create_manim_animation tool."""
        @self.mcp.tool
        def create_manim_animation(code: str, quality: str = 'medium') -> str:
            """
            Create a Manim animation.

            Args:
                code: Manim animation code
                quality: Quality setting ('low', 'medium', 'high', 'fourk')

            Returns:
                JSON string with animation results
            """
            from .server.manim_helpers import create_manim_animation_helper
            return create_manim_animation_helper(code, quality, self.ctx)

    def _register_list_manim_animations_tool(self) -> None:
        """Register the list_manim_animations tool."""
        @self.mcp.tool
        def list_manim_animations() -> str:
            """
            List all Manim animations.

            Returns:
                JSON string with animation listing
            """
            from .server.manim_helpers import list_manim_animations_helper
            return list_manim_animations_helper(self.ctx)

    def _register_cleanup_manim_animation_tool(self) -> None:
        """Register the cleanup_manim_animation tool."""
        @self.mcp.tool
        def cleanup_manim_animation(animation_name: str) -> str:
            """
            Clean up a Manim animation.

            Args:
                animation_name: Name of the animation to clean up

            Returns:
                JSON string with cleanup results
            """
            from .server.manim_helpers import cleanup_manim_animation_helper
            return cleanup_manim_animation_helper(animation_name, self.ctx)

    def _register_install_package_tool(self) -> None:
        """Register the install_package tool."""
        @self.mcp.tool
        def install_package(package_name: str, version: Optional[str] = None) -> str:
            """
            Install a Python package in the virtual environment.

            Args:
                package_name: Name of the package to install
                version: Optional specific version

            Returns:
                JSON string with installation results
            """
            from .server.package_helpers import install_package_helper
            return install_package_helper(package_name, version, self.ctx)

    def _register_list_installed_packages_tool(self) -> None:
        """Register the list_installed_packages tool."""
        @self.mcp.tool
        def list_installed_packages() -> str:
            """
            List all installed packages in the virtual environment.

            Returns:
                JSON string with package listing
            """
            from .server.package_helpers import list_installed_packages_helper
            return list_installed_packages_helper(self.ctx)

    def _register_shell_execute_tool(self) -> None:
        """Register the shell_execute tool."""
        @self.mcp.tool
        def shell_execute(command: str, cwd: Optional[str] = None) -> str:
            """
            Execute a shell command in the sandbox area.

            Args:
                command: Shell command to execute
                cwd: Optional working directory

            Returns:
                JSON string with command results
            """
            from .server.shell_helpers import shell_execute_helper
            return shell_execute_helper(command, cwd, self.ctx)

    def _register_get_execution_info_tool(self) -> None:
        """Register the get_execution_info tool."""
        @self.mcp.tool
        def get_execution_info() -> str:
            """
            Get detailed information about the current execution environment.

            Returns:
                JSON string with execution environment details
            """
            from .server.info_helpers import get_execution_info_helper
            return get_execution_info_helper(self.ctx)

    def _register_get_comprehensive_help_tool(self) -> None:
        """Register the get_comprehensive_help tool."""
        @self.mcp.tool
        def get_comprehensive_help() -> str:
            """
            Get comprehensive help and usage examples for the sandbox environment.

            Returns:
                JSON string with help information
            """
            from .server.info_helpers import get_comprehensive_help_helper
            return get_comprehensive_help_helper()

    def _register_get_sandbox_recommendations_tool(self) -> None:
        """Register the get_sandbox_recommendations tool."""
        @self.mcp.tool
        def get_sandbox_recommendations() -> str:
            """
            Get recommendations for using the sandbox environment effectively.

            Returns:
                JSON string with recommendations
            """
            from .server.info_helpers import get_sandbox_recommendations_helper
            return get_sandbox_recommendations_helper()


def create_tool_registry(mcp_server: FastMCP, execution_context: Any) -> ToolRegistry:
    """
    Create and initialize a tool registry.

    Args:
        mcp_server: FastMCP server instance.
        execution_context: ExecutionContext instance.

    Returns:
        Initialized ToolRegistry instance.
    """
    return ToolRegistry(mcp_server, execution_context)
