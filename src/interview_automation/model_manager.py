from __future__ import annotations

from datetime import datetime, timezone

from .config import PipelineConfig
from .utils import read_json, write_json


def ensure_qwen_model(config: PipelineConfig, force: bool = False) -> dict:
    """Download once, pin the resolved commit hash, and verify future loads."""
    from huggingface_hub import HfApi, snapshot_download

    lock = read_json(config.model_lock, {})
    api = HfApi()
    desired_revision = config.model_revision or lock.get("resolved_revision") or "main"
    info = api.model_info(config.model_id, revision=desired_revision)
    resolved = info.sha

    if lock and not force and lock.get("resolved_revision") != resolved:
        raise RuntimeError(
            "Qwen revision mismatch. Existing lock has "
            f"{lock.get('resolved_revision')}, remote resolved {resolved}."
        )

    local_path = snapshot_download(
        repo_id=config.model_id,
        revision=resolved,
        local_dir=config.model_dir,
        local_dir_use_symlinks=False,
    )
    lock_data = {
        "model_id": config.model_id,
        "resolved_revision": resolved,
        "local_path": str(local_path),
        "pinned_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(config.model_lock, lock_data)
    return lock_data


def load_text_generator(config: PipelineConfig):
    """Load Qwen locally from the pinned/cached snapshot."""
    if config.local_generation:
        raise RuntimeError("Mock/local template generation is disabled for video scripts. Use Qwen.")

    from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

    lock = read_json(config.model_lock, {})
    revision = lock.get("resolved_revision") or config.model_revision
    if not revision:
        raise RuntimeError("Run `interview-auto model-setup` before model generation.")
    tokenizer = AutoTokenizer.from_pretrained(config.model_dir, local_files_only=True, revision=revision)
    model = AutoModelForCausalLM.from_pretrained(config.model_dir, local_files_only=True, revision=revision)
    return pipeline("text-generation", model=model, tokenizer=tokenizer, device=-1)
