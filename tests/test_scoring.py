from __future__ import annotations

from datetime import datetime, timezone

from interview_automation.scoring import near_duplicate, score_signal


def test_near_duplicate_detects_similar_titles() -> None:
    assert near_duplicate("Top 10 LangGraph Interview Questions", "Top 10 LangGraph Interview Questions")
    assert not near_duplicate("Top 10 LangGraph Interview Questions", "Docker Networking Deep Dive")


def test_score_signal_uses_public_current_stats_without_fake_history() -> None:
    signal = {
        "published_at": datetime.now(timezone.utc).isoformat(),
        "view_count": 5000,
        "subscriber_count": 10000,
    }
    assert score_signal(signal) > 0
