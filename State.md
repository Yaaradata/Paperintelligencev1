# State — PaperIntelligenceV1

**Updated:** 2026-09-15 (Phase 1 scaffold)

## Where the project is

Repository initialised with folder scaffold, versioned prompts/policies, coordination docs, and Cursor agent/rule configuration. **No pipeline stage code yet.**

Fixed sequence:

1. Architecture / scaffold documents (this phase)
2. Schema + interface contract commit (unblocks Urmila)
3. Both worktrees rebase onto that commit
4. Parallel Engineer work begins

Neither Engineer makes substantial pipeline changes before the schema/interface commit lands.

## What exists

| Asset | Status |
|---|---|
| arXiv OAI-PMH ingestion | Exists (Research Radar) — **not rebuilt** |
| `content_items` / `paper_metadata` | Exists — **not duplicated** |
| Audience/domain enrichment | Exists ad-hoc upstream — **refactor into classify stage**, do not rewrite from scratch blindly |
| Screen / quality stages | Not created |
| Affiliation resolution (PI schema) | Not created |
| Adjudication + current state writer | Not created |
| External cache / observability (Urmila) | Not created |
| Golden loaders / evaluate_golden | Not created |
| `paper_intelligence` schema migration | Draft `001_schema.sql` present — **will be revised in Phase 2** to match this brief; **not applied** |

## Open decisions (need human)

1. Final canonical column types / CHECK constraints for new tables after Phase 2 delta review
2. Exact `StageResult` / `Evidence` / `RunContext` field set (Architect proposes in Phase 2)
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

Nothing — Phase 1 documentation in progress; Phase 2 schema next.

## Next cycle

1. Commit Phase 1 scaffold
2. Architect architecture delta + Phase 2 schema/interfaces
3. Land schema+contract on `main` (or merge path), Urmila rebases
4. Vertical slice starting at `normalize_authors`
