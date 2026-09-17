FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Prophet's cmdstanpy backend needs a working CmdStan toolchain. The
# prophet wheel ships its own bundled-but-incomplete CmdStan copy at
# prophet/stan_model/cmdstan-<ver> (missing its makefile), which
# cmdstanpy.validate_cmdstan_path() rejects -- so Prophet() always raised
# `AttributeError: 'Prophet' object has no attribute 'stan_backend'` and
# silently fell back to the naive forecaster on every call. Installing a
# real CmdStan and removing that broken bundled copy lets cmdstanpy fall
# through to the real install (prophet_model.bin, the precompiled model
# binary the wheel ships, still loads fine against it).
RUN python -c "import cmdstanpy; cmdstanpy.install_cmdstan()" \
    && rm -rf /usr/local/lib/python3.11/site-packages/prophet/stan_model/cmdstan-*

COPY . .

RUN mkdir -p /app/generated_terraform && chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["web"]
