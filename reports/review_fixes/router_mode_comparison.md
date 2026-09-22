# Router mode comparison 2026-09-01 → 2026-09-15

Baseline: **window+judge** (n=1661, gate=15.0%).
Default production scope is unchanged (`window`).

## Modes

| Mode | Selected | + vs baseline | − vs baseline | + already quality | + need quality | + dry-run $ |
|---|---:|---:|---:|---:|---:|---:|
| `window+judge` | 1661 | 0 | 0 | 0 | 0 | $0.0000 |
| `window+raw_ooi` | 1661 | 0 | 0 | 0 | 0 | $0.0000 |
| `day+judge` | 1667 | 90 | 84 | 90 | 0 | $0.0000 |
| `day+raw_ooi` | 1667 | 90 | 84 | 90 | 0 | $0.0000 |

## Per-day counts (single-day windows)

- 2026-09-01: selected=145
- 2026-09-02: selected=131
- 2026-09-03: selected=135
- 2026-09-04: selected=118
- 2026-09-05: selected=79
- 2026-09-06: selected=69
- 2026-09-07: selected=123
- 2026-09-08: selected=131
- 2026-09-09: selected=114
- 2026-09-10: selected=100
- 2026-09-11: selected=116
- 2026-09-12: selected=62
- 2026-09-13: selected=72
- 2026-09-14: selected=160
- 2026-09-15: selected=112

No LLM calls. No default scope change.

