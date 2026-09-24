# Wrap up my day

**Trigger:** when the user says **"wrap up my day"**, execute this file end to end, in order, with no paid LLM/API calls unless the user explicitly authorises them in the same message.

**Purpose:** durable decisions, accurate state, backlog hygiene, flow diagram, and a push that actually landed on the remote.

---

## Sequence (mandatory order)

### 1. DECISIONS → `Context.md`

Scan today's work (commits, reports, chat, agent files, migrations, flags). Update **`Context.md`**:

- **Decisions made today** — each entry must include:
  - the decision (what changed / what was locked)
  - the **evidence** (report path, test, metric, or explicit human instruction)
  - the **date** (`YYYY-MM-DD`)
- **Decisions still open** — each entry must include:
  - the options
  - what each option **costs or risks**
- **Conflicts** (architectural call needed, not yet taken) — write as a **question** with named alternatives. **Do not** recommend an option.

**Rules:** never fabricate a decision that was not made. If unsure whether something was decided, put it under open or conflict, not under made.

---

### 2. STATE → `State.md`

Update **`State.md`** so the next agent can act without re-discovery:

| Section | Content |
|---|---|
| **Running today** | live jobs / windows / PIDs or log paths |
| **Wired but off** | feature + **env/flag name** + **default** |
| **Built but unwired** | code exists; no flag or call path in production pipeline |
| **Next unblocked item** | single next step that does not wait on an open decision |

---

### 3. PROJECT.md

Update **`PROJECT.md`** only if a **settled** decision changed pipeline shape, ownership, or locked defaults.

If `PROJECT.md` is behind the repo (stale stage order, missing engines, outdated golden pointers), **say so explicitly inside the file** — do not silently patch around the gap in other docs only.

---

### 4. BACKLOG

- Move finished items to **`BacklogClosed.md`** with **verifier evidence** (report path, gate numbers, or Verifier note).  
  **Never** mark an item closed without that evidence.
- Add anything **discovered today** to **`Backlog.md`** (bugs, follow-ups, open decisions that became work items).

---

### 5. FLOW DIAGRAM → `docs/pipeline_flow.md`

If any stage order, model, engine flag, or affiliation evidence path changed today, update **`docs/pipeline_flow.md`** (Mermaid). It must show:

1. **Stage order** (ingest → … → reports)
2. **Model or engine per stage** (including `QUALITY_ENGINE=terra|jev_glm`)
3. **Affiliation evidence hierarchy:** arXiv HTML → ROR → OpenAlex, with the **LLM affiliation judge after deep**

If nothing in those areas changed, leave the diagram unchanged and note that in the report.

---

### 6. UNCOMMITTED CHECK

Run `git status` (and `git status -u` if needed). **List every uncommitted file** — code, markdown, SQL, configs, golden assets. Nothing is omitted because it is "just an `.md`".

Classify each path for the report: commit / leave uncommitted (with reason).

---

### 7. COMMIT AND PUSH

- Group changes into **logical conventional commits** (e.g. `feat(…)`, `docs(…)`, `fix(…)`, `chore(…)`).
- Commit only what belongs in the repo (no secrets, prefer not to commit huge runtime dumps / `.log` if gitignored).
- **Push** to the tracked remote branch.
- Confirm durability:

```bash
git log origin/<branch> -1
```

A commit that exists only locally is **not** durable. If push fails, stop and report — do not claim wrap-up complete.

---

### 8. REPORT (print to the user)

Print:

1. What was **committed** (hash + message per commit)
2. What was **pushed** (branch + `git log origin/<branch> -3`)
3. **Decisions recorded** (made / open / conflicts)
4. **Open questions** carried forward
5. Anything that **did not** get committed, and **why**
6. **Migrations:** if a migration was written but **not applied**, say so explicitly. **Never apply DDL** during wrap-up.

---

## Hard rules (always)

| Rule | |
|---|---|
| No fabricated decisions | Evidence or it goes under open/conflict |
| No false backlog closes | Verifier evidence required |
| No DDL | Agents write migrations; humans/ops apply |
| No paid calls | Unless the wrap-up message explicitly authorises them |
| Push is mandatory | Local-only commits fail the wrap-up |
| Honesty over tidiness | Prefer "still open" / "uncommitted because …" over a clean-looking lie |

---

## Suggested scan order for "today's work"

1. `git log --since=midnight --oneline` and `git status`
2. New/changed under `reports/`, `docs/`, `golden/`, `.cursor/agents/`, `sql/migrations/`
3. Flags in `src/paper_intelligence/common/config.py` and `config/settings.yaml`
4. `Context.md` / `State.md` / `Backlog.md` / `PROJECT.md` as they stood this morning
