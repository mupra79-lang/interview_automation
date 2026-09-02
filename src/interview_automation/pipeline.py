from __future__ import annotations

from pathlib import Path

from .cleanup import cleanup_run
from .config import PipelineConfig
from .discovery import discover_topics
from .logging_setup import configure_logging
from .model_manager import load_text_generator
from .publisher import prepare_publish_metadata
from .quality import validate_script
from .rendering import render_video
from .scoring import select_topic
from .script_generation import generate_script
from .state import RunState
from .thumbnail import generate_thumbnail
from .tts import synthesize_segments
from .utils import read_json, slugify, write_json
from .validation import validate_package
from .visuals import generate_visuals


def run_pipeline(config: PipelineConfig, resume: bool = True) -> Path:
    config.ensure_dirs()
    run_slug = slugify(config.topic)
    run_dir = config.runs_dir / run_slug
    run_dir.mkdir(parents=True, exist_ok=True)
    logger = configure_logging(run_dir, verbose=True)
    state = RunState(run_dir)
    final_artifacts = [
        run_dir / "final.mp4",
        run_dir / "thumbnail.png",
        run_dir / "script.json",
        run_dir / "manifest.json",
    ]
    if resume and state.completed("publish_ready") and all(path.exists() for path in final_artifacts):
        cleanup_run(run_dir, run_dir / "cleanup_report.json", keep_intermediate=config.keep_intermediate)
        logger.info("Reusing completed package at %s", run_dir)
        return run_dir

    discovery_path = run_dir / "discovery.json"
    if not (resume and state.completed("discovery") and discovery_path.exists()):
        state.mark("discovery", "running")
        signals = discover_topics(config, discovery_path, logger)
        state.artifact("discovery", discovery_path)
        state.mark("discovery", "completed", {"signals": len(signals)})

    selected_path = run_dir / "selected_topic.json"
    if not (resume and state.completed("topic_selection") and selected_path.exists()):
        state.mark("topic_selection", "running")
        signals = read_json(discovery_path, {"signals": []})["signals"]
        selected = select_topic(signals, config.cache_dir / "channel_history.json", selected_path, config.topic)
        state.artifact("selected_topic", selected_path)
        state.mark("topic_selection", "completed", {"topic": selected["topic"]})

    script_path = run_dir / "script.json"
    if not (resume and state.completed("script") and script_path.exists()):
        state.mark("script", "running")
        selected = read_json(selected_path)
        generator = load_text_generator(config)
        script = generate_script(selected["topic"], config.question_count, script_path, generator)
        state.artifact("script", script_path)
        state.mark("script", "completed", {"fingerprint": script["uniqueness_fingerprint"]})

    quality_path = run_dir / "quality_report.json"
    if not (resume and state.completed("quality_check") and quality_path.exists()):
        state.mark("quality_check", "running")
        report = validate_script(read_json(script_path), config.cache_dir / "channel_history.json", quality_path)
        state.artifact("quality_report", quality_path)
        state.mark("quality_check", "completed", report)

    audio_manifest_path = run_dir / "audio_manifest.json"
    if not (resume and state.completed("narration") and audio_manifest_path.exists()):
        state.mark("narration", "running")
        audio = synthesize_segments(read_json(script_path), run_dir / "audio", audio_manifest_path, config)
        state.artifact("audio_manifest", audio_manifest_path)
        state.mark("narration", "completed", {"segments": len(audio["segments"])})

    slides_manifest_path = run_dir / "slides_manifest.json"
    if not (resume and state.completed("visuals") and slides_manifest_path.exists()):
        state.mark("visuals", "running")
        slides = generate_visuals(read_json(script_path), config, run_dir / "slides", slides_manifest_path)
        state.artifact("slides_manifest", slides_manifest_path)
        state.mark("visuals", "completed", {"slides": len(slides["slides"])})

    render_manifest_path = run_dir / "render_manifest.json"
    if not (resume and state.completed("render") and render_manifest_path.exists()):
        state.mark("render", "running")
        render = render_video(read_json(slides_manifest_path), read_json(audio_manifest_path), config, run_dir / "render", render_manifest_path)
        final_video = run_dir / "final.mp4"
        Path(render["video"]).replace(final_video)
        thumbnail_path = generate_thumbnail(read_json(script_path), config, run_dir / "thumbnail.png")
        state.artifact("final_video", final_video)
        state.artifact("thumbnail", thumbnail_path)
        state.mark("render", "completed", {"video": str(final_video)})

    validation_path = run_dir / "validation_report.json"
    if not (resume and state.completed("validation") and validation_path.exists()):
        state.mark("validation", "running")
        report = validate_package(
            run_dir / "final.mp4",
            run_dir / "thumbnail.png",
            read_json(slides_manifest_path),
            config,
            validation_path,
        )
        state.artifact("validation_report", validation_path)
        state.mark("validation", "completed", report)

    manifest_path = run_dir / "manifest.json"
    if not (resume and state.completed("publish_ready") and manifest_path.exists()):
        state.mark("publish_ready", "running")
        script = read_json(script_path)
        manifest = {
            "script": str(script_path),
            "video": str(run_dir / "final.mp4"),
            "thumbnail": str(run_dir / "thumbnail.png"),
            "publish": prepare_publish_metadata(script, enabled=config.publish_enabled),
        }
        write_json(manifest_path, manifest)
        state.artifact("manifest", manifest_path)
        state.mark("publish_ready", "completed", {"publish": manifest["publish"]["status"]})

    cleanup_run(run_dir, run_dir / "cleanup_report.json", keep_intermediate=config.keep_intermediate)
    logger.info("Package ready at %s", run_dir)
    return run_dir
