# Post-compat rollback model (after `PI_WRITE_RADAR_COMPAT=0`)

**Date:** 2026-09-21  
**Principle:** After final cutover, **PaperIntelligence catalog is authoritative**. Radar is no longer a complete mirror.

## Why `PI_USE_PAPERS_CATALOG=0` stops being a full rollback

Once Radar dual-write is off:

- New papers exist only in `paper_intelligence.papers`
- Those IDs may never appear in `research_radar.content_items`
- Switching the reader flag back to Radar would **orphan** PI-only papers and silently under-count windows

Therefore flag-off is a **partial emergency reader fallover for shared IDs only**, not a system rollback.

## Authoritative system

| Phase | Authoritative identity | Authoritative funnel |
|---|---|---|
| Now (pre-final) | Dual (Radar + PI), PI preferred when flag=1 | PI relevance/stage results when flag=1 |
| After final cutover | **PI `papers`** | **PI stage result tables** |

## Recovery if PI catalog mode misbehaves after Radar writes are off

1. **Keep PI authoritative.** Do not re-promote Radar as source of truth.
2. Fix forward in PI (bugfix, replay free stages, restore from PI backups/snapshots).
3. Optionally re-enable `PI_WRITE_RADAR_COMPAT=1` temporarily to **reconcile PI → Radar** for downstream Radar consumers — never Radar → PI for identity.
4. Reader flag `PI_USE_PAPERS_CATALOG` should remain **1** except for surgically comparing shared-ID subsets.

## Re-enable Radar compatibility?

Yes, as a **one-way projection**:

```
PI papers / relevance / rejects  →  best-effort Radar content_items status + metadata
```

Rules:

- Projection must be idempotent on `legacy_content_item_id` / identity_map
- PI-only papers get new Radar rows only if a Radar consumer still requires them
- Projection failure must not roll back PI

## Preserving PI-only IDs

- `paper_id` is stable and is the FK target after migration
- `paper_identity_map` retains arxiv/doi/radar crosswalks
- Do not recycle Radar IDs for new PI papers after compat-off unless identity_map explicitly links them

## Preventing a stale Radar catalog from becoming authoritative again

- Code default: `PI_USE_PAPERS_CATALOG=1`
- Remove / gate `PI_ELIGIBLE_STATUSES` so it cannot affect production eligibility
- Ops alert if any job sets catalog flag off in production
- Documentation: Radar tables are compatibility mirrors, not PI truth

## Emergency checklist

1. Confirm incident is PI reader/orchestrator (not data loss)
2. Patch PI; keep flag ON
3. If Radar consumers break: re-enable compat write + project from PI
4. Only for forensic diff: run shadow scripts with flag off on a **copy** or read-only session
