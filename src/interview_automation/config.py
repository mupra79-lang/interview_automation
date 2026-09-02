from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class PipelineConfig:
    root: Path = ROOT
    runs_dir: Path = ROOT / "runs"
    cache_dir: Path = ROOT / "cache"
    model_dir: Path = ROOT / "models" / "qwen2_5_1_5b_instruct"
    model_lock: Path = ROOT / "models" / "qwen2_5_1_5b_instruct.lock.json"
    model_id: str = "Qwen/Qwen2.5-1.5B-Instruct"
    model_revision: str | None = os.getenv("QWEN_REVISION")
    chatterbox_voice_sample: Path = Path(os.getenv("CHATTERBOX_VOICE_SAMPLE", str(ROOT / "voice" / "sample.wav")))
    chatterbox_voice_profile: Path = Path(os.getenv("CHATTERBOX_VOICE_PROFILE", str(ROOT / "voice" / "sample_chatterbox_conds.pt")))
    chatterbox_model_type: str = os.getenv("CHATTERBOX_MODEL_TYPE", "turbo")
    chatterbox_device: str = os.getenv("CHATTERBOX_DEVICE", "auto")
    youtube_api_key: str | None = os.getenv("YOUTUBE_API_KEY")
    youtube_daily_quota_units: int = int(os.getenv("YOUTUBE_DAILY_QUOTA_UNITS", "450"))
    youtube_cache_cooldown_hours: int = int(os.getenv("YOUTUBE_CACHE_COOLDOWN_HOURS", "24"))
    question_count: int = 10
    topic: str = "Top 10 LangGraph Interview Questions"
    brand: str = os.getenv("CHANNEL_BRAND", "CodeMentor AI")
    watermark: str = os.getenv("CHANNEL_WATERMARK", "CodeMentor AI")
    dry_run: bool = True
    local_generation: bool = False
    publish_enabled: bool = False
    stage_timeout_seconds: int = int(os.getenv("STAGE_TIMEOUT_SECONDS", "900"))
    width: int = 1920
    height: int = 1080
    fps: int = 30
    keep_intermediate: bool = False
    tts_engine: str = os.getenv("TTS_ENGINE", "chatterbox")
    extra: dict[str, str] = field(default_factory=dict)

    def ensure_dirs(self) -> None:
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.model_dir.parent.mkdir(parents=True, exist_ok=True)
