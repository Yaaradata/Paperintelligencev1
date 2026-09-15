# Subha stream — Backlog

## Rules

Same as root `Backlog.md`: one item per Engineer pass; Verifier closes; blocked-by required; golden set named for classify/affiliation.

## Items

| ID | Item | Maps to | Blocked-by | Acceptance | Golden |
|---|---|---|---|---|---|
| S-001 | Architecture delta document set | P-001 | — | `docs/architecture.md` etc. answer exists/reuse/missing/sequence | — |
| S-002 | Revise migrations to Phase 2 table list | P-002 | S-001 | Idempotent; views use DROP IF EXISTS; not applied | — |
| S-003 | Common stage contract + Evidence types | P-003 | S-001 | Protocol + dataclasses + unit tests | — |
| S-004 | External client typed stubs + tests | P-003 | S-003 | Docstrings; no live calls | — |
| S-005 | Document Urmila table shapes | P-003 | S-002 | `external_requests`/`llm_requests` in data_model.md | — |
| S-006 | `normalize_authors` | P-004 | S-002, S-003 | Idempotent; unicode; empty authors | — |
| S-007 | `screen` stage + prompt wiring | P-005 | S-006 | Gate in code; dry-run; cost summary | — |
| S-008 | `classify` stage + vocab validation | P-006 | S-007 | Four task_type rows; OOV metrics | `GOLDEN_AUDIENCE_DOMAIN_V1` |
| S-009 | `quality` stage; no org/author inputs | P-007 | S-007 | Signature + tests assert isolation | — |
| S-010 | Affiliation extract + deterministic aliases | P-008 | S-004, S-007 | `no_evidence_supplied` distinct | `GOLDEN_AUTHOR_AFFILIATION_V1` |
| S-011 | Wire ROR/OpenAlex via stubs/impl boundary | P-008 | S-010 | Clients decide nothing | same |
| S-012 | Adjudication policy application | P-009 | S-008, S-009, S-011 | Append-only adjudicated rows | both |
| S-013 | Populate `paper_intelligence_current` | P-009 | S-012 | Derived only | — |
| S-014 | Run/stage/item provenance end-to-end | P-009 | S-006+ | One query chain traceable | — |
| S-015 | Support M1 demo queries / scripts | P-012 | S-013, S-014 | M1 checklist answerable | both |

## Closed

See `coordination/subha/BacklogClosed.md`.
