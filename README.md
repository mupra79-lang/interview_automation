# interview_automation

Offline-first Python automation for creating original YouTube interview-preparation videos.

The first implemented path is a complete hosted/local generation package for **Top 10 LangGraph Interview Questions**. Publishing and scheduled trend discovery are intentionally disabled until the local package is validated.

## What it builds

The pipeline has idempotent stages:

`discovery -> topic_selection -> script -> quality_check -> narration -> visuals -> render -> validation -> publish_ready`

Each stage writes `runs/<topic-slug>/checkpoint.json`, so a failed run can resume without regenerating valid content. The final cleaned package keeps:

- `final.mp4`
- `thumbnail.png`
- `script.json`
- `manifest.json`
- useful logs and validation reports

Temporary audio, slides, and FFmpeg files are deleted only after validation unless `--keep-intermediate` is used.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Install FFmpeg and make sure `ffmpeg` and `ffprobe` are on `PATH`.

Put your owned Chatterbox voice sample here:

```text
voice/sample.wav
```

On the first run, the system prepares and saves:

```text
voice/sample_chatterbox_conds.pt
```

Later runs reuse that voice profile without preparing it again.

## Dry run

```bash
interview-auto dry-run
```

The package is written to:

```text
runs/top-10-langgraph-interview-questions/
```

## Local model setup

The content model is `Qwen/Qwen2.5-1.5B-Instruct`. This repo does not use paid APIs and does not commit model weights.

Download and pin the model revision once:

```bash
interview-auto model-setup
```

This resolves the current Hugging Face commit SHA, downloads the snapshot into `models/`, and writes:

```text
models/qwen2_5_1_5b_instruct.lock.json
```

Future model runs verify the resolved revision against that lock. In GitHub Actions, Hugging Face cache and `models/` are cached to avoid downloading the same model every run.

CPU runners can be slow, so the hosted generation workflow runs one video at a time with hard timeouts and caches both Hugging Face files and the prepared Chatterbox voice profile.

## GitHub Actions hosted generation

Use the manual **Generate Interview Video** workflow. The model and Chatterbox voice run inside GitHub Actions, not on your computer.

Do not put `sample.wav` directly into a GitHub secret. GitHub secrets are limited to 48 KB, and voice WAV files are usually much larger. Instead, commit only an encrypted copy of the file and store only the passphrase as a secret.

Create an encrypted voice sample:

```text
gpg --symmetric --cipher-algo AES256 voice/sample.wav
```

This creates:

```text
voice/sample.wav.gpg
```

Commit only `voice/sample.wav.gpg`. Never commit `voice/sample.wav`.

Add this repository secret in GitHub:

```text
VOICE_SAMPLE_GPG_PASSPHRASE
```

GitHub UI path:

`Repository -> Settings -> Secrets and variables -> Actions -> Secrets -> New repository secret`

Name:

```text
VOICE_SAMPLE_GPG_PASSPHRASE
```

Value:

```text
the passphrase you typed when creating voice/sample.wav.gpg
```

The workflow decrypts `voice/sample.wav`, downloads/verifies Qwen once, prepares `voice/sample_chatterbox_conds.pt` once, generates the package, and uploads the MP4, thumbnail, script JSON, manifest, and logs as an artifact.

## YouTube research

Trend research uses only the official YouTube Data API.

Set this secret or environment variable:

```text
YOUTUBE_API_KEY
```

The implementation does not use Selenium, browser automation, scraping, page refresh loops, proxies, or limit-avoidance behavior. It uses small fixed result sets, retries, a strict daily quota budget, and SQLite caching.

Default quota controls:

```text
YOUTUBE_DAILY_QUOTA_UNITS=450
YOUTUBE_CACHE_COOLDOWN_HOURS=24
```

The default run checks two expanded queries across recent 24-hour and 7-day windows with small fixed result sets. Important limitation: the YouTube API returns current public statistics. It does not provide exact 24-hour views or historical channel average views. Growth can only be calculated from snapshots saved by this project over time.

## Topic fallback

If no trend qualifies, the system rotates evergreen topics such as Python, Java, SQL, DSA, DBMS, OS, networking, Docker, Kubernetes, AWS, Azure, FastAPI, React, LangChain, LangGraph, RAG, LLM evaluation, ML, GenAI, and Agentic AI while checking channel history for near duplicates.

## Publishing

Publishing is disabled by default. The current publisher only writes metadata with:

```text
status: disabled
api: official_youtube_oauth_only
rate_limit: one_video_per_day
```

When publishing is added later, use official YouTube OAuth, require manual approval, and keep a controlled schedule such as one video per day.

## Tests

```bash
pytest
```

Tests cover scoring, duplicate detection, schema validation, visual output size/text rendering safety, resume checkpoints, and cleanup behavior.

## Safety

Never commit:

- API keys
- OAuth tokens
- model weights
- generated MP4/audio files
- large intermediate outputs
