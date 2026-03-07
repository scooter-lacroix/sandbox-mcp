import logging
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List

from fastmcp import FastMCP

from .core.execution_context import PersistentExecutionContext
from .core.resource_manager import get_resource_manager
from .core.security import SecurityLevel, get_security_manager
from .server.tool_registry import create_tool_registry

# Set up logging to file instead of stderr to avoid MCP protocol interference
log_file = Path(tempfile.gettempdir()) / "sandbox_mcp_server.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stderr)
        if os.getenv("SANDBOX_MCP_DEBUG")
        else logging.NullHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Create FastMCP server named "python-sandbox"
mcp = FastMCP("python-sandbox")


class ExecutionContext:
    """Global execution context for the stdio MCP server."""

    def __init__(self) -> None:
        current_file = Path(__file__).resolve()
        if "src/sandbox" in str(current_file):
            self.project_root = current_file.parent.parent.parent
        else:
            self.project_root = current_file.parent

        self.sandbox_area = self.project_root.parent / "sandbox_area"
        self.sandbox_area.mkdir(exist_ok=True)

        self.venv_path = self.project_root / ".venv"
        self.artifacts_dir: Path | None = None
        self.web_servers: Dict[str, Any] = {}
        self.execution_globals: Dict[str, Any] = {}
        self.compilation_cache: Dict[str, Any] = {}
        self.cache_hits = 0
        self.cache_misses = 0
        self._setup_environment()

    def _setup_environment(self) -> None:
        """Setup sys.path and virtual environment with robust path detection."""
        project_root_str = str(self.project_root)
        project_parent_str = str(self.project_root.parent)

        venv_site_packages = None
        if self.venv_path.exists():
            for py_version in ["python3.11", "python3.12", "python3.10", "python3.9"]:
                candidate = self.venv_path / "lib" / py_version / "site-packages"
                if candidate.exists():
                    venv_site_packages = candidate
                    break

        from collections import OrderedDict

        current_paths = OrderedDict.fromkeys(sys.path)

        paths_to_add = [project_parent_str, project_root_str]
        if venv_site_packages:
            paths_to_add.append(str(venv_site_packages))

        new_sys_path = []
        for path in paths_to_add:
            if path not in current_paths:
                new_sys_path.append(path)
                current_paths[path] = None

        sys.path[:] = new_sys_path + list(current_paths.keys())

        if self.venv_path.exists():
            venv_python = self.venv_path / "bin" / "python"
            venv_bin = self.venv_path / "bin"

            if venv_python.exists():
                os.environ["VIRTUAL_ENV"] = str(self.venv_path)

                current_path = os.environ.get("PATH", "")
                venv_bin_str = str(venv_bin)
                if venv_bin_str not in current_path.split(os.pathsep):
                    os.environ["PATH"] = f"{venv_bin_str}{os.pathsep}{current_path}"

                sys.executable = str(venv_python)

        logger.info(f"Project root: {self.project_root}")
        logger.info(
            f"Virtual env: {self.venv_path if self.venv_path.exists() else 'Not found'}"
        )
        logger.info(f"sys.executable: {sys.executable}")
        logger.info(f"sys.path (first 5): {sys.path[:5]}")
        logger.info(f"VIRTUAL_ENV: {os.environ.get('VIRTUAL_ENV', 'Not set')}")

    def create_artifacts_dir(self) -> str:
        """Create a structured directory for execution artifacts within the project."""
        if self.artifacts_dir and self.artifacts_dir.exists():
            return str(self.artifacts_dir)

        execution_id = str(uuid.uuid4())[:8]
        artifacts_root = self.project_root / "artifacts"
        artifacts_root.mkdir(exist_ok=True)

        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = f"session_{timestamp}_{execution_id}"

        self.artifacts_dir = artifacts_root / session_dir
        self.artifacts_dir.mkdir(exist_ok=True)

        for subdir in [
            "plots",
            "images",
            "animations",
            "files",
            "audio",
            "data",
            "models",
            "documents",
            "web_assets",
        ]:
            (self.artifacts_dir / subdir).mkdir(exist_ok=True)

        return str(self.artifacts_dir)

    def cleanup_artifacts(self) -> None:
        """Clean up artifacts directory."""
        if self.artifacts_dir and self.artifacts_dir.exists():
            shutil.rmtree(self.artifacts_dir, ignore_errors=True)

    def backup_artifacts(self, backup_name: str | None = None) -> str:
        """Create a versioned backup of current artifacts."""
        if not self.artifacts_dir or not self.artifacts_dir.exists():
            return "No artifacts directory to backup"

        backup_root = self.project_root / "artifact_backups"
        backup_root.mkdir(exist_ok=True)

        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = (
            f"{backup_name}_{timestamp}" if backup_name else f"backup_{timestamp}"
        )
        backup_path = backup_root / backup_name

        shutil.copytree(self.artifacts_dir, backup_path)
        self._cleanup_old_backups(backup_root)

        return str(backup_path)

    def _cleanup_old_backups(self, backup_root: Path, max_backups: int = 10) -> None:
        """Clean up old backup directories to prevent storage overflow."""
        try:
            backups = [d for d in backup_root.iterdir() if d.is_dir()]
            backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)

            for backup in backups[max_backups:]:
                shutil.rmtree(backup, ignore_errors=True)
                logger.info(f"Removed old backup: {backup}")
        except Exception as e:
            logger.warning(f"Failed to cleanup old backups: {e}")

    def list_artifact_backups(self) -> List[Dict[str, Any]]:
        """List all available artifact backups."""
        backup_root = self.project_root / "artifact_backups"
        if not backup_root.exists():
            return []

        backups = []
        for backup_dir in backup_root.iterdir():
            if backup_dir.is_dir():
                try:
                    stat = backup_dir.stat()
                    size = sum(
                        f.stat().st_size for f in backup_dir.rglob("*") if f.is_file()
                    )
                    backups.append(
                        {
                            "name": backup_dir.name,
                            "path": str(backup_dir),
                            "created": stat.st_ctime,
                            "modified": stat.st_mtime,
                            "size_bytes": size,
                            "size_mb": size / (1024 * 1024),
                            "file_count": len(list(backup_dir.rglob("*"))),
                        }
                    )
                except Exception as e:
                    logger.warning(f"Failed to stat backup {backup_dir}: {e}")

        backups.sort(key=lambda x: x["created"], reverse=True)
        return backups

    def rollback_artifacts(self, backup_name: str) -> str:
        """Rollback to a previous artifact version with improved validation."""
        backup_root = self.project_root / "artifact_backups"

        if not backup_root.exists():
            return "No backups directory found. Available backups: none"

        backup_path = backup_root / backup_name

        if not backup_path.exists():
            available_backups = [d.name for d in backup_root.iterdir() if d.is_dir()]
            if available_backups:
                preview = ", ".join(available_backups[:5])
                suffix = "..." if len(available_backups) > 5 else ""
                return f"Backup '{backup_name}' not found. Available backups: {preview}{suffix}"
            return f"Backup '{backup_name}' not found. No backups available."

        if not self.artifacts_dir:
            return "No current artifacts directory. Please create artifacts first."

        current_backup = self.backup_artifacts("pre_rollback")

        try:
            if self.artifacts_dir and self.artifacts_dir.exists():
                shutil.rmtree(self.artifacts_dir)

            shutil.copytree(backup_path, self.artifacts_dir)

            return (
                f"Successfully rolled back to backup '{backup_name}'. "
                f"Previous state saved as '{Path(current_backup).name}'"
            )
        except Exception as e:
            return f"Failed to rollback: {str(e)}"

    def get_backup_info(self, backup_name: str) -> Dict[str, Any]:
        """Get detailed information about a specific backup."""
        backup_root = self.project_root / "artifact_backups"
        backup_path = backup_root / backup_name

        if not backup_path.exists():
            return {"error": f"Backup '{backup_name}' not found"}

        try:
            stat = backup_path.stat()
            files = list(backup_path.rglob("*"))

            categories: Dict[str, List[Dict[str, Any]]] = {}
            for file_path in files:
                if file_path.is_file():
                    category = file_path.parent.name
                    categories.setdefault(category, []).append(
                        {
                            "name": file_path.name,
                            "size": file_path.stat().st_size,
                            "extension": file_path.suffix,
                        }
                    )

            return {
                "name": backup_name,
                "path": str(backup_path),
                "created": stat.st_ctime,
                "modified": stat.st_mtime,
                "total_files": len([f for f in files if f.is_file()]),
                "total_size_bytes": sum(f.stat().st_size for f in files if f.is_file()),
                "categories": categories,
            }
        except Exception as e:
            return {"error": f"Failed to get backup info: {str(e)}"}


ctx = ExecutionContext()
resource_manager = get_resource_manager()
security_manager = get_security_manager(SecurityLevel.MEDIUM)

tool_registry = create_tool_registry(
    mcp,
    ctx,
    logger=logger,
    resource_manager=resource_manager,
    security_manager=security_manager,
    persistent_context_factory=PersistentExecutionContext,
)
tool_registry.register_all()


def main() -> None:
    """Entry point for the stdio MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
