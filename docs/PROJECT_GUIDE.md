# Project Guide: Multi-Cloud Cost Optimisation & Anomaly Detection Platform

This document explains **everything** about this project — what it does, why
it's built the way it is, how every piece works, and what happened while
building it — in enough detail that you can explain it to a professor, a
recruiter, or a teammate without me in the room.

It's written to be read top to bottom, but each section stands alone if you
just need to answer one question.

---

## 1. The problem this solves (in plain English)

HCLTech manages cloud infrastructure for large enterprise clients across
three providers: **AWS, Azure, and GCP**. Each provider has its own billing
dashboard (AWS Cost Explorer, Azure Cost Management, GCP Billing), but none
of them talk to each other. So if you're managing 100 clients across three
clouds, you have to log into three separate consoles per client just to
answer "why did our bill spike last Tuesday?" or "which servers are we
paying for but not using?"

This project builds **one unified layer** that:
1. Pulls in billing data from all three clouds into one place.
2. Automatically flags days where spend looks abnormal ("anomaly
   detection") instead of a human having to eyeball a spreadsheet.
3. Forecasts what next month's bill will look like.
4. Finds servers that are paying for capacity nobody is using, and
   auto-writes the **Terraform code** (infrastructure-as-code) needed to
   fix it — so a DevOps engineer can review and apply it instead of
   manually resizing things by hand.

That's "FinOps" (Financial Operations for cloud) — the discipline of
treating cloud cost like an engineering problem, not just an accounting one.

---

## 2. Why no real AWS/Azure/GCP account was needed

You don't have cloud accounts, and getting three (AWS + Azure + GCP) purely
to demo a college project would cost money and take time to set up. So the
whole platform is built around one design decision:

> **Every cloud integration goes through one common interface
> (`CostConnector`). A "mock" implementation of that interface generates
> realistic, reproducible fake billing data. Real implementations
> (`AWSCostConnector`, `AzureCostConnector`, `GCPCostConnector`) exist too,
> written against the real SDKs, but are only switched on if you flip one
> setting (`USE_MOCK_CLOUD_DATA=false`) and provide real credentials.**

This is exactly how a real production system would be built anyway (you
always want to develop/test without hitting real billing APIs), so it's
not a "fake version" of the architecture — it's the real architecture,
with a synthetic data source plugged in by default. This is the single most
important idea to be able to explain, because it's what makes the whole
project a genuinely working system rather than a static mockup.

---

## 3. High-level architecture

```
                    ┌──────────────────────────┐
                    │   React Dashboard (nginx) │  :5173
                    └─────────────┬─────────────┘
                                  │ REST (JSON over HTTP)
                    ┌─────────────▼─────────────┐
                    │   Django + DRF API         │  :8000
                    └───┬─────────┬─────────┬────┘
                        │         │         │
          ┌─────────────▼──┐  ┌───▼────┐  ┌─▼────────────────┐
          │ Connectors      │  │ ML      │  │ Remediation       │
          │ (AWS/Azure/GCP  │  │ Isolation│ │ right-sizing +    │
          │  or Mock)       │  │ Forest, │  │ Terraform HCL gen │
          │                 │  │ Prophet │  │                    │
          └─────────────────┘  └─────────┘  └───────────────────┘
                        │
                 ┌──────▼──────┐      ┌────────────┐
                 │  Postgres   │      │ Celery      │
                 │  (all data) │      │ worker+beat │──> Redis (message broker)
                 └─────────────┘      └────────────┘
```

Each box is a separate **Docker container**, all started together with one
command (`docker compose up`). Here's what each one is *for*, in plain terms:

| Container | What it is | Why it exists |
|---|---|---|
| `db` | PostgreSQL database | Stores every cost record, anomaly, forecast, and recommendation. |
| `redis` | In-memory message queue | The "mailbox" Celery uses to hand off background jobs. |
| `backend` | Django + gunicorn, serving the REST API | The brain: all business logic (ingestion, ML, right-sizing, API). |
| `celery_worker` | Runs the same Django code, but as a background job processor | So "run the whole pipeline" doesn't block the web request / freeze the UI. |
| `celery_beat` | A scheduler | Automatically re-triggers the pipeline every 6 hours, simulating a live FinOps feed. |
| `frontend` | React app built and served via nginx | What you actually look at in the browser. |

**Why Celery/Redis at all, instead of just running everything directly in
the Django view?** Because ingesting 6 months of data across 3 clouds and
then fitting a machine learning model per service takes real time (a few
seconds here, but in a real system with millions of billing rows it would
be minutes). If that ran directly inside the HTTP request that serves the
"Run Analysis" button, the browser would sit there waiting and eventually
time out. Celery lets the API respond immediately ("started, here's a run
ID") while the actual work happens in the background, and the frontend
polls for completion. This is the standard pattern for any
long-running-job problem, not something specific to this project.

---

## 4. Repository walkthrough

```
hcl-ps03-cloudcost/
├── docker-compose.yml       <- defines and wires together all 6 containers above
├── .env / .env.example      <- all configuration (DB passwords, feature flags, API keys)
├── README.md                <- quick-start instructions
├── docs/PROJECT_GUIDE.md    <- this file
│
├── backend/                 <- the Django project (Python)
│   ├── Dockerfile           <- how to build the backend's container image
│   ├── entrypoint.sh        <- what runs when the container starts (see §8)
│   ├── requirements.txt     <- every Python package used, and why (see §9)
│   ├── config/              <- Django "project" config (settings, URL root, Celery setup)
│   └── costs/                <- the actual application ("app" in Django terms)
│       ├── models.py          <- database tables (see §5)
│       ├── catalog.py         <- static reference data: instance types & their relative cost
│       ├── connectors/        <- one file per cloud provider, all implementing the same interface
│       ├── ml/                <- anomaly detection + forecasting
│       ├── remediation/       <- right-sizing logic + Terraform file generation
│       ├── pipeline.py        <- glues ingestion -> ML -> remediation into one run
│       ├── tasks.py           <- the Celery task wrapper around pipeline.py
│       ├── views.py           <- the REST API endpoints
│       ├── serializers.py     <- how database rows get turned into JSON
│       ├── urls.py            <- API routing table
│       └── management/commands/ <- CLI scripts (seed_accounts, ingest_costs, run_analysis)
│
└── frontend/                 <- the React dashboard (JavaScript)
    ├── src/App.jsx             <- the page layout
    ├── src/api.js              <- all calls to the backend API
    └── src/components/         <- one file per dashboard widget (charts, tables, buttons)
```

---

## 5. The database model (what gets stored, and why)

Everything lives in `backend/costs/models.py`. There are six tables:

1. **`CloudAccount`** — one row per cloud account you're tracking (we seed
   3: one AWS, one Azure, one GCP). Has a `provider` field and an
   `external_id` (the account/subscription/project ID).

2. **`CostRecord`** — the raw billing data. One row per (account, date,
   service, resource). This is the "fact table" everything else is
   computed from. Includes `avg_utilization_pct` — how busy that resource
   actually was — which is the number the right-sizing engine reads.

3. **`Anomaly`** — a day where a service's spend was flagged as unusual.
   Stores the actual amount, what was "expected" (baseline), the
   percentage deviation, a severity (low/medium/high/critical), and the
   raw Isolation Forest score.

4. **`Forecast`** — a predicted future cost for one (account, service,
   date), with a lower/upper confidence band, and which model produced it
   (`prophet` or `naive_seasonal`, explained in §7).

5. **`Recommendation`** — one right-sizing suggestion per resource: current
   vs. recommended instance type, estimated monthly savings, and the
   rendered Terraform script text.

6. **`AnalysisRun`** — a log row for each time the full pipeline was
   triggered: when it started/finished, how many records/anomalies/
   forecasts/recommendations it produced, and whether it succeeded. This
   is what the "Run Analysis" button on the dashboard polls to know when
   it's done.

Why a real relational database (Postgres) instead of just files or an
in-memory structure? Because the API needs to filter, aggregate (sum
spend by provider, group by date), and join across these tables on demand
— exactly what SQL is for — and because the data needs to survive a
container restart.

---

## 6. The pipeline, step by step (the heart of the project)

Everything above exists to support one sequence, defined in
`backend/costs/pipeline.py`, function `run_full_pipeline()`. This is what
happens every time you click "Run Analysis" (or every 6 hours, via Celery
beat):

### Step 1 — Ingestion (`ingest_costs_for_account`)
For each active `CloudAccount`, ask its connector
(`costs/connectors/get_connector(account)`) for the last 180 days of daily
cost records, then bulk-save them into `CostRecord`. In mock mode
(default), this is `MockCostConnector` (see §6a below) generating
synthetic data instead of calling a real billing API.

### Step 2 — Anomaly detection (`costs/ml/anomaly.py`)
For every distinct service within an account (e.g. "Amazon EC2", "Azure
Blob Storage"), build a **daily time series** of total spend, engineer a
few features (7-day rolling mean, rolling std, day-of-week, day-over-day
% change), and fit a **scikit-learn `IsolationForest`** on those features.
Any day it flags as an outlier — and where spend is *above* the rolling
baseline (we only care about overspend, not underspend) — becomes an
`Anomaly` row with a severity based on how far above baseline it was.

### Step 3 — Forecasting (`costs/ml/forecast.py`)
For the same per-service daily series, fit **Facebook/Meta's Prophet**
model (an additive time-series model good at capturing trend + weekly
seasonality) and predict the next 14 days, with a confidence interval.
If Prophet can't be used for any reason, the code **automatically falls
back** to a simpler statistics-only forecaster (linear trend + learned
day-of-week seasonal factors) so the pipeline never just crashes. See §11
for the real bug we found and fixed here.

### Step 4 — Right-sizing (`costs/remediation/rightsizing.py`)
For every compute resource, look at its average utilization over the last
30 days. If it's below a threshold (35% by default):
- If it's *very* idle (< 8%), recommend **terminating** it.
- Otherwise, look up the next smaller/cheaper instance type in the same
  family (`costs/catalog.py`) and recommend **downsizing** to it, with an
  estimated dollar savings.

Each recommendation immediately gets a **Terraform file** rendered and
written to `backend/generated_terraform/` (see §6b).

### Step 5 — Bookkeeping
The whole run is recorded as one `AnalysisRun` row (start time, finish
time, counts, success/failure), which is what the dashboard's "Run
Analysis" button polls to show progress and then refresh the page.

---

## 6a. How the mock data generator actually works

File: `backend/costs/connectors/mock.py`. This deserves its own
explanation because it's not just "random numbers" — it's built to be
**realistic and reproducible**:

- For each account, it creates 3 "compute" resources (EC2 instances / Azure
  VMs / GCE instances) and 4 "non-compute" services (storage, managed
  database, serverless functions, CDN).
- Each resource gets a **stable seed** derived from hashing its own ID, so
  re-running ingestion for the same date range always produces the exact
  same numbers (important for demos and grading — the results are
  reproducible, not different every time).
- Daily cost = a slow upward trend × a weekly pattern (spend dips on
  weekends, which is realistic — fewer batch jobs running) × random noise.
- On ~4% of days (deterministically chosen per resource), the cost is
  multiplied by 2.2×–4.5× to simulate a genuine cost spike — this is the
  "ground truth" anomaly detection is supposed to catch.
- ~40% of compute resources are deliberately given a low baseline
  utilization (so the right-sizing engine has real candidates to flag).

This means you can actually **measure** the anomaly detector's accuracy:
since we know exactly which (resource, day) pairs were artificially
spiked, you can compare that against what `IsolationForest` actually
flagged and compute precision/recall — which is exactly the kind of
metric an IEEE paper needs (see §14).

---

## 6b. How Terraform generation works

File: `backend/costs/remediation/terraform_templates.py`. For each
`Recommendation`, this renders a `.tf` file using plain Python string
templates (no templating engine needed — they're simple enough). Example
output for a downsize recommendation:

```hcl
# Right-sizing remediation
# Account : HCL DBS - AWS Prod (aws)
# Resource: aws-123456789012-compute-2
# Reason  : Average utilisation over the last 30 days was only 21.3%...
# Estimated monthly savings: $89.92 (24%)

resource "aws_instance" "aws_123456789012_compute_2" {
  # NOTE: import the existing instance before applying:
  #   terraform import aws_instance.aws_123456789012_compute_2 <instance-id>
  instance_type = "m5.2xlarge" # was "r5.2xlarge"
  ...
}
```

The comment about `terraform import` matters: this isn't meant to be
blindly `terraform apply`'d — it's a **remediation proposal** a real
engineer would review, import the real resource into Terraform state, then
apply. That's the realistic workflow, and it's why the file is downloadable
from the dashboard rather than auto-applied.

---

## 7. The two ML models, explained simply

### Isolation Forest (anomaly detection)
Think of it like this: it randomly picks a feature (say, "amount spent")
and a random split point, and asks "how many random splits does it take to
isolate this one data point from all the others?" A normal, "boring" data
point takes many splits to isolate because it's surrounded by similar
points. An outlier — a day with a weird cost spike — gets isolated in just
a few splits, because there's nothing else nearby. Do this hundreds of
times with random trees, average the results, and points that are
consistently easy to isolate get flagged as anomalies. It's fast, doesn't
need labeled training data (we never tell it "this day was bad"), and
that's exactly the situation with real billing data — nobody hands you a
labeled dataset of "these were the fraud/waste days."

### Prophet (forecasting)
Prophet decomposes a time series into: **trend** (is spend generally going
up or down) + **seasonality** (does it dip on weekends, spike at
month-end, etc.) + **noise**. It fits all of this using Bayesian curve
fitting under the hood (via Stan, a probabilistic programming language —
this is why installing it requires a C++ compiler, see §11). We chose it
because it handles the "irregular but structured" pattern of billing data
well without needing much tuning, and it's the tool named explicitly in
the problem statement's recommended tech stack.

**The fallback**: if Prophet can't run (missing dependency, too little
data, etc.), `forecast.py` catches the exception and instead fits a much
simpler model by hand: a straight-line trend (linear regression) plus a
per-day-of-week adjustment factor learned from history, with a confidence
band based on how much actual data deviates from that fitted line. This
guarantees the pipeline **never hard-fails** just because a Prophet model
couldn't be fit — a real production consideration, not just a demo safety
net.

---

## 8. What happens when you run `docker compose up`

1. **`db`** starts, and Docker waits until its healthcheck (`pg_isready`)
   passes before anything else proceeds.
2. **`backend`** container starts. Its `entrypoint.sh` script:
   - Waits until it can open a TCP connection to Postgres (belt-and-braces
     on top of the healthcheck).
   - Runs `python manage.py migrate` — creates all the database tables from
     `costs/migrations/0001_initial.py`.
   - Runs `python manage.py seed_accounts` — inserts the 3 demo
     `CloudAccount` rows (idempotent — safe to run every time).
   - Starts `gunicorn` (a production-grade Python web server) serving the
     Django app on port 8000.
3. **`celery_worker`** and **`celery_beat`** start the same image, but with
   a different entrypoint argument (`worker` / `beat` instead of `web`),
   so instead of running gunicorn they run `celery -A config worker` /
   `celery -A config beat`.
4. **`frontend`** is a multi-stage build: stage 1 uses Node to run
   `npm install && npm run build` (compiles the React app into static
   HTML/JS/CSS); stage 2 copies just that compiled output into a small
   nginx image. This means the final frontend container doesn't need
   Node.js installed at all — just nginx serving static files, which is
   smaller and faster.

All 6 containers share one Docker network (`hcl-ps03-cloudcost_default`),
so they can reach each other by service name (`backend` talks to `db` and
`redis` by hostname, not `localhost`).

---

## 9. Why each backend dependency is in `requirements.txt`

| Package | Purpose |
|---|---|
| `Django` | The web framework — models, admin panel, ORM. |
| `djangorestframework` | Turns Django models into a JSON REST API. |
| `django-cors-headers` | Lets the React app (different port) call the API without the browser blocking it. |
| `psycopg2-binary` | The Python driver that lets Django talk to Postgres. |
| `celery` + `redis` | Background job queue (see §3). |
| `pandas` / `numpy` | Data wrangling — turning raw rows into the daily time series ML models need. |
| `scikit-learn` | Provides `IsolationForest`. |
| `prophet` | Forecasting model (see §7). |
| `boto3` | AWS SDK — used by the real (non-mock) AWS connector. |
| `azure-identity` / `azure-mgmt-costmanagement` | Azure SDKs — used by the real Azure connector. |
| `google-cloud-billing` | GCP SDK — used by the real GCP connector. |
| `gunicorn` | Production web server that actually serves Django (Django's own dev server isn't meant for this). |
| `python-dotenv` | Reads the `.env` file. |

---

## 10. The API surface (what the frontend actually calls)

| Endpoint | Method | What it does |
|---|---|---|
| `/api/dashboard/` | GET | One call that returns *everything* the dashboard needs: 30-day totals, per-provider spend, 60-day trend, forecast series, latest anomalies, open recommendations. |
| `/api/analysis-runs/trigger/` | POST | Kicks off the full pipeline (async via Celery, or synchronously if Celery isn't reachable) and returns a run ID. |
| `/api/analysis-runs/{id}/` | GET | Poll this to see if that run is still `running`, or `success`/`failed`. |
| `/api/accounts/` | GET/POST/... | Full CRUD on cloud accounts. |
| `/api/costs/` | GET | Raw cost records, filterable by account/provider/service/date range. |
| `/api/anomalies/` | GET | All detected anomalies, filterable by severity. |
| `/api/forecasts/` | GET | All forecast points. |
| `/api/recommendations/` | GET | All right-sizing recommendations. |
| `/api/recommendations/{id}/terraform/` | GET | Downloads that recommendation's `.tf` file as plain text. |
| `/api/recommendations/{id}/status_update/` | PATCH | Dismiss/apply a recommendation. |

The dashboard's "Run Analysis" button (`frontend/src/components/RunAnalysisButton.jsx`)
calls `trigger`, then polls the run every 1.5 seconds until it's done, then
tells the page to refetch `/api/dashboard/`.

---

## 11. Real bugs found and fixed while building this

This section is worth memorizing for a viva — "what challenges did you
face and how did you debug them" is a near-guaranteed question, and these
are genuine, non-trivial bugs (not made up for the story):

### Bug 1 — Prophet silently never actually ran
Symptom: the pipeline "succeeded", but every single forecast used the
fallback model, and the worker logs were full of
`AttributeError: 'Prophet' object has no attribute 'stan_backend'`.

Root cause: Prophet needs a compiled backend (CmdStan, written in C++) to
actually run its statistical model. The `prophet` Python package ships
with its *own* bundled copy of CmdStan at a fixed path inside the package
— but that bundled copy is incomplete (missing its makefile), so
`cmdstanpy`'s validation step rejects it. Prophet's own error handling
swallows that real error inside a retry loop and only surfaces a confusing
downstream `AttributeError`.

Fix: in `backend/Dockerfile`, we (1) install a real, complete CmdStan via
`cmdstanpy.install_cmdstan()` during the image build, then (2) delete
Prophet's own broken bundled copy, so Prophet falls through to the
correctly installed one. Verified by checking `Forecast.model_used` in the
database — all rows now say `"prophet"`, not `"naive_seasonal"`.

*How I found it*: rather than guessing, I `exec`'d into the running
container and reproduced the failure interactively line-by-line
(`StanBackendEnum.get_backend_class(...)`) until the real underlying
`ValueError` about the missing makefile surfaced.

### Bug 2 — "Distinct" query returning duplicates (Django + Postgres gotcha)
Symptom: after the first pipeline run, the counters were absurd —
"38,010 forecasts generated" for a dataset that should produce about 210.

Root cause: `CostRecord.objects.filter(...).values_list("service",
flat=True).distinct()` was meant to return each service name once. But
`CostRecord`'s model `Meta` sets a default ordering (`ordering =
["-date"]`). PostgreSQL requires that if a query has both `DISTINCT` and
`ORDER BY`, the `ORDER BY` column must be included in what's compared for
distinctness. Django silently adds the model's default ordering to the
query, which meant it was actually running `SELECT DISTINCT service, date
...` — i.e. distinct per **(service, date)** pair, not per service alone.
So the loop iterated over the same service name ~180 times (once per day
in the dataset) instead of once.

Fix: add `.order_by()` (which clears ordering) immediately before
`.distinct()` in the three places this pattern appeared
(`costs/ml/anomaly.py`, `costs/ml/forecast.py`,
`costs/remediation/rightsizing.py`).

*Why this matters to understand*: this is a well-known but easy-to-miss
Django gotcha — **any model with a default `ordering` in its `Meta` can
silently break `.distinct()` or `.values().annotate()` grouping**, unless
you explicitly reset ordering first. Worth mentioning if anyone asks about
testing/data-integrity practices.

### Bug 3 — "Downsize" recommendations with *negative* savings
Symptom: one right-sizing recommendation suggested moving an Azure VM from
`Standard_D2s_v3` to `Standard_E4s_v3` — and `Standard_E4s_v3` is actually
*more* expensive. The dashboard showed a total "potential savings" of
**-$211**.

Root cause: `costs/catalog.py` lists instance types grouped by family
(all the D-series together, then all the E-series, then F-series), each
internally sorted big-to-small. But the right-sizing code
(`next_size_down()`) just picks "the next item in the list" — it assumed
the *whole list* was sorted by cost, not just each sub-family. Since
D-series and E-series costs interleave (a small D-series can cost less
than a small E-series, which costs less than a big D-series), walking to
"the next item" sometimes jumped from a cheap D-series instance to a
pricier E-series one.

Fix: sort each provider's entire instance-type list by relative cost,
descending, once at module load time (`AWS_EC2_FAMILY.sort(key=lambda t:
-t[1])` etc.), so "next item in the list" is always guaranteed to be
cheaper, regardless of which sub-family it belongs to.

*How I found it*: I didn't just eyeball the code — I ran the pipeline,
looked at the actual `/api/recommendations/` JSON output, and noticed the
savings number was negative, which is an impossible/nonsensical value for
a "recommendation to save money." That's the general debugging lesson:
**check what the system actually outputs, not just whether it ran without
crashing.**

### Bug 4 (minor) — Generated Terraform files invisible on the host
The `docker-compose.yml` originally mounted a separate named Docker volume
at `/app/generated_terraform`, on top of an existing bind mount of the
whole `./backend` folder to `/app`. Docker resolves overlapping mounts by
the most specific path winning — so the named volume silently shadowed
the bind mount for that one subfolder, meaning files written there by the
backend were invisible from the host filesystem (they existed, just inside
a Docker-managed volume you can't `ls` directly). Fix: removed the
redundant named volume; the existing `./backend:/app` bind mount already
covers that subfolder correctly.

---

## 12. How this maps to the official PS-03 requirements

| Requirement | Where it's implemented |
|---|---|
| Python + Django backend | `backend/` (entire Django project) |
| AWS Cost Explorer / Azure Cost Management / GCP Billing integration | `costs/connectors/aws.py`, `azure.py`, `gcp.py` (real SDK calls, active when `USE_MOCK_CLOUD_DATA=false`) |
| Isolation Forest for anomaly detection | `costs/ml/anomaly.py` |
| Prophet for forecasting | `costs/ml/forecast.py` |
| Automated Terraform right-sizing scripts | `costs/remediation/rightsizing.py` + `terraform_templates.py` |
| Containerised SaaS web application | Every component runs as its own Docker container, defined in `docker-compose.yml` |
| React dashboard | `frontend/` |
| "Kubernetes" (per the original brief) | Descoped to Docker Compose only, per your explicit instruction — see note below |

**Note on Kubernetes**: the original brief mentions deploying on
Kubernetes. We deliberately scoped this out (you asked to skip K8s
manifests entirely and use only Docker Compose) since you don't have a
cluster to demo against and Compose already proves the "containerised,
multi-service SaaS" architecture. If you need K8s manifests later for
submission completeness, the existing `docker-compose.yml` translates
fairly directly (each service becomes a Deployment + Service); it's a
follow-up task, not a redesign.

---

## 13. How to run and demo it (cheat sheet)

```bash
cd ~/hcl-ps03-cloudcost

# start everything (first run builds images, including a ~2 min CmdStan compile)
docker compose up -d --build

# open the dashboard
open http://localhost:5173

# click "Run Analysis" in the UI, or trigger it from the CLI:
curl -X POST http://localhost:8000/api/analysis-runs/trigger/

# watch it work
docker compose logs -f celery_worker

# check results
curl http://localhost:8000/api/dashboard/ | python3 -m json.tool

# stop everything
docker compose down

# stop AND wipe all data (start completely fresh next time)
docker compose down -v
```

Django admin (useful for showing someone the raw data model):
```bash
docker compose exec backend python manage.py createsuperuser
# then visit http://localhost:8000/admin/
```

---

## 14. If you extend this into the IEEE/Scopus paper track

The mock data generator plants **known** anomalies deterministically (see
§6a), which means you already have ground truth to evaluate against —
this is normally the hardest part of writing an anomaly-detection paper
(getting labeled data). Concretely, you could report:

- **Precision/recall of the anomaly detector**: compare `Anomaly` rows
  against the actual injected-spike days (recoverable from the same seed
  logic in `mock.py`).
- **Forecast accuracy**: once enough real days pass, compare
  `Forecast.predicted_amount` against the actual `CostRecord` total for
  that date (MAPE or RMSE) — and compare Prophet's accuracy against the
  naive-seasonal fallback's, which is a nice built-in ablation study.
- **Cost impact**: sum `Recommendation.estimated_monthly_savings` as your
  headline "X% cost reduction" result.
- **Contamination sensitivity**: `ANOMALY_CONTAMINATION` (in `.env`) is the
  Isolation Forest's expected outlier rate — sweeping this and plotting
  precision/recall trade-offs is a standard, easy-to-generate figure for a
  paper.

---

## 15. Likely questions and how to answer them

**"Is this connected to real AWS/Azure/GCP?"**
Not by default — it uses a synthetic data generator so it can be
demonstrated without cloud credentials. But the real connector code is
fully written against each provider's actual SDK/API and is a one-line
config change (`USE_MOCK_CLOUD_DATA=false`) plus real credentials away
from live data. The architecture doesn't change either way.

**"Why Isolation Forest and not something simpler, like a fixed threshold?"**
A fixed threshold (e.g. "flag if cost > $500") doesn't adapt per service —
some services normally cost $50/day, others $5,000/day. Isolation Forest
learns each service's own normal range from its own history and adapts
automatically, and it doesn't need pre-labeled "this was an anomaly"
training data, which billing systems never have.

**"Why does forecasting sometimes use a different model?"**
Prophet can fail to fit in edge cases (too little history, degenerate
data). Rather than let the whole pipeline crash, there's an automatic
fallback to a simpler model, so the system degrades gracefully instead of
failing outright — a real production concern.

**"What would break first at real scale?"**
The per-service loop in the ML step is currently sequential (one service
at a time); at real enterprise scale (thousands of services) you'd want to
parallelize that across multiple Celery workers, which the architecture
already supports (Celery workers scale horizontally — this only needs a
`docker compose up --scale celery_worker=N`, not a redesign).

**"How do you know the pipeline actually works, not just that it runs
without crashing?"**
That's exactly what bugs 2 and 3 in §11 were about — the pipeline "ran
successfully" both times, with no errors, but produced numbers that were
obviously wrong on inspection (impossible counts, negative savings). Real
verification means checking the actual output values, not just the exit
code.
