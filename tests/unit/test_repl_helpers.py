"""
Unit tests for REPL helpers and help text generation.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def fake_ctx(tmp_path):
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()

    venv_path = tmp_path / ".venv"
    venv_path.mkdir()

    return SimpleNamespace(
        artifacts_dir=artifacts_dir,
        execution_globals={"alpha": 1, "beta": 2},
        venv_path=venv_path,
        sandbox_area=tmp_path / "sandbox_area",
        project_root=tmp_path,
        web_servers={},
    )


class TestHelpText:
    """Tests for help text generator functions."""

    def test_get_manim_examples_returns_expected_structure(self):
        from sandbox.server.help_text import get_manim_examples

        payload = json.loads(get_manim_examples())

        assert "examples" in payload
        assert "usage" in payload
        assert isinstance(payload["examples"], dict)
        assert "simple_circle" in payload["examples"]
        assert "moving_square" in payload["examples"]
        assert "text_animation" in payload["examples"]
        assert "graph_plot" in payload["examples"]
        assert "from manim import *" in payload["examples"]["simple_circle"]

    def test_get_comprehensive_help_returns_expected_sections(self):
        from sandbox.server.help_text import get_comprehensive_help

        payload = json.loads(get_comprehensive_help())

        assert "getting_started" in payload
        assert "advanced_features" in payload
        assert "troubleshooting" in payload
        assert "best_practices" in payload
        assert "tool_categories" in payload

        assert "basic_execution" in payload["getting_started"]
        assert "artifact_management" in payload["getting_started"]
        assert "web_applications" in payload["getting_started"]

        assert "manim_animations" in payload["advanced_features"]
        assert "package_management" in payload["advanced_features"]
        assert "shell_commands" in payload["advanced_features"]

    def test_get_comprehensive_help_contains_expected_tool_categories(self):
        from sandbox.server.help_text import get_comprehensive_help

        payload = json.loads(get_comprehensive_help())
        categories = payload["tool_categories"]

        assert "execution" in categories
        assert "artifacts" in categories
        assert "web_apps" in categories
        assert "manim" in categories
        assert "packages" in categories
        assert "system" in categories
        assert "help" in categories

        assert "execute" in categories["execution"]
        assert "list_artifacts" in categories["artifacts"]
        assert "create_manim_animation" in categories["manim"]

    def test_get_sandbox_limitations_returns_expected_sections(self, fake_ctx):
        from sandbox.server.help_text import get_sandbox_limitations

        payload = json.loads(get_sandbox_limitations(fake_ctx))

        assert payload["status"] == "success"
        assert "limitations" in payload
        assert "recommendations" in payload

        limitations = payload["limitations"]
        assert "network_access" in limitations
        assert "file_system_access" in limitations
        assert "package_installation" in limitations
        assert "system_commands" in limitations
        assert "repl_functionality" in limitations

    def test_get_sandbox_limitations_uses_context_values(self, fake_ctx):
        from sandbox.server.help_text import get_sandbox_limitations

        payload = json.loads(get_sandbox_limitations(fake_ctx))
        fs_info = payload["limitations"]["file_system_access"]

        assert fs_info["sandboxed_area"] == str(fake_ctx.sandbox_area)
        assert fs_info["artifacts_dir"] == str(fake_ctx.artifacts_dir)

    def test_get_sandbox_limitations_without_context(self):
        from sandbox.server.help_text import get_sandbox_limitations

        payload = json.loads(get_sandbox_limitations())

        assert payload["status"] == "success"
        assert payload["limitations"]["file_system_access"]["sandboxed_area"] is None


class TestBasicReplHelpers:
    """Tests for basic REPL helper functions."""

    def test_start_repl_returns_expected_payload(self, fake_ctx):
        from sandbox.server.repl_helpers import start_repl

        payload = json.loads(start_repl(fake_ctx))

        assert payload["status"] == "repl_started"
        assert "Interactive REPL session started" in payload["message"]
        assert "alpha" in payload["globals_available"]
        assert "beta" in payload["globals_available"]
        assert isinstance(payload["sys_path_active"], list)

    def test_package_status_reports_available_and_missing(self):
        from sandbox.server.repl_helpers import _package_status

        status = _package_status(["json", "definitely_missing_package_xyz"])

        assert status["json"] == "available"
        assert status["definitely_missing_package_xyz"] == "not_installed"

    def test_check_network_connectivity_returns_bool(self):
        from sandbox.server.repl_helpers import _check_network_connectivity

        result = _check_network_connectivity()
        assert isinstance(result, bool)


class TestEnhancedRepl:
    """Tests for EnhancedREPL behavior."""

    def _create_repl(self, fake_ctx, **overrides):
        from sandbox.server.repl_helpers import EnhancedREPL

        list_artifacts = overrides.get("list_artifacts", lambda: "artifacts")
        backup_current_artifacts = overrides.get(
            "backup_current_artifacts", lambda name=None: f"backup:{name}"
        )
        list_artifact_backups = overrides.get(
            "list_artifact_backups", lambda: "backups"
        )
        install_package = overrides.get(
            "install_package", lambda pkg, version=None: f"install:{pkg}:{version}"
        )
        list_installed_packages = overrides.get(
            "list_installed_packages", lambda: "packages"
        )
        get_execution_info = overrides.get("get_execution_info", lambda: "env-info")
        create_manim_animation = overrides.get(
            "create_manim_animation", lambda code: f"manim:{code}"
        )
        get_manim_examples_fn = overrides.get(
            "get_manim_examples_fn", lambda: "examples"
        )
        package_probes = overrides.get(
            "package_probes", ["json", "definitely_missing_package_xyz"]
        )

        return EnhancedREPL(
            fake_ctx,
            list_artifacts=list_artifacts,
            backup_current_artifacts=backup_current_artifacts,
            list_artifact_backups=list_artifact_backups,
            install_package=install_package,
            list_installed_packages=list_installed_packages,
            get_execution_info=get_execution_info,
            create_manim_animation=create_manim_animation,
            get_manim_examples_fn=get_manim_examples_fn,
            package_probes=package_probes,
        )

    def test_build_magic_handlers_artifacts_commands(self, fake_ctx):
        repl = self._create_repl(fake_ctx)
        handlers = repl.build_magic_handlers()

        assert handlers.artifacts_magic("") == "artifacts"
        assert handlers.artifacts_magic("backup") == "backup:None"
        assert handlers.artifacts_magic("backup demo") == "backup:demo"
        assert handlers.artifacts_magic("list_backups") == "backups"
        assert (
            handlers.artifacts_magic("unknown")
            == "Usage: %artifacts [backup [name] | list_backups]"
        )

    def test_build_magic_handlers_install_command(self, fake_ctx):
        repl = self._create_repl(fake_ctx)
        handlers = repl.build_magic_handlers()

        assert handlers.install_magic("") == "Usage: %install package_name [version]"
        assert handlers.install_magic("numpy") == "install:numpy:None"
        assert handlers.install_magic("numpy 1.26.0") == "install:numpy:1.26.0"

    def test_build_magic_handlers_packages_and_env(self, fake_ctx):
        repl = self._create_repl(fake_ctx)
        handlers = repl.build_magic_handlers()

        assert handlers.packages_magic("") == "packages"
        assert handlers.env_info_magic("") == "env-info"

    def test_build_magic_handlers_manim(self, fake_ctx):
        repl = self._create_repl(fake_ctx)
        handlers = repl.build_magic_handlers()

        assert handlers.manim_magic("") == "examples"
        assert handlers.manim_magic("scene code") == "manim:scene code"

    def test_base_metadata_contains_expected_fields(self, fake_ctx):
        repl = self._create_repl(fake_ctx)

        metadata = repl._base_metadata()

        assert "network_available" in metadata
        assert "package_status" in metadata
        assert "missing_packages" in metadata
        assert "installed_packages" in metadata
        assert "globals_available" in metadata
        assert "artifacts_dir" in metadata
        assert "virtual_env" in metadata

        assert metadata["package_status"]["json"] == "available"
        assert (
            metadata["package_status"]["definitely_missing_package_xyz"]
            == "not_installed"
        )

    def test_ipython_metadata_structure(self, fake_ctx):
        repl = self._create_repl(fake_ctx)

        metadata = repl._ipython_metadata()

        assert "available" in metadata
        assert "version" in metadata
        assert "shell_class" in metadata
        assert "error" in metadata

    def test_success_payload_contains_magic_commands(self, fake_ctx):
        repl = self._create_repl(fake_ctx)

        payload = repl._success_payload(
            ipython_version="9.0.0",
            network_available=True,
            packages_status={"json": "available"},
        )

        assert payload["status"] == "ipython_repl_started"
        assert payload["ipython_available"] is True
        assert payload["features"]["magic_commands"] is True
        assert any(
            cmd.startswith("%artifacts") for cmd in payload["available_magic_commands"]
        )

    def test_fallback_payload_contains_recommendation(self, fake_ctx):
        repl = self._create_repl(fake_ctx)

        payload = repl._fallback_payload(
            network_available=False,
            packages_status={"json": "available", "missing": "not_installed"},
        )

        assert payload["status"] == "basic_repl_started"
        assert payload["ipython_available"] is False
        assert "recommendation" in payload
        assert "IPython" in payload["recommendation"]

    def test_register_magics_calls_shell_registration(self, fake_ctx):
        repl = self._create_repl(fake_ctx)
        handlers = repl.build_magic_handlers()

        shell = MagicMock()
        repl._register_magics(shell, handlers)

        assert shell.register_magic_function.call_count == 5

    def test_configure_shell_updates_namespace(self, fake_ctx):
        repl = self._create_repl(fake_ctx)

        shell = MagicMock()
        shell.user_ns = {}
        shell.history_manager = SimpleNamespace(enabled=False)

        repl._configure_shell(shell)

        assert shell.user_ns["ctx"] is fake_ctx
        assert shell.user_ns["artifacts_dir"] == fake_ctx.artifacts_dir
        assert shell.user_ns["alpha"] == 1
        assert shell.user_ns["beta"] == 2
        assert shell.colors == "Linux"
        assert shell.confirm_exit is False
        assert shell.history_manager.enabled is True

    def test_start_returns_json_payload(self, fake_ctx):
        repl = self._create_repl(fake_ctx)

        payload = json.loads(repl.start())

        assert payload["status"] in {
            "ipython_repl_started",
            "ipython_setup_failed",
            "basic_repl_started",
        }

    def test_start_handles_internal_error(self, fake_ctx, monkeypatch):
        repl = self._create_repl(fake_ctx)

        monkeypatch.setattr(
            repl, "_ipython_metadata", MagicMock(side_effect=RuntimeError("boom"))
        )

        payload = json.loads(repl.start())

        assert payload["status"] == "error"
        assert "Failed to start enhanced REPL" in payload["message"]


class TestStartEnhancedReplWrapper:
    """Tests for the convenience wrapper function."""

    def test_start_enhanced_repl_wrapper_returns_expected_status(self, fake_ctx):
        from sandbox.server.repl_helpers import start_enhanced_repl

        payload = json.loads(
            start_enhanced_repl(
                fake_ctx,
                list_artifacts=lambda: "artifacts",
                backup_current_artifacts=lambda name=None: "backup",
                list_artifact_backups=lambda: "backups",
                install_package=lambda pkg, version=None: "install",
                list_installed_packages=lambda: "packages",
                get_execution_info=lambda: "env-info",
                create_manim_animation=lambda code: "manim",
                get_manim_examples_fn=lambda: "examples",
            )
        )

        assert payload["status"] in {
            "ipython_repl_started",
            "ipython_setup_failed",
            "basic_repl_started",
        }
