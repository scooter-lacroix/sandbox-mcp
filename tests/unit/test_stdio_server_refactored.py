"""
Smoke tests for the refactored stdio MCP server module.
"""

from __future__ import annotations

import asyncio

import pytest


class TestRefactoredStdioServerImports:
    """Import and module structure smoke tests."""

    def test_server_module_imports(self):
        """The refactored stdio server module should import successfully."""
        from sandbox import mcp_sandbox_server_stdio

        assert mcp_sandbox_server_stdio is not None

    def test_server_exports_core_objects(self):
        """The module should expose the expected top-level server objects."""
        from sandbox.mcp_sandbox_server_stdio import (
            ExecutionContext,
            ctx,
            main,
            mcp,
            tool_registry,
        )

        assert ExecutionContext is not None
        assert ctx is not None
        assert main is not None
        assert mcp is not None
        assert tool_registry is not None

    def test_execution_context_initializes(self):
        """ExecutionContext should still be instantiable after refactor."""
        from sandbox.mcp_sandbox_server_stdio import ExecutionContext

        context = ExecutionContext()

        assert context is not None
        assert hasattr(context, "project_root")
        assert hasattr(context, "sandbox_area")
        assert hasattr(context, "venv_path")
        assert hasattr(context, "execution_globals")
        assert hasattr(context, "create_artifacts_dir")

    def test_tool_registry_instance_exists(self):
        """The stdio server should create a central tool registry."""
        from sandbox.mcp_sandbox_server_stdio import tool_registry

        assert tool_registry is not None
        assert hasattr(tool_registry, "register_all")
        assert hasattr(tool_registry, "mcp")
        assert hasattr(tool_registry, "ctx")


class TestRefactoredStdioServerTools:
    """Smoke tests for MCP tool registration after refactor."""

    @pytest.mark.asyncio
    async def test_registered_tools_are_available(self):
        """All expected refactored tools should be registered on the MCP server."""
        from sandbox.mcp_sandbox_server_stdio import mcp

        tools = await mcp.get_tools()
        tool_names = set(tools.keys())

        expected_tools = {
            "execute",
            "list_artifacts",
            "clear_cache",
            "cleanup_artifacts",
            "start_repl",
            "start_web_app",
            "cleanup_temp_artifacts",
            "shell_execute",
            "create_manim_animation",
            "list_manim_animations",
            "cleanup_manim_animation",
            "get_execution_info",
            "get_artifact_report",
            "categorize_artifacts",
            "cleanup_artifacts_by_type",
            "start_enhanced_repl",
            "execute_with_artifacts",
            "backup_current_artifacts",
            "list_artifact_backups",
            "rollback_to_backup",
            "get_backup_details",
            "cleanup_old_backups",
            "export_web_app",
            "list_web_app_exports",
            "get_export_details",
            "build_docker_image",
            "cleanup_web_app_export",
            "install_package",
            "list_installed_packages",
            "get_sandbox_limitations",
            "get_comprehensive_help",
        }

        missing = expected_tools - tool_names
        assert not missing, f"Missing registered tools: {sorted(missing)}"

    @pytest.mark.asyncio
    async def test_registered_tool_count_is_reasonable(self):
        """The refactored server should register the full expected tool surface."""
        from sandbox.mcp_sandbox_server_stdio import mcp

        tools = await mcp.get_tools()

        assert len(tools) >= 32

    @pytest.mark.asyncio
    async def test_key_tools_can_be_looked_up(self):
        """Important tools should be individually retrievable."""
        from sandbox.mcp_sandbox_server_stdio import mcp

        execute_tool = await mcp.get_tool("execute")
        repl_tool = await mcp.get_tool("start_enhanced_repl")
        help_tool = await mcp.get_tool("get_comprehensive_help")

        assert execute_tool is not None
        assert repl_tool is not None
        assert help_tool is not None

    @pytest.mark.asyncio
    async def test_tool_descriptions_are_exposed(self):
        """Important tools should provide concise descriptions to MCP clients."""
        from sandbox.mcp_sandbox_server_stdio import mcp

        tools = await mcp.get_tools()

        assert tools["execute"].description is not None
        assert "persistent state" in tools["execute"].description
        assert tools["create_manim_animation"].description is not None
        assert "Manim" in tools["create_manim_animation"].description


class TestRefactoredStdioServerPromptsAndResources:
    """Smoke tests for prompt and resource registration."""

    @pytest.mark.asyncio
    async def test_prompts_are_registered(self):
        """Interactive templates and skills should be exposed as MCP prompts."""
        from sandbox.mcp_sandbox_server_stdio import mcp

        prompts = await mcp.get_prompts()

        expected_prompts = {
            "manim_storyboard_skill",
            "manim_scene_template",
            "sandbox_example_template",
            "sandbox_web_app_template",
        }

        assert expected_prompts.issubset(set(prompts.keys()))

    @pytest.mark.asyncio
    async def test_prompt_can_render(self):
        """The skill prompt should render a usable user-facing template."""
        from sandbox.mcp_sandbox_server_stdio import mcp

        prompts = await mcp.get_prompts()
        rendered = await prompts["manim_storyboard_skill"].render(
            {"concept": "Binary search"}
        )

        assert rendered
        assert "Concept: Binary search" in rendered[0].content.text

    @pytest.mark.asyncio
    async def test_resources_are_registered(self):
        """Catalog resources should be available for capability discovery."""
        from sandbox.mcp_sandbox_server_stdio import mcp

        resources = await mcp.get_resources()
        templates = await mcp.get_resource_templates()

        assert "sandbox://server/overview" in resources
        assert "sandbox://catalog/interfaces" in resources
        assert "sandbox://catalog/skill/{skill_name}" in templates
        assert "sandbox://catalog/template/{template_name}" in templates

    @pytest.mark.asyncio
    async def test_catalog_resource_returns_structured_content(self):
        """The server overview resource should expose a readable JSON summary."""
        from sandbox.mcp_sandbox_server_stdio import mcp

        resources = await mcp.get_resources()
        overview = await resources["sandbox://server/overview"].read()

        assert "Sandbox MCP" in overview
        assert "streamable-http" in overview

    @pytest.mark.asyncio
    async def test_template_resource_can_be_materialized(self):
        """Template resources should expand into concrete resource content."""
        from sandbox.mcp_sandbox_server_stdio import mcp

        templates = await mcp.get_resource_templates()
        template = templates["sandbox://catalog/template/{template_name}"]
        resource = await template.create_resource(
            "sandbox://catalog/template/manim_scene_template",
            {"template_name": "manim_scene_template"},
        )
        content = await resource.read()

        assert "Manim Scene Template" in content


class TestRefactoredStdioServerStartup:
    """Basic startup behavior smoke tests."""

    def test_main_invokes_mcp_run(self, monkeypatch):
        """main() should delegate to the MCP server run method."""
        from sandbox import mcp_sandbox_server_stdio as server_module

        called = {"run": False}

        def fake_run():
            called["run"] = True

        monkeypatch.setattr(server_module.mcp, "run", fake_run)

        server_module.main()

        assert called["run"] is True

    def test_mcp_server_instance_has_expected_interface(self):
        """The MCP server instance should expose the expected callable interface."""
        from sandbox.mcp_sandbox_server_stdio import mcp

        assert hasattr(mcp, "tool")
        assert hasattr(mcp, "get_tool")
        assert hasattr(mcp, "get_tools")
        assert hasattr(mcp, "run")

    def test_module_import_does_not_require_server_start(self):
        """Importing the server module should not automatically run the server."""
        from sandbox.mcp_sandbox_server_stdio import mcp

        assert mcp is not None


class TestRefactoredModuleLayout:
    """Tests that the refactored helper modules are importable."""

    def test_helper_modules_import(self):
        """Helper modules introduced by the refactor should import successfully."""
        from sandbox.server import (
            artifact_helpers,
            execution_helpers,
            help_text,
            info_helpers,
            manim_helpers,
            package_helpers,
            repl_helpers,
            shell_helpers,
            tool_registry,
        )

        assert tool_registry is not None
        assert repl_helpers is not None
        assert help_text is not None
        assert execution_helpers is not None
        assert artifact_helpers is not None
        assert manim_helpers is not None
        assert package_helpers is not None
        assert shell_helpers is not None
        assert info_helpers is not None

    def test_tool_registry_factory_imports(self):
        """The tool registry factory should remain importable."""
        from sandbox.server.tool_registry import ToolRegistry, create_tool_registry

        assert ToolRegistry is not None
        assert create_tool_registry is not None

    def test_repl_helper_exports_import(self):
        """REPL helper exports should remain importable."""
        from sandbox.server.repl_helpers import (
            EnhancedREPL,
            start_enhanced_repl,
            start_repl,
        )

        assert EnhancedREPL is not None
        assert start_repl is not None
        assert start_enhanced_repl is not None

    def test_help_text_exports_import(self):
        """Help text helper exports should remain importable."""
        from sandbox.server.help_text import (
            get_comprehensive_help,
            get_manim_examples,
            get_sandbox_limitations,
        )

        assert get_comprehensive_help is not None
        assert get_manim_examples is not None
        assert get_sandbox_limitations is not None
