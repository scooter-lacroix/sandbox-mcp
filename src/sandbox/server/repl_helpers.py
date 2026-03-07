"""
REPL helpers with magic command support and REPL metadata.
"""

from __future__ import annotations

import json
import os
import socket
import sys
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from .help_text import get_manim_examples

DEFAULT_PACKAGE_PROBES = [
    "numpy",
    "pandas",
    "matplotlib",
    "scipy",
    "sklearn",
    "sympy",
    "requests",
    "beautifulsoup4",
    "jupyter",
    "notebook",
    "plotly",
    "seaborn",
    "opencv-python",
    "pillow",
    "tensorflow",
    "torch",
    "flask",
    "streamlit",
    "fastapi",
    "django",
    "manim",
]


def start_repl(ctx: Any) -> str:
    """Start a simulated REPL session for MCP usage."""
    return json.dumps(
        {
            "status": "repl_started",
            "message": "Interactive REPL session started (simulated)",
            "note": "In a full implementation, this would provide streaming I/O over MCP",
            "globals_available": list(getattr(ctx, "execution_globals", {}).keys()),
            "sys_path_active": sys.path[:3],
        },
        indent=2,
    )


def _check_network_connectivity() -> bool:
    """Perform a lightweight network connectivity check."""
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3).close()
        return True
    except (socket.error, OSError):
        return False


def _package_status(packages: Optional[List[str]] = None) -> Dict[str, str]:
    """Return availability status for commonly used packages."""
    package_list = packages or DEFAULT_PACKAGE_PROBES
    status: Dict[str, str] = {}

    for package in package_list:
        try:
            __import__(package.replace("-", "_"))
            status[package] = "available"
        except ImportError:
            status[package] = "not_installed"

    return status


@dataclass
class MagicCommandHandlers:
    """Collection of magic command handlers used by the enhanced REPL."""

    artifacts_magic: Callable[[str], str]
    install_magic: Callable[[str], str]
    packages_magic: Callable[[str], str]
    env_info_magic: Callable[[str], str]
    manim_magic: Callable[[str], str]


class EnhancedREPL:
    """Enhanced REPL facade with optional IPython integration and custom magics."""

    def __init__(
        self,
        ctx: Any,
        *,
        list_artifacts: Callable[[], str],
        backup_current_artifacts: Callable[[Optional[str]], str],
        list_artifact_backups: Callable[[], str],
        install_package: Callable[[str, Optional[str]], str],
        list_installed_packages: Callable[[], str],
        get_execution_info: Callable[[], str],
        create_manim_animation: Callable[[str], str],
        get_manim_examples_fn: Callable[[], str] = get_manim_examples,
        package_probes: Optional[List[str]] = None,
    ) -> None:
        self.ctx = ctx
        self._list_artifacts = list_artifacts
        self._backup_current_artifacts = backup_current_artifacts
        self._list_artifact_backups = list_artifact_backups
        self._install_package = install_package
        self._list_installed_packages = list_installed_packages
        self._get_execution_info = get_execution_info
        self._create_manim_animation = create_manim_animation
        self._get_manim_examples = get_manim_examples_fn
        self.package_probes = package_probes or DEFAULT_PACKAGE_PROBES

    def build_magic_handlers(self) -> MagicCommandHandlers:
        """Create the line-magic handlers used by the REPL."""

        def artifacts_magic(line: str) -> str:
            command = line.strip()
            if not command:
                return self._list_artifacts()
            if command == "backup":
                return self._backup_current_artifacts(None)
            if command.startswith("backup "):
                return self._backup_current_artifacts(command[7:].strip() or None)
            if command == "list_backups":
                return self._list_artifact_backups()
            return "Usage: %artifacts [backup [name] | list_backups]"

        def install_magic(line: str) -> str:
            command = line.strip()
            if not command:
                return "Usage: %install package_name [version]"
            parts = command.split()
            package_name = parts[0]
            version = parts[1] if len(parts) > 1 else None
            return self._install_package(package_name, version)

        def packages_magic(line: str) -> str:
            _ = line
            return self._list_installed_packages()

        def env_info_magic(line: str) -> str:
            _ = line
            return self._get_execution_info()

        def manim_magic(line: str) -> str:
            command = line.strip()
            if not command:
                return self._get_manim_examples()
            return self._create_manim_animation(command)

        return MagicCommandHandlers(
            artifacts_magic=artifacts_magic,
            install_magic=install_magic,
            packages_magic=packages_magic,
            env_info_magic=env_info_magic,
            manim_magic=manim_magic,
        )

    def _ipython_metadata(self) -> Dict[str, Any]:
        """Return import metadata for IPython availability."""
        try:
            import IPython  # noqa: F401
            from IPython.terminal.interactiveshell import TerminalInteractiveShell

            return {
                "available": True,
                "version": IPython.__version__,
                "shell_class": TerminalInteractiveShell,
                "error": None,
            }
        except ImportError:
            return {
                "available": False,
                "version": None,
                "shell_class": None,
                "error": None,
            }
        except Exception as exc:
            return {
                "available": False,
                "version": None,
                "shell_class": None,
                "error": str(exc),
            }

    def _base_metadata(self) -> Dict[str, Any]:
        """Build common metadata shared by all REPL modes."""
        packages_status = _package_status(self.package_probes)
        network_available = _check_network_connectivity()

        return {
            "network_available": network_available,
            "package_status": packages_status,
            "missing_packages": [
                pkg
                for pkg, status in packages_status.items()
                if status == "not_installed"
            ],
            "installed_packages": [
                pkg for pkg, status in packages_status.items() if status == "available"
            ],
            "globals_available": list(
                getattr(self.ctx, "execution_globals", {}).keys()
            ),
            "artifacts_dir": (
                str(self.ctx.artifacts_dir)
                if getattr(self.ctx, "artifacts_dir", None)
                else None
            ),
            "virtual_env": os.environ.get("VIRTUAL_ENV"),
        }

    def _register_magics(self, shell: Any, handlers: MagicCommandHandlers) -> None:
        """Register custom line magics on an IPython shell instance."""
        shell.register_magic_function(handlers.artifacts_magic, "line", "artifacts")
        shell.register_magic_function(handlers.install_magic, "line", "install")
        shell.register_magic_function(handlers.packages_magic, "line", "packages")
        shell.register_magic_function(handlers.env_info_magic, "line", "env_info")
        shell.register_magic_function(handlers.manim_magic, "line", "manim")

    def _configure_shell(self, shell: Any) -> None:
        """Configure the IPython shell with sandbox-specific defaults."""
        shell.user_ns.update(getattr(self.ctx, "execution_globals", {}))
        shell.user_ns["ctx"] = self.ctx
        shell.user_ns["artifacts_dir"] = getattr(self.ctx, "artifacts_dir", None)

        shell.colors = "Linux"
        shell.confirm_exit = False

        history_manager = getattr(shell, "history_manager", None)
        if history_manager is not None:
            history_manager.enabled = True

        try:
            import matplotlib

            matplotlib.use("Agg")
            shell.run_line_magic("matplotlib", "inline")
        except Exception:
            pass

    def _success_payload(
        self,
        *,
        ipython_version: str,
        network_available: bool,
        packages_status: Dict[str, str],
    ) -> Dict[str, Any]:
        """Build the standard success payload for IPython-backed REPL startup."""
        return {
            "status": "ipython_repl_started",
            "ipython_available": True,
            "ipython_version": ipython_version,
            "network_available": network_available,
            "features": {
                "tab_completion": True,
                "history": True,
                "magic_commands": True,
                "syntax_highlighting": True,
                "artifact_management": True,
                "manim_support": True,
                "virtual_env": self.ctx.venv_path.exists(),
                "package_installation": self.ctx.venv_path.exists(),
                "network_access": network_available,
                "custom_magics": True,
            },
            "available_magic_commands": [
                "%artifacts - List and manage artifacts",
                "%install pkg - Install packages",
                "%packages - List installed packages",
                "%env_info - Show environment information",
                "%manim [code] - Execute Manim animations",
                "%who - List variables",
                "%whos - Detailed variable info",
                "%history - Command history",
                "%time - Time execution",
                "%timeit - Benchmark code",
            ],
            "package_status": packages_status,
            "missing_packages": [
                pkg
                for pkg, status in packages_status.items()
                if status == "not_installed"
            ],
            "installed_packages": [
                pkg for pkg, status in packages_status.items() if status == "available"
            ],
            "globals_available": list(
                getattr(self.ctx, "execution_globals", {}).keys()
            ),
            "artifacts_dir": (
                str(self.ctx.artifacts_dir)
                if getattr(self.ctx, "artifacts_dir", None)
                else None
            ),
            "virtual_env": os.environ.get("VIRTUAL_ENV"),
            "shell_instance": "TerminalInteractiveShell configured",
            "message": (
                f"IPython {ipython_version} REPL started with custom magic commands "
                "and artifact management"
            ),
        }

    def _fallback_payload(
        self,
        *,
        network_available: bool,
        packages_status: Dict[str, str],
    ) -> Dict[str, Any]:
        """Build the fallback response when IPython is unavailable."""
        return {
            "status": "basic_repl_started",
            "ipython_available": False,
            "ipython_version": None,
            "network_available": network_available,
            "features": {
                "tab_completion": False,
                "history": False,
                "magic_commands": False,
                "syntax_highlighting": False,
                "artifact_management": True,
                "manim_support": True,
                "virtual_env": self.ctx.venv_path.exists(),
                "package_installation": self.ctx.venv_path.exists(),
                "network_access": network_available,
            },
            "available_commands": [
                "Use execute() function to run Python code",
                "Use install_package() to install packages",
                "Use list_artifacts() to manage artifacts",
                "Use get_execution_info() for environment info",
            ],
            "package_status": packages_status,
            "missing_packages": [
                pkg
                for pkg, status in packages_status.items()
                if status == "not_installed"
            ],
            "installed_packages": [
                pkg for pkg, status in packages_status.items() if status == "available"
            ],
            "globals_available": list(
                getattr(self.ctx, "execution_globals", {}).keys()
            ),
            "artifacts_dir": (
                str(self.ctx.artifacts_dir)
                if getattr(self.ctx, "artifacts_dir", None)
                else None
            ),
            "virtual_env": os.environ.get("VIRTUAL_ENV"),
            "recommendation": 'Install IPython for enhanced REPL: install_package("ipython")',
            "message": (
                "Basic REPL info provided. IPython not available. "
                f"Network: {'available' if network_available else 'blocked'}, "
                f"Packages: {len([p for p in packages_status.values() if p == 'available'])}/"
                f"{len(packages_status)} available"
            ),
        }

    def start(self) -> str:
        """Start the enhanced REPL and return structured metadata."""
        try:
            ipython = self._ipython_metadata()
            base = self._base_metadata()
            handlers = self.build_magic_handlers()

            if ipython["available"] and ipython["shell_class"] is not None:
                try:
                    shell = ipython["shell_class"].instance()
                    self._configure_shell(shell)
                    self._register_magics(shell, handlers)

                    payload = self._success_payload(
                        ipython_version=ipython["version"],
                        network_available=base["network_available"],
                        packages_status=base["package_status"],
                    )
                    return json.dumps(payload, indent=2)
                except Exception as exc:
                    return json.dumps(
                        {
                            "status": "ipython_setup_failed",
                            "ipython_available": True,
                            "ipython_version": ipython["version"],
                            "error": str(exc),
                            "message": (
                                "IPython available but setup failed: "
                                f"{exc}. Falling back to basic info."
                            ),
                        },
                        indent=2,
                    )

            return json.dumps(
                self._fallback_payload(
                    network_available=base["network_available"],
                    packages_status=base["package_status"],
                ),
                indent=2,
            )

        except Exception as exc:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Failed to start enhanced REPL: {exc}",
                },
                indent=2,
            )


def start_enhanced_repl(
    ctx: Any,
    *,
    list_artifacts: Callable[[], str],
    backup_current_artifacts: Callable[[Optional[str]], str],
    list_artifact_backups: Callable[[], str],
    install_package: Callable[[str, Optional[str]], str],
    list_installed_packages: Callable[[], str],
    get_execution_info: Callable[[], str],
    create_manim_animation: Callable[[str], str],
    get_manim_examples_fn: Callable[[], str] = get_manim_examples,
) -> str:
    """Convenience wrapper for starting the enhanced REPL."""
    repl = EnhancedREPL(
        ctx,
        list_artifacts=list_artifacts,
        backup_current_artifacts=backup_current_artifacts,
        list_artifact_backups=list_artifact_backups,
        install_package=install_package,
        list_installed_packages=list_installed_packages,
        get_execution_info=get_execution_info,
        create_manim_animation=create_manim_animation,
        get_manim_examples_fn=get_manim_examples_fn,
    )
    return repl.start()


__all__ = [
    "EnhancedREPL",
    "MagicCommandHandlers",
    "start_enhanced_repl",
    "start_repl",
]
