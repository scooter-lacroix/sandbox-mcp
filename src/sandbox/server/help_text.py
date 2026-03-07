"""
Help text helpers for sandbox documentation and Manim examples.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
from typing import Any, Dict


def _ipython_available() -> bool:
    """Return True when IPython can be imported."""
    try:
        import IPython  # noqa: F401

        return True
    except ImportError:
        return False


def _check_network_access() -> Dict[str, bool]:
    """Perform lightweight connectivity checks used by help output."""
    checks = {
        "dns_resolution": False,
        "http_access": False,
        "pypi_access": False,
    }

    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3).close()
        checks["dns_resolution"] = True

        socket.create_connection(("httpbin.org", 80), timeout=3).close()
        checks["http_access"] = True

        socket.create_connection(("pypi.org", 443), timeout=3).close()
        checks["pypi_access"] = True
    except (socket.error, OSError):
        pass

    return checks


def get_manim_examples() -> str:
    """Return example Manim snippets for common animation patterns."""
    examples = {
        "simple_circle": """
from manim import *

class SimpleCircle(Scene):
    def construct(self):
        circle = Circle()
        circle.set_fill(PINK, opacity=0.5)
        self.play(Create(circle))
        self.wait(1)
""".strip(),
        "moving_square": """
from manim import *

class MovingSquare(Scene):
    def construct(self):
        square = Square()
        square.set_fill(BLUE, opacity=0.5)
        self.play(Create(square))
        self.play(square.animate.shift(RIGHT * 2))
        self.play(square.animate.shift(UP * 2))
        self.wait(1)
""".strip(),
        "text_animation": """
from manim import *

class TextAnimation(Scene):
    def construct(self):
        text = Text("Hello, Manim!")
        text.set_color(YELLOW)
        self.play(Write(text))
        self.play(text.animate.scale(1.5))
        self.wait(1)
""".strip(),
        "graph_plot": """
from manim import *

class GraphPlot(Scene):
    def construct(self):
        axes = Axes(
            x_range=[-3, 3, 1],
            y_range=[-3, 3, 1],
            x_length=6,
            y_length=6,
        )
        axes.add_coordinates()

        graph = axes.plot(lambda x: x**2, color=BLUE)
        graph_label = axes.get_graph_label(graph, label="f(x) = x^2")

        self.play(Create(axes))
        self.play(Create(graph))
        self.play(Write(graph_label))
        self.wait(1)
""".strip(),
    }

    return json.dumps(
        {
            "examples": examples,
            "usage": "Use create_manim_animation() with any of these examples to generate animations.",
        },
        indent=2,
    )


def get_sandbox_limitations(ctx: Any | None = None) -> str:
    """
    Return detailed sandbox limitations and recommendations.

    Args:
        ctx: Optional execution context with sandbox and environment metadata.
    """
    network_tests = _check_network_access()

    restricted_commands = [
        "rm",
        "rmdir",
        "sudo",
        "su",
        "chmod",
        "chown",
        "mount",
        "umount",
        "systemctl",
        "service",
        "reboot",
        "shutdown",
        "fdisk",
        "mkfs",
        "ping",
        "curl",
        "wget",
        "ssh",
        "scp",
        "rsync",
    ]

    command_availability = {
        cmd: shutil.which(cmd) is not None for cmd in restricted_commands
    }

    sandbox_area = str(getattr(ctx, "sandbox_area", "")) if ctx else None
    artifacts_dir = getattr(ctx, "artifacts_dir", None) if ctx else None
    venv_path = getattr(ctx, "venv_path", None) if ctx else None

    limitations = {
        "network_access": {
            "dns_resolution": network_tests["dns_resolution"],
            "http_access": network_tests["http_access"],
            "pypi_access": network_tests["pypi_access"],
            "description": "Network access may be restricted by firewall or security policies",
        },
        "file_system_access": {
            "sandboxed_area": sandbox_area,
            "artifacts_dir": str(artifacts_dir) if artifacts_dir else None,
            "home_directory_access": os.path.expanduser("~") != "/root",
            "description": "File system access is typically limited to the sandbox area and managed artifact locations",
        },
        "package_installation": {
            "virtual_env_available": bool(
                venv_path and getattr(venv_path, "exists", lambda: False)()
            ),
            "pip_available": bool(
                venv_path
                and getattr(venv_path, "exists", lambda: False)()
                and (venv_path / "bin" / "pip").exists()
            ),
            "network_required": True,
            "description": "Package installation requires both a virtual environment and outbound package index access",
        },
        "system_commands": {
            "restricted_commands": {
                cmd: {"available": available, "blocked": available}
                for cmd, available in command_availability.items()
            },
            "description": "Many system administration and networking commands are restricted or blocked",
        },
        "repl_functionality": {
            "ipython_available": _ipython_available(),
            "tab_completion": _ipython_available(),
            "magic_commands": _ipython_available(),
            "description": "Enhanced REPL features depend on IPython availability",
        },
    }

    return json.dumps(
        {
            "status": "success",
            "limitations": limitations,
            "recommendations": [
                'Install IPython for enhanced REPL functionality: install_package("ipython")',
                'Install common data science packages: install_package("numpy"), install_package("pandas")',
                "Use artifact management tools for persistent storage",
                "Export web applications for external deployment",
                "Use shell_execute() for safe command execution in the sandbox area",
            ],
            "message": "Sandbox limitations and recommendations provided",
        },
        indent=2,
    )


def get_comprehensive_help() -> str:
    """Return comprehensive help and usage examples for the sandbox environment."""
    help_info: Dict[str, Any] = {
        "getting_started": {
            "basic_execution": {
                "description": "Execute Python code with artifact management",
                "examples": [
                    'execute("import numpy as np; print(np.array([1, 2, 3]))")',
                    'execute("import matplotlib.pyplot as plt; plt.plot([1, 2, 3]); plt.show()")',
                    "execute(\"print('Hello, Sandbox!')\", interactive=True)",
                ],
            },
            "artifact_management": {
                "description": "Create, manage, and back up artifacts",
                "examples": [
                    "list_artifacts()",
                    'backup_current_artifacts("my_backup")',
                    "list_artifact_backups()",
                    'rollback_to_backup("backup_20240101_120000")',
                    'cleanup_artifacts_by_type("plots")',
                ],
            },
            "web_applications": {
                "description": "Create, launch, and export web applications",
                "examples": [
                    "start_web_app(\"from flask import Flask; app = Flask(__name__); @app.route('/') def hello(): return 'Hello!'\", \"flask\")",
                    'export_web_app("import streamlit as st; st.title(\'My App\'); st.write(\'Hello!\')", "streamlit", "my_app")',
                    "list_web_app_exports()",
                    'build_docker_image("my_app")',
                ],
            },
        },
        "advanced_features": {
            "manim_animations": {
                "description": "Create mathematical animations with Manim",
                "examples": [
                    "get_manim_examples()",
                    'create_manim_animation("from manim import *; class MyScene(Scene): def construct(self): circle = Circle(); self.play(Create(circle))", "medium_quality")',
                    "list_manim_animations()",
                ],
            },
            "package_management": {
                "description": "Install and manage Python packages",
                "examples": [
                    'install_package("numpy")',
                    'install_package("pandas", "1.5.0")',
                    "list_installed_packages()",
                ],
            },
            "shell_commands": {
                "description": "Execute shell commands safely",
                "examples": [
                    'shell_execute("ls -la")',
                    'shell_execute("python --version")',
                    'shell_execute("find . -name \\"*.py\\"")',
                    'shell_execute("git status", "/path/to/repo")',
                ],
            },
        },
        "troubleshooting": {
            "common_issues": {
                "import_errors": {
                    "description": "Module not found errors",
                    "solutions": [
                        "Check if package is installed: list_installed_packages()",
                        'Install missing package: install_package("package_name")',
                        "Check virtual environment: get_execution_info()",
                    ],
                },
                "network_issues": {
                    "description": "Network access blocked",
                    "solutions": [
                        "Check limitations: get_sandbox_limitations()",
                        "Use offline packages when possible",
                        "Export applications for external deployment",
                    ],
                },
                "artifact_issues": {
                    "description": "Artifacts not appearing or disappearing",
                    "solutions": [
                        "Check artifacts directory: get_execution_info()",
                        "List current artifacts: list_artifacts()",
                        "Create backup before cleanup: backup_current_artifacts()",
                    ],
                },
            }
        },
        "best_practices": [
            "Always back up important artifacts before cleanup",
            "Use descriptive names for backups and exports",
            "Check sandbox limitations before attempting network operations",
            "Use the virtual environment for package installations",
            "Export web applications for persistence beyond the sandbox session",
            "Use shell_execute() instead of os.system() for safety",
        ],
        "tool_categories": {
            "execution": ["execute", "execute_with_artifacts", "start_enhanced_repl"],
            "artifacts": [
                "list_artifacts",
                "backup_current_artifacts",
                "list_artifact_backups",
                "rollback_to_backup",
                "cleanup_artifacts_by_type",
            ],
            "web_apps": [
                "start_web_app",
                "export_web_app",
                "list_web_app_exports",
                "build_docker_image",
            ],
            "manim": [
                "create_manim_animation",
                "list_manim_animations",
                "get_manim_examples",
            ],
            "packages": ["install_package", "list_installed_packages"],
            "system": [
                "shell_execute",
                "get_execution_info",
                "get_sandbox_limitations",
            ],
            "help": ["get_comprehensive_help"],
        },
    }

    return json.dumps(help_info, indent=2)


__all__ = [
    "get_comprehensive_help",
    "get_manim_examples",
    "get_sandbox_limitations",
]
