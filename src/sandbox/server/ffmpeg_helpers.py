"""
FFMPEG helper functions for stdio server tools.
"""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

import json
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional


def create_ffmpeg_video(
    input_clips: List[str],
    ctx: Any,
    logger: Any,
    audio_path: Optional[str] = None,
    subtitle_path: Optional[str] = None,
    resolution: str = "1920x1080",
    framerate: int = 60,
    output_filename: str = "final_render.mp4",
) -> str:
    """Wrap FFmpeg CLI to concatenate clips, add audio, burn subtitles, and normalize resolution/framerate."""
    if not ctx.artifacts_dir:
        ctx.create_artifacts_dir()

    run_id = str(uuid.uuid4())[:8]
    ffmpeg_dir = Path(ctx.artifacts_dir) / f"ffmpeg_{run_id}"
    ffmpeg_dir.mkdir(parents=True, exist_ok=True)
    
    # Secure output path
    output_path = ffmpeg_dir / output_filename

    result: Dict[str, Any] = {
        "success": False,
        "output": "",
        "error": None,
        "video_path": None,
        "run_id": run_id,
        "artifacts_dir": str(ffmpeg_dir),
        "execution_time": 0,
    }

    start_time = time.time()

    try:
        # Step 1: Pre-flight format validation and normalization to intermediate files
        normalized_clips = []
        for i, clip in enumerate(input_clips):
            clip_path = Path(clip)
            if not clip_path.exists():
                result["error"] = f"Input clip not found: {clip}"
                return json.dumps(result, indent=2)
                
            norm_clip_path = ffmpeg_dir / f"norm_{i}.mp4"
            # Force resolution, framerate, and standard codec
            norm_cmd = [
                "ffmpeg", "-y", "-i", str(clip_path),
                "-vf", f"scale={resolution},setsar=1",
                "-r", str(framerate),
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-ar", "44100",
                str(norm_clip_path)
            ]
            
            logger.info(f"Normalizing clip {i}: {' '.join(norm_cmd)}")
            norm_proc = subprocess.run(norm_cmd, capture_output=True, text=True)
            if norm_proc.returncode != 0:
                result["success"] = False
                result["error"] = f"Failed to normalize clip {i}. {norm_proc.stderr}"
                return json.dumps(result, indent=2)
                
            normalized_clips.append(str(norm_clip_path))

        # Step 2: Create concat demuxer file
        concat_file_path = ffmpeg_dir / "concat_list.txt"
        with open(concat_file_path, "w") as f:
            for clip in normalized_clips:
                f.write(f"file '{clip}'\n")

        # Step 3: Stitching and final assembly
        assemble_cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file_path)]
        
        filter_complex = []
        
        # Add audio
        if audio_path:
            audio_p = Path(audio_path)
            if audio_p.exists():
                assemble_cmd.extend(["-i", str(audio_p)])
                # Truncate audio to shortest (video duration)
                assemble_cmd.extend(["-shortest"])
            else:
                logger.warning(f"Audio path not found: {audio_path}")

        # Add subtitles
        if subtitle_path:
            sub_p = Path(subtitle_path)
            if sub_p.exists():
                # Escape path for FFmpeg filter
                escaped_sub = str(sub_p).replace("\\", "/").replace(":", "\\:")
                filter_complex.append(f"subtitles='{escaped_sub}'")
            else:
                logger.warning(f"Subtitle path not found: {subtitle_path}")

        if filter_complex:
            assemble_cmd.extend(["-vf", ",".join(filter_complex)])
            # Re-encode video if applying filters like subtitles
            assemble_cmd.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p"])
        else:
            # Lossless concatenation if no visual filters
            assemble_cmd.extend(["-c:v", "copy"])

        # Audio codec
        if audio_path:
            assemble_cmd.extend(["-c:a", "aac"])
        else:
            assemble_cmd.extend(["-c:a", "copy"])

        assemble_cmd.append(str(output_path))
        
        logger.info(f"Assembling video: {' '.join(assemble_cmd)}")
        assemble_proc = subprocess.run(assemble_cmd, capture_output=True, text=True)
        
        result["execution_time"] = time.time() - start_time
        
        if assemble_proc.returncode == 0:
            result["success"] = True
            result["video_path"] = str(output_path)
            result["output"] = "FFMPEG assembly successful."
            result["summary"] = f"Assembled {len(input_clips)} clips into {resolution} at {framerate}fps."
        else:
            result["success"] = False
            result["error"] = f"Assembly failed. {assemble_proc.stderr}"
            # Keep original output for debugging on failure
            result["output"] = assemble_proc.stdout

    except Exception as exc:
        result["error"] = f"Error during FFmpeg execution: {exc}"
        result["execution_time"] = time.time() - start_time
        logger.error(f"FFmpeg execution error: {exc}")

    return json.dumps(result, indent=2)

__all__ = ["create_ffmpeg_video"]
