# Subha stream — Context

## Scope and ownership

Subha owns architecture, schema semantics, classification policy, author/affiliation policy, adjudication, and the stage implementations: `normalize`, `screen`, `classify`, `quality`, `author_affiliation`, `organisation_resolution`, `adjudication`, plus derived `paper_intelligence_current`.

Worktree: `~/Paperintelligencev1/worktrees/subha` · Branch: `dev/subha`.

## Does **not** own (Urmila)

- Deterministic request hashing / JSON.gz raw cache
- `external_requests` / `llm_requests` persistence implementation
- ROR / OpenAlex / OpenRouter client **implementations** (Subha specifies stubs/contracts)
- Golden dataset loaders and evaluation runner implementation
- Fixtures for live-API-free unit tests of clients

## Interface dependency blocking Urmila

Until Phase 2 lands on `main`:

- Table shapes for `external_requests` and `llm_requests` (documented)
- `Stage` / `StageResult` / `RunContext` contracts
- Typed stubs: `ror.resolve_affiliation`, `openalex.get_work`, `openrouter.complete`

## Classification decisions already taken

- Screen + classify: GLM 5.3 Flash, **reasoning off**
- Closed vocabularies **inline** in prompts
- `general_method` is correct for most papers; mutually exclusive with sector labels
- Audience + domain + subdomain + application_domain = **one** LLM call, **multiple** append-only rows

## Affiliation policy

Precedence: explicit paper affiliation → strong deterministic → ROR → OpenAlex paper-specific → author-profile secondary only. Unknown beats wrong. Unlisted orgs keep `organisation_id NULL`.

## Working rules

- Subha **writes** migrations; the **human applies** DDL
- Only Verifier marks items complete
- Agent sequence: Architect → Scout → Engineer → Verifier (never parallel coding)
- Commit code and MD together at end of cycle
