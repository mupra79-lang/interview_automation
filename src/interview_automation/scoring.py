from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .discovery import TAXONOMY
from .utils import read_json, sha256_text, write_json


EVERGREEN = [
    "Python",
    "Java",
    "SQL",
    "DSA",
    "DBMS",
    "Operating Systems",
    "Networking",
    "Docker",
    "Kubernetes",
    "AWS",
    "Azure",
    "FastAPI",
    "React",
    "LangChain",
    "LangGraph",
    "RAG",
    "LLM Evaluation",
    "Machine Learning",
    "GenAI",
    "Agentic AI",
]

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "do",
    "does",
    "explain",
    "for",
    "how",
    "in",
    "interview",
    "is",
    "it",
    "of",
    "the",
    "to",
    "top",
    "what",
    "when",
    "why",
    "would",
    "you",
}


def near_duplicate(a: str, b: str, threshold: float = 0.82) -> bool:
    aw = {word for word in a.lower().split() if word not in STOPWORDS and len(word) > 2}
    bw = {word for word in b.lower().split() if word not in STOPWORDS and len(word) > 2}
    if not aw or not bw:
        return False
    return len(aw & bw) / len(aw | bw) >= threshold


def score_signal(signal: dict, snapshot_growth: int = 0) -> float:
    published = datetime.fromisoformat(signal["published_at"].replace("Z", "+00:00"))
    age_hours = max(1.0, (datetime.now(timezone.utc) - published).total_seconds() / 3600)
    recency = max(0.1, 1.0 / age_hours)
    views = int(signal.get("view_count") or 0)
    subs = signal.get("subscriber_count")
    vps = views / max(1, int(subs)) if subs else 0.0
    competition_penalty = 0.15 if views > 100000 else 0.0
    return (recency * 40) + min(40, views / 1000) + min(30, vps * 100) + min(30, snapshot_growth / 500) - competition_penalty


def select_topic(signals: list[dict], history_path: Path, out_path: Path, fallback_topic: str) -> dict:
    history = read_json(history_path, {"videos": []}).get("videos", [])
    previous_titles = [item.get("title", "") for item in history]
    candidates = []
    for signal in signals:
        title = signal.get("title") or fallback_topic
        if any(near_duplicate(title, prev) for prev in previous_titles):
            continue
        candidates.append({"topic": fallback_topic, "signal": signal, "score": score_signal(signal)})

    if not candidates:
        used = {item.get("topic") for item in history}
        fallback = next((topic for topic in EVERGREEN if topic not in used), "Python")
        selected = {
            "topic": f"Top 10 {fallback} Interview Questions",
            "signal": {"source": "evergreen_rotation", "title": fallback},
            "score": 0,
        }
    else:
        selected = sorted(candidates, key=lambda item: item["score"], reverse=True)[0]

    selected["uniqueness_seed"] = sha256_text(selected["topic"])[:16]
    write_json(out_path, selected)
    return selected
