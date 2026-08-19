# Starter Workspace Reference

Use this reference when the user asks to create a lightweight alpha reproduction workspace in a repo that does not already contain `alpha-repro-lite/`.

## Minimum folder tree

```text
alpha-repro-lite/
  README.md
  AGENTS.md
  cases/
    <case_id>/
      case.yaml
      current-target.md
      follow-up.md
      progress.md
      run-log.md
      workflow/
        00-bootstrap.md
        01-source-intake.md
        02-audit.md
        03-spec-lock.md
        04-data-check.md
        05-coding.md
        06-backtest.md
        07-evaluation.md
        08-review.md
        09-report.md
      subagents/
        source-validator-agent.md
        implementation-agent.md
        evaluation-review-agent.md
      sources/
      audit/
      specs/
      data/
      src/
      tests/
      artifacts/
      evaluation/
      review/
      reports/
```

## Initial context files

`current-target.md` must state:

- case id;
- current stage;
- next action;
- files to read first;
- allowed actions;
- blocked actions;
- expected result.

`follow-up.md` must state:

- last completed stage;
- current stage;
- important decisions;
- known blockers;
- suggested next prompt.

`progress.md` must provide a stage table with status and result artifact.

`run-log.md` must append chronological actions with actor, stage, action, result, and next step.

## Minimal first case state

Start a new case at Stage 00 or Stage 01. Do not pre-fill audit, spec, evaluation, or report files with conclusions. Empty templates are acceptable only when they are marked `pending`.

## Subagent packet source

Copy the three packet templates from:

```text
alpha-repro-lite/templates/subagents/
```

into:

```text
alpha-repro-lite/cases/<case_id>/subagents/
```

Do not create one subagent per stage unless the user explicitly wants heavier orchestration.
