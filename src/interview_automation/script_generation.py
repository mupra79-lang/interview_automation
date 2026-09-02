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
    """Return the first complete JSON object in a model response.

    Models occasionally add a short preamble, or include braces in that preamble.
    Trying every complete, balanced object avoids mistaking those braces for the
    requested payload.  Malformed JSON is deliberately not guessed or silently
    repaired here: the same local model receives a focused repair request.
    """
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    candidate = match.group(1) if match else text
    errors: list[json.JSONDecodeError] = []
    for start in (index for index, char in enumerate(candidate) if char == "{"):
        json_text = _find_balanced_json_object(candidate[start:])
        if not json_text:
            continue
        try:
            value = json.loads(json_text)
        except json.JSONDecodeError as exc:
            errors.append(exc)
            continue
        if isinstance(value, dict):
            return value
    if errors:
        raise errors[-1]
    raise ValueError("Qwen did not return a complete JSON object.")


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
        max_new_tokens=4096,
        do_sample=False,
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


def build_piece_repair_prompt(topic: str, purpose: str, raw: str, error: Exception) -> str:
    return f"""
The following response for {purpose} in an original {topic} interview-preparation
video is malformed JSON.

JSON error: {error}

Return only one valid JSON object. Preserve the generated educational content,
but remove markdown, comments, trailing commas, and any prose outside the JSON.
Do not invent company-specific claims.

Broken response:
{raw}
""".strip()


def build_metadata_prompt(topic: str, count: int) -> str:
    return f"""
Create metadata for an original YouTube interview-preparation video about {topic}.
Return JSON only with exactly these fields: title, title_ideas, audience,
difficulty, description, tags, thumbnail_text, sources.
The video contains {count} questions. Keep language useful and original. Do not
make company-specific claims or copy another channel. sources must be
["Original educational content"].
""".strip()


def build_question_batch_prompt(topic: str, start: int, size: int) -> str:
    end = start + size - 1
    return f"""
Create exactly {size} original interview questions for {topic}, numbered {start}
through {end}. Return JSON only in this shape:
{{"questions":[{{"number":{start},"question":"...","answer":"...","key_points":["...","...","..."],"example":"..."}}]}}
Each answer must be 45 to 95 words, spoken, accurate, and useful in an interview.
Do not use company-specific claims, copied questions, markdown, or comments.
""".strip()


def build_narration_prompt(topic: str, title: str, questions: list[dict[str, Any]]) -> str:
    question_context = json.dumps(
        [
            {
                "number": item["number"],
                "question": item["question"],
                "answer": item["answer"],
                "key_points": item["key_points"],
                "example": item["example"],
            }
            for item in questions
        ],
        ensure_ascii=True,
    )
    return f"""
Write narration for an original interview-preparation video.
Topic: {topic}
Title: {title}
Return JSON only: {{"narration":[...]}}.
Return exactly {len(questions) + 2} narration strings: a warm opening that welcomes
the viewer and says they will practise {len(questions)} questions, one spoken
segment per supplied question in order, then a concise outro. Each question
segment must include its question and sample answer. Use only these generated
questions and do not add company-specific claims.
Questions:
{question_context}
""".strip()


def _generate_json_piece(
    generator: Callable[..., Any],
    prompt: str,
    topic: str,
    purpose: str,
    out_path: Path,
    validator: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    for attempt in range(1, 5):
        raw = _call_generator(generator, prompt)
        raw_path = out_path.with_name(f"{out_path.stem}.{purpose}.raw_attempt_{attempt}.txt")
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(raw, encoding="utf-8")
        try:
            payload = _extract_json(raw)
            if validator:
                validator(payload)
            return payload
        except (json.JSONDecodeError, ValueError) as exc:
            errors.append(f"attempt {attempt}: {exc}")
            prompt = build_piece_repair_prompt(topic, purpose, raw, exc)
    raise ValueError(f"Qwen failed to produce valid {purpose} JSON. " + " | ".join(errors))


def validate_metadata_payload(payload: dict[str, Any]) -> None:
    for field in ("title", "audience", "difficulty", "description", "thumbnail_text"):
        require_text(payload.get(field), f"metadata {field}")
    for field in ("title_ideas", "tags", "sources"):
        if not coerce_string_list(payload.get(field)):
            raise ValueError(f"Missing generated metadata {field}.")


def validate_question_batch_payload(payload: dict[str, Any], start: int, size: int) -> None:
    expected_numbers = list(range(start, start + size))
    questions = coerce_questions(payload.get("questions"))
    selected = [item for item in questions if item.get("number") in expected_numbers]
    if [item.get("number") for item in selected] != expected_numbers:
        raise ValueError(f"Expected numbered questions {expected_numbers}, got {[item.get('number') for item in selected]}.")
    for item in selected:
        require_text(item.get("question"), f"question {item['number']}")
        require_text(item.get("answer"), f"answer {item['number']}")


def validate_narration_payload(payload: dict[str, Any], count: int) -> None:
    narration = coerce_string_list(payload.get("narration"))
    if len(narration) != count + 2:
        raise ValueError(f"Expected {count + 2} narration segments, got {len(narration)}.")


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
    # Small deterministic model calls are substantially more reliable than one
    # response containing duplicated answers in questions, narration, chapters,
    # and metadata. Every educational word still originates with local Qwen.
    metadata = _generate_json_piece(
        generator,
        build_metadata_prompt(topic, count),
        topic,
        "metadata",
        out_path,
        validate_metadata_payload,
    )

    questions: list[dict[str, Any]] = []
    batch_size = 3
    for start in range(1, count + 1, batch_size):
        size = min(batch_size, count - start + 1)
        batch = _generate_json_piece(
            generator,
            build_question_batch_prompt(topic, start, size),
            topic,
            f"questions_{start:02d}_{start + size - 1:02d}",
            out_path,
            lambda payload, batch_start=start, batch_size=size: validate_question_batch_payload(
                payload, batch_start, batch_size
            ),
        )
        generated_questions = [
            item
            for item in coerce_questions(batch.get("questions"))
            if item.get("number") in range(start, start + size)
        ]
        if len(generated_questions) != size:
            raise ValueError(
                f"Qwen returned {len(generated_questions)} questions for batch {start}-{start + size - 1}; expected {size}."
            )
        questions.extend(generated_questions)

    preliminary = normalize_script(
        {**metadata, "questions": questions, "narration": ["pending"] * (count + 2)},
        topic,
        count,
    )
    narration_payload = _generate_json_piece(
        generator,
        build_narration_prompt(topic, preliminary["title"], preliminary["questions"]),
        topic,
        "narration",
        out_path,
        lambda payload: validate_narration_payload(payload, count),
    )
    narration = coerce_string_list(narration_payload.get("narration"))
    if len(narration) != count + 2:
        raise ValueError(
            f"Qwen returned {len(narration)} narration segments; expected {count + 2}."
        )

    script = normalize_script(
        {**metadata, "questions": questions, "narration": narration}, topic, count
    )
    write_json(out_path, script)
    return script
