# Backlog — PaperIntelligenceV1

## Rules

- One backlog item = one Engineer pass
- Every classification or affiliation item names its gating golden set
- Blocked items name the blocking ID
- Only **Verifier** closes an item
- Engineer never marks own work complete

## Active

| ID | Item | Owner | Blocked-by | Acceptance | Gating golden |
|---|---|---|---|---|---|
| P-001 | Architecture delta (exists / reuse / missing / migration sequence / Urmila interfaces) | Subha | — | Written under `docs/`; human reviewed | — |
| P-002 | Schema migrations for identity, classification, runs, golden | Subha | P-001 | Idempotent SQL in `sql/migrations/`; **not applied by agent** | — |
| P-003 | Stage contract + typed external client stubs | Subha | P-001 | `Stage`/`StageResult` + ror/openalex/openrouter stubs with tests; docs for `external_requests`/`llm_requests` shapes | — |
| P-004 | `normalize_authors` | Subha | P-002, P-003 | Idempotent; unicode preserved; empty authors clean | — |
| P-005 | `screen` Pass 1 (GLM non-reasoning, batch 15, gate in code) | Subha | P-004 | Four numeric dims; 0.5 increments; gate stored not delete; `--from`/`--until`/`--dry-run` | — |
| P-006 | `classify` one-call audience/domain/subdomain/application_domain | Subha | P-005 | Separate append-only rows; OOV logged; vocab inline | `GOLDEN_AUDIENCE_DOMAIN_V1` |
| P-007 | `quality` Pass 2 on top GATE_PERCENTILE; no affiliation input | Subha | P-005 | Rubric + reason_not_higher; unknown-org strong > weak watchlist (boosts post-score) | — |
| P-008 | `affiliation` OAI→alias→ROR→OpenAlex | Subha | P-003 (clients), P-005 | Grounding rules; `no_evidence_supplied` ≠ `review_required`; null org id preserved | `GOLDEN_AUTHOR_AFFILIATION_V1` |
| P-009 | Adjudication + `paper_intelligence_current` | Subha | P-006, P-007, P-008 | Traceable run→stage→version→prompt→evidence→answer | both |
| P-010 | `evaluate_golden.py` with manual vs llm_adjudicated split | Urmila (+Subha metrics defs) | P-003 | Regressions by paper; FP org attribution | both |
| P-011 | `check_schema.py` + `run_stage.py` dry-run/cost | Shared | P-002 | Read-only schema probe; paid stages refuse without window | — |
| P-012 | M1 golden replay demo on 200+200 | Both | P-009, P-010, P-011 | M1 checklist answerable per paper | both |

## Deferred — not now

| Topic | Why deferred |
|---|---|
| S3 mirroring of raw cache | First implementation stays on disk |
| Embeddings / semantic search index | Downstream of M1 |
| Newsletter selection integration | Separate product surface |
| Claim extraction | Out of M1 scope |
| People watchlist seeding | After identity resolution stabilises |
