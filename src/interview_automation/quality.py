from __future__ import annotations

import re
from pathlib import Path

from jsonschema import validate

from .schema import SCRIPT_SCHEMA
from .scoring import near_duplicate
from .utils import read_json, sha256_text, write_json


BLOCKED_CLAIMS = [
    r"\basked by\b.*\b(google|microsoft|amazon|meta|openai)\b",
    r"\bexact\b.*\b(company|interview)\b",
    r"\bguaranteed\b.*\binterview\b",
]


def validate_script(script: dict, history_path: Path, report_path: Path) -> dict:
    issues: list[str] = []
    validate(instance=script, schema=SCRIPT_SCHEMA)

    questions = [item["question"] for item in script["questions"]]
    for index, question in enumerate(questions):
        for other in questions[index + 1 :]:
            if near_duplicate(question, other, threshold=0.75):
                issues.append(f"Duplicate or near-duplicate question: {question}")

    for item in script["questions"]:
        if len(item["answer"].split()) < 25:
            issues.append(f"Weak answer for question {item['number']}")

    full_text = " ".join(
        [script["title"], script["description"]]
        + questions
        + [item["answer"] for item in script["questions"]]
    )
    for pattern in BLOCKED_CLAIMS:
        if re.search(pattern, full_text, flags=re.IGNORECASE):
            issues.append(f"Unsupported company-specific claim matched: {pattern}")

    history = read_json(history_path, {"videos": []}).get("videos", [])
    for previous in history:
        if previous.get("fingerprint") == script["uniqueness_fingerprint"]:
            issues.append("Script fingerprint already exists in channel history.")
        if near_duplicate(previous.get("title", ""), script["title"], threshold=0.82):
            issues.append("Near-duplicate title exists in channel history.")

    report = {
        "approved": not issues,
        "issues": issues,
        "question_count": len(questions),
        "fingerprint": script["uniqueness_fingerprint"] or sha256_text(full_text),
    }
    write_json(report_path, report)
    if issues:
        raise ValueError("Script quality check failed: " + "; ".join(issues))
    return report
