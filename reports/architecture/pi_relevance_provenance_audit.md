# Migrated Relevance Provenance Audit

## Answers

| Q | Answer |
|---|---|
| A. Radar → keep | `RELEVANT, ENRICHED, ENTITY_RESOLVED, SCORED, CANDIDATE` |
| B. Radar → reject | `REJECTED` |
| C. ENTITY_RESOLVED → keep? | **Yes** |
| D. Why | Radar lifecycle after relevance; not a reject; preserves Phase-2-class papers |
| E. keep contradicted by PI screen fail? | **208** (screen fail ≠ relevance contradiction) |
| F. reject contradicted by screen pass? | **0** |

## Method relabel

Updated `28383` rows: `method='migrated'` → `method='migrated_legacy_state'`.

## Status × decision counts

```json
[
  {
    "radar_status": "ENTITY_RESOLVED",
    "decision": "keep",
    "n": 13959
  },
  {
    "radar_status": "REJECTED",
    "decision": "reject",
    "n": 8083
  },
  {
    "radar_status": "RELEVANT",
    "decision": "keep",
    "n": 5107
  },
  {
    "radar_status": "SCORED",
    "decision": "keep",
    "n": 990
  },
  {
    "radar_status": "CANDIDATE",
    "decision": "keep",
    "n": 242
  },
  {
    "radar_status": "ENRICHED",
    "decision": "keep",
    "n": 2
  }
]
```

## Screen join

```json
[
  {
    "decision": "keep",
    "n": 20300,
    "with_screen": 7756,
    "screen_gate_passed": 7548,
    "screen_gate_failed": 208,
    "no_screen": 12544
  },
  {
    "decision": "reject",
    "n": 8083,
    "with_screen": 0,
    "screen_gate_passed": 0,
    "screen_gate_failed": 0,
    "no_screen": 8083
  }
]
```

## Stop?

`stop_for_contradictions` = **False**
