# State — PaperIntelligenceV1

**Updated:** 2026-09-15 (Phase 3.1 normalize_authors implemented — awaiting Verifier)

## Where the project is

Phases 1–2 landed on `main`; `001_schema.sql` **applied on RDS** by human. Phase 3.1 `normalize_authors` implemented on `dev/subha` (Engineer). **Not Verifier-closed yet.**

Fixed sequence:

1. ~~Architecture / scaffold documents~~ done
2. ~~Schema + interface contract on `main`~~ done
3. ~~Worktrees rebased~~ done
4. Vertical slice in progress — next after Verifier: `screen`

## What exists

| Asset | Status |
|---|---|
| arXiv OAI-PMH ingestion | Exists (Research Radar) — **not rebuilt** |
| `content_items` / `paper_metadata` | Exists — **not duplicated** |
| Docs / prompts / policies / agents | Created (Phase 1) |
| Stage contract + client stubs | Created (Phase 2) |
| `paper_intelligence` schema on RDS | **Applied** (18 tables) |
| `normalize_authors` | Implemented (`v001`) — Verifier pending |
| Screen / classify / quality / affiliation | Not created |
| External cache / observability implementations | Not created (Urmila) |
| Golden loaders / evaluate_golden | Stub only |

## Open decisions (need human)

1. Final canonical column types / CHECK constraints for new tables after Phase 2 delta review
2. ~~`StageResult` / `Evidence` / `RunContext`~~ proposed in `common/stage.py` — human confirm before post-interface schema churn
3. `subdomain`: confirm multi-label (`subdomains` jsonb) vs single
4. Adjudication precedence when LLM and deterministic evidence conflict
5. Production values for `SCREEN_MIN_AI_RELEVANCE` (default 5.0) and `GATE_PERCENTILE` (default 15)
6. Concrete `QUALITY_MODEL` id on OpenRouter

## Known risks (from predecessor — design out)

| Risk | Mitigation |
|---|---|
| Schema drift — migrations written but never applied; mid-run failure skips later migrations | `check_schema.py` before diagnosis; idempotent migrations; verify on re-run; `DROP VIEW IF EXISTS` before `CREATE VIEW` |
| Silent data loss — orgs discarded for not being on watchlist | Nullable `organisation_id`; preserve raw name + evidence |
| Unverified claims in output — empty field treated as unknown inventively | Explicit unresolved markers; post-generation checks on reader-facing output |
| Cost surprises — paid stage without date window | Mandatory `--from`/`--until`; print scope; free `--dry-run` |
| Invented enum values — CHECK silently drops | Vocabularies inline in prompts; OOV logged and counted |

## Blocked

Nothing for normalize. Verifier should falsify S-006 / P-004 before starting `screen`.

## Next cycle

1. Verifier on `normalize_authors`
2. Implement `screen` (P-005 / S-007)
3. Then classify → quality ∥ affiliation → adjudication
