from __future__ import annotations

from interview_automation.cleanup import cleanup_run
from interview_automation.state import RunState


def test_run_state_marks_resume_stage(tmp_path) -> None:
    state = RunState(tmp_path)
    state.mark("script", "completed", {"ok": True})
    assert state.completed("script")


def test_safe_cleanup_keeps_final_artifacts(tmp_path) -> None:
    keep = tmp_path / "final.mp4"
    temp_dir = tmp_path / "audio"
    keep.write_bytes(b"video")
    temp_dir.mkdir()
    (temp_dir / "segment.wav").write_bytes(b"audio")
    cleanup_run(tmp_path, tmp_path / "cleanup_report.json")
    assert keep.exists()
    assert not temp_dir.exists()
