# LLM cost repricing audit (read-only)

Calls: **1282**
Old table total: **$6.3708**
New table total: **$17.0409**
Logged estimated total: **$6.3708**

## By month / stage / model

| month | stage | model | calls | in tok | out tok | old $ | new $ | ratio |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 2026-09 | affiliation_judge | `z-ai/glm-4.6` | 68 | 64739 | 62596 | 0.0410 | 0.1374 | 3.35 |
| 2026-09 | audience_domain | `z-ai/glm-5.3-flash` | 19 | 108371 | 87175 | 0.0598 | 0.0598 | 1.0 |
| 2026-09 | classify | `z-ai/glm-5.3-flash` | 291 | 1680437 | 955053 | 0.7296 | 0.7296 | 1.0 |
| 2026-09 | quality | `openai/gpt-5.6-sol` | 379 | 800434 | 378606 | 4.7866 | 15.3603 | 3.209 |
| 2026-09 | screen | `z-ai/glm-5.3-flash` | 525 | 2637363 | 716448 | 0.7538 | 0.7538 | 1.0 |

## Runs (match to OpenRouter activity)

- `e2e6e7ce-f297-4296-b518-407b336701b0` · 2026-09-15T11:34:17.159031+00:00 · paper_intelligence.screen · calls=1 · stages=screen · models=z-ai/glm-5.3-flash
- `8896be79-fde1-4925-bece-ef719e0c8dce` · 2026-09-15T11:35:01.527353+00:00 · paper_intelligence.screen · calls=348 · stages=screen · models=z-ai/glm-5.3-flash
- `5970ab85-2005-42c1-ab8d-dd13ba3102f2` · 2026-09-15T11:54:54.445756+00:00 · paper_intelligence.screen · calls=2 · stages=screen · models=z-ai/glm-5.3-flash
- `08d4012c-924d-4670-b8d7-c5ddcaceb65c` · 2026-09-15T11:55:17.274900+00:00 · paper_intelligence.classify · calls=71 · stages=classify · models=z-ai/glm-5.3-flash
- `05747117-ebdb-45f1-b83e-954204df1ad0` · 2026-09-15T11:55:18.655110+00:00 · paper_intelligence.quality · calls=40 · stages=quality · models=openai/gpt-5.6-sol
- `ddad0dbf-d793-4a5b-9c73-aa9597b67984` · 2026-09-15T11:57:17.005282+00:00 · paper_intelligence.quality · calls=43 · stages=quality · models=openai/gpt-5.6-sol
- `3bff3da1-25b6-4298-9eae-1c3fd56e4cc0` · 2026-09-15T12:35:41.784773+00:00 · paper_intelligence.quality · calls=172 · stages=quality · models=openai/gpt-5.6-sol
- `4f53aca7-1e4c-4a94-91a1-6996181beaf2` · 2026-09-15T13:07:07.273605+00:00 · paper_intelligence.classify · calls=68 · stages=classify · models=z-ai/glm-5.3-flash
- `0960fb85-c648-4c15-9edd-2652436dabf1` · 2026-09-15T13:12:08.426378+00:00 · paper_intelligence.classify · calls=1 · stages=classify · models=z-ai/glm-5.3-flash
- `a91962e6-0e69-46cd-b878-41d361dc91b7` · 2026-09-16T06:08:37.067793+00:00 · paper_intelligence.screen · calls=155 · stages=screen · models=z-ai/glm-5.3-flash
- `4c473872-8613-4622-bee6-25e712cc8e17` · 2026-09-16T06:13:39.457809+00:00 · paper_intelligence.classify · calls=151 · stages=classify · models=z-ai/glm-5.3-flash
- `4f5c16ce-1f7f-4265-baa9-988b7d6e1202` · 2026-09-16T06:28:10.151661+00:00 · paper_intelligence.quality · calls=110 · stages=quality · models=openai/gpt-5.6-sol
- `8a90c677-3164-4bb5-8e83-c6f95b3f5b45` · 2026-09-17T12:28:31.839251+00:00 · paper_intelligence.screen · calls=17 · stages=screen · models=z-ai/glm-5.3-flash
- `744c135a-cda2-4faa-a6b1-f6c13d8b37a1` · 2026-09-17T12:30:03.172344+00:00 · paper_intelligence.audience_domain · calls=17 · stages=audience_domain · models=z-ai/glm-5.3-flash
- `8df5a471-2fd7-4bf0-a695-309a57072a6c` · 2026-09-17T12:33:08.750533+00:00 · paper_intelligence.quality · calls=10 · stages=quality · models=openai/gpt-5.6-sol
- `63bd94f0-6060-45fb-b420-3a2d21621a8b` · 2026-09-21T06:54:34.923054+00:00 · paper_intelligence.screen · calls=1 · stages=screen · models=z-ai/glm-5.3-flash
- `6921ff86-15f6-43dd-845f-259262fd7ef8` · 2026-09-21T06:54:51.232433+00:00 · paper_intelligence.audience_domain · calls=1 · stages=audience_domain · models=z-ai/glm-5.3-flash
- `d09809e3-f43c-4469-a8da-404a16e37622` · 2026-09-21T06:55:22.267379+00:00 · paper_intelligence.quality · calls=2 · stages=quality · models=openai/gpt-5.6-sol
- `fbda9b10-90e7-48ce-ac0a-7595e1816530` · 2026-09-21T06:59:54.480140+00:00 · paper_intelligence.screen · calls=1 · stages=screen · models=z-ai/glm-5.3-flash
- `9c76d27a-16a8-41af-b6a7-481dbb7e6101` · 2026-09-21T07:00:59.017941+00:00 · paper_intelligence.audience_domain · calls=1 · stages=audience_domain · models=z-ai/glm-5.3-flash
- `aaa40c2c-7f5b-4b64-8437-a741e71dbe4d` · 2026-09-21T07:02:34.343757+00:00 · paper_intelligence.quality · calls=2 · stages=quality · models=openai/gpt-5.6-sol
