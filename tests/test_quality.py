from __future__ import annotations

import pytest

from interview_automation.quality import validate_script
from interview_automation.script_generation import generate_script
from tests.helpers import fake_qwen_generator


def test_schema_validation_accepts_generated_script(tmp_path) -> None:
    script = generate_script("Top 10 LangGraph Interview Questions", 10, tmp_path / "script.json", fake_qwen_generator)
    report = validate_script(script, tmp_path / "history.json", tmp_path / "report.json")
    assert report["approved"]


def test_duplicate_questions_are_rejected(tmp_path) -> None:
    script = generate_script("Top 10 LangGraph Interview Questions", 10, tmp_path / "script.json", fake_qwen_generator)
    script["questions"][1]["question"] = script["questions"][0]["question"]
    with pytest.raises(ValueError):
        validate_script(script, tmp_path / "history.json", tmp_path / "report.json")


def test_fake_company_claims_are_rejected(tmp_path) -> None:
    script = generate_script("Top 10 LangGraph Interview Questions", 10, tmp_path / "script.json", fake_qwen_generator)
    script["questions"][0]["answer"] += " This exact interview question was asked by Google."
    with pytest.raises(ValueError):
        validate_script(script, tmp_path / "history.json", tmp_path / "report.json")


def test_malformed_qwen_json_is_repaired_by_retry(tmp_path) -> None:
    calls = {"count": 0}

    def flaky_generator(prompt: str, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return [{"generated_text": '{"title": "Broken" "questions": []}'}]
        return fake_qwen_generator(prompt, **kwargs)

    script = generate_script("Top 10 LangGraph Interview Questions", 10, tmp_path / "script.json", flaky_generator)
    assert script["title"] == "Top 10 LangGraph Interview Questions"
    assert calls["count"] == 2
    assert (tmp_path / "script.raw_attempt_1.txt").exists()


def test_short_qwen_narration_is_built_from_generated_questions(tmp_path) -> None:
    script = generate_script("Top 10 LangGraph Interview Questions", 10, tmp_path / "script.json", fake_qwen_generator)
    script["narration"] = script["narration"][:4]
    from interview_automation.script_generation import normalize_script

    normalized = normalize_script(script, "Top 10 LangGraph Interview Questions", 10)
    assert len(normalized["narration"]) == 12
    assert normalized["questions"][0]["question"] in normalized["narration"][1]


def test_extra_qwen_questions_are_trimmed_and_metadata_is_filled(tmp_path) -> None:
    from interview_automation.script_generation import normalize_script

    script = fake_qwen_generator("")[0]["generated_text"]
    import json

    data = json.loads(script)
    data["questions"].append(data["questions"][0].copy())
    data.pop("tags")
    data.pop("title_ideas")
    data["narration"] = []
    normalized = normalize_script(data, "Top 10 LangGraph Interview Questions", 10)
    assert len(normalized["questions"]) == 10
    assert len(normalized["title_ideas"]) == 3
    assert normalized["tags"]
    assert len(normalized["narration"]) == 12
