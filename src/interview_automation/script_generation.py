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
- Generate exactly {count} question objects, numbered 1 to {count}.
- Generate exactly {count + 2} narration strings: opening, one segment for each question, and outro.
- Keep every answer between 45 and 95 words so it fits video slides.
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
    json_text = _find_balanced_json_object(candidate)
    if not json_text:
        raise ValueError("Qwen did not return a JSON object.")
    return json.loads(json_text)


def _find_balanced_json_object(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _call_generator(generator: Callable[..., Any], prompt: str) -> str:
    result = generator(
        prompt,
        max_new_tokens=8192,
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


def build_repair_prompt(topic: str, count: int, raw: str, error: Exception) -> str:
    return f"""
The previous response was meant to be strict JSON for a YouTube interview-preparation video, but it failed to parse.

Topic: {topic}
Question count: {count}
JSON error: {error}

Fix the response below into valid JSON only. Do not add markdown, comments, explanations, or extra text.
Preserve the original meaning, keep exactly {count} questions, and keep exactly {count + 2} narration segments.
If metadata is missing, add suitable original metadata. If narration is missing, create narration from the existing questions and answers.
If there are more than {count} questions, keep the best {count}. If there are fewer than {count}, add original questions for the same topic.

Broken response:
{raw}
""".strip()


def normalize_script(script: dict[str, Any], topic: str, count: int) -> dict[str, Any]:
    questions = coerce_questions(script.get("questions", []))
    if len(questions) > count:
        questions = questions[:count]
    if len(questions) != count:
        raise ValueError(f"Expected {count} questions from Qwen, got {len(questions)}.")
    for index, question in enumerate(questions, start=1):
        question["number"] = index
        question["question"] = require_text(question.get("question"), f"question {index}")
        question["answer"] = require_text(question.get("answer"), f"answer {index}")
        question["key_points"] = coerce_string_list(question.get("key_points"))[:5]
        if not question["key_points"]:
            question["key_points"] = infer_key_points(question["answer"])
        question["example"] = str(question.get("example") or "").strip()
    script["questions"] = questions

    title = str(script.get("title") or topic).strip()
    narration = coerce_string_list(script.get("narration", []))
    if len(narration) != count + 2:
        narration = build_narration_from_generated_content(title, questions, count)
    script["narration"] = narration

    if len(narration) != count + 2:
        raise ValueError(f"Expected {count + 2} narration segments, got {len(narration)}.")

    script["title"] = title
    title_ideas = coerce_string_list(script.get("title_ideas"))
    script["title_ideas"] = (title_ideas + [title, f"{topic} Interview Preparation", f"{topic} Questions and Answers"])[:3]
    script["audience"] = str(script.get("audience") or "Students and developers preparing for technical interviews.").strip()
    difficulty = str(script.get("difficulty") or "intermediate").strip().lower()
    script["difficulty"] = difficulty if difficulty in {"beginner", "intermediate", "advanced"} else "intermediate"
    chapters = script.get("chapters")
    script["chapters"] = chapters if isinstance(chapters, list) and chapters else (
        [{"time": "00:00", "title": "Intro"}]
        + [{"time": "", "title": f"Q{item['number']}: {item['question']}"} for item in questions]
    )
    script["description"] = str(script.get("description") or f"Practice {count} original interview questions with concise sample answers for {topic}.").strip()
    tags = coerce_string_list(script.get("tags"))
    script["tags"] = (tags + [topic, "Interview Questions", "Interview Preparation"])[:12]
    sources = coerce_string_list(script.get("sources"))
    script["sources"] = sources or ["Original educational content"]
    script["thumbnail_text"] = str(script.get("thumbnail_text") or title[:80]).strip()

    full = " ".join(
        [script.get("title", title)]
        + [item.get("question", "") + " " + item.get("answer", "") for item in questions]
    )
    script["uniqueness_fingerprint"] = sha256_text(full)
    return script


def coerce_questions(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def coerce_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def require_text(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"Missing generated {label}.")
    return text


def infer_key_points(answer: str) -> list[str]:
    words = [
        word.strip(".,:;!?()[]{}").lower()
        for word in answer.split()
        if len(word.strip(".,:;!?()[]{}")) > 5
    ]
    seen: list[str] = []
    for word in words:
        if word not in seen:
            seen.append(word)
        if len(seen) == 3:
            break
    return seen or ["definition", "use case", "interview framing"]


def build_narration_from_generated_content(title: str, questions: list[dict[str, Any]], count: int) -> list[str]:
    narration = [
        (
            f"Welcome to {title}. Today we will practice {count} important interview "
            "questions with clear sample answers, key points, and practical examples."
        )
    ]
    for item in questions:
        key_points = ", ".join(item.get("key_points", []))
        example = item.get("example", "")
        segment = (
            f"Question {item['number']}. {item['question']} "
            f"Sample answer. {item['answer']}"
        )
        if key_points:
            segment += f" Key points to cover: {key_points}."
        if example:
            segment += f" Example: {example}"
        narration.append(segment)
    narration.append(
        "That completes this interview preparation set. Review each sample answer, "
        "practice speaking it in your own words, and use the key points to stay clear and confident."
    )
    return narration


def generate_script(
    topic: str,
    count: int,
    out_path: Path,
    generator: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    if generator is None:
        raise RuntimeError("Script generation requires the local Qwen2.5-1.5B-Instruct generator.")
    prompt = build_script_prompt(topic, count)
    errors: list[str] = []
    raw = ""
    for attempt in range(1, 5):
        raw = _call_generator(generator, prompt)
        raw_path = out_path.with_name(f"{out_path.stem}.raw_attempt_{attempt}.txt")
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(raw, encoding="utf-8")
        try:
            script = normalize_script(_extract_json(raw), topic, count)
            write_json(out_path, script)
            return script
        except (json.JSONDecodeError, ValueError) as exc:
            errors.append(f"attempt {attempt}: {exc}")
            prompt = build_repair_prompt(topic, count, raw, exc)

    raise ValueError("Qwen failed to produce valid script JSON after repair attempts. " + " | ".join(errors))
