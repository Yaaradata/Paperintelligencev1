# Subha stream — State

**Updated:** 2026-09-15

## Owns

Architecture docs · migrations (write-only) · stage contracts · normalize/screen/classify/quality/affiliation/adjudication · policies/prompts for those stages · backlog P/S items she owns.

## Current cycle

**Phase 3.1 — `normalize_authors`.** Engineer implementation complete on `dev/subha`; awaiting Verifier (S-006 / P-004).

## Cycle checklist

**Start**

```bash
git status && git fetch origin && git rebase origin/main
```

Then read `/Context.md` → `/State.md` → `coordination/subha/State.md` → `coordination/subha/Backlog.md`.

**End**

1. Tests pass locally where applicable
2. Relevant golden evaluation (when stage exists)
3. Update Backlog / BacklogClosed / State (and Context if architecture changed)
4. `git add` code + MD together → commit → push

## Waiting-on

| Need | From | Status |
|---|---|---|
| Confirm SCREEN_MIN / GATE_PERCENTILE / QUALITY_MODEL | Human | Open |
| Apply DDL after Phase 2 migration written | Human | Not yet |

## Owed to Urmila (critical path)

| Interface | Status |
|---|---|
| `external_requests` / `llm_requests` column contract in `docs/data_model.md` | Done on `dev/subha` |
| `Stage` / `StageResult` / `Evidence` / `RunContext` | Done |
| `ror.resolve_affiliation` / `openalex.get_work` / `openrouter.complete` stubs | Done |
| Schema commit on `main` for rebase | Done (`15a104e`); schema applied on RDS |

## Decisions made

_(empty — fill with date and reasoning)_
