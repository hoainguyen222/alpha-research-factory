# Subagent Contract

Alpha Repro Lite uses three optional worker packets, not one agent per stage. Each packet is written as a custom-agent prompt card with role, pipeline context, decision rubric, hard prohibitions, and a strict output schema.

## Worker packets

| Packet | Stage coverage | Main outputs |
|---|---|---|
| `source-validator-agent.md` | 01-02 | source registry, paper/code audit, validator report |
| `implementation-agent.md` | 04-06 | data report, code/tests, backtest artifacts |
| `evaluation-review-agent.md` | 07-09 | evaluation, review, final report |

Stage 00 Bootstrap and Stage 03 Spec Lock usually remain main-agent or human-controlled because they define case scope and lock assumptions.

## Authority boundary

Subagents are workers, not authorities. They can produce artifacts, but they cannot approve stage transitions by chat statement alone.

A subagent should receive only:

- the relevant packet from `cases/<case_id>/subagents/`;
- `current-target.md`;
- the input files listed inside that packet;
- allowed actions;
- expected output paths;
- blocked actions.

## Return contract

Every subagent response should include:

```text
status: completed | blocked | needs_human_decision
files changed:
evidence produced:
blockers:
next recommended stage:
```

When a packet provides a JSON-compatible output schema, prefer that schema over prose. The schema is the handoff contract for the orchestrator.

## Core rule

The workflow truth is still the case files and artifacts, not the subagent chat transcript.
