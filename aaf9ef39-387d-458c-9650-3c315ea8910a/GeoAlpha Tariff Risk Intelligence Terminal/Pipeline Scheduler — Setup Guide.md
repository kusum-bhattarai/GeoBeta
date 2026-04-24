# 🗓️ Pipeline Scheduler — Daily Cron Job

## What Was Built

A **Zerve Scheduled Deployment** (`pipeline_scheduler`) that orchestrates the full data pipeline in strict sequence:

| Step | Source | Key Columns (Idempotent Upsert) |
|------|--------|--------------------------------|
| 1 | **EDGAR** | `cik`, `accession_number`, `filing_date` |
| 2 | **Alpha Vantage** | `ticker`, `date` |
| 3 | **FRED** | `series_id`, `observation_date` |
| 4 | **GDELT** | `event_id`, `date` |
| 5 | **Prediction Markets** | `market_id`, `snapshot_ts` |
| 6 | **Escalation Index** | `date`, `entity` |
| 7 | **Misprice Analysis** | `ticker`, `analysis_date` |
| 8 | **Prediction Model** | `model_version`, `ticker`, `inference_date` |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Service info, next run time, stage list |
| `GET` | `/health` | Liveness probe |
| `GET` | `/status` | Last run result, duration, stage breakdown |
| `POST` | `/run` | Manually trigger an immediate full pipeline run |
| `POST` | `/schedule` | Update cron expression at runtime |

## Default Schedule

```
0 6 * * *   →  Daily at 06:00 UTC
```

## Change the Schedule

**Option A — Environment Variable (before deploy):**
```
PIPELINE_CRON=0 */4 * * *    # every 4 hours
PIPELINE_CRON=0 6,18 * * *   # twice daily at 06:00 and 18:00
PIPELINE_CRON=0 6 * * 1-5   # weekdays only
```

**Option B — Live API call (no restart needed):**
```bash
curl -X POST https://<your-deployment-url>/schedule \
  -H "Content-Type: application/json" \
  -d '{"cron": "0 */4 * * *"}'
```

## Plug In Your Stage Logic

Each stage in `app/main.py` has a `# TODO` comment. Replace the stubs with real code:

```python
def run_edgar_stage() -> dict:
    from zerve import variable
    edgar_df = variable(block_name="edgar_ingest", variable_name="edgar_df")
    # upsert edgar_df to your DB here
    return {"records_upserted": len(edgar_df)}
```

## Idempotency Guarantee

All stages use **upsert semantics** — re-running on the same day overwrites existing rows rather than creating duplicates. Safe to run multiple times.

## Deploy

1. Open the **`pipeline_scheduler`** script (Scripts panel)
2. Click **Deploy**
3. Set `PIPELINE_CRON` env var if you want a non-default schedule
4. Monitor via `GET /status` endpoint
