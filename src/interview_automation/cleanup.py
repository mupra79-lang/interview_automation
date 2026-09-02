from __future__ import annotations

import shutil
from pathlib import Path

from .utils import write_json


KEEP_NAMES = {
    "final.mp4",
    "thumbnail.png",
    "script.json",
    "manifest.json",
    "pipeline.log",
    "quality_report.json",
    "validation_report.json",
    "checkpoint.json",
}


def cleanup_run(run_dir: Path, report_path: Path, keep_intermediate: bool = False) -> dict:
    removed: list[str] = []
    if keep_intermediate:
        report = {"removed": removed, "kept_intermediate": True}
        write_json(report_path, report)
        return report
    for child in run_dir.iterdir():
        if child.name in KEEP_NAMES:
            continue
        if child.is_dir():
            shutil.rmtree(child)
            removed.append(str(child))
        elif child.is_file() and child.name not in KEEP_NAMES:
            child.unlink()
            removed.append(str(child))
    report = {"removed": removed, "kept_intermediate": False}
    write_json(report_path, report)
    return report
