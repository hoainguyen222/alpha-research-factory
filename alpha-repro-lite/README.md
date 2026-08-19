# Alpha Repro Lite

Alpha Repro Lite is a file-based workflow workspace for reproducing crypto alpha papers, repos, notebooks, or strategy writeups supplied by the user.

This folder intentionally has no database, no dashboard, no vector index, and no orchestration engine. The workflow is driven by Markdown/YAML files that humans, Codex, Claude Code, and other coding agents can read directly.

## Installable skill

This workspace also includes an installable Agent Skill:

```text
skills/alpha-reproduction-lite/SKILL.md
```

Use `INSTALL.md` to copy the skill into Codex, Claude Code, or another Agent Skills directory. If a tool does not support skills, use this folder directly through `AGENTS.md`.

## Core idea

```text
YAML = structured state
Markdown = human/agent context
Artifacts = evidence
```

The most important rule is simple: chat history is not workflow truth. A new or compacted AI session should read the case files before doing work.

## Fundamentals

Alpha Repro Lite is designed around a few non-negotiable rules:

1. Reproduction first, discovery later. Use this workflow when the user already has a paper, repo, notebook, blog post, dataset, or strategy writeup.
2. Case files are the source of truth. Chat context can help, but it must not be required to resume work.
3. Gates are hard. Do not code before data readiness, do not backtest before tests pass, and do not report before evaluation and review.
4. The spec lock is a boundary. After `specs/spec_lock.yaml` is locked, coding/backtesting agents must not change strategy assumptions to improve results.
5. Backtests are deterministic evidence, not alpha claims. Evaluation and review decide what the result supports.
6. Subagents are optional workers. They produce artifacts, but they do not authorize stage transitions by chat statement alone.
7. Keep the lite version local-first and file-based. Add databases, dashboards, vector indexes, or orchestration services only when the workflow outgrows files.

## Start here

For an active case, read these files in order:

```text
cases/<case_id>/current-target.md
cases/<case_id>/follow-up.md
cases/<case_id>/progress.md
cases/<case_id>/run-log.md
```

Then read the stage protocol named in `current-target.md`, for example:

```text
cases/<case_id>/workflow/03-spec-lock.md
```

## Workflow stages

| Stage | Main result |
|---|---|
| 00 Bootstrap | `case.yaml`, `current-target.md`, `progress.md`, `run-log.md`, `follow-up.md` |
| 01 Source Intake | `sources/source_registry.yaml` |
| 02 Audit | `audit/paper_audit.md`, `audit/code_audit.md`, `audit/validator_report.md` |
| 03 Spec Lock | `specs/reproduction_spec.md`, `backtest_config.yaml`, `evaluation_plan.md`, `spec_lock.yaml` |
| 04 Data Check | `data/data_manifest.yaml`, `data/data_quality_report.md` |
| 05 Coding | `src/`, `tests/`, implementation notes |
| 06 Backtest | `artifacts/run_001/run_manifest.yaml`, metrics, trades, equity, logs |
| 07 Evaluation | `evaluation/eval_report.md` |
| 08 Review | `review/reproduction_review.md` |
| 09 Report | `reports/final_report.md` |

## Gate rules

- No `sources/source_registry.yaml` -> no audit.
- No `audit/validator_report.md` -> no spec lock.
- No `specs/spec_lock.yaml` -> no backtest.
- No `data/data_quality_report.md` -> no coding/backtest.
- No `artifacts/run_*/run_manifest.yaml` and `metrics.json` -> no evaluation.
- No `evaluation/eval_report.md` -> no review.
- No `review/reproduction_review.md` -> no final report.

## Subagent usage

Subagents are optional. The lite workflow uses three broad task packets rather than one agent per stage:

| Packet | Stage coverage |
|---|---|
| `source-validator-agent.md` | Source intake and audit |
| `implementation-agent.md` | Data check, coding, and backtest |
| `evaluation-review-agent.md` | Evaluation, review, and final report |

Subagents should receive a task packet from `cases/<case_id>/subagents/`. A subagent should not read the entire workspace unless explicitly asked. It should return one of:

```text
completed
blocked
needs_human_decision
```

Every subagent output should include files changed, evidence produced, and blockers.

Template packets live under:

```text
templates/subagents/
```
