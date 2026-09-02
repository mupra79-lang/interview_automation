from __future__ import annotations

from PIL import Image

from interview_automation.config import PipelineConfig
from interview_automation.script_generation import generate_script
from interview_automation.visuals import generate_visuals
from tests.helpers import fake_qwen_generator


def test_visual_generation_creates_1080p_slides(tmp_path) -> None:
    script = generate_script("Top 10 LangGraph Interview Questions", 10, tmp_path / "script.json", fake_qwen_generator)
    config = PipelineConfig(root=tmp_path, runs_dir=tmp_path / "runs", cache_dir=tmp_path / "cache")
    manifest = generate_visuals(script, config, tmp_path / "slides", tmp_path / "slides_manifest.json")
    assert len(manifest["slides"]) == 12
    with Image.open(manifest["slides"][1]) as img:
        assert img.size == (1920, 1080)


def test_long_text_visual_stays_1080p_without_overflow_crash(tmp_path) -> None:
    script = generate_script("Top 10 LangGraph Interview Questions", 10, tmp_path / "script.json", fake_qwen_generator)
    script["questions"][0]["answer"] = " ".join(["LangGraph state, routing, checkpointing, and validation"] * 70)
    config = PipelineConfig(root=tmp_path, runs_dir=tmp_path / "runs", cache_dir=tmp_path / "cache")
    manifest = generate_visuals(script, config, tmp_path / "slides", tmp_path / "slides_manifest.json")
    with Image.open(manifest["slides"][1]) as img:
        assert img.size == (1920, 1080)
