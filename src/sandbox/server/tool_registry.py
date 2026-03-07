"""
Tool registry for stdio MCP server tool registration.

This module centralizes MCP tool registration so the stdio server can keep
tool implementations in focused helper modules while preserving the same
public tool names and behavior.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .artifact_helpers import (
    backup_current_artifacts as backup_current_artifacts_helper,
)
from .artifact_helpers import categorize_artifacts as categorize_artifacts_helper
from .artifact_helpers import cleanup_artifacts as cleanup_artifacts_helper
from .artifact_helpers import (
    cleanup_artifacts_by_type as cleanup_artifacts_by_type_helper,
)
from .artifact_helpers import cleanup_old_backups as cleanup_old_backups_helper
from .artifact_helpers import cleanup_temp_artifacts as cleanup_temp_artifacts_helper
from .artifact_helpers import clear_cache as clear_cache_helper
from .artifact_helpers import get_artifact_report as get_artifact_report_helper
from .artifact_helpers import get_backup_details as get_backup_details_helper
from .artifact_helpers import list_artifact_backups as list_artifact_backups_helper
from .artifact_helpers import list_artifacts as list_artifacts_helper
from .artifact_helpers import rollback_to_backup as rollback_to_backup_helper
from .execution_helpers import (
    collect_artifacts,
    launch_web_app,
)
from .execution_helpers import (
    execute as execute_helper,
)
from .execution_helpers import (
    execute_with_artifacts as execute_with_artifacts_helper,
)
from .help_text import get_manim_examples
from .info_helpers import (
    get_comprehensive_help_info,
    get_sandbox_limitations_info,
)
from .info_helpers import (
    get_execution_info as get_execution_info_helper,
)
from .manim_helpers import cleanup_manim_animation as cleanup_manim_animation_helper
from .manim_helpers import create_manim_animation as create_manim_animation_helper
from .manim_helpers import list_manim_animations as list_manim_animations_helper
from .package_helpers import (
    install_package as install_package_helper,
)
from .package_helpers import list_installed_packages as list_installed_packages_helper
from .repl_helpers import (
    start_enhanced_repl as start_enhanced_repl_helper,
)
from .repl_helpers import start_repl as start_repl_helper
from .shell_helpers import shell_execute as shell_execute_helper
from .web_export_service import get_web_export_service


class ToolRegistry:
    """
    Registry that attaches stdio server tools to an MCP server instance.

    The registry keeps the server module lightweight by registering wrappers
    around helper-module functions and services.
    """

    def __init__(
        self,
        mcp: Any,
        ctx: Any,
        *,
        logger: Any,
        resource_manager: Any,
        security_manager: Any,
        persistent_context_factory: Callable[[], Any],
    ) -> None:
        self.mcp = mcp
        self.ctx = ctx
        self.logger = logger
        self.resource_manager = resource_manager
        self.security_manager = security_manager
        self.persistent_context_factory = persistent_context_factory

    def _collect_artifacts(self) -> list[dict[str, Any]]:
        return collect_artifacts(self.ctx, self.logger)

    def _launch_web_app(self, code: str, app_type: str) -> str | None:
        return launch_web_app(
            code=code,
            app_type=app_type,
            ctx=self.ctx,
            logger=self.logger,
            resource_manager=self.resource_manager,
        )

    def _web_export_service(self) -> Any:
        artifacts_dir = Path(self.ctx.create_artifacts_dir())
        return get_web_export_service(artifacts_dir)

    def register_all(self) -> None:
        """Register all stdio MCP tools."""
        self.register_execute()
        self.register_list_artifacts()
        self.register_clear_cache()
        self.register_cleanup_artifacts()
        self.register_start_repl()
        self.register_start_web_app()
        self.register_cleanup_temp_artifacts()
        self.register_shell_execute()
        self.register_create_manim_animation()
        self.register_list_manim_animations()
        self.register_cleanup_manim_animation()
        self.register_get_manim_examples()
        self.register_get_execution_info()
        self.register_get_artifact_report()
        self.register_categorize_artifacts()
        self.register_cleanup_artifacts_by_type()
        self.register_start_enhanced_repl()
        self.register_execute_with_artifacts()
        self.register_backup_current_artifacts()
        self.register_list_artifact_backups()
        self.register_rollback_to_backup()
        self.register_get_backup_details()
        self.register_cleanup_old_backups()
        self.register_export_web_app()
        self.register_list_web_app_exports()
        self.register_get_export_details()
        self.register_build_docker_image()
        self.register_cleanup_web_app_export()
        self.register_install_package()
        self.register_list_installed_packages()
        self.register_get_sandbox_limitations()
        self.register_get_comprehensive_help()

    def register_execute(self) -> None:
        @self.mcp.tool
        def execute(
            code: str,
            interactive: bool = False,
            web_app_type: str | None = None,
        ) -> str:
            return execute_helper(
                code=code,
                ctx=self.ctx,
                logger=self.logger,
                launch_web_app=self._launch_web_app,
                interactive=interactive,
                web_app_type=web_app_type,
            )

    def register_list_artifacts(self) -> None:
        @self.mcp.tool
        def list_artifacts() -> str:
            return list_artifacts_helper(self._collect_artifacts)

    def register_clear_cache(self) -> None:
        @self.mcp.tool
        def clear_cache(important_only: bool = False) -> str:
            return clear_cache_helper(self.ctx, important_only=important_only)

    def register_cleanup_artifacts(self) -> None:
        @self.mcp.tool
        def cleanup_artifacts() -> str:
            return cleanup_artifacts_helper(self.ctx)

    def register_start_repl(self) -> None:
        @self.mcp.tool
        def start_repl() -> str:
            return start_repl_helper(self.ctx)

    def register_start_web_app(self) -> None:
        @self.mcp.tool
        def start_web_app(code: str, app_type: str = "flask") -> str:
            url = self._launch_web_app(code, app_type)
            if url:
                return json.dumps(
                    {
                        "status": "success",
                        "url": url,
                        "app_type": app_type,
                        "message": f"{app_type.title()} application launched successfully",
                    },
                    indent=2,
                )
            return json.dumps(
                {
                    "status": "error",
                    "app_type": app_type,
                    "message": f"Failed to launch {app_type} application",
                },
                indent=2,
            )

    def register_cleanup_temp_artifacts(self) -> None:
        @self.mcp.tool
        def cleanup_temp_artifacts(max_age_hours: int = 24) -> str:
            return cleanup_temp_artifacts_helper(
                self.logger,
                max_age_hours=max_age_hours,
            )

    def register_shell_execute(self) -> None:
        @self.mcp.tool
        def shell_execute(
            command: str,
            working_directory: str | None = None,
            timeout: int = 30,
        ) -> str:
            return shell_execute_helper(
                command=command,
                security_manager=self.security_manager,
                ctx=self.ctx,
                working_directory=working_directory,
                timeout=timeout,
            )

    def register_create_manim_animation(self) -> None:
        @self.mcp.tool
        def create_manim_animation(
            manim_code: str,
            quality: str = "medium_quality",
        ) -> str:
            return create_manim_animation_helper(
                manim_code=manim_code,
                ctx=self.ctx,
                logger=self.logger,
                quality=quality,
            )

    def register_list_manim_animations(self) -> None:
        @self.mcp.tool
        def list_manim_animations() -> str:
            return list_manim_animations_helper(self.ctx)

    def register_cleanup_manim_animation(self) -> None:
        @self.mcp.tool
        def cleanup_manim_animation(animation_id: str) -> str:
            return cleanup_manim_animation_helper(animation_id, self.ctx)

    def register_get_manim_examples(self) -> None:
        @self.mcp.tool(name="get_manim_examples")
        def get_manim_examples_tool() -> str:
            return get_manim_examples()

    def register_get_execution_info(self) -> None:
        @self.mcp.tool
        def get_execution_info() -> str:
            return get_execution_info_helper(self.ctx)

    def register_get_artifact_report(self) -> None:
        @self.mcp.tool
        def get_artifact_report() -> str:
            return get_artifact_report_helper(
                self.ctx,
                self.persistent_context_factory,
            )

    def register_categorize_artifacts(self) -> None:
        @self.mcp.tool
        def categorize_artifacts() -> str:
            return categorize_artifacts_helper(
                self.ctx,
                self.persistent_context_factory,
            )

    def register_cleanup_artifacts_by_type(self) -> None:
        @self.mcp.tool
        def cleanup_artifacts_by_type(artifact_type: str) -> str:
            return cleanup_artifacts_by_type_helper(
                artifact_type=artifact_type,
                ctx=self.ctx,
                logger=self.logger,
                persistent_context_factory=self.persistent_context_factory,
            )

    def register_start_enhanced_repl(self) -> None:
        @self.mcp.tool
        def start_enhanced_repl() -> str:
            return start_enhanced_repl_helper(
                self.ctx,
                list_artifacts=lambda: list_artifacts_helper(self._collect_artifacts),
                backup_current_artifacts=lambda backup_name=None: (
                    backup_current_artifacts_helper(self.ctx, backup_name)
                ),
                list_artifact_backups=lambda: list_artifact_backups_helper(self.ctx),
                install_package=lambda package_name, version=None: (
                    install_package_helper(package_name, self.ctx, version)
                ),
                list_installed_packages=lambda: list_installed_packages_helper(
                    self.ctx
                ),
                get_execution_info=lambda: get_execution_info_helper(self.ctx),
                create_manim_animation=lambda manim_code: create_manim_animation_helper(
                    manim_code=manim_code,
                    ctx=self.ctx,
                    logger=self.logger,
                ),
                get_manim_examples_fn=get_manim_examples,
            )

    def register_execute_with_artifacts(self) -> None:
        @self.mcp.tool
        def execute_with_artifacts(
            code: str,
            track_artifacts: bool = True,
        ) -> str:
            return execute_with_artifacts_helper(
                code=code,
                ctx=self.ctx,
                logger=self.logger,
                persistent_context_factory=self.persistent_context_factory,
                track_artifacts=track_artifacts,
            )

    def register_backup_current_artifacts(self) -> None:
        @self.mcp.tool
        def backup_current_artifacts(backup_name: str | None = None) -> str:
            return backup_current_artifacts_helper(self.ctx, backup_name)

    def register_list_artifact_backups(self) -> None:
        @self.mcp.tool
        def list_artifact_backups() -> str:
            return list_artifact_backups_helper(self.ctx)

    def register_rollback_to_backup(self) -> None:
        @self.mcp.tool
        def rollback_to_backup(backup_name: str) -> str:
            return rollback_to_backup_helper(self.ctx, backup_name)

    def register_get_backup_details(self) -> None:
        @self.mcp.tool
        def get_backup_details(backup_name: str) -> str:
            return get_backup_details_helper(self.ctx, backup_name)

    def register_cleanup_old_backups(self) -> None:
        @self.mcp.tool
        def cleanup_old_backups(max_backups: int = 10) -> str:
            return cleanup_old_backups_helper(
                self.ctx,
                self.logger,
                max_backups=max_backups,
            )

    def register_export_web_app(self) -> None:
        @self.mcp.tool
        def export_web_app(
            code: str,
            app_type: str = "flask",
            export_name: str | None = None,
        ) -> str:
            service = self._web_export_service()
            result = service.export_web_app(
                code, app_type=app_type, export_name=export_name
            )
            return json.dumps(result, indent=2)

    def register_list_web_app_exports(self) -> None:
        @self.mcp.tool
        def list_web_app_exports() -> str:
            service = self._web_export_service()
            result = service.list_web_app_exports()
            return json.dumps(result, indent=2)

    def register_get_export_details(self) -> None:
        @self.mcp.tool
        def get_export_details(export_name: str) -> str:
            service = self._web_export_service()
            result = service.get_export_details(export_name)
            return json.dumps(result, indent=2)

    def register_build_docker_image(self) -> None:
        @self.mcp.tool
        def build_docker_image(export_name: str) -> str:
            service = self._web_export_service()
            result = service.build_docker_image(export_name)
            return json.dumps(result, indent=2)

    def register_cleanup_web_app_export(self) -> None:
        @self.mcp.tool
        def cleanup_web_app_export(export_name: str) -> str:
            service = self._web_export_service()
            result = service.cleanup_web_app_export(export_name)
            return json.dumps(result, indent=2)

    def register_install_package(self) -> None:
        @self.mcp.tool
        def install_package(package_name: str, version: str | None = None) -> str:
            return install_package_helper(package_name, self.ctx, version)

    def register_list_installed_packages(self) -> None:
        @self.mcp.tool
        def list_installed_packages() -> str:
            return list_installed_packages_helper(self.ctx)

    def register_get_sandbox_limitations(self) -> None:
        @self.mcp.tool
        def get_sandbox_limitations() -> str:
            return get_sandbox_limitations_info(self.ctx)

    def register_get_comprehensive_help(self) -> None:
        @self.mcp.tool
        def get_comprehensive_help() -> str:
            return get_comprehensive_help_info()


def create_tool_registry(
    mcp: Any,
    ctx: Any,
    *,
    logger: Any,
    resource_manager: Any,
    security_manager: Any,
    persistent_context_factory: Callable[[], Any],
) -> ToolRegistry:
    """Create a configured tool registry instance."""
    return ToolRegistry(
        mcp,
        ctx,
        logger=logger,
        resource_manager=resource_manager,
        security_manager=security_manager,
        persistent_context_factory=persistent_context_factory,
    )


__all__ = [
    "ToolRegistry",
    "create_tool_registry",
]
