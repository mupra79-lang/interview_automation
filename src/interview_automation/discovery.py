from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import requests

from .config import PipelineConfig
from .utils import read_json, sha256_text, write_json


TAXONOMY = [
    "Python interview questions",
    "Java interview questions",
    "SQL interview questions",
    "DSA interview questions",
    "DBMS interview questions",
    "operating systems interview questions",
    "networking interview questions",
    "Docker interview questions",
    "Kubernetes interview questions",
    "AWS interview questions",
    "Azure interview questions",
    "FastAPI interview questions",
    "React interview questions",
    "LangChain interview questions",
    "LangGraph interview questions",
    "RAG interview questions",
    "LLM evaluation interview questions",
    "machine learning interview questions",
    "Generative AI interview questions",
    "Agentic AI interview questions",
]


@dataclass(frozen=True)
class TopicSignal:
    query: str
    title: str
    video_id: str
    channel_id: str
    published_at: str
    view_count: int
    subscriber_count: int | None
    source: str = "youtube_api"


class DiscoveryCache:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as con:
            con.execute(
                "CREATE TABLE IF NOT EXISTS api_cache "
                "(key TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL)"
            )
            con.execute(
                "CREATE TABLE IF NOT EXISTS quota "
                "(day TEXT PRIMARY KEY, units INTEGER NOT NULL)"
            )

    def get(self, key: str, cooldown_hours: int) -> dict | None:
        with sqlite3.connect(self.db_path) as con:
            row = con.execute("SELECT created_at, payload FROM api_cache WHERE key=?", (key,)).fetchone()
        if not row:
            return None
        created_at = datetime.fromisoformat(row[0])
        if datetime.now(timezone.utc) - created_at > timedelta(hours=cooldown_hours):
            return None
        return read_json_from_string(row[1])

    def put(self, key: str, payload: dict) -> None:
        with sqlite3.connect(self.db_path) as con:
            con.execute(
                "REPLACE INTO api_cache VALUES (?, ?, ?)",
                (key, datetime.now(timezone.utc).isoformat(), json_dumps(payload)),
            )

    def spend_quota(self, units: int, limit: int) -> None:
        day = datetime.now(timezone.utc).date().isoformat()
        with sqlite3.connect(self.db_path) as con:
            row = con.execute("SELECT units FROM quota WHERE day=?", (day,)).fetchone()
            used = row[0] if row else 0
            if used + units > limit:
                raise RuntimeError(f"YouTube quota budget exceeded: {used + units}/{limit}")
            con.execute("REPLACE INTO quota VALUES (?, ?)", (day, used + units))


def json_dumps(payload: dict) -> str:
    import json

    return json.dumps(payload, sort_keys=True)


def read_json_from_string(value: str) -> dict:
    import json

    return json.loads(value)


def expand_taxonomy(topic: str, count: int = 8) -> list[str]:
    base = [topic, f"{topic} interview questions", f"{topic} tutorial interview preparation"]
    for item in TAXONOMY:
        if len(base) >= count:
            break
        if item.lower() not in {q.lower() for q in base}:
            base.append(item)
    return base[:count]


def youtube_request(
    config: PipelineConfig,
    cache: DiscoveryCache,
    endpoint: str,
    params: dict,
    quota_units: int,
    logger: logging.Logger,
) -> dict:
    key = sha256_text(endpoint + json_dumps(params))
    cached = cache.get(key, config.youtube_cache_cooldown_hours)
    if cached is not None:
        logger.info("Using cached YouTube API result for %s", endpoint)
        return cached
    cache.spend_quota(quota_units, config.youtube_daily_quota_units)
    if not config.youtube_api_key:
        raise RuntimeError("YOUTUBE_API_KEY is required for YouTube discovery.")

    url = f"https://www.googleapis.com/youtube/v3/{endpoint}"
    params = {**params, "key": config.youtube_api_key}
    delay = 1.0
    for attempt in range(4):
        logger.info("YouTube API call endpoint=%s attempt=%s", endpoint, attempt + 1)
        response = requests.get(url, params=params, timeout=20)
        if response.status_code < 500:
            response.raise_for_status()
            payload = response.json()
            cache.put(key, payload)
            return payload
        time.sleep(delay)
        delay *= 2
    response.raise_for_status()
    raise RuntimeError("unreachable")


def discover_topics(config: PipelineConfig, out_path: Path, logger: logging.Logger) -> list[dict]:
    if config.dry_run:
        signals = [
            {
                "query": "LangGraph interview questions",
                "title": "Top LangGraph Interview Questions for AI Engineers",
                "video_id": "dry-run",
                "channel_id": "dry-run",
                "published_at": datetime.now(timezone.utc).isoformat(),
                "view_count": 0,
                "subscriber_count": None,
                "source": "dry_run_seed",
            }
        ]
        write_json(out_path, {"signals": signals, "note": "Dry run skips YouTube API."})
        return signals

    cache = DiscoveryCache(config.cache_dir / "youtube.sqlite3")
    windows = {
        "24h": (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(),
        "7d": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),
    }
    signals: list[dict] = []
    for query in expand_taxonomy(config.topic, count=2):
        for window_name, published_after in windows.items():
            search_payload = youtube_request(
                config,
                cache,
                "search",
                {
                    "part": "snippet",
                    "q": query,
                    "type": "video",
                    "order": "date",
                    "maxResults": "3",
                    "publishedAfter": published_after,
                },
                100,
                logger,
            )
            video_ids = [item["id"]["videoId"] for item in search_payload.get("items", [])]
            if not video_ids:
                continue
            stats_payload = youtube_request(
                config,
                cache,
                "videos",
                {"part": "statistics,snippet", "id": ",".join(video_ids), "maxResults": "3"},
                1,
                logger,
            )
            channel_ids = list({item["snippet"]["channelId"] for item in stats_payload.get("items", [])})
            channel_payload = youtube_request(
                config,
                cache,
                "channels",
                {"part": "statistics", "id": ",".join(channel_ids), "maxResults": "3"},
                1,
                logger,
            )
            subscribers = {
                item["id"]: int(item.get("statistics", {}).get("subscriberCount", 0))
                for item in channel_payload.get("items", [])
                if not item.get("statistics", {}).get("hiddenSubscriberCount", False)
            }
            for item in stats_payload.get("items", []):
                snippet = item["snippet"]
                signal = TopicSignal(
                    query=query,
                    title=snippet["title"],
                    video_id=item["id"],
                    channel_id=snippet["channelId"],
                    published_at=snippet["publishedAt"],
                    view_count=int(item.get("statistics", {}).get("viewCount", 0)),
                    subscriber_count=subscribers.get(snippet["channelId"]),
                ).__dict__
                signal["window"] = window_name
                signals.append(signal)
    write_json(out_path, {"signals": signals})
    return signals


def load_previous_history(path: Path) -> list[dict]:
    payload = read_json(path, {"videos": []})
    return payload.get("videos", [])
