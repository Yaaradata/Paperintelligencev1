# PI Catalog FINAL CUTOVER Report

**Date:** 2026-09-21  
**Branch:** `dev/subha`  
**Defaults now:** `PI_USE_PAPERS_CATALOG=1`, `PI_WRITE_RADAR_COMPAT=0`

---

## 1. Explanation of the 604-row count difference

| Claim | Value |
|---|---:|
| Radar-only in horizon before backfill | 29,609 |
| Incorrect “rows reported backfilled” narrative | 30,213 (= 29,609 + 604) |

**The 604 are a subset of the original 29,609**, not an extra import.

| Field | Value |
|---|---|
| Count | 604 |
| Date range | 2026-06-01 … 2026-07-13 (602 July, 2 June) |
| Source | `arxiv_oai` only |
| Radar status | all `INGESTED` |
| Reason included | Same in-scope Radar-only set; first long transaction left them uncommitted / savepoint leftovers; second apply finished them |

Safety checks after reconciliation:

- duplicate canonical arXiv IDs: **0**
- duplicate DOI identities: **0**
- accidental out-of-scope import: **0** (arxiv_oai only)
- unexpected `paper_id` ≠ `legacy_content_item_id` collisions: **0**

Unique PI scope coverage = **29,609** (= original Radar-only count).

Detail: `reports/architecture/pi_backfill_604_reconciliation.md`

---

## 2. Pre-cutover commit SHA

`1f7e12e26b8236cc837733847643e892ae090f95` — complete scope coverage and cutover readiness

---

## 3. PI-default-ON commit SHA

`2bbc53a9a7c27de5ae04e13f0d4de318c578d08f` — `PI_USE_PAPERS_CATALOG` default **1** (compat still ON at that commit)

Related follow-up (required for live ingest):  
`bdce450fa1c5cdf832f97a30b1ecdb0a35b556f4` — cast nullable `arxiv_version` in PI upsert SQL

---

## 4. Daily production canary results

**Path:** `scripts/run_pipeline.py` (production orchestration)  
**Flags:** catalog ON + Radar compat ON  
**Day:** `2026-09-15` with `--allow-paid --limit 10` (ordinary residual budget; no historical catch-up)

| Stage | Result |
|---|---|
| ingest | ok — seen 2382 / kept 2270 / new 69 / dupe 2201 |
| relevance | candidates 0 (window already scored) |
| normalize_authors | 10 succeeded / 0 failed |
| screen | 7 ok / 0 failed / **$0.0007** |
| affiliation_fast | 10 items |
| audience_domain | 10 ok / **$0.0015** |
| quality | 10 ok / **$0.0267** |
| affiliation_deep | 10 items |
| hf_signals | matched/wrote 10 |
| adjudication | 508 current-state rows / 0 screen–quality disagreements |
| reports | tech / business / audience / combined written |
| failed papers | **0** |
| duplicate papers | **0** |
| orphan PI rows | **0** |
| unexpected reruns | none observed beyond skip_done residual |
| total paid (this canary) | **~$0.029** |

Also exercised next-day OAI ingest `2026-09-16` (free stages): checkpoint COMPLETE; 48 new PI papers; all new IDs originated in `paper_intelligence.papers` with Radar legacy links while compat was ON.

---

## 5. Archive cutover result

- Migration **007** `paper_intelligence.archive_records` authoritative index
- Code writes PI index first; Radar `s3_archives` only while compat ON
- Object key scheme unchanged: `paper-intelligence/rejected/...`
- Same `(s3_bucket, s3_key)` does **not** duplicate index rows (`ON CONFLICT`)
- Live S3 PutObject denied by IAM on this host; index + key + recovery validated with upload mock
- Result: **PASS** (index authoritative; no object duplication)

---

## 6. FK migration result

- Migration **008** applied: PI `content_item_id` → `papers(paper_id)` `ON DELETE NO ACTION`, `NOT VALID` → `VALIDATE`
- Orphan precheck before add: **0** on all 11 child tables
- Radar FKs retained until stage 9
- Result counts / stage queries unchanged after add

---

## 7. Soak result

**Second operational day:** `2026-09-14` via `run_pipeline.py` (catalog ON + compat ON, `--limit 10`)

| Check | Result |
|---|---|
| unexplained catalog differences (`soak_pi_catalog_final.py` on Sep 15) | **0** / passed |
| canonical duplicates | **0** |
| orphan PI rows | **0** |
| Radar-status-dependent eligibility | **0** (catalog path) |
| unexpected compat failures affecting PI | **0** |
| report/editorial regressions | none observed |
| paid soak cost | screen $0.0018 + audience $0.0026 + quality $0.0259 ≈ **$0.030** |

---

## 8. Radar-compat-OFF commit SHA

`4eeb563b285ae2e0ecfa4278310bf61d3a5501a3` — `PI_WRITE_RADAR_COMPAT` default **0**

FK migration files commit (applied 008; 009 applied later):  
`9972571b4640379e59ea6c75e96b6f0c195df928`

---

## 9. PI-only independence test

Synthetic arXiv `9999.64741` → `paper_id=195814`

| Check | Result |
|---|---|
| arXiv/OAI → `paper_intelligence.papers` | PASS |
| PI checkpoint controls resume | PASS (`COMPLETE`) |
| PI relevance candidate + result | PASS (keep, score 9.3) |
| screen eligibility | PASS (in screen pool) |
| reports/editorial lookup via PI | PASS |
| no Radar `content_items` row required | PASS |
| no Radar `paper_metadata` required | PASS |
| no Radar status consulted | PASS |
| no Radar checkpoint controls resume | PASS |
| no Radar archive index required | PASS |
| valid with Radar absent (`legacy_content_item_id` NULL) | PASS |

Artifact: `reports/architecture/pi_only_independence_final.json`

---

## 10. Radar FKs removed

Migration **009** applied. All PI → `research_radar.content_items` FKs dropped.  
PI → `papers` FKs remain. Radar tables **not** deleted.

Post-drop: orphans **0**, `radar_fks_remaining` **0**, stage queries OK, PI-only paper 195814 still valid.

---

## 11. Remaining Radar reads

Deprecated / flag-off / forensic only:

- `db/results.py` Radar SQL when `PI_USE_PAPERS_CATALOG=0`
- `_run_one_window_radar` ingest branch
- affiliation / HF / adjudication Radar joins on flag-off
- some editorial loaders’ legacy branches
- tests / shadow / canary scripts

See `reports/architecture/pi_remaining_radar_dependencies.md`

---

## 12. Remaining Radar writes

**None by default.** Compat dual-write paths exist but are gated by `PI_WRITE_RADAR_COMPAT=0`:

- ingest `content_items` / `paper_metadata`
- checkpoints
- relevance status / scores / topics
- `s3_archives` index

Re-enable only for optional one-way **PI → Radar** projection.

---

## 13. Remaining Radar dependencies

- Radar tables retained (legacy consumers / forensics)
- Historic shared IDs (`paper_id = legacy_content_item_id`) still joinable
- No schema FK from PI → Radar
- Stale Radar must not be re-authoritized by flipping the reader flag off

---

## 14. Tests passed

| Suite | Result |
|---|---|
| Unit (`tests/unit`) | **131 passed** |
| Integration (`tests/integration`) | **2 passed** |
| Combined | **133 passed** |

Coverage exercised: catalog normalization, ingest idempotency paths (unit), relevance versioning, quality router, affiliation, HF matching units, adjudication units, FK integrity (DB), org coverage unit file present but not newly required for cutover.

---

## 15. Failed papers / issues

| Issue | Disposition |
|---|---|
| Live ingest `IndeterminateDatatype` on null `arxiv_version` | **Fixed** (`bdce450`) |
| Sep-16/15 OAI windows mostly revisions → 0 new `published_at` that day | Expected OAI datestamp vs created behavior; canary used Sep-15 published window |
| Live S3 PutObject AccessDenied for archive bucket | Index/key/recovery validated with mock; IAM outside this cutover |
| Historical quality/audience backlog | **Not run** (explicitly excluded) |

Failed papers in canary/soak paid stages: **0**

---

## 16. Final architecture status

**COMPLETE — PI catalog is permanently authoritative.**

```
arXiv OAI
  → paper_intelligence.papers (+ identity_map, ingest_checkpoints)
  → paper_relevance_results
  → screen / audience / quality / affiliation / HF / adjudication
  → reports / editorial loaders (PI reads)
  → archive_records (authoritative index)
```

Radar is compatibility/legacy only. Rollback = fix PI forward (± optional PI→Radar export), **not** switch production to stale Radar.

**Not done in this cutover (deferred):**

- 38 quality catch-up
- 468 September quality catch-up
- historical paid backfill
- January-to-present catch-up
