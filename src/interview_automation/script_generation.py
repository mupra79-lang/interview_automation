from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

from .utils import sha256_text, write_json


def build_script_prompt(topic: str, count: int) -> str:
    return f"""
Create an original YouTube interview-preparation script as strict JSON only.

Topic: {topic}
Question count: {count}

Requirements:
- Write for students and developers preparing for technical interviews.
- Do not copy competitor questions, scripts, thumbnails, narration, branding, or visuals.
- Do not claim a question was asked by a named company unless a provided source proves it.
- Do not invent private YouTube metrics, exact 24-hour views, or historical channel averages.
- Include a strong opening narration that starts after the viewer clicks the video, welcomes them, names the topic, and promises {count} practical questions with sample answers.
- Make every answer concise, spoken, useful, and interview-ready.
- Use beginner-to-intermediate clarity with practical examples where useful.
- Return exactly this schema:
{{
  "title": "string",
  "title_ideas": ["string", "string", "string"],
  "audience": "string",
  "difficulty": "beginner|intermediate|advanced",
  "questions": [
    {{
      "number": 1,
      "question": "string",
      "answer": "string",
      "key_points": ["string", "string", "string"],
      "example": "string"
    }}
  ],
  "narration": [
    "opening narration",
    "one narration segment per question",
    "outro narration"
  ],
  "chapters": [{{"time": "00:00", "title": "Intro"}}],
  "description": "string",
  "tags": ["string"],
  "thumbnail_text": "string",
  "sources": ["Original educational content"],
  "uniqueness_fingerprint": ""
}}
""".strip()


def _extract_json(text: str) -> dict[str, Any]:
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    candidate = match.group(1) if match else text
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Qwen did not return a JSON object.")
    return json.loads(candidate[start : end + 1])


def _call_generator(generator: Callable[..., Any], prompt: str) -> str:
    result = generator(
        prompt,
        max_new_tokens=4096,
        do_sample=True,
        temperature=0.7,
        top_p=0.9,
        return_full_text=False,
    )
    if isinstance(result, str):
        return result
    if isinstance(result, list) and result:
        first = result[0]
        if isinstance(first, dict):
            return str(first.get("generated_text", ""))
        return str(first)
    raise ValueError("Qwen generator returned an unsupported response.")


def normalize_script(script: dict[str, Any], topic: str, count: int) -> dict[str, Any]:
    questions = script.get("questions", [])
    if len(questions) != count:
        raise ValueError(f"Expected {count} questions from Qwen, got {len(questions)}.")
    for index, question in enumerate(questions, start=1):
        question["number"] = index

    narration = script.get("narration", [])
    if len(narration) != count + 2:
        raise ValueError(f"Expected {count + 2} narration segments, got {len(narration)}.")

    full = " ".join(
        [script.get("title", topic)]
        + [item.get("question", "") + " " + item.get("answer", "") for item in questions]
    )
    script["uniqueness_fingerprint"] = sha256_text(full)
    script.setdefault("sources", ["Original educational content"])
    script.setdefault("thumbnail_text", script.get("title", topic)[:80])
    return script


def generate_script(
    topic: str,
    count: int,
    out_path: Path,
    generator: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    if generator is None:
        raise RuntimeError("Script generation requires the local Qwen2.5-1.5B-Instruct generator.")
    prompt = build_script_prompt(topic, count)
    raw = _call_generator(generator, prompt)
    script = normalize_script(_extract_json(raw), topic, count)
    write_json(out_path, script)
    return script
