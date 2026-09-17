# Automated Multi-Cloud Cost Optimisation & Anomaly Detection Platform

HCLTech PS-03 (Cloud & DevOps, DBS Business) working prototype: a FinOps
intelligence layer that ingests AWS / Azure / GCP billing data, detects cost
anomalies, forecasts spend, and auto-generates Terraform right-sizing
remediation scripts.

Runs entirely on your laptop with **Docker Compose** and needs **no cloud
account** — every connector defaults to a realistic synthetic data generator.
Real AWS/Azure/GCP SDK integration code is included and can be switched on
later with one environment variable once you have credentials.

## Architecture

```
                    ┌──────────────────────────┐
                    │   React Dashboard (nginx) │  :5173
                    └─────────────┬─────────────┘
                                  │ REST (JSON)
                    ┌─────────────▼─────────────┐
                    │   Django + DRF API         │  :8000
                    │   costs/views.py           │
                    └───┬─────────┬─────────┬────┘
                        │         │         │
          ┌─────────────▼──┐  ┌───▼────┐  ┌─▼────────────────┐
          │ Connectors      │  │ ML      │  │ Remediation       │
          │ (AWS/Azure/GCP  │  │ Isolation│ │ right-sizing +    │
          │  or Mock)       │  │ Forest, │  │ Terraform HCL gen │
          │ costs/connectors│  │ Prophet │  │ costs/remediation │
          └─────────────────┘  └─────────┘  └───────────────────┘
                        │
                 ┌──────▼──────┐      ┌────────────┐
                 │  Postgres   │      │ Celery      │
                 │  (cost data)│      │ worker+beat │──> Redis broker
                 └─────────────┘      └────────────┘
```

- **Ingestion**: `costs/connectors/*` implement one `CostConnector`
  interface. `mock.py` generates reproducible, realistic multi-cloud billing
  data (trend + weekly seasonality + injected spikes + per-resource
  utilisation); `aws.py` / `azure.py` / `gcp.py` call the real Cost
  Explorer / Cost Management / Billing-export APIs and are used automatically
  when `USE_MOCK_CLOUD_DATA=false`.
- **Anomaly detection**: `costs/ml/anomaly.py` runs scikit-learn
  `IsolationForest` per (account, service) daily cost series, using rolling
  mean/std/day-of-week features, and stores flagged spikes with a severity.
- **Forecasting**: `costs/ml/forecast.py` fits `Prophet` per service for a
  14-day forward forecast with confidence bands. If Prophet can't be fit
  (e.g. too little data, or its Stan backend can't build in a restricted
  network), it transparently falls back to a lightweight seasonal-naive
  forecaster so the pipeline never breaks.
- **Right-sizing**: `costs/remediation/rightsizing.py` flags persistently
  under-utilised compute resources and either recommends downsizing to the
  next smaller instance type in its family (`costs/catalog.py`) or, if
  effectively idle, decommissioning it — then renders a ready-to-review
  Terraform `.tf` file per recommendation (`costs/remediation/terraform_templates.py`).
- **Orchestration**: `costs/pipeline.py` runs ingest → anomaly detection →
  forecast → right-sizing as one pipeline, invoked via Celery (worker +
  beat, every 6h) or synchronously as a fallback, and tracked as an
  `AnalysisRun` row so the dashboard can show progress/history.
- **API**: single `GET /api/dashboard/` powers the whole dashboard in one
  call; granular REST endpoints (`/api/costs/`, `/api/anomalies/`,
  `/api/forecasts/`, `/api/recommendations/`) support drill-down.

## Running it

```bash
cp .env.example .env
docker compose up --build
```

Then open:
- Dashboard: http://localhost:5173
- API: http://localhost:8000/api/dashboard/
- Django admin: http://localhost:8000/admin/ (create a superuser first: `docker compose exec backend python manage.py createsuperuser`)

On first boot the `backend` container automatically runs migrations and
seeds three demo cloud accounts (one AWS, one Azure, one GCP). The dashboard
starts empty — click **Run Analysis** to ingest ~6 months of synthetic
billing data and run the full anomaly detection / forecasting / right-sizing
pipeline (takes a few seconds to a couple of minutes the first time, mostly
Prophet model fitting). After that, Celery beat re-runs the pipeline every 6
hours automatically, or click **Run Analysis** again any time.

Generated Terraform remediation scripts are written to
`backend/generated_terraform/` on the host (mounted volume) and downloadable
from the Recommendations table in the dashboard.

## Running it on a different machine

The project has no local Python/Node install and no external service
dependency beyond Docker — everything (Postgres, Redis, Django, Celery,
the compiled React app) runs inside containers. Moving it to another
laptop is just: get the folder there, make sure Docker is installed, run
the same two commands as above.

### 1. Prerequisites on the new machine

- **Docker Desktop** (Mac/Windows) or **Docker Engine + the Compose
  plugin** (Linux) — this is the only thing that needs installing.
  Verify with:
  ```bash
  docker --version
  docker compose version
  ```
- Ports **5173, 8000, 5432, 6379** free (not already used by something
  else on that machine).
- Works the same on Intel, Apple Silicon (M-series), and Linux x86/ARM —
  the backend image compiles Prophet's CmdStan backend from source during
  the build rather than shipping a prebuilt binary, so there's no
  architecture mismatch to worry about (it just takes a couple of extra
  minutes on the very first build).

### 2. Get the project onto the new machine

Pick whichever is easiest for you:

**Option A — copy the folder directly** (simplest, no GitHub needed).
The whole project is ~300 KB (no `node_modules`/`venv` are stored locally
— those only exist inside the containers), so it zips and transfers
instantly:
```bash
# on this machine
cd ~
zip -r hcl-ps03-cloudcost.zip hcl-ps03-cloudcost -x "*.git*"
# copy hcl-ps03-cloudcost.zip to the other machine (USB drive, AirDrop,
# Google Drive, scp, etc.), then on the other machine:
unzip hcl-ps03-cloudcost.zip
```

**Option B — push to GitHub/GitLab and clone it** (better if you want
version history or plan to keep editing from both machines):
```bash
# on this machine, one-time setup
cd ~/hcl-ps03-cloudcost
git init
git add .
git commit -m "Initial commit"
git remote add origin <your-repo-url>
git push -u origin main

# on the other machine
git clone <your-repo-url>
```

### 3. First-time setup on the new machine

```bash
cd hcl-ps03-cloudcost
cp .env.example .env

# IMPORTANT: some transfer methods (zip on Windows, certain USB
# filesystems, some git configs) strip the executable bit from shell
# scripts. Re-set it explicitly before building, otherwise the backend
# container fails immediately with "permission denied":
chmod +x backend/entrypoint.sh

docker compose up -d --build
```

The first build takes a few minutes (mostly compiling Prophet's CmdStan
backend, done once and cached in the image after that). Once it's up:

```bash
docker compose ps          # all 6 services should show "Up"/"healthy"
```

Then open **http://localhost:5173** and click **Run Analysis**, exactly
as on the original machine — migrations and demo accounts are created
automatically on first boot, same as before.

### 4. If something looks wrong

- `docker compose logs backend` / `celery_worker` — check for errors.
- `permission denied` on `entrypoint.sh` → re-run the `chmod +x` above,
  then `docker compose up -d --build` again.
- Nothing responds on a port → something else on that machine is already
  using it; either stop that process or change the port mapping (the
  left-hand side of `"5173:80"` etc. in `docker-compose.yml`).
- Want a completely clean slate → `docker compose down -v` (wipes the
  database too), then `docker compose up -d --build` again.

## Switching from synthetic data to real cloud accounts

No code changes needed — set in `.env`:

```
USE_MOCK_CLOUD_DATA=false
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AZURE_SUBSCRIPTION_ID=...
AZURE_TENANT_ID=...
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
GCP_PROJECT_ID=...
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

Then update the seeded `CloudAccount.external_id` values (via `/admin/`) to
your real account/subscription/project IDs. `costs/connectors/get_connector()`
picks the real connector per provider automatically.

## Project layout

```
backend/            Django project
  config/           settings, urls, celery app
  costs/            the whole domain: models, connectors, ml, remediation, API
  generated_terraform/   .tf files written by the right-sizing engine
frontend/           React (Vite) dashboard, served by nginx in production
docker-compose.yml  db (Postgres), redis, backend, celery_worker, celery_beat, frontend
```

## Useful commands

```bash
# Re-run the full pipeline from the CLI instead of the dashboard button
docker compose exec backend python manage.py run_analysis

# Just (re)ingest cost data without running ML
docker compose exec backend python manage.py ingest_costs --days-back 180

# Tail logs
docker compose logs -f backend celery_worker

# Django shell
docker compose exec backend python manage.py shell
```

## Extending for the IEEE / Scopus paper track

The pipeline already records enough to evaluate quantitatively:
- **Anomaly detection quality**: since spikes are injected deterministically
  in `costs/connectors/mock.py` (`_stable_seed(resource_id, str(d)) % 100 < 4`),
  you can compute precision/recall of `Anomaly` rows against the known
  injected-spike ground truth.
- **Forecast accuracy**: compare `Forecast.predicted_amount` against actual
  ingested `CostRecord` totals once those dates arrive (MAPE/RMSE), and
  compare the Prophet path vs. the naive-seasonal fallback path.
- **Savings impact**: sum `Recommendation.estimated_monthly_savings` across
  a run as the platform's headline FinOps metric.
