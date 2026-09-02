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
