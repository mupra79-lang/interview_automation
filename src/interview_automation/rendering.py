from __future__ import annotations

import subprocess
from pathlib import Path

from .config import PipelineConfig
from .utils import write_json


def audio_duration(path: Path, timeout: int) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return max(1.5, float(result.stdout.strip()))


def render_video(slides: dict, audio: dict, config: PipelineConfig, out_dir: Path, manifest_path: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    list_path = out_dir / "ffmpeg_slides.txt"
    final = out_dir / "final.mp4"
    lines = []
    slide_paths = [Path(p) for p in slides["slides"]]
    audio_paths = [Path(item["path"]) for item in audio["segments"]]
    durations = [audio_duration(path, config.stage_timeout_seconds) for path in audio_paths]
    for slide, duration in zip(slide_paths, durations, strict=False):
        lines.append(f"file '{slide.as_posix()}'")
        lines.append(f"duration {duration:.3f}")
    lines.append(f"file '{slide_paths[-1].as_posix()}'")
    list_path.write_text("\n".join(lines), encoding="utf-8")

    audio_list = out_dir / "ffmpeg_audio.txt"
    audio_list.write_text(
        "\n".join(f"file '{path.as_posix()}'" for path in audio_paths),
        encoding="utf-8",
    )
    merged_audio = out_dir / "narration.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(audio_list), "-c", "copy", str(merged_audio)],
        check=True,
        timeout=config.stage_timeout_seconds,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-i",
            str(merged_audio),
            "-vf",
            f"fps={config.fps},format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-c:a",
            "aac",
            "-shortest",
            "-movflags",
            "+faststart",
            str(final),
        ],
        check=True,
        timeout=config.stage_timeout_seconds,
    )
    manifest = {"video": str(final), "audio": str(merged_audio), "slide_list": str(list_path)}
    write_json(manifest_path, manifest)
    return manifest
