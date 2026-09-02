from __future__ import annotations


def prepare_publish_metadata(script: dict, enabled: bool = False) -> dict:
    metadata = {
        "enabled": enabled,
        "status": "disabled" if not enabled else "manual_approval_required",
        "title": script["title"],
        "description": script["description"],
        "tags": script["tags"],
        "rate_limit": "one_video_per_day",
        "api": "official_youtube_oauth_only",
    }
    if enabled:
        raise RuntimeError("Publishing is intentionally not implemented in dry-run mode.")
    return metadata
