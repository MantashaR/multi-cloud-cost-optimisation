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

## Tech stack

Python, Django, Django REST Framework, PostgreSQL, Celery, Redis,
scikit-learn, Prophet, Terraform, React, Docker Compose.

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
- Django admin: http://localhost:8000/admin/ (create a superuser first with
  `docker compose exec backend python manage.py createsuperuser`)

To stop the project:
```bash
docker compose down       # stop
docker compose down -v    # stop and wipe all data
```
