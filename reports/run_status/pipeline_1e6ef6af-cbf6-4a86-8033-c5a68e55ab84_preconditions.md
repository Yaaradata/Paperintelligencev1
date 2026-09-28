# Aug 25–31 run — preconditions (run_id 1e6ef6af-cbf6-4a86-8033-c5a68e55ab84)

Launched 2026-09-28 07:38 UTC, detached, code at `1c347e5` (origin/dev/subha).

Command: `QUALITY_ENGINE=jev_glm SCREEN_MODEL=z-ai/glm-5.3-flash CLASSIFY_MODEL=z-ai/glm-5.3-flash`
`scripts/run_pipeline.py --from 2026-08-25 --until 2026-08-31 --allow-paid --max-cost-usd 4`
(via `scripts/launch_pipeline_run.py`). Defaults unchanged; the engine and models are explicit env flags.

## 1. Completeness (v1 date 2026-08-25..31) — PASS after free ingest

- First check: OAI v1 count 4,121, DB 4,000, so 121 missing. All were papers announced after the
  last ingest (e.g. `2609.29487`) whose v1 submission date is in the window.
- Ran the free OAI ingest stage: 121 new.
- Re-check: OAI 4,121 = DB 4,121; missing 0; in DB but not in OAI 0.
  (`reports/ingest_status/v1_completeness_2026-08-25_2026-08-31.json`)
- **Not independent of the ingest source.** The reference count comes from the same OAI-PMH
  arXivRaw feed that ingest uses. It detects ingest gaps, not gaps in OAI itself. The arXiv API
  (`export.arxiv.org`) returns HTTP 406 from this host, so an independent count must be taken by
  hand from another machine.

## 2. OpenRouter credit — PASS

Account $208.00 total − $190.86 used = $17.14 remaining. Key limit remaining $9.98. Both > $5.

## 3. Prose fix live — PASS

One paper per call, reasoning effort low, max_tokens 800. 20-paper test (run `971ac6f6`):
20 ok / 0 failed, $0.0035.

## 4. Runguard on every paid stage — wired, then PASS

- Previously prose only. Now `run_batches` feeds a RunGuard (>10% of last 100 papers failed,
  from paper 20) for screen, audience_domain, quality and jev_score. Pipeline prose runs with a
  guard too.
- A trip marks the stage `cancelled` (reason in metadata); run_stage exits 3 and run_pipeline
  stops.

## 5. audience_domain fix (approved before launch)

- The Aug run failed 1,755/3,655 with "unparseable batch_index": prompt v002 asks for
  `content_item_id` but the parser read only `batch_index`. The parser now accepts both.
- GLM reasoning effort low; max_tokens 4000.
- 20-paper test (run `eaa20700`): 20 ok / 0 failed, $0.0020.
- An earlier test with only the reasoning change failed 20/20 on the key mismatch; the guard
  tripped as designed (run `a741a6b5`, closed as cancelled).

## 6. Dry-run projection — PASS (≤ $3)

| Stage | Candidates | Projected |
|---|---:|---:|
| screen | 205 | $0.02 |
| audience_domain | 1,199 | $0.14 |
| quality (jev_glm) | 183 | $0.10 |
| **Total** | | **$0.26** |

Upper bound, counting the 121 new papers that reach screen only after relevance: ≈ $0.45.

## 283 papers that moved into Aug 25–31

All 283 have relevance results, 187 have screen results and 51 have quality scores. The eligible
remainder is included in the screen (205) and quality (183) candidates above.
