"""
Package helper functions for stdio server tools.
"""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List


def _network_available(
    host: str = "pypi.org", port: int = 443, timeout: int = 5
) -> bool:
    """Return True when outbound network access is available for package installation."""
    try:
        socket.create_connection((host, port), timeout=timeout).close()
        return True
    except (socket.error, OSError):
        return False


def install_package(package_name: str, ctx: Any, version: str | None = None) -> str:
    """
    Install a Python package into the configured virtual environment using uv or pip.

    Args:
        package_name: Name of the package to install.
        ctx: Execution context providing project and virtualenv metadata.
        version: Optional exact version string.

    Returns:
        JSON string with installation results and fallback attempt details.
    """
    if not package_name or not package_name.strip():
        return json.dumps(
            {
                "status": "error",
                "message": "Package name must be a non-empty string.",
            },
            indent=2,
        )

    if not ctx.venv_path.exists():
        return json.dumps(
            {
                "status": "error",
                "message": "Virtual environment not found. Cannot install packages.",
            },
            indent=2,
        )

    if not _network_available():
        return json.dumps(
            {
                "status": "error",
                "message": "Network access blocked. Cannot install packages from PyPI.",
            },
            indent=2,
        )

    package_spec = f"{package_name}=={version}" if version else package_name

    uv_executable = shutil.which("uv")
    pip_executable = Path(ctx.venv_path) / "bin" / "pip"
    python3_executable = shutil.which("python3") or sys.executable

    installation_methods: List[Dict[str, Any]] = []

    if uv_executable:
        installation_methods.append(
            {
                "tool": "uv add",
                "command": [uv_executable, "add", package_spec],
                "cwd": str(ctx.project_root),
            }
        )
        installation_methods.append(
            {
                "tool": "uv pip",
                "command": [uv_executable, "pip", "install", package_spec],
                "cwd": str(ctx.project_root),
            }
        )

    if pip_executable.exists():
        installation_methods.append(
            {
                "tool": "pip",
                "command": [str(pip_executable), "install", package_spec],
                "cwd": None,
            }
        )

    if python3_executable:
        installation_methods.append(
            {
                "tool": "python3 -m pip",
                "command": [python3_executable, "-m", "pip", "install", package_spec],
                "cwd": None,
            }
        )

    if not installation_methods:
        return json.dumps(
            {
                "status": "error",
                "message": "No installation tools found. Cannot install packages.",
            },
            indent=2,
        )

    env = dict(**__import__("os").environ)
    env["VIRTUAL_ENV"] = str(ctx.venv_path)
    env["PATH"] = (
        f"{ctx.venv_path / 'bin'}{__import__('os').pathsep}{env.get('PATH', '')}"
    )

    attempts: List[Dict[str, Any]] = []
    last_error: Dict[str, Any] | None = None

    for method in installation_methods:
        try:
            install_result = subprocess.run(
                method["command"],
                capture_output=True,
                text=True,
                timeout=300,
                env=env,
                cwd=method["cwd"],
            )

            attempt = {
                "method": method["tool"],
                "success": install_result.returncode == 0,
                "stdout": install_result.stdout,
                "stderr": install_result.stderr,
                "return_code": install_result.returncode,
            }
            attempts.append(attempt)

            if install_result.returncode == 0:
                return json.dumps(
                    {
                        "status": "success",
                        "package": package_name,
                        "version": version,
                        "package_spec": package_spec,
                        "installer_used": method["tool"],
                        "install_output": install_result.stdout,
                        "attempts": attempts,
                        "message": f"Successfully installed {package_spec} using {method['tool']}",
                    },
                    indent=2,
                )

            last_error = {
                "method": method["tool"],
                "stdout": install_result.stdout,
                "stderr": install_result.stderr,
                "return_code": install_result.returncode,
            }

        except subprocess.TimeoutExpired:
            last_error = {
                "method": method["tool"],
                "error": "Installation timed out after 300 seconds",
            }
            attempts.append(
                {
                    "method": method["tool"],
                    "success": False,
                    "error": "Installation timed out after 300 seconds",
                }
            )
        except Exception as exc:
            last_error = {
                "method": method["tool"],
                "error": str(exc),
            }
            attempts.append(
                {
                    "method": method["tool"],
                    "success": False,
                    "error": str(exc),
                }
            )

    return json.dumps(
        {
            "status": "error",
            "package": package_name,
            "version": version,
            "package_spec": package_spec,
            "attempts": attempts,
            "last_error": last_error,
            "message": (
                f"Failed to install {package_spec} using all available methods: "
                f"{[method['tool'] for method in installation_methods]}"
            ),
        },
        indent=2,
    )


def list_installed_packages(ctx: Any) -> str:
    """
    List all installed packages from the configured virtual environment.

    Args:
        ctx: Execution context providing virtualenv metadata.

    Returns:
        JSON string describing installed packages or failure details.
    """
    if not ctx.venv_path.exists():
        return json.dumps(
            {
                "status": "error",
                "message": "Virtual environment not found",
            },
            indent=2,
        )

    pip_executable = Path(ctx.venv_path) / "bin" / "pip"
    if not pip_executable.exists():
        return json.dumps(
            {
                "status": "error",
                "message": "pip not found in virtual environment",
            },
            indent=2,
        )

    try:
        list_result = subprocess.run(
            [str(pip_executable), "list", "--format=json"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if list_result.returncode != 0:
            return json.dumps(
                {
                    "status": "error",
                    "message": "Failed to list packages",
                    "error": list_result.stderr,
                },
                indent=2,
            )

        try:
            packages = json.loads(list_result.stdout)
        except json.JSONDecodeError:
            return json.dumps(
                {
                    "status": "error",
                    "message": "Failed to parse package list",
                    "raw_output": list_result.stdout,
                },
                indent=2,
            )

        return json.dumps(
            {
                "status": "success",
                "total_packages": len(packages),
                "packages": packages,
                "message": f"Found {len(packages)} installed packages",
            },
            indent=2,
        )

    except subprocess.TimeoutExpired:
        return json.dumps(
            {
                "status": "error",
                "message": "Package listing timed out",
            },
            indent=2,
        )
    except Exception as exc:
        return json.dumps(
            {
                "status": "error",
                "message": f"Failed to list packages: {exc}",
            },
            indent=2,
        )


__all__ = [
    "install_package",
    "list_installed_packages",
]
