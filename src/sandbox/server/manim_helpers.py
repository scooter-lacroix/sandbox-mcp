"""
Manim helper functions for stdio server tools.
"""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

import json
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict


def execute_manim_code(
    manim_code: str,
    ctx: Any,
    logger: Any,
    quality: str = "medium_quality",
) -> Dict[str, Any]:
    """Execute Manim code and save generated media into the current artifacts directory."""
    if not ctx.artifacts_dir:
        ctx.create_artifacts_dir()

    animation_id = str(uuid.uuid4())[:8]
    manim_dir = Path(ctx.artifacts_dir) / f"manim_{animation_id}"
    manim_dir.mkdir(parents=True, exist_ok=True)

    script_path = manim_dir / "scene.py"

    result: Dict[str, Any] = {
        "success": False,
        "output": "",
        "error": None,
        "video_path": None,
        "animation_id": animation_id,
        "artifacts_dir": str(manim_dir),
        "scenes_found": [],
        "execution_time": 0,
        "warning": None,
    }

    start_time = time.time()

    try:
        if "from manim import *" not in manim_code and "import manim" not in manim_code:
            manim_code = "from manim import *\n" + manim_code

        script_path.write_text(manim_code, encoding="utf-8")

        quality_flags = {
            "low_quality": ["-ql"],
            "medium_quality": ["-qm"],
            "high_quality": ["-qh"],
            "production_quality": ["-qp"],
        }.get(quality, ["-qm"])

        manim_executable = None
        if ctx.venv_path.exists():
            venv_manim = ctx.venv_path / "bin" / "manim"
            if venv_manim.exists():
                manim_executable = str(venv_manim)

        if not manim_executable:
            if ctx.venv_path.exists():
                venv_python = ctx.venv_path / "bin" / "python"
                if venv_python.exists():
                    cmd = (
                        [str(venv_python), "-m", "manim"]
                        + quality_flags
                        + [str(script_path)]
                    )
                else:
                    cmd = (
                        [sys.executable, "-m", "manim"]
                        + quality_flags
                        + [str(script_path)]
                    )
            else:
                cmd = (
                    [sys.executable, "-m", "manim"] + quality_flags + [str(script_path)]
                )
        else:
            cmd = [manim_executable] + quality_flags + [str(script_path)]

        env = dict(**__import__("os").environ)
        if ctx.venv_path.exists():
            env["VIRTUAL_ENV"] = str(ctx.venv_path)
            env["PATH"] = (
                f"{ctx.venv_path / 'bin'}{__import__('os').pathsep}{env.get('PATH', '')}"
            )

        logger.info(f"Executing Manim with command: {' '.join(cmd)}")

        process = subprocess.run(
            cmd,
            cwd=str(manim_dir),
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
        )

        result["output"] = process.stdout
        result["execution_time"] = time.time() - start_time

        if process.returncode == 0:
            result["success"] = True

            media_dir = manim_dir / "media"
            if media_dir.exists():
                video_files = list(media_dir.rglob("*.mp4"))
                image_files = list(media_dir.rglob("*.png"))

                if video_files:
                    result["video_path"] = str(video_files[0])
                    logger.info(f"Manim animation saved to: {video_files[0]}")

                if image_files:
                    result["image_files"] = [
                        str(file_path) for file_path in image_files
                    ]

                import re

                scene_matches = re.findall(r"Scene: ([A-Za-z0-9_]+)", result["output"])
                result["scenes_found"] = scene_matches

                if not video_files and not image_files:
                    result["error"] = "No output files generated"
            else:
                result["error"] = "No media directory found"
        else:
            result["success"] = False
            result["error"] = process.stderr or "Manim execution failed"

    except subprocess.TimeoutExpired:
        result["error"] = "Manim execution timed out (5 minutes)"
        result["execution_time"] = time.time() - start_time
    except Exception as exc:
        result["error"] = f"Error during Manim execution: {exc}"
        result["execution_time"] = time.time() - start_time
        logger.error(f"Manim execution error: {exc}")

    return result


def create_manim_animation(
    manim_code: str,
    ctx: Any,
    logger: Any,
    quality: str = "medium_quality",
) -> str:
    """Create a Manim animation and return JSON metadata."""
    result = execute_manim_code(
        manim_code=manim_code, ctx=ctx, logger=logger, quality=quality
    )
    return json.dumps(result, indent=2)


def list_manim_animations(ctx: Any) -> str:
    """List all Manim animations in the current artifacts directory."""
    if not ctx.artifacts_dir or not Path(ctx.artifacts_dir).exists():
        return "No artifacts directory found. Create an animation first."

    animations = []
    for item in Path(ctx.artifacts_dir).iterdir():
        if item.is_dir() and item.name.startswith("manim_"):
            animation_info: Dict[str, Any] = {
                "animation_id": item.name.replace("manim_", ""),
                "path": str(item),
                "created": item.stat().st_ctime,
                "size_mb": sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
                / 1024
                / 1024,
            }

            video_files = list(item.rglob("*.mp4"))
            if video_files:
                animation_info["video_file"] = str(video_files[0])
                animation_info["video_size_mb"] = (
                    video_files[0].stat().st_size / 1024 / 1024
                )

            animations.append(animation_info)

    if not animations:
        return "No Manim animations found."

    return json.dumps(
        {
            "total_animations": len(animations),
            "animations": animations,
        },
        indent=2,
    )


def cleanup_manim_animation(animation_id: str, ctx: Any) -> str:
    """Remove a specific Manim animation directory."""
    if not ctx.artifacts_dir or not Path(ctx.artifacts_dir).exists():
        return "No artifacts directory found."

    manim_dir = Path(ctx.artifacts_dir) / f"manim_{animation_id}"

    if not manim_dir.exists():
        return f"Animation directory not found: {animation_id}"

    try:
        import shutil

        shutil.rmtree(manim_dir)
        return f"Successfully cleaned up animation: {animation_id}"
    except Exception as exc:
        return f"Failed to clean up animation {animation_id}: {exc}"


__all__ = [
    "cleanup_manim_animation",
    "create_manim_animation",
    "execute_manim_code",
    "list_manim_animations",
]
