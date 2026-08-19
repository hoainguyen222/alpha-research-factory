# Install Alpha Reproduction Lite Skill

This folder contains an installable Agent Skill:

```text
alpha-repro-lite/skills/alpha-reproduction-lite/SKILL.md
```

The skill makes the file-based workflow discoverable in tools that support Agent Skills. The workspace folder remains portable and can still be used directly through `alpha-repro-lite/AGENTS.md`.

## Codex

For this Codex setup, personal skills are available under:

```text
%USERPROFILE%\.codex\skills
```

PowerShell install command from the repo root:

```powershell
$dest = Join-Path $env:USERPROFILE ".codex\skills\alpha-reproduction-lite"
if (Test-Path -LiteralPath $dest) { Remove-Item -LiteralPath $dest -Recurse -Force }
Copy-Item -LiteralPath ".\alpha-repro-lite\skills\alpha-reproduction-lite" -Destination $dest -Recurse
```

Restart or refresh the Codex session if skills are only loaded at session start.

## Claude Code

Claude Code commonly uses:

```text
%USERPROFILE%\.claude\skills
```

PowerShell install command from the repo root:

```powershell
$dest = Join-Path $env:USERPROFILE ".claude\skills\alpha-reproduction-lite"
if (Test-Path -LiteralPath $dest) { Remove-Item -LiteralPath $dest -Recurse -Force }
Copy-Item -LiteralPath ".\alpha-repro-lite\skills\alpha-reproduction-lite" -Destination $dest -Recurse
```

## Generic Agent Skills / Droid-style tools

If the tool supports an Agent Skills folder, copy:

```text
alpha-repro-lite/skills/alpha-reproduction-lite
```

into that tool's skills directory. If the tool does not support Agent Skills, use the portable fallback:

```text
Read alpha-repro-lite/AGENTS.md before doing alpha reproduction work.
```

## Verify install package shape

The installed folder should contain:

```text
alpha-reproduction-lite/
  SKILL.md
  references/
    workflow-contract.md
    starter-workspace.md
    subagent-contract.md
```
