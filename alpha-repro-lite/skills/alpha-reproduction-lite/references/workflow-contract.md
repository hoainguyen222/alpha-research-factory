# Alpha Reproduction Lite Workflow Contract

Use this reference when deciding the current stage, the expected output, or the correct subagent packet.

## Stage map

| Stage | Actor | Required input | Required result | Gate |
|---|---|---|---|---|
| 00 Bootstrap | main agent | user source links or case intent | `case.yaml`, `current-target.md`, `progress.md`, `run-log.md`, `follow-up.md` | links ready or explicitly pending |
| 01 Source Intake | source-validator-agent | `sources/links.md` | `sources/source_registry.yaml` | all sources classified |
| 02 Audit | source-validator-agent | `source_registry.yaml`, source files | `paper_audit.md`, `code_audit.md`, `validator_report.md` | verdict allows reproduction |
| 03 Spec Lock | main agent | audit reports | `reproduction_spec.md`, `backtest_config.yaml`, `evaluation_plan.md`, locked `spec_lock.yaml` | spec lock status is `locked` |
| 04 Data Check | implementation-agent | locked spec and referenced data | `data_manifest.yaml`, `data_quality_report.md` | verdict is `pass` or `pass_with_warnings` |
| 05 Coding | implementation-agent | locked spec and data report | `src/`, `tests/`, implementation notes | tests pass |
| 06 Backtest | implementation-agent | code, tests, locked config, data | `artifacts/run_###/` with manifest, metrics, equity, trades, logs | run manifest status is `completed` |
| 07 Evaluation | evaluation-review-agent | completed run, eval plan, data report | `evaluation/eval_report.md` | evaluation verdict is explicit |
| 08 Review | evaluation-review-agent | full reproduction package | `review/reproduction_review.md` | review verdict is explicit |
| 09 Report | evaluation-review-agent | reviewed package | `reports/final_report.md` | final verdict is explicit |

## Verdict vocabularies

Validator verdict:

```text
reproducible
reproducible_with_assumptions
blocked
reject
```

Evaluation verdict:

```text
pass
inconclusive
fail
blocked
```

Review verdict:

```text
pass
pass_with_caveats
fail
blocked
```

Final report verdict:

```text
verified_alpha
partial_reproduction
workflow_completed
inconclusive
reject
```

## Required follow-up behavior

When handing off to a fresh session, point the next agent at:

```text
alpha-repro-lite/cases/<case_id>/current-target.md
```

The next agent must read the target, then the follow-up context, progress, run log, and current workflow stage file before doing work.
