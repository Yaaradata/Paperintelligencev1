# Runbook — PaperIntelligenceV1

## Before diagnosing anything

```bash
python scripts/check_schema.py
```

If objects are missing, apply pending migrations **manually** (agents do not apply DDL).

## Worktrees

| Person | Path | Branch |
|---|---|---|
| Canonical | `~/Paperintelligencev1/repo` | `main` |
| Subha | `~/Paperintelligencev1/worktrees/subha` | `dev/subha` |
| Urmila | `~/Paperintelligencev1/worktrees/urmila` | `dev/urmila` |

Raw cache (outside git): `~/Paperintelligencev1/shared_data/raw/{provider}/YYYY/MM/DD/`.

## Stage dry run

```bash
python scripts/run_stage.py --stage screen --from 2026-09-01 --until 2026-09-07 --dry-run
```

Live paid run requires `--allow-paid` and a date window.

## Agent sequence

Architect → Scout (optional factual) → Engineer (one item) → Verifier → fix → commit.

## Do not

- Apply DDL from the agent
- Run paid stages without window + prior dry run
- Edit existing prompt/policy version files in place — add `v002` instead
