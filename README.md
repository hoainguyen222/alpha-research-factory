# AlphaResearch Agent

Lightweight, file-based agent workflow for reproducing user-provided alpha research sources: papers, repos, notebooks, blog posts, datasets, or strategy writeups.

The current installable package is:

```text
alpha-repro-lite/
```

## What this repo contains

- An installable Agent Skill for Codex, Claude Code, and similar coding-agent tools.
- A minimal alpha reproduction workflow with explicit stage gates.
- Three custom subagent prompt-card templates:
  - `source-validator-agent`
  - `implementation-agent`
  - `evaluation-review-agent`
- Markdown/YAML templates for case state, progress tracking, spec lock, data validation, backtest run manifests, evaluation, review, and final reporting.

## What this repo intentionally avoids

- No database requirement.
- No dashboard requirement.
- No vector index requirement.
- No orchestration service requirement.
- No committed research cases, raw data, processed market data, or backtest artifacts.

## Start here

Read:

```text
alpha-repro-lite/README.md
alpha-repro-lite/INSTALL.md
alpha-repro-lite/AGENTS.md
```

Installable skill:

```text
alpha-repro-lite/skills/alpha-reproduction-lite/SKILL.md
```

Subagent prompt-card templates:

```text
alpha-repro-lite/templates/subagents/
```

## Core operating rule

Chat history is not workflow truth.

The workflow truth is:

```text
case files + stage protocols + artifacts
```

For a fresh or compacted agent session, the agent should read:

```text
cases/<case_id>/current-target.md
cases/<case_id>/follow-up.md
cases/<case_id>/progress.md
cases/<case_id>/run-log.md
```

before taking action.

