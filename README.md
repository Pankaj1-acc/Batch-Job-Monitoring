# Batch Job Monitoring

An automated agent that monitors **Microsoft Dynamics 365 Finance & Operations (D365 F&O)** batch jobs on a daily basis, alerting the team when jobs fail or are cancelled.

---

## Features

| Feature | Details |
|---|---|
| **Daily scheduling** | Runs automatically every day via GitHub Actions (cron `0 6 * * *`, 06:00 UTC). Can also be triggered manually. |
| **OAuth2 authentication** | Uses MSAL with Azure AD client credentials (service principal) — no user interaction required. |
| **OData pagination** | Retrieves all batch jobs across multiple pages so no records are missed. |
| **Alert detection** | Flags jobs in configurable statuses (`Error`, `Canceling`, `Canceled` by default). |
| **Email notification** | Sends an HTML + plain-text email via SMTP/TLS. |
| **Teams notification** | Posts an Adaptive Card to a Microsoft Teams channel via incoming webhook. |
| **Exit codes** | Exits `0` when all jobs are healthy, `1` when alerts are found (useful for CI gating). |

---

## Repository Structure

```
.
├── main.py                        # Entry point (single-run or --schedule mode)
├── requirements.txt               # Python dependencies
├── .env.example                   # Template for environment variables
├── src/
│   ├── config.py                  # Typed configuration (reads from env / .env)
│   ├── d365_client.py             # D365 F&O OData client (auth + batch job queries)
│   ├── monitor.py                 # Monitoring logic, MonitoringReport dataclass
│   └── notifier.py                # Email & Teams notification
├── tests/
│   ├── test_config.py
│   ├── test_d365_client.py
│   ├── test_monitor.py
│   └── test_notifier.py
└── .github/
    └── workflows/
        └── daily_monitor.yml      # GitHub Actions daily schedule
```

---

## Prerequisites

- Python 3.10+
- An **Azure AD App Registration** (service principal) with access to your D365 F&O environment
- The app registration must be added as a D365 application user with appropriate security roles (e.g. *System administrator* or a custom role that can read batch jobs)

---

## Configuration

All settings are read from environment variables. Copy `.env.example` to `.env` and fill in your values for local runs.

### Required

| Variable | Description |
|---|---|
| `AZURE_TENANT_ID` | Azure Active Directory tenant ID |
| `AZURE_CLIENT_ID` | App Registration (service principal) client ID |
| `AZURE_CLIENT_SECRET` | App Registration client secret |
| `D365_URL` | Base URL of your D365 F&O environment, e.g. `https://contoso.operations.dynamics.com` |

### Optional

| Variable | Default | Description |
|---|---|---|
| `D365_RESOURCE` | *(same as D365_URL)* | OAuth2 resource URI (usually matches `D365_URL`) |
| `ALERT_STATUSES` | `Error,Canceling,Canceled` | Comma-separated batch job statuses that trigger alerts |
| `ODATA_PAGE_SIZE` | `1000` | Records per OData page |
| `SMTP_HOST` | *(disabled)* | SMTP server hostname for email alerts |
| `SMTP_PORT` | `587` | SMTP port (STARTTLS) |
| `SMTP_USER` | | SMTP username |
| `SMTP_PASSWORD` | | SMTP password |
| `ALERT_SENDER` | *(SMTP_USER)* | From address for alert emails |
| `ALERT_RECIPIENTS` | | Comma-separated recipient email addresses |
| `TEAMS_WEBHOOK_URL` | *(disabled)* | Microsoft Teams incoming webhook URL |

---

## GitHub Actions Setup

1. Go to **Settings → Secrets and variables → Actions** in your repository.
2. Add the required secrets: `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `D365_URL`.
3. Optionally add notification secrets: `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `ALERT_RECIPIENTS`, `TEAMS_WEBHOOK_URL`.
4. The workflow (`.github/workflows/daily_monitor.yml`) will run automatically every day at 06:00 UTC. You can also trigger it manually from the **Actions** tab.

---

## Local Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Copy and edit the environment file
cp .env.example .env
# (edit .env with your values)

# Run once
python main.py

# Run on a daily schedule (blocking)
python main.py --schedule --time 06:00
```

---

## Running Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

---

## Batch Job Status Reference

| Status | Meaning |
|---|---|
| `Waiting` | Job is queued and waiting to execute |
| `Executing` | Job is currently running |
| `Finished` | Job completed successfully |
| `Error` | Job encountered an error ⚠️ |
| `Canceling` | Cancellation requested ⚠️ |
| `Canceled` | Job was cancelled ⚠️ |
| `Hold` | Job is on hold |

