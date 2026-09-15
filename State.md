# State — PaperIntelligenceV1

**Updated:** 2026-09-15 (Phase 2 schema + interfaces)

## Where the project is

Phase 1 scaffold committed. Phase 2 delivers revised `001_schema.sql`, stage contract, and typed external stubs on `dev/subha`. **Still no stage runtime code. Migrations not applied.**

Fixed sequence:

1. ~~Architecture / scaffold documents~~ done
2. Schema + interface contract (this commit) — then land on `main`
3. Both worktrees rebase onto that commit
4. Parallel Engineer work begins

## What exists

| Asset | Status |
|---|---|
| arXiv OAI-PMH ingestion | Exists (Research Radar) — **not rebuilt** |
| `content_items` / `paper_metadata` | Exists — **not duplicated** |
| Audience/domain enrichment | Exists ad-hoc upstream — **refactor into classify stage** |
| Docs / prompts / policies / agents | Created (Phase 1) |
| Stage contract + client stubs | Created (Phase 2) |
| `001_schema.sql` | Phase 2 revised — **written, not applied** |
| Screen / classify / quality / affiliation stages | Not created |
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

Waiting on human to: review schema · apply DDL · merge/rebase contract onto `main` for Urmila.

## Next cycle

1. Merge Phase 2 to `main`; Urmila rebases `dev/urmila`
2. Vertical slice: `normalize_authors` (S-006 / P-004)
3. Then screen → classify → …
