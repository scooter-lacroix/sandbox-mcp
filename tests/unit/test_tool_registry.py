"""
Unit tests for stdio tool registry wrappers and helper registration.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


class FakeMCP:
    """Minimal MCP stub that records registered tool functions."""

    def __init__(self) -> None:
        self.tools = {}

    def tool(self, fn=None, **_kwargs):
        if fn is None:

            def decorator(inner):
                self.tools[inner.__name__] = inner
                return inner

            return decorator

        self.tools[fn.__name__] = fn
        return fn


@pytest.fixture
def fake_ctx(tmp_path):
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()

    ctx = SimpleNamespace(
        project_root=tmp_path,
        sandbox_area=tmp_path / "sandbox_area",
        venv_path=tmp_path / ".venv",
        artifacts_dir=artifacts_dir,
        web_servers={},
        execution_globals={"alpha": 1},
        compilation_cache={},
        cache_hits=0,
        cache_misses=0,
    )
    ctx.sandbox_area.mkdir(exist_ok=True)
    ctx.venv_path.mkdir(exist_ok=True)

    def create_artifacts_dir():
        artifacts_dir.mkdir(exist_ok=True)
        return str(artifacts_dir)

    ctx.create_artifacts_dir = create_artifacts_dir
    ctx.cleanup_artifacts = MagicMock()
    ctx.backup_artifacts = MagicMock(return_value=str(tmp_path / "backup_1"))
    ctx.list_artifact_backups = MagicMock(return_value=[])
    ctx.rollback_artifacts = MagicMock(return_value="Successfully rolled back")
    ctx.get_backup_info = MagicMock(
        return_value={"created": 1, "modified": 1, "total_size_bytes": 0}
    )
    return ctx


@pytest.fixture
def registry(fake_ctx, monkeypatch):
    from sandbox.server.tool_registry import ToolRegistry

    mcp = FakeMCP()
    logger = MagicMock()
    resource_manager = MagicMock()
    security_manager = MagicMock()
    persistent_context_factory = MagicMock()

    instance = ToolRegistry(
        mcp,
        fake_ctx,
        logger=logger,
        resource_manager=resource_manager,
        security_manager=security_manager,
        persistent_context_factory=persistent_context_factory,
    )

    monkeypatch.setattr(instance, "_web_export_service", MagicMock())
    return instance, mcp


def test_registry_initialization(registry):
    instance, mcp = registry
    assert instance.mcp is mcp
    assert instance.ctx is not None
    assert instance.logger is not None
    assert instance.resource_manager is not None
    assert instance.security_manager is not None


def test_register_all_registers_expected_tools(registry):
    instance, mcp = registry

    instance.register_all()

    expected = {
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

    assert expected.issubset(set(mcp.tools))


def test_execute_wrapper_calls_helper(registry, monkeypatch):
    instance, mcp = registry
    called = {}

    def fake_execute(**kwargs):
        called.update(kwargs)
        return '{"ok": true}'

    monkeypatch.setattr("sandbox.server.tool_registry.execute_helper", fake_execute)

    instance.register_execute()
    result = mcp.tools["execute"]("print('hi')", interactive=True, web_app_type="flask")

    assert result == '{"ok": true}'
    assert called["code"] == "print('hi')"
    assert called["ctx"] is instance.ctx
    assert called["logger"] is instance.logger
    assert called["interactive"] is True
    assert called["web_app_type"] == "flask"


def test_list_artifacts_wrapper_calls_helper(registry, monkeypatch):
    instance, mcp = registry
    sentinel = "artifact listing"

    def fake_list_artifacts(collector):
        assert callable(collector)
        return sentinel

    monkeypatch.setattr(
        "sandbox.server.tool_registry.list_artifacts_helper", fake_list_artifacts
    )

    instance.register_list_artifacts()
    assert mcp.tools["list_artifacts"]() == sentinel


def test_clear_cache_wrapper_calls_helper(registry, monkeypatch):
    instance, mcp = registry
    helper = MagicMock(return_value="cleared")
    monkeypatch.setattr("sandbox.server.tool_registry.clear_cache_helper", helper)

    instance.register_clear_cache()
    result = mcp.tools["clear_cache"](important_only=True)

    assert result == "cleared"
    helper.assert_called_once_with(instance.ctx, important_only=True)


def test_cleanup_artifacts_wrapper_calls_helper(registry, monkeypatch):
    instance, mcp = registry
    helper = MagicMock(return_value="done")
    monkeypatch.setattr("sandbox.server.tool_registry.cleanup_artifacts_helper", helper)

    instance.register_cleanup_artifacts()
    assert mcp.tools["cleanup_artifacts"]() == "done"
    helper.assert_called_once_with(instance.ctx)


def test_start_repl_wrapper_calls_helper(registry, monkeypatch):
    instance, mcp = registry
    helper = MagicMock(return_value='{"status":"repl_started"}')
    monkeypatch.setattr("sandbox.server.tool_registry.start_repl_helper", helper)

    instance.register_start_repl()
    assert json.loads(mcp.tools["start_repl"]())["status"] == "repl_started"
    helper.assert_called_once_with(instance.ctx)


def test_start_web_app_success(registry, monkeypatch):
    instance, mcp = registry
    monkeypatch.setattr(
        instance, "_launch_web_app", MagicMock(return_value="http://127.0.0.1:8000")
    )

    instance.register_start_web_app()
    payload = json.loads(mcp.tools["start_web_app"]("code", "flask"))

    assert payload["status"] == "success"
    assert payload["url"] == "http://127.0.0.1:8000"


def test_start_web_app_error(registry, monkeypatch):
    instance, mcp = registry
    monkeypatch.setattr(instance, "_launch_web_app", MagicMock(return_value=None))

    instance.register_start_web_app()
    payload = json.loads(mcp.tools["start_web_app"]("code", "flask"))

    assert payload["status"] == "error"


def test_cleanup_temp_artifacts_wrapper_calls_helper(registry, monkeypatch):
    instance, mcp = registry
    helper = MagicMock(return_value='{"cleaned_directories":1}')
    monkeypatch.setattr(
        "sandbox.server.tool_registry.cleanup_temp_artifacts_helper", helper
    )

    instance.register_cleanup_temp_artifacts()
    assert (
        json.loads(mcp.tools["cleanup_temp_artifacts"](12))["cleaned_directories"] == 1
    )
    helper.assert_called_once_with(instance.logger, max_age_hours=12)


def test_shell_execute_wrapper_calls_helper(registry, monkeypatch):
    instance, mcp = registry
    helper = MagicMock(return_value='{"return_code":0}')
    monkeypatch.setattr("sandbox.server.tool_registry.shell_execute_helper", helper)

    instance.register_shell_execute()
    payload = json.loads(mcp.tools["shell_execute"]("ls", "/tmp", 5))

    assert payload["return_code"] == 0
    helper.assert_called_once_with(
        command="ls",
        security_manager=instance.security_manager,
        ctx=instance.ctx,
        working_directory="/tmp",
        timeout=5,
    )


def test_create_manim_animation_wrapper_calls_helper(registry, monkeypatch):
    instance, mcp = registry
    helper = MagicMock(return_value='{"success": true}')
    monkeypatch.setattr(
        "sandbox.server.tool_registry.create_manim_animation_helper", helper
    )

    instance.register_create_manim_animation()
    payload = json.loads(mcp.tools["create_manim_animation"]("scene", "high_quality"))

    assert payload["success"] is True
    helper.assert_called_once_with(
        manim_code="scene",
        ctx=instance.ctx,
        logger=instance.logger,
        quality="high_quality",
    )


def test_list_manim_animations_wrapper_calls_helper(registry, monkeypatch):
    instance, mcp = registry
    helper = MagicMock(return_value='{"total_animations": 1}')
    monkeypatch.setattr(
        "sandbox.server.tool_registry.list_manim_animations_helper", helper
    )

    instance.register_list_manim_animations()
    assert json.loads(mcp.tools["list_manim_animations"]())["total_animations"] == 1
    helper.assert_called_once_with(instance.ctx)


def test_cleanup_manim_animation_wrapper_calls_helper(registry, monkeypatch):
    instance, mcp = registry
    helper = MagicMock(return_value="removed")
    monkeypatch.setattr(
        "sandbox.server.tool_registry.cleanup_manim_animation_helper", helper
    )

    instance.register_cleanup_manim_animation()
    assert mcp.tools["cleanup_manim_animation"]("abc123") == "removed"
    helper.assert_called_once_with("abc123", instance.ctx)


def test_get_execution_info_wrapper_calls_helper(registry, monkeypatch):
    instance, mcp = registry
    helper = MagicMock(return_value='{"project_root": "/tmp"}')
    monkeypatch.setattr(
        "sandbox.server.tool_registry.get_execution_info_helper", helper
    )

    instance.register_get_execution_info()
    assert json.loads(mcp.tools["get_execution_info"]())["project_root"] == "/tmp"
    helper.assert_called_once_with(instance.ctx)


def test_get_artifact_report_wrapper_calls_helper(registry, monkeypatch):
    instance, mcp = registry
    helper = MagicMock(return_value='{"status":"ok"}')
    monkeypatch.setattr(
        "sandbox.server.tool_registry.get_artifact_report_helper", helper
    )

    instance.register_get_artifact_report()
    assert json.loads(mcp.tools["get_artifact_report"]())["status"] == "ok"
    helper.assert_called_once_with(instance.ctx, instance.persistent_context_factory)


def test_categorize_artifacts_wrapper_calls_helper(registry, monkeypatch):
    instance, mcp = registry
    helper = MagicMock(return_value='{"plots": []}')
    monkeypatch.setattr(
        "sandbox.server.tool_registry.categorize_artifacts_helper", helper
    )

    instance.register_categorize_artifacts()
    assert "plots" in json.loads(mcp.tools["categorize_artifacts"]())
    helper.assert_called_once_with(instance.ctx, instance.persistent_context_factory)


def test_cleanup_artifacts_by_type_wrapper_calls_helper(registry, monkeypatch):
    instance, mcp = registry
    helper = MagicMock(return_value='{"status":"success"}')
    monkeypatch.setattr(
        "sandbox.server.tool_registry.cleanup_artifacts_by_type_helper", helper
    )

    instance.register_cleanup_artifacts_by_type()
    payload = json.loads(mcp.tools["cleanup_artifacts_by_type"]("plots"))

    assert payload["status"] == "success"
    helper.assert_called_once_with(
        artifact_type="plots",
        ctx=instance.ctx,
        logger=instance.logger,
        persistent_context_factory=instance.persistent_context_factory,
    )


def test_start_enhanced_repl_wrapper_calls_helper(registry, monkeypatch):
    instance, mcp = registry
    captured = {}

    def fake_start_enhanced_repl(ctx, **kwargs):
        captured["ctx"] = ctx
        captured["kwargs"] = kwargs
        return '{"status":"ipython_repl_started"}'

    monkeypatch.setattr(
        "sandbox.server.tool_registry.start_enhanced_repl_helper",
        fake_start_enhanced_repl,
    )

    instance.register_start_enhanced_repl()
    payload = json.loads(mcp.tools["start_enhanced_repl"]())

    assert payload["status"] == "ipython_repl_started"
    assert captured["ctx"] is instance.ctx
    assert "list_artifacts" in captured["kwargs"]
    assert "install_package" in captured["kwargs"]


def test_execute_with_artifacts_wrapper_calls_helper(registry, monkeypatch):
    instance, mcp = registry
    helper = MagicMock(return_value='{"artifact_report":{}}')
    monkeypatch.setattr(
        "sandbox.server.tool_registry.execute_with_artifacts_helper", helper
    )

    instance.register_execute_with_artifacts()
    payload = json.loads(mcp.tools["execute_with_artifacts"]("print(1)", False))

    assert payload["artifact_report"] == {}
    helper.assert_called_once_with(
        code="print(1)",
        ctx=instance.ctx,
        logger=instance.logger,
        persistent_context_factory=instance.persistent_context_factory,
        track_artifacts=False,
    )


def test_backup_current_artifacts_wrapper_calls_helper(registry, monkeypatch):
    instance, mcp = registry
    helper = MagicMock(return_value='{"status":"success"}')
    monkeypatch.setattr(
        "sandbox.server.tool_registry.backup_current_artifacts_helper", helper
    )

    instance.register_backup_current_artifacts()
    assert (
        json.loads(mcp.tools["backup_current_artifacts"]("named"))["status"]
        == "success"
    )
    helper.assert_called_once_with(instance.ctx, "named")


def test_list_artifact_backups_wrapper_calls_helper(registry, monkeypatch):
    instance, mcp = registry
    helper = MagicMock(return_value='{"backups":[]}')
    monkeypatch.setattr(
        "sandbox.server.tool_registry.list_artifact_backups_helper", helper
    )

    instance.register_list_artifact_backups()
    assert json.loads(mcp.tools["list_artifact_backups"]())["backups"] == []
    helper.assert_called_once_with(instance.ctx)


def test_rollback_to_backup_wrapper_calls_helper(registry, monkeypatch):
    instance, mcp = registry
    helper = MagicMock(return_value='{"status":"success"}')
    monkeypatch.setattr(
        "sandbox.server.tool_registry.rollback_to_backup_helper", helper
    )

    instance.register_rollback_to_backup()
    assert json.loads(mcp.tools["rollback_to_backup"]("b1"))["status"] == "success"
    helper.assert_called_once_with(instance.ctx, "b1")


def test_get_backup_details_wrapper_calls_helper(registry, monkeypatch):
    instance, mcp = registry
    helper = MagicMock(return_value='{"backup_info":{}}')
    monkeypatch.setattr(
        "sandbox.server.tool_registry.get_backup_details_helper", helper
    )

    instance.register_get_backup_details()
    assert json.loads(mcp.tools["get_backup_details"]("b1"))["backup_info"] == {}
    helper.assert_called_once_with(instance.ctx, "b1")


def test_cleanup_old_backups_wrapper_calls_helper(registry, monkeypatch):
    instance, mcp = registry
    helper = MagicMock(return_value='{"cleaned_count":2}')
    monkeypatch.setattr(
        "sandbox.server.tool_registry.cleanup_old_backups_helper", helper
    )

    instance.register_cleanup_old_backups()
    assert json.loads(mcp.tools["cleanup_old_backups"](3))["cleaned_count"] == 2
    helper.assert_called_once_with(instance.ctx, instance.logger, max_backups=3)


def test_export_web_app_wrapper_calls_service(registry):
    instance, mcp = registry
    service = MagicMock()
    service.export_web_app.return_value = {"success": True, "export_name": "demo"}
    instance._web_export_service = MagicMock(return_value=service)

    instance.register_export_web_app()
    payload = json.loads(mcp.tools["export_web_app"]("code", "flask", "demo"))

    assert payload["success"] is True
    service.export_web_app.assert_called_once_with(
        "code", app_type="flask", export_name="demo"
    )


def test_list_web_app_exports_wrapper_calls_service(registry):
    instance, mcp = registry
    service = MagicMock()
    service.list_web_app_exports.return_value = {"exports": []}
    instance._web_export_service = MagicMock(return_value=service)

    instance.register_list_web_app_exports()
    payload = json.loads(mcp.tools["list_web_app_exports"]())

    assert payload["exports"] == []
    service.list_web_app_exports.assert_called_once_with()


def test_get_export_details_wrapper_calls_service(registry):
    instance, mcp = registry
    service = MagicMock()
    service.get_export_details.return_value = {"status": "success"}
    instance._web_export_service = MagicMock(return_value=service)

    instance.register_get_export_details()
    payload = json.loads(mcp.tools["get_export_details"]("demo"))

    assert payload["status"] == "success"
    service.get_export_details.assert_called_once_with("demo")


def test_build_docker_image_wrapper_calls_service(registry):
    instance, mcp = registry
    service = MagicMock()
    service.build_docker_image.return_value = {"status": "success"}
    instance._web_export_service = MagicMock(return_value=service)

    instance.register_build_docker_image()
    payload = json.loads(mcp.tools["build_docker_image"]("demo"))

    assert payload["status"] == "success"
    service.build_docker_image.assert_called_once_with("demo")


def test_cleanup_web_app_export_wrapper_calls_service(registry):
    instance, mcp = registry
    service = MagicMock()
    service.cleanup_web_app_export.return_value = {"status": "success"}
    instance._web_export_service = MagicMock(return_value=service)

    instance.register_cleanup_web_app_export()
    payload = json.loads(mcp.tools["cleanup_web_app_export"]("demo"))

    assert payload["status"] == "success"
    service.cleanup_web_app_export.assert_called_once_with("demo")


def test_install_package_wrapper_calls_helper(registry, monkeypatch):
    instance, mcp = registry
    helper = MagicMock(return_value='{"status":"success"}')
    monkeypatch.setattr("sandbox.server.tool_registry.install_package_helper", helper)

    instance.register_install_package()
    payload = json.loads(mcp.tools["install_package"]("numpy", "1.26.0"))

    assert payload["status"] == "success"
    helper.assert_called_once_with("numpy", instance.ctx, "1.26.0")


def test_list_installed_packages_wrapper_calls_helper(registry, monkeypatch):
    instance, mcp = registry
    helper = MagicMock(return_value='{"packages":[]}')
    monkeypatch.setattr(
        "sandbox.server.tool_registry.list_installed_packages_helper", helper
    )

    instance.register_list_installed_packages()
    payload = json.loads(mcp.tools["list_installed_packages"]())

    assert payload["packages"] == []
    helper.assert_called_once_with(instance.ctx)


def test_get_sandbox_limitations_wrapper_calls_helper(registry, monkeypatch):
    instance, mcp = registry
    helper = MagicMock(return_value='{"status":"success"}')
    monkeypatch.setattr(
        "sandbox.server.tool_registry.get_sandbox_limitations_info", helper
    )

    instance.register_get_sandbox_limitations()
    payload = json.loads(mcp.tools["get_sandbox_limitations"]())

    assert payload["status"] == "success"
    helper.assert_called_once_with(instance.ctx)


def test_get_comprehensive_help_wrapper_calls_helper(registry, monkeypatch):
    instance, mcp = registry
    helper = MagicMock(return_value='{"getting_started":{}}')
    monkeypatch.setattr(
        "sandbox.server.tool_registry.get_comprehensive_help_info", helper
    )

    instance.register_get_comprehensive_help()
    payload = json.loads(mcp.tools["get_comprehensive_help"]())

    assert payload["getting_started"] == {}
    helper.assert_called_once_with()


def test_create_tool_registry_factory(fake_ctx):
    from sandbox.server.tool_registry import ToolRegistry, create_tool_registry

    mcp = FakeMCP()
    registry = create_tool_registry(
        mcp,
        fake_ctx,
        logger=MagicMock(),
        resource_manager=MagicMock(),
        security_manager=MagicMock(),
        persistent_context_factory=MagicMock(),
    )

    assert isinstance(registry, ToolRegistry)


def test_repl_start_repl_payload(fake_ctx):
    from sandbox.server.repl_helpers import start_repl

    payload = json.loads(start_repl(fake_ctx))

    assert payload["status"] == "repl_started"
    assert "alpha" in payload["globals_available"]


def test_enhanced_repl_magic_handlers(fake_ctx):
    from sandbox.server.repl_helpers import EnhancedREPL

    repl = EnhancedREPL(
        fake_ctx,
        list_artifacts=lambda: "artifacts",
        backup_current_artifacts=lambda name=None: f"backup:{name}",
        list_artifact_backups=lambda: "backups",
        install_package=lambda pkg, version=None: f"install:{pkg}:{version}",
        list_installed_packages=lambda: "packages",
        get_execution_info=lambda: "env",
        create_manim_animation=lambda code: f"manim:{code}",
        get_manim_examples_fn=lambda: "examples",
    )

    handlers = repl.build_magic_handlers()

    assert handlers.artifacts_magic("") == "artifacts"
    assert handlers.artifacts_magic("backup") == "backup:None"
    assert handlers.artifacts_magic("backup demo") == "backup:demo"
    assert handlers.artifacts_magic("list_backups") == "backups"
    assert handlers.install_magic("") == "Usage: %install package_name [version]"
    assert handlers.install_magic("numpy 1.0") == "install:numpy:1.0"
    assert handlers.packages_magic("") == "packages"
    assert handlers.env_info_magic("") == "env"
    assert handlers.manim_magic("") == "examples"
    assert handlers.manim_magic("scene code") == "manim:scene code"


def test_start_enhanced_repl_wrapper_payload(fake_ctx):
    from sandbox.server.repl_helpers import start_enhanced_repl

    payload = json.loads(
        start_enhanced_repl(
            fake_ctx,
            list_artifacts=lambda: "artifacts",
            backup_current_artifacts=lambda name=None: "backup",
            list_artifact_backups=lambda: "backups",
            install_package=lambda pkg, version=None: "install",
            list_installed_packages=lambda: "packages",
            get_execution_info=lambda: "env",
            create_manim_animation=lambda code: "manim",
            get_manim_examples_fn=lambda: "examples",
        )
    )

    assert payload["status"] in {
        "ipython_repl_started",
        "ipython_setup_failed",
        "basic_repl_started",
    }
