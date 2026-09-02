from __future__ import annotations

from pathlib import Path

from .config import PipelineConfig
from .utils import sha256_text, write_json


def _choose_device(preferred: str) -> str:
    if preferred != "auto":
        return preferred
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _find_voice_sample(config: PipelineConfig) -> Path:
    candidates = [
        config.chatterbox_voice_sample,
        config.root / "voice" / "sample.wav",
        config.root.parent / "voice" / "sample.wav",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(
        "Chatterbox voice sample not found. Put your owned voice at voice/sample.wav "
        "or set CHATTERBOX_VOICE_SAMPLE."
    )


def _find_voice_profile(config: PipelineConfig) -> Path:
    candidates = [
        config.chatterbox_voice_profile,
        config.root / "voice" / "sample_chatterbox_conds.pt",
        config.root.parent / "voice" / "sample_chatterbox_conds.pt",
    ]
    for path in candidates:
        if path.exists():
            return path
    return config.chatterbox_voice_profile


def _load_chatterbox(config: PipelineConfig, device: str):
    if config.chatterbox_model_type == "turbo":
        from chatterbox.tts_turbo import ChatterboxTurboTTS, Conditionals

        return ChatterboxTurboTTS.from_pretrained(device=device), Conditionals
    if config.chatterbox_model_type == "nano":
        from chatterbox.tts_turbo import ChatterboxTurboTTS, Conditionals

        return ChatterboxTurboTTS.from_pretrained(device=device, nano=True), Conditionals
    if config.chatterbox_model_type == "base":
        from chatterbox.tts import ChatterboxTTS, Conditionals

        return ChatterboxTTS.from_pretrained(device=device), Conditionals
    raise ValueError(f"Unsupported Chatterbox model type: {config.chatterbox_model_type}")


def prepare_chatterbox_voice_once(model, config: PipelineConfig, profile_path: Path) -> Path:
    if profile_path.exists():
        return profile_path
    sample_path = _find_voice_sample(config)
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    model.prepare_conditionals(sample_path, exaggeration=0.5)
    model.conds.save(profile_path)
    return profile_path


def synthesize_segments(script: dict, audio_dir: Path, manifest_path: Path, config: PipelineConfig) -> dict:
    if config.tts_engine != "chatterbox":
        raise ValueError("Only Chatterbox TTS is supported for video narration.")

    import torchaudio as ta

    audio_dir.mkdir(parents=True, exist_ok=True)
    device = _choose_device(config.chatterbox_device)
    model, conditionals_class = _load_chatterbox(config, device)
    profile_path = prepare_chatterbox_voice_once(model, config, _find_voice_profile(config))
    model.conds = conditionals_class.load(profile_path, map_location=device).to(device)

    segments = []
    for index, text in enumerate(script["narration"], start=1):
        digest = sha256_text(text)[:12]
        path = audio_dir / f"segment_{index:03d}_{digest}.wav"
        if not path.exists():
            wav = model.generate(text, exaggeration=0.5, temperature=0.8)
            ta.save(path, wav.cpu(), model.sr)
        if path.stat().st_size < 1000:
            raise RuntimeError(f"Generated Chatterbox audio is empty or invalid: {path}")
        segments.append({"index": index, "text": text, "path": str(path), "hash": digest})
    manifest = {"segments": segments, "engine": "chatterbox", "voice_profile": str(profile_path)}
    write_json(manifest_path, manifest)
    return manifest
