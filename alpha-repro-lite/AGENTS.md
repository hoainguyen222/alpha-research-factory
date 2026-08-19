# Agent Instructions

This workspace is file-based and intentionally lightweight.

## Required first read

Before doing case work, read:

1. `cases/<case_id>/current-target.md`
2. `cases/<case_id>/follow-up.md`
3. `cases/<case_id>/progress.md`
4. `cases/<case_id>/run-log.md`
5. The matching `cases/<case_id>/workflow/<stage>.md`

## Rules

- Do not infer permission from chat history.
- Do not skip stage gates.
- Do not run backtest before `specs/spec_lock.yaml` exists.
- Do not claim alpha before `evaluation/eval_report.md` and `review/reproduction_review.md` exist.
- Do not overwrite old run artifacts; create a new `artifacts/run_###/` folder.
- If a required input is missing, return `blocked` and name the missing file.

## Completion update

After completing a stage, update:

- `progress.md`
- `run-log.md`
- `follow-up.md`
- `current-target.md`

