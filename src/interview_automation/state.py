from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .utils import read_json, write_json


STAGES = [
    "discovery",
    "topic_selection",
    "script",
    "quality_check",
    "narration",
    "visuals",
    "render",
    "validation",
    "publish_ready",
]


@dataclass
class RunState:
    run_dir: Path

    @property
    def path(self) -> Path:
        return self.run_dir / "checkpoint.json"

    def load(self) -> dict[str, Any]:
        return read_json(self.path, {"stages": {}, "artifacts": {}, "created_at": self.now()})

    def completed(self, stage: str) -> bool:
        return self.load().get("stages", {}).get(stage, {}).get("status") == "completed"

    def artifact_exists(self, key: str) -> bool:
        artifact = self.load().get("artifacts", {}).get(key)
        return bool(artifact and Path(artifact).exists())

    def mark(self, stage: str, status: str, data: dict[str, Any] | None = None) -> None:
        state = self.load()
        state.setdefault("stages", {})[stage] = {
            "status": status,
            "updated_at": self.now(),
            "data": data or {},
        }
        write_json(self.path, state)

    def artifact(self, key: str, path: Path) -> None:
        state = self.load()
        state.setdefault("artifacts", {})[key] = str(path)
        write_json(self.path, state)

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat()
