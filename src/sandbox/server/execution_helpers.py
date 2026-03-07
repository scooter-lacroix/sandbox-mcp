"""
Execution helpers for stdio MCP tool logic and artifact-aware patching.
"""

from __future__ import annotations

import base64
import io
import json
import os
import signal
import subprocess
import sys
import traceback
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


def monkey_patch_matplotlib(ctx: Any, logger: Any) -> bool:
    """Monkey patch matplotlib to save plots into the current artifacts directory."""
    try:
        import matplotlib

        backends = ["Agg", "svg", "pdf", "ps", "Cairo"]
        backend_set = False

        for backend in backends:
            try:
                matplotlib.use(backend, force=True)
                logger.info(f"Successfully set matplotlib backend to: {backend}")
                backend_set = True
                break
            except Exception as backend_error:
                logger.warning(f"Failed to set backend {backend}: {backend_error}")

        if not backend_set:
            logger.warning("No matplotlib backend could be set, using default")

        try:
            current_backend = matplotlib.get_backend()
            logger.info(f"Final matplotlib backend: {current_backend}")
        except Exception as exc:
            logger.error(f"Error getting current backend: {exc}")

        import matplotlib.pyplot as plt

        original_show = plt.show

        if getattr(plt.show, "_sandbox_patched", False):
            return True

        def patched_show(*args: Any, **kwargs: Any) -> Any:
            try:
                if ctx.artifacts_dir:
                    plots_dir = Path(ctx.artifacts_dir) / "plots"
                    plots_dir.mkdir(parents=True, exist_ok=True)

                    save_formats = [("png", "PNG"), ("svg", "SVG"), ("pdf", "PDF")]
                    saved = False

                    for ext, format_name in save_formats:
                        try:
                            save_path = plots_dir / f"plot_{uuid.uuid4().hex[:8]}.{ext}"
                            plt.savefig(
                                save_path,
                                dpi=150,
                                bbox_inches="tight",
                                format=ext,
                            )
                            logger.info(f"Image saved to artifacts: {save_path}")
                            saved = True
                            break
                        except Exception as save_error:
                            logger.warning(
                                f"Failed to save as {format_name}: {save_error}"
                            )

                    if not saved:
                        logger.error("Failed to save plot in any format")

                return original_show(*args, **kwargs)
            except Exception as exc:
                logger.error(f"Error in patched_show: {exc}")
                return original_show(*args, **kwargs)

        patched_show._sandbox_patched = True  # type: ignore[attr-defined]
        plt.show = patched_show
        return True
    except ImportError:
        logger.warning("Matplotlib not available for monkey patching")
        return False
    except Exception as exc:
        logger.error(f"Critical error in matplotlib monkey patch: {exc}")
        return False


def monkey_patch_pil(ctx: Any, logger: Any) -> bool:
    """Monkey patch PIL image display/save hooks for artifact capture."""
    try:
        from PIL import Image

        if getattr(Image.Image.show, "_sandbox_patched", False):
            return True

        original_show = Image.Image.show
        original_save = Image.Image.save

        def patched_show(self: Any, title: Any = None, command: Any = None) -> Any:
            if ctx.artifacts_dir:
                images_dir = Path(ctx.artifacts_dir) / "images"
                images_dir.mkdir(parents=True, exist_ok=True)
                image_path = images_dir / f"image_{uuid.uuid4().hex[:8]}.png"
                self.save(image_path)
                logger.info(f"Image saved to: {image_path}")
            return original_show(self, title, command)

        def patched_save(self: Any, fp: Any, format: Any = None, **params: Any) -> Any:
            result = original_save(self, fp, format, **params)
            if ctx.artifacts_dir and str(fp).startswith(str(ctx.artifacts_dir)):
                logger.info(f"Image saved to artifacts: {fp}")
            return result

        patched_show._sandbox_patched = True  # type: ignore[attr-defined]
        patched_save._sandbox_patched = True  # type: ignore[attr-defined]
        Image.Image.show = patched_show
        Image.Image.save = patched_save
        return True
    except ImportError:
        return False
    except Exception as exc:
        logger.error(f"Critical error in PIL monkey patch: {exc}")
        return False


def collect_artifacts(ctx: Any, logger: Any) -> List[Dict[str, Any]]:
    """Collect artifacts from the current artifact directory recursively."""
    artifacts: List[Dict[str, Any]] = []
    if not ctx.artifacts_dir or not Path(ctx.artifacts_dir).exists():
        return artifacts

    artifacts_root = Path(ctx.artifacts_dir)

    for file_path in artifacts_root.rglob("*"):
        if not file_path.is_file():
            continue

        try:
            with open(file_path, "rb") as handle:
                content = base64.b64encode(handle.read()).decode("utf-8")

            relative_path = file_path.relative_to(artifacts_root)
            artifacts.append(
                {
                    "name": file_path.name,
                    "path": str(file_path),
                    "relative_path": str(relative_path),
                    "type": file_path.suffix.lower(),
                    "content_base64": content,
                    "size": file_path.stat().st_size,
                    "category": file_path.parent.name,
                }
            )
        except Exception as exc:
            logger.error(f"Error reading artifact {file_path}: {exc}")

    return artifacts


def execute(
    code: str,
    ctx: Any,
    logger: Any,
    launch_web_app: Callable[[str, str], Optional[str]],
    interactive: bool = False,
    web_app_type: Optional[str] = None,
) -> str:
    """
    Execute Python code with artifact capture and optional web app launch support.
    """
    artifacts_dir = ctx.create_artifacts_dir()

    matplotlib_patched = monkey_patch_matplotlib(ctx, logger)
    pil_patched = monkey_patch_pil(ctx, logger)

    old_stdout, old_stderr = sys.stdout, sys.stderr
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    result: Dict[str, Any] = {
        "stdout": "",
        "stderr": "",
        "error": None,
        "artifacts": [],
        "web_url": None,
        "execution_info": {
            "sys_executable": sys.executable,
            "sys_path_first_3": sys.path[:3],
            "project_root": str(ctx.project_root),
            "artifacts_dir": artifacts_dir,
            "matplotlib_patched": matplotlib_patched,
            "pil_patched": pil_patched,
        },
    }

    try:
        sys.stdout = stdout_capture
        sys.stderr = stderr_capture

        if web_app_type in ["flask", "streamlit"]:
            url = launch_web_app(code, web_app_type)
            if url:
                result["web_url"] = url
                result["stdout"] = f"Web application launched at: {url}"
            else:
                result["stderr"] = f"Failed to launch {web_app_type} application"
        else:
            logger.debug(f"Executing code: {repr(code)}")
            logger.debug(f"Code length: {len(code)}")
            logger.debug(f"Code lines: {code.count(chr(10)) + 1}")

            if len(code) > 10:
                if code.count('"') % 2 != 0 or code.count("'") % 2 != 0:
                    logger.warning(
                        "Code appears to have unmatched quotes - possible truncation"
                    )
                    result["stderr"] = (
                        "Warning: Code appears to have unmatched quotes. "
                        "This might indicate the code was truncated during transmission."
                    )

                open_parens = code.count("(") - code.count(")")
                if open_parens != 0:
                    logger.warning(
                        f"Code has unmatched parentheses ({open_parens} open) - possible truncation"
                    )
                    result["stderr"] = (
                        f"Warning: Code has {open_parens} unmatched opening parentheses. "
                        "This might indicate the code was truncated during transmission."
                    )

            try:
                compile(code, "<string>", "exec")
                logger.debug("Code compilation successful")
            except SyntaxError as exc:
                logger.error(f"Syntax error during compilation: {exc}")
                logger.error(f"Error line: {exc.lineno}")
                logger.error(f"Error text: {exc.text}")
                logger.error(f"Error position: {exc.offset}")

                if "was never closed" in str(exc) or "unterminated" in str(exc).lower():
                    error_msg = (
                        f"Syntax error: {exc}\n\n"
                        "This error often occurs when code is truncated during transmission.\n"
                        f"The code received was {len(code)} characters long with "
                        f"{code.count(chr(10)) + 1} lines.\n"
                        "Please try sending the code in smaller chunks or verify the complete "
                        "code was transmitted."
                    )
                    result["stderr"] = error_msg
                    result["error"] = {
                        "type": "TruncationError",
                        "message": error_msg,
                        "original_error": str(exc),
                        "code_length": len(code),
                        "code_lines": code.count(chr(10)) + 1,
                    }
                    return json.dumps(result, indent=2)

                raise

            try:

                def signal_handler(signum: int, frame: Any) -> None:
                    logger.error(f"Signal {signum} received during execution")
                    raise RuntimeError(f"Code execution interrupted by signal {signum}")

                old_handlers: Dict[int, Any] = {}
                for sig in [signal.SIGSEGV, signal.SIGFPE, signal.SIGILL]:
                    try:
                        old_handlers[sig] = signal.signal(sig, signal_handler)
                    except (ValueError, OSError, AttributeError):
                        pass

                try:
                    exec(code, ctx.execution_globals)
                    logger.debug("Code execution completed successfully")
                except Exception as exec_error:
                    logger.error(f"Exception during code execution: {exec_error}")
                    logger.error(f"Exception type: {type(exec_error).__name__}")
                    raise
                finally:
                    for sig, old_handler in old_handlers.items():
                        try:
                            signal.signal(sig, old_handler)
                        except (ValueError, OSError, AttributeError):
                            pass

            except RuntimeError as exc:
                if "signal" in str(exc).lower():
                    result["error"] = {
                        "type": "SystemError",
                        "message": f"Code execution caused a system-level error: {exc}",
                        "suggestion": (
                            "This may be due to incompatible libraries or CPU instruction "
                            "issues. Try simpler code or different libraries."
                        ),
                    }
                    result["stderr"] = (
                        f"System error: {exc}\n\n"
                        "This often indicates library compatibility issues or CPU instruction problems."
                    )
                    return json.dumps(result, indent=2)
                raise

        if interactive:
            result["stdout"] += (
                "\n[Interactive mode enabled - code executed successfully]\n"
            )
            result["stdout"] += (
                "Note: REPL mode would be available in a real terminal session\n"
            )

    except ImportError as exc:
        error_trace = traceback.format_exc()
        module_name = str(exc).split("'")[1] if "'" in str(exc) else "unknown"

        result["error"] = {
            "type": "ImportError",
            "message": str(exc),
            "module": module_name,
            "traceback": error_trace,
            "sys_path": sys.path[:5],
            "attempted_paths": [p for p in sys.path if Path(p).exists()],
        }
        result["stderr"] = f"Import Error: {exc}\n\nFull traceback:\n{error_trace}"

    except Exception as exc:
        error_trace = traceback.format_exc()
        result["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": error_trace,
        }
        result["stderr"] = f"Error: {exc}\n\nFull traceback:\n{error_trace}"

    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        result["stdout"] += stdout_capture.getvalue()
        result["stderr"] += stderr_capture.getvalue()
        result["artifacts"] = collect_artifacts(ctx, logger)

    return json.dumps(result, indent=2)


def execute_with_artifacts(
    code: str,
    ctx: Any,
    logger: Any,
    persistent_context_factory: Callable[[], Any],
    track_artifacts: bool = True,
) -> str:
    """
    Execute Python code with before/after artifact tracking and reporting.
    """
    artifacts_dir = ctx.create_artifacts_dir()

    matplotlib_patched = monkey_patch_matplotlib(ctx, logger)
    pil_patched = monkey_patch_pil(ctx, logger)

    temp_ctx = persistent_context_factory()
    temp_ctx.artifacts_dir = Path(artifacts_dir)

    artifacts_before = temp_ctx._get_current_artifacts() if track_artifacts else set()

    old_stdout, old_stderr = sys.stdout, sys.stderr
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    result: Dict[str, Any] = {
        "stdout": "",
        "stderr": "",
        "error": None,
        "artifacts": [],
        "artifact_report": None,
        "execution_info": {
            "sys_executable": sys.executable,
            "artifacts_dir": artifacts_dir,
            "matplotlib_patched": matplotlib_patched,
            "pil_patched": pil_patched,
            "track_artifacts": track_artifacts,
        },
    }

    try:
        sys.stdout = stdout_capture
        sys.stderr = stderr_capture
        exec(code, ctx.execution_globals)

    except Exception as exc:
        error_trace = traceback.format_exc()
        result["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": error_trace,
        }
        result["stderr"] = f"Error: {exc}\n\nFull traceback:\n{error_trace}"

    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

        result["stdout"] = stdout_capture.getvalue()
        result["stderr"] += stderr_capture.getvalue()

        if track_artifacts:
            artifacts_after = temp_ctx._get_current_artifacts()
            new_artifacts = artifacts_after - artifacts_before
            if new_artifacts:
                result["artifacts"] = list(new_artifacts)
                result["artifact_report"] = temp_ctx.get_artifact_report()

    return json.dumps(result, indent=2)


def find_free_port(start_port: int = 8000) -> int:
    """Find a free localhost port starting from the provided base port."""
    import socket

    for port in range(start_port, start_port + 100):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    raise RuntimeError("No free ports available")


def launch_web_app(
    code: str,
    app_type: str,
    ctx: Any,
    logger: Any,
    resource_manager: Any,
) -> Optional[str]:
    """Launch a Flask or Streamlit app and return its local URL."""
    try:
        resource_manager.check_resource_limits()
        port = find_free_port()
        resource_manager.process_manager.cleanup_finished()

        if not ctx.artifacts_dir:
            ctx.create_artifacts_dir()

        if app_type == "flask":
            modified_code = (
                code
                + "\nif __name__ == '__main__': "
                + f"app.run(host='127.0.0.1', port={port}, debug=False)"
            )
        elif app_type == "streamlit":
            script_path = (
                Path(ctx.artifacts_dir) / f"streamlit_app_{uuid.uuid4().hex[:8]}.py"
            )
            with open(script_path, "w", encoding="utf-8") as handle:
                handle.write(code)

            cmd = [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(script_path),
                "--server.port",
                str(port),
                "--server.headless",
                "true",
            ]
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            process_id = resource_manager.process_manager.add_process(
                process,
                name=f"streamlit_{port}",
                metadata={"type": "streamlit", "port": port},
            )

            import time

            time.sleep(2)

            if process.poll() is None:
                url = f"http://127.0.0.1:{port}"
                ctx.web_servers[url] = process_id
                return url
            return None
        else:
            return None

        if app_type == "flask":

            def run_flask() -> None:
                exec(modified_code, ctx.execution_globals)

            resource_manager.thread_pool.submit(run_flask)

            import time

            time.sleep(1)
            return f"http://127.0.0.1:{port}"

    except Exception as exc:
        logger.error(f"Failed to launch web app: {exc}")
        return None

    return None


__all__ = [
    "collect_artifacts",
    "execute",
    "execute_with_artifacts",
    "find_free_port",
    "launch_web_app",
    "monkey_patch_matplotlib",
    "monkey_patch_pil",
]
