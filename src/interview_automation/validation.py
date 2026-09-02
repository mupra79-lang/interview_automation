from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image

from .config import PipelineConfig
from .utils import write_json


def probe(path: Path, timeout: int) -> dict:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=width,height,codec_type",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    import json

    return json.loads(result.stdout)


def validate_package(video_path: Path, thumbnail_path: Path, slides_manifest: dict, config: PipelineConfig, report_path: Path) -> dict:
    issues: list[str] = []
    if not video_path.exists() or video_path.stat().st_size < 1000:
        issues.append("Final video is missing or too small.")
    if not thumbnail_path.exists():
        issues.append("Thumbnail is missing.")
    else:
        with Image.open(thumbnail_path) as img:
            if img.size != (config.width, config.height):
                issues.append(f"Thumbnail size is {img.size}, expected {(config.width, config.height)}.")
    for slide in slides_manifest.get("slides", []):
        with Image.open(slide) as img:
            if img.size != (config.width, config.height):
                issues.append(f"Slide has wrong size: {slide}")
    metadata = probe(video_path, config.stage_timeout_seconds) if video_path.exists() else {}
    if metadata:
        duration = float(metadata.get("format", {}).get("duration", 0))
        if duration < 10:
            issues.append("Video duration is unexpectedly short.")
        if not any(stream.get("codec_type") == "audio" for stream in metadata.get("streams", [])):
            issues.append("Video has no audio stream.")
    report = {"approved": not issues, "issues": issues, "ffprobe": metadata}
    write_json(report_path, report)
    if issues:
        raise ValueError("Validation failed: " + "; ".join(issues))
    return report
