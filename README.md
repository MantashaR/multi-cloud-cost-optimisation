# Automated Multi-Cloud Cost Optimisation & Anomaly Detection Platform

A FinOps intelligence platform that unifies cost visibility across **AWS,
Azure, and GCP**. It ingests multi-cloud billing data, detects cost
anomalies, forecasts future spend, and automatically generates Terraform
scripts to right-size or decommission under-utilised resources.

## Features

- **Unified multi-cloud cost ingestion** across AWS, Azure, and GCP through
  a common connector interface (ships with a realistic synthetic data
  generator, so it runs out of the box with no cloud account required)
- **Anomaly detection** using Isolation Forest to flag abnormal cost spikes
  per service, with severity ranking and a monthly spike breakdown by
  service
- **Cost forecasting** using Prophet, with confidence intervals
- **Automated right-sizing recommendations** with ready-to-apply Terraform
  remediation scripts, priority ranking, and projected savings (monthly and
  annual)
- **React dashboard** with plain-language insights, spend trends, and
  drill-down tables
- **Monitoring with Prometheus + Grafana** covering API health (uptime,
  request rate, latency, errors, DB queries), analysis-run status, and the
  FinOps numbers themselves, with alert rules for failures

## Tech stack

Python, Django, Django REST Framework, PostgreSQL, Celery, Redis,
scikit-learn, Prophet, Terraform, React, Docker Compose, Prometheus, Grafana.

## Running the project

**Prerequisites:** Docker Desktop (Mac/Windows) or Docker Engine + Compose
plugin (Linux).

```bash
git clone <this-repo-url>
cd multi-cloud-cost-optimisation
cp .env.example .env
docker compose up -d --build
```

The first build takes a few minutes (it compiles Prophet's forecasting
backend). Once it's up:

```bash
docker compose ps   # all services should show "Up" / "healthy"
```

Open the dashboard at **http://localhost:5173** and click **Run Analysis**
to ingest sample billing data and generate anomalies, forecasts, and
right-sizing recommendations.

Other useful URLs:
- API: http://localhost:8000/api/dashboard/
- Grafana monitoring dashboard: http://localhost:3000 (opens without login;
  sign in as `admin` / `admin` to edit)
- Prometheus: http://localhost:9090 (alerts at http://localhost:9090/alerts)
- Raw metrics: http://localhost:8000/metrics
- Django admin: http://localhost:8000/admin/ (create a superuser first with
  `docker compose exec backend python manage.py createsuperuser`)

## Monitoring

```
Django API  --/metrics-->  Prometheus (scrapes every 15s)  -->  Grafana dashboard
                                   |
                                   +--> alert rules (monitoring/prometheus/alerts.yml)
```

The backend exposes Prometheus metrics at `/metrics`:

- **Platform health** (via `django-prometheus`): request rate per endpoint,
  p50/p95 latency, responses by HTTP status, database queries and errors.
- **FinOps metrics** (`backend/costs/metrics.py`, read from the database on
  each scrape): spend per provider over the last 30 days of billing data,
  anomalies by severity, recommendations by status, potential monthly
  savings, and the status, duration and time of the last analysis run.

Grafana loads the **Cloud Cost Platform - Overview** dashboard automatically
from `monitoring/grafana/dashboards/`. Prometheus evaluates these alerts:

| Alert | Fires when |
|---|---|
| `BackendDown` | The API stops answering scrapes for 1 minute |
| `HighErrorRate` | More than 5% of responses are 5xx for 5 minutes |
| `SlowApi` | p95 latency is above 1 second for 5 minutes |
| `AnalysisFailed` | The latest analysis run failed |
| `AnalysisStale` | No successful analysis in 7 hours (the schedule is every 6) |

To stop the project:
```bash
docker compose down       # stop
docker compose down -v    # stop and wipe all data
```
