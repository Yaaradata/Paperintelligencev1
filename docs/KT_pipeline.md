# PaperIntelligence V1 — Knowledge Transfer

**As of:** 5 Oct 2026 · **Branch:** `dev/subha` · **Owner during build:** Subha

This is the single document to read before touching the pipeline. Older docs
(`PROJECT.md`, `State.md`, `Context.md`, `docs/pipeline*.md`) stop at 24 Sep and
are behind on the catalog cutover, the `jev_glm` engine, backlog chains, cron and
the health email. Where they disagree with this file, this file is newer.

---

## 1. What the pipeline does

Every day arXiv publishes ~700–1,450 new papers. The pipeline pulls them, throws
away the ones that aren't about AI, scores the rest with LLMs for relevance,
audience (tech / business / product), domain and quality, looks up the authors'
organisations, adds Hugging Face "featured" signals, and produces ranked top-N
lists per audience. Those lists feed the newsletter and LinkedIn selection.

Scope: papers whose arXiv v1 date is on or after **1 Jul 2026** (the "v1 floor",
`PI_V1_DATE_FLOOR`). Older papers stay in the database but are excluded from
scoring and reports unless `--include-pre-v1-floor` is passed.

---

## 2. Where everything lives

| Thing | Location |
|---|---|
| Server | EC2 `i-08557534bff6fc4f1`, region ap-south-1, **clock is UTC** |
| Canonical repo | `~/Paperintelligencev1/repo` (`main`) |
| Working tree used for runs | `~/Paperintelligencev1/worktrees/subha` (`dev/subha`) |
| Other worktree | `~/Paperintelligencev1/worktrees/urmila` (`dev/urmila`) |
| GitHub | `Yaaradata/Paperintelligencev1` |
| Secrets / config | `~/Paperintelligencev1/.env` (DB URL, OpenRouter key, SES settings). Do not print values. |
| Python | `/home/ubuntu/theneural/Newsletter agent/.venv/bin/python` (it is `python` on PATH) |
| Database | Postgres via `$DATABASE_URL`, schema `paper_intelligence` (legacy `research_radar` still exists) |
| Raw API cache | `~/Paperintelligencev1/shared_data/raw/{provider}/YYYY/MM/DD/` |
| Run logs + status | `reports/run_status/` (`pipeline_<run_id>.log/.json`, `backlog_<run_id>.log/.json`) |
| Ingest logs | `reports/ingest_status/` |
| Cron logs | `reports/cron/free_stages.log`, `reports/cron/health.log` |
| Daily health reports | `reports/health/YYYY-MM-DD_HHMM.txt` |
| Top-N reports | `reports/{tech,business,audience}_top_20_<from>_to_<until>.md` |
| Exports | `reports/exports/` (e.g. `tech_top_400_…csv`, `product_top_400_…csv`) |

Every shell needs this first, or psql/scripts fail with socket / missing-key errors:

```bash
cd ~/Paperintelligencev1/worktrees/subha
set -a && . ~/Paperintelligencev1/.env && set +a
export PYTHONPATH=src
```

---

## 3. Stages

Order is fixed (`DEFAULT_STAGES` in `scripts/run_pipeline.py`):

| # | Stage | Cost | What it does | Writes |
|---|---|---|---|---|
| 0 | `ingest` | free | arXiv OAI-PMH harvest for the window; dedupes; never merges two arXiv papers on a shared DOI (second keeps no DOI, `raw_metadata.doi_conflict`) | `papers`, checkpoints |
| 1 | `relevance` | free | Deterministic AI filter (~70–75% kept). Rejects can go to S3 if `S3_ARCHIVE_ENABLED` | relevance results |
| 2 | `normalize_authors` | free | Author rows | `paper_authors` |
| 3 | `screen` | **paid** | LLM `ai_relevance` gate (min 5.0). `SCREEN_MODEL`, batch 15 | `paper_classification_results` (screen) |
| 4 | `affiliation_fast` | free | OAI / alias / domain / arXiv HTML. Feeds quality router labels | `paper_author_affiliations` |
| 5 | `audience_domain` ("classify") | **paid** | Audience, domain, subdomains, application domain. `CLASSIFY_MODEL`, policy v001, batch 15 | 4 rows per paper in results |
| 6 | `quality` | **paid** | Every screen survivor is scored (`ROUTER_SCORE_ALL_SURVIVORS=1`). Engine `QUALITY_ENGINE`: `terra` (default in code) or `jev_glm` (used for all runs since Jul). Author/org-blind | results (quality) + prose |
| 7 | `affiliation_deep` | free | arXiv HTML → ROR → OpenAlex | affiliations, organisations |
| 8 | `hf_signals` | free | Hugging Face Daily Papers by arxiv_id (14-day lookback). Display only, **not** in any score | `paper_hf_signals`, `paper_intelligence_current.hf_*` |
| 9 | `adjudication` | free | Builds the canonical current row per paper incl. `quality_status` | `paper_intelligence_current` |
| 10 | `reports` | free | Tech / business / audience top-N markdown | `reports/*.md` |

Paid stages only run with `--allow-paid`. They skip any paper that already has a
result for the same (task, stage version, prompt version, policy version, model),
so re-running a window only pays for what's missing.

Safety rails built into stages:
- **RunGuard**: a paid or affiliation stage stops (exit 3) if >10% of the last 100
  items failed, checked from item 20. The pipeline then stops later stages.
- **Malformed JSON retry**: screen and classify retry a batch once if the model
  returns unparseable JSON (`common/llm_stage.py::call_until_parsed`).
- **Budget cap**: `--max-cost-usd` is cumulative across paid stages in one run
  (default 25). Quality refuses to start if its projection exceeds the remaining
  cap (`--force-over-projection` overrides). The projection is ~2.5× actual.

---

## 4. How runs are launched

### 4.1 Detached single window (normal manual run)

Writes a `pipeline_detached` run record first, then supervises `run_pipeline.py`
in the background. Safe to close the laptop.

```bash
QUALITY_ENGINE=jev_glm SCREEN_MODEL=z-ai/glm-5.3-flash CLASSIFY_MODEL=z-ai/glm-5.3-flash \
python scripts/launch_pipeline_run.py -- --from 2026-09-29 --until 2026-10-04 \
  --allow-paid --max-cost-usd 3
```

**Always pass the three env vars.** `.env` sets `CLASSIFY_MODEL` to an older
model (the cron log banner shows `classify=z-ai/glm-4.6`) and `QUALITY_ENGINE`
defaults to `terra` in code. Every Jul–Sep run used the values above.

Watch it:

```bash
tail -f reports/run_status/pipeline_<run_id>.log
cat reports/run_status/pipeline_<run_id>.json      # state, current stage, budget line
pgrep -af 'run_pipeline.py|run_stage.py'           # is anything running?
```

### 4.2 Dry run first (projection)

```bash
python scripts/run_pipeline.py --from X --until Y --dry-run
```

Known weakness: projections are computed before screen, so for a window that
hasn't been screened yet the post-screen stages project near $0. Treat the dry
run as "is anything obviously wrong", not a cost forecast. Real cost: ~$0.25–0.30
per 1,000 ingested papers (all three paid stages, jev_glm).

### 4.3 One stage

```bash
python scripts/run_stage.py --stage hf_signals --from X --until Y
python scripts/run_stage.py --stage screen --from X --until Y --dry-run
```

`--stage classify` = `audience_domain`. `run_stage.py` has no `reports` stage —
reports come from the pipeline path.

### 4.4 Backlog chain (many weeks, gated)

`scripts/launch_backlog_chain.py` runs weeks one after another. Per week: checks
OpenRouter key credit, requires a v1 completeness file from
`check_v1_window_completeness.py --split`, dry-runs, runs with a per-week cap, and
only starts the next week if the run succeeded **and** the audit says YES. Stops
the whole chain at `--cumulative-stop` spend or low key credit.

```bash
python scripts/launch_backlog_chain.py --foreground \
  --weeks 2026-08-01:2026-08-07,2026-08-08:2026-08-14 \
  --per-week-cap 3 --cumulative-stop 7 \
  --env QUALITY_ENGINE=jev_glm --env SCREEN_MODEL=z-ai/glm-5.3-flash --env CLASSIFY_MODEL=z-ai/glm-5.3-flash
```

`--foreground` is for tmux panes. Two chains on disjoint weeks can run side by
side (each only counts child runs whose window starts on its own week).
Status helper: `~/bin/pi_backlog_status.sh` (read-only).

### 4.5 tmux

Long runs were done in tmux sessions. **Rule from the owner: agents never kill
tmux sessions; the owner does that manually.**

---

## 5. After a run: verify before publishing

```bash
python scripts/audit_window_completeness.py --from X --until Y \
  --out reports/run_status/audit_X_Y.md --json reports/run_status/audit_X_Y.json
```

Prints `Complete enough to publish: YES/NO`. Blocks when prose is missing on
>10% of scored papers, among other checks. If prose is missing (e.g. a run
interrupted after scoring):

```bash
python scripts/backfill_jev_glm_prose.py --from X --until Y --dry-run
python scripts/backfill_jev_glm_prose.py --from X --until Y --allow-paid --max-cost-usd 0.20
```

Then re-run the free `adjudication,reports` stages for the window.

Exports used by the editorial side:
- `scripts/generate_audience_tops.py` — weekly top-20s (policy v001; tech and business pools are exclusive).
- `scripts/export_top_papers.py` — top-400 tech/product. Tech is tiered by
  *measured* efficiency outcomes (Ranjith's brief: "a measured way to reduce
  engineering cost", "reduce inference cost, improve performance in inference").
  Tier A = a number within one sentence of an efficiency term + direction word.
  Not yet validated against hand labels (~3–4 of 30 spot-checked picks weak).
- `scripts/select_newsletter.py`, `scripts/select_linkedin.py` — selection (only consumer of HF signals).

---

## 6. Automation (cron) and the daily health email

Installed for user `ubuntu` (`crontab -l`). Times are UTC because the server is UTC.

| UTC | IST | Job | Script |
|---|---|---|---|
| 20:30 | 02:00 | Free stages for a rolling 6-day window ending yesterday (UTC): ingest, relevance, normalize_authors, affiliation_fast, affiliation_deep, hf_signals | `scripts/cron/pi_free_stages.sh` |
| 00:30 | 06:00 | Health report, emailed | `scripts/cron/pi_health_report.sh` → `scripts/daily_health_report.py` |

**Written decision (30 Sep 2026): cron never runs a paid stage.** Screen,
classify and quality are run by hand (section 4.1). So every day the free stages
pull and filter new papers, and they wait unscored until someone runs the paid
window. Changing this needs an explicit decision plus a `DAILY_SPEND_CAP` guard
and a fixed yesterday window.

Why 6 days: arXiv announces Thursday-afternoon submissions on Sunday 20:00 ET
(Mon 00:00 UTC), after Sunday's run. Monday's run must still reach back to
Thursday. A 3-day window would have dropped those papers (fixed 5 Oct).

### Health report

The health job is deliberately separate from the pipeline so it still reports
when the pipeline never ran. Read-only against the database.

```bash
python scripts/daily_health_report.py --dry-run               # print, don't send
python scripts/daily_health_report.py --dry-run --skip-tests --skip-audit   # fast
```

Subject carries the verdict: `[OK]`, `[ATTENTION] <first problem>`, or
`[ERROR] … health check crashed` (sent if the report itself throws). Body
sections: NEEDS ATTENTION, PIPELINE STATUS, PULL, PROCESSING (per stage in → ok /
failed), SPEND (today IST, month to date, caps), CHECKS.

Checks: key tables present · a pipeline run started in the last 24h · last run
succeeded · newest paper ≤3 days old (4 on Sun/Mon) · no stage >5% failures ·
no run stuck RUNNING >1h · daily / monthly spend under `DAILY_SPEND_CAP` (3) /
`MONTHLY_SPEND_CAP` (50) · classify out-of-vocabulary rate <2% · window audit
(only when the run included quality) · unit tests pass. Thresholds are env
overridable (`HEALTH_*`).

**No email by 08:00 IST = the box or the health check is down. Treat silence as urgent.**

Email delivery: SES in ap-south-1, credentials from the EC2 **instance role**
(never the static AWS keys in `.env`). `SES_FROM` and `ALERT_RECIPIENTS` are in
`.env` (currently subhashini.m@yaaralabs.ai). **Not working yet** — see section 9.
Until it is, read `reports/health/` for the day's report.

---

## 7. Data model — what to query

| Table | Use |
|---|---|
| `papers` | Catalog (authoritative since cutover; `PI_USE_PAPERS_CATALOG=1`). `paper_id`, `arxiv_id`, `published_at` = arXiv v1 date |
| `paper_classification_results` | Append-only LLM outputs. `content_item_id` = `papers.paper_id`. `task_type` ∈ screen, audience, domain, subdomain, application_domain, quality |
| `paper_intelligence_current` | One derived row per paper: scores, audiences, domain, `quality_status` (scored / not_selected / skipped / failed), `hf_*` |
| `paper_author_affiliations`, `organisations`, `organisation_aliases` | Affiliations (append-only; NULL org = unlisted) |
| `paper_hf_signals` | HF featured / upvotes |
| `pipeline_runs` | One row per run (stages and wrappers). `metadata` holds window, costs, stop reasons |
| `stage_runs`, `item_stage_runs` | Finer run tracking |
| `external_requests`, `llm_requests` | Every API call; `llm_requests.actual_cost`/`estimated_cost` is the spend ledger |
| `golden_human_scores` | Human labels for `quality_scoring_golden_v1` |

Useful queries:

```sql
-- What ran recently
SELECT started_at, pipeline_name, status, items_input, items_succeeded, items_failed,
       metadata->>'date_from' AS from_, metadata->>'date_until' AS until_
FROM paper_intelligence.pipeline_runs ORDER BY started_at DESC LIMIT 20;

-- Papers per day and how many are scored
SELECT p.published_at::date, count(*),
  count(*) FILTER (WHERE EXISTS (SELECT 1 FROM paper_intelligence.paper_classification_results r
                   WHERE r.content_item_id = p.paper_id AND r.task_type = 'quality')) AS scored
FROM paper_intelligence.papers p WHERE p.published_at >= now() - interval '10 days'
GROUP BY 1 ORDER BY 1;

-- Spend: today (IST) and month to date
SELECT sum(coalesce(actual_cost, estimated_cost)) FROM paper_intelligence.llm_requests
WHERE created_at >= date_trunc('day', now() AT TIME ZONE 'Asia/Kolkata') AT TIME ZONE 'Asia/Kolkata';
```

DDL lives in `sql/migrations/` (latest `022_golden_dataset_version.sql`, written,
**not applied**). Agents never apply DDL.

---

## 8. Rules (non-negotiable)

1. Never apply DDL from an agent. Ops applies migrations manually.
2. No paid calls without explicit authorisation, a window, a cap, and a dry run.
3. Cron never runs paid stages (decision 30 Sep 2026).
4. Scoring changes are measured against **human** labels, never against another model.
5. No default changes, no weights applied, no policy edits without a decision. New prompt/policy versions are added as `v002` files, never edited in place.
6. Prose stays on `quality_prose/v001` until hand labels + Luna agreement justify v002.
7. Don't close backlog items without verifier evidence (`BacklogClosed.md`).
8. Push must be confirmed on the remote (`git fetch && git log origin/dev/subha`).
9. Never commit `jev_j1b_quality_scores*.json` or `.gitignore-review`. Don't read secret values in `.env`.
10. Don't kill tmux sessions; the owner does.

---

## 9. Current state (5 Oct 2026)

**Coverage scored and audited YES:** 1 Jul – 28 Sep 2026.
The late-Sep backlog runs (Jul 1 – Aug 24 and Sep 23–28) cost ≈ $6.90, roughly
$0.5–0.85 per full week. September's total LLM spend was $23.08 (includes golden
and experiment work).

**Ingested but not scored (needs a manual paid run):**

| v1 date | Papers | Screened |
|---|---|---|
| 29 Sep | 1,330 | 0 |
| 30 Sep | 1,262 | 0 |
| 1 Oct | 772 (rest arrives with tonight's cron) | 0 |

Expected cost to score 29 Sep – 4 Oct after tonight's ingest: about $1.0–1.5.
Command: section 4.1 with `--from 2026-09-29 --until 2026-10-04 --max-cost-usd 3`,
then the audit in section 5.

**Cron:** running daily since 1 Oct; every free run succeeded. 0 new papers on the
3 and 4 Oct runs is the normal arXiv weekend gap.

**Health email:** the report is generated every day at 06:00 IST, but **sending
fails**: `instanceRole` has no `ses:SendEmail` permission. Every daily report is
still saved to `reports/health/` and the failure is in `reports/cron/health.log`.
Every report currently says `[ATTENTION]` because of the 20 stuck runs below.

---

## 10. Open items and known issues

| Item | Owner action |
|---|---|
| **SES permission** | Someone with IAM access: grant `ses:SendEmail` (and `ses:SendRawEmail`) to `instanceRole`; verify sender + recipient addresses in SES ap-south-1 (sandbox). Then test: `python scripts/daily_health_report.py` (without `--dry-run`). |
| **20 runs stuck in RUNNING** (15–24 Sep, crashed/killed runs never closed) | Owner chose to handle manually. Closing them = one `UPDATE pipeline_runs SET status='cancelled', ended_at=now() WHERE status='running' AND started_at < '2026-09-25'` — review the rows first. |
| **Unscored days** 29 Sep onward | Manual paid run (section 9). |
| **HF cache never refreshes** | `raw_store` reuses any cached HF response forever, so a same-day partial daily list or old upvotes are never refreshed. Fix proposed (bypass cache for recent dates), not done. Workaround: none cheap; re-runs only fetch uncached dates. |
| **Dry-run projection blind to unscreened weeks** | Known; use real cost per 1k papers instead. |
| **`check_schema.py` has no DB probe** | Always exits 0. Health report checks key tables exist instead. |
| **Tech top-400 heuristic unvalidated** | ~60 picks offered for hand labelling. |
| **Prose v002** | Waiting on owner's hand labels. |
| Older carried items | `Backlog.md`: `write_jev_glm_report.py` SQL bug, migration 022, Ranjith double-label import, G3c weights, screen-gate policy, default `QUALITY_ENGINE`, org_boost, notable people. |

---

## 11. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `STOP: stage X tripped the runguard (exit 3)` | >10% failures. Look at the stage log for the error. Malformed JSON is now retried once; persistent failures usually mean provider trouble — wait and re-run the window (already-scored papers are skipped, so re-running is cheap). |
| Quality refuses: projection > remaining cap | Projection is ~2.5× actual. Raise `--max-cost-usd` modestly or pass `--force-over-projection` if authorised. |
| Ingest aborts with UniqueViolation on DOI | Fixed (39d05b3). If it recurs, check `find_existing_paper_id` / `doi_holder` in `catalog/ingest.py`. |
| Audit says NO, prose missing | Prose backfill (section 5), then adjudication + reports. |
| psql "socket" / missing `DATABASE_URL` | You didn't source `.env` in this shell. |
| Health email `[ERROR] … crashed` | The report couldn't connect/query. Check DB reachability first; the traceback is in the email and `reports/health/`. |
| No health report file for today | Cron or the box is down: `systemctl status cron`, `crontab -l`, `tail reports/cron/health.log`. |
| Free cron ran but 0 new papers on a weekday | Check `reports/cron/free_stages.log` and the run log; check arXiv OAI availability. On Sat/Sun runs, 0 is normal. |
| Two scripts racing (test before edit, etc.) | Don't run dependent commands in parallel. |

---

## 12. Code map

```
scripts/
  launch_pipeline_run.py     detached single-window run (+ run record)
  run_pipeline.py            stage orchestration, budget, RunGuard stop
  run_stage.py               one stage; writes per-stage run metadata
  launch_backlog_chain.py    multi-week gated chain
  audit_window_completeness.py   publish gate
  backfill_jev_glm_prose.py  prose repair
  daily_health_report.py     health email
  cron/pi_free_stages.sh, cron/pi_health_report.sh
  generate_audience_tops.py, export_top_papers.py, select_newsletter.py, select_linkedin.py
src/paper_intelligence/
  ingest/arxiv_oai.py, catalog/ingest.py   OAI harvest, catalog upsert, DOI conflict
  relevance/  screen/  audience_domain/  quality/ (jev_glm_engine.py)
  author_affiliation/  organisation_resolution/   fast/deep affiliation
  hf_signals/  external/huggingface.py
  adjudication/   common/ (config.py, batch_runner.py, llm_stage.py, budget.py, v1_floor.py)
  observability/ (pipeline_runs)   openrouter/   db/
policies/  prompts/   versioned YAML / prompt files (add v002, never edit v001)
golden/    quality_scoring_golden_v1 (human labels)
tests/unit/  `python -m pytest -q tests/unit` (375 tests)
```
