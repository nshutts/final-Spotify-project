# 100-review cost and runtime report

Generated offline from `measurements.json`, `usage.csv` and `rates.csv`. Pilot measured 2026-10-20T14:05:06.

## Measured pilot (real calls)

- Input: `data/cost_100.csv`, SHA-256 `c884ac3b9be5066995d5063f96ad9af6e5e082975788c1684c4f6b6ea661dd0e`; 100 rows, 100 unique nonempty texts.
- Provider/model: TypeSafe Jev `jev-1.13.0` (no thinking/effort setting exists for Jev); 1 review per request; 1 worker; prompt versions in `pipeline/prompts.py`.
- Cold run: 100 enriched + 0 cache copies completed, 0 quarantined; 100 enrich requests, 100 attempts, 0 failed attempts; verify sample 20.
- Warm run: 0 new enrich requests (cache hits: 100 originals reused); verify 0, group 0, memo 0 new calls.

| Run | Wall-clock s | Enrich s | Verify s | Group s | Rank s | Memo s | API cost (USD) |
|---|---|---|---|---|---|---|---|
| cold | 22.062 | 17.259 | 3.505 | 1.102 | 0.005 | 0.188 | 0.004464 |
| warm | 0.03 | 0.012 | 0.008 | 0.004 | 0.002 | 0.003 | 0 |

### Cold-run cost by stage

| Stage | Model | Calls | Failed | Input tokens | Rate (USD/M) | Cost (USD) |
|---|---|---|---|---|---|---|
| enrich | jev-1.13.0 | 100 | 0 | 83287 | 0.042 | 0.003498 |
| verify | jev-1.13.0 | 20 | 0 | 15858 | 0.042 | 0.000666 |
| group | jev-1.13.0 | 7 | 0 | 6075 | 0.042 | 0.000255 |
| memo | jev-1.13.0 | 1 | 0 | 1075 | 0.042 | 0.000045 |

- Cold API total: **$0.004464**; per 1,000 input rows $0.044640; per completed record $0.000045.
- Enrichment throughput (1 worker): 5.79 requests/s; mean 832.9 billed input tokens per enrich request.
- Output tokens are billed at $0 by Jev. Local compute (a laptop running Python) is not priced: **unknown, not zero**.
- Rates: jev-1.13.0 uncached_input $0.042/M as of 2026-10-19 (https://docs.typesafe.ai/models), jev-1.13.0 output $0.0/M as of 2026-10-19 (https://docs.typesafe.ai/models).

## Full-run projection (estimates, not measurements)

Budget (editable in `assumptions.json`): **$10** total API spend. Max workers 8; fallback fraction 0 (no stronger-model fallback is used); output-token cap: not applicable (Jev returns fixed-size structured answers, output billed at $0).

| Scenario | Enrich requests | Retry rate | Verify | Enrich cost | Other stages | Total | Hours at workers | Over budget? |
|---|---|---|---|---|---|---|---|---|
| base | 489,030 | 0.01 | 1000 | $17.106565 | $0.034268 | **$17.140833** | 3.3 h at 8 | **YES: over budget** |
| conservative | 508,398 | 0.05 | 1000 | $17.784052 | $0.035234 | **$17.819286** | 6.1 h at 8 | **YES: over budget** |
| no_reuse | 667,215 | 0.01 | 1000 | $23.339544 | $0.034268 | **$23.373812** | 4.4 h at 8 | **YES: over budget** |

Projection method: measured billed tokens per enrich request x projected requests x rate; verify scaled by sample size; group and memo are fixed overhead counted once (one call per issue, one memo call). Time assumes enrich latency stays at the pilot value and workers overlap with the stated efficiency; the provider's rate limits may cap this. No-reuse comparison uses 660,609 requests instead of 484,189.

## Controls

- Spend: one ledger (`runs/spend_ledger.json`) shared by every run, worker and stage; worst-case cost is reserved before each dispatch and work stops when spent + reserved + next reservation would pass the cap.
- Retries: HTTP 429/5xx/529 and network errors retried up to 4 times with exponential backoff, jitter and Retry-After; invalid output retried once, then quarantined with the reason.
- Recovery: results are appended and fsynced in batches; a rerun loads completed IDs and sends only pending work. Ctrl-C stops dispatch, drains in-flight calls and saves a checkpoint.

## Replay

Offline (no key, no calls): `python3 -m cost.pilot report`. Edit `rates.csv` or `assumptions.json` and rerun to see the effect. Paid pilot: `python3 -m cost.pilot run --csv data/cost_100.csv`.
