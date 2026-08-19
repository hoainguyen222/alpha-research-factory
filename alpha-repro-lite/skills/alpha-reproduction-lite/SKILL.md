---
name: alpha-reproduction-lite
description: Use when reproducing, validating, coding, backtesting, evaluating, or reviewing a user-provided alpha trading paper, crypto strategy repo, notebook, blog post, dataset, or source link with a lightweight file-based workflow.
---

# Alpha Reproduction Lite

## Overview

Use a lightweight file-based workflow for alpha reproduction cases where the user already provides sources. The core rule is: chat history is not workflow truth. Use case files, stage protocols, and artifacts as the operating context.

## Required first step

If the target repo already contains `alpha-repro-lite/`, read:

1. `alpha-repro-lite/AGENTS.md`
2. `alpha-repro-lite/cases/<case_id>/current-target.md`
3. `alpha-repro-lite/cases/<case_id>/follow-up.md`
4. `alpha-repro-lite/cases/<case_id>/progress.md`
5. `alpha-repro-lite/cases/<case_id>/run-log.md`
6. the workflow file named by `current-target.md`

If the target repo does not contain `alpha-repro-lite/` and the user asks to set up a case workspace, create the folder from `references/starter-workspace.md`. If the user only asks for conceptual advice, do not create files.

## Core pattern

Keep the workflow intentionally small:

```text
YAML = structured state
Markdown = human/agent context
Artifacts = evidence
```

Do not introduce SQLite, dashboard, vector index, Obsidian sync, or orchestration services unless the user explicitly asks to graduate beyond the lite workflow.

## Stage routing

Use `references/workflow-contract.md` for the stage map. The normal sequence is:

```text
00 Bootstrap
01 Source Intake
02 Audit
03 Spec Lock
04 Data Check
05 Coding
06 Backtest
07 Evaluation
08 Review
09 Report
```

Never skip gates:

- No `sources/source_registry.yaml` -> no audit.
- No `audit/validator_report.md` -> no spec lock.
- No locked `specs/spec_lock.yaml` -> no backtest.
- No `data/data_quality_report.md` -> no coding/backtest.
- No completed `artifacts/run_###/run_manifest.yaml` and `metrics.json` -> no evaluation.
- No `evaluation/eval_report.md` -> no review.
- No `review/reproduction_review.md` -> no final report.

## Subagent handoff

When using subagents, prefer the three lite packets described in `references/subagent-contract.md`:

- `source-validator-agent.md`
- `implementation-agent.md`
- `evaluation-review-agent.md`

Pass only the relevant task packet from `cases/<case_id>/subagents/` plus the input files named inside that packet. A subagent should return:

```text
status: completed | blocked | needs_human_decision
files changed:
evidence produced:
blockers:
next recommended stage:
```

Subagents are workers, not authorities. They may produce artifacts, but they may not approve stage transitions by chat statement alone.

## Completion update

After completing a stage, update these four files:

- `progress.md`
- `run-log.md`
- `follow-up.md`
- `current-target.md`

If the stage is blocked, record the blocker in all relevant context files and do not move the target to the next stage.

## Common mistakes

| Mistake | Correction |
|---|---|
| Starting from chat memory | Read current target, follow-up, progress, run log, and workflow stage file first. |
| Coding before spec lock | Stop and complete Stage 03. |
| Backtesting before data check | Stop and complete Stage 04. |
| Treating backtest output as alpha | Run evaluation and independent review first. |
| Giving a subagent the whole repo with vague instructions | Use the stage-specific subagent task packet. |
| Adding database/scripts too early | Keep the lite workflow file-based unless the user explicitly upgrades scope. |
