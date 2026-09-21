# Remaining Radar dependencies (POST final cutover)

**Date:** 2026-09-21  
**Flags (production defaults):** `PI_USE_PAPERS_CATALOG=1`, `PI_WRITE_RADAR_COMPAT=0`

**Architecture status:** PaperIntelligence catalog is **permanently authoritative**.
Radar tables remain in the database for legacy consumers and forensic reads.
They are **stale for new papers** and must **not** be re-promoted as source of truth
by flipping `PI_USE_PAPERS_CATALOG=0`.

---

## Remaining Radar **reads** (legacy / optional)

| Area | Notes |
|---|---|
| `db/results.py` Radar SQL branches | Only when `PI_USE_PAPERS_CATALOG=0` (deprecated emergency subset compare) |
| `ingest/arxiv_oai.py` `_run_one_window_radar` | Deprecated rollback ingest path |
| `author_affiliation` / `hf_signals` / `adjudication` Radar joins | Flag-off branches only |
| Editorial scripts with dual loaders | Prefer PI when catalog flag on |
| Tests / shadow / canary scripts | Dev-only |

## Remaining Radar **writes**

| Area | Notes |
|---|---|
| Compat dual-write paths | **Disabled by default** (`PI_WRITE_RADAR_COMPAT=0`) |
| `upsert_item` / `upsert_paper_metadata` | Called only if compat re-enabled |
| Radar `backfill_checkpoints` | Not written when compat off |
| Radar `s3_archives` | Not written when compat off |
| Radar status / scores / topics | Not written when compat off |

## Remaining Radar **dependencies**

| Item | Status |
|---|---|
| Schema FKs PI → `research_radar.content_items` | **Removed** (migration 009) |
| PI FKs → `paper_intelligence.papers` | **Active** (migration 008) |
| Radar tables themselves | Retained (not dropped) |
| Shared historic IDs (`paper_id = legacy_content_item_id`) | Still useful for forensic joins |

## Deprecated code policy

Legacy Radar branches are **deprecated / compatibility-only**:

- Keep them for short-term forensic diffs and optional one-way PI→Radar projection.
- Do **not** delete in this cutover commit.
- Do **not** treat them as production rollback.

## Rollback model (post-cutover)

1. Fix / redeploy PI.
2. Optionally re-enable `PI_WRITE_RADAR_COMPAT=1` to project PI → Radar.
3. Reconcile PI → Radar for any remaining Radar consumers.
4. **Never** switch production identity/eligibility back to stale Radar state.
