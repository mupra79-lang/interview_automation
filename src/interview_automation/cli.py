from __future__ import annotations

import argparse

from .config import PipelineConfig
from .model_manager import ensure_qwen_model
from .pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interview-preparation video automation.")
    sub = parser.add_subparsers(dest="command", required=True)

    dry = sub.add_parser("dry-run", help="Create one complete local package without YouTube discovery or publishing.")
    dry.add_argument("--topic", default="Top 10 LangGraph Interview Questions")
    dry.add_argument("--questions", type=int, choices=(10, 20), default=10)
    dry.add_argument("--keep-intermediate", action="store_true")
    dry.add_argument("--no-resume", action="store_true")

    run = sub.add_parser("run", help="Run official-API discovery and create one package.")
    run.add_argument("--topic", default="AI ML interview questions")
    run.add_argument("--questions", type=int, choices=(10, 20), default=10)
    run.add_argument("--keep-intermediate", action="store_true")
    run.add_argument("--no-resume", action="store_true")

    setup = sub.add_parser("model-setup", help="Download Qwen once and pin the resolved revision.")
    setup.add_argument("--force", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "model-setup":
        lock = ensure_qwen_model(PipelineConfig(dry_run=True), force=args.force)
        print(f"Model ready: {lock['model_id']} @ {lock['resolved_revision']}")
        return 0

    if args.command == "dry-run":
        config = PipelineConfig(
            dry_run=True,
            local_generation=False,
            topic=args.topic,
            question_count=args.questions,
            keep_intermediate=args.keep_intermediate,
        )
        run_dir = run_pipeline(config, resume=not args.no_resume)
        print(f"Dry-run package ready: {run_dir}")
        return 0

    config = PipelineConfig(
        dry_run=False,
        local_generation=False,
        topic=args.topic,
        question_count=args.questions,
        keep_intermediate=args.keep_intermediate,
    )
    run_dir = run_pipeline(config, resume=not args.no_resume)
    print(f"Package ready: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
