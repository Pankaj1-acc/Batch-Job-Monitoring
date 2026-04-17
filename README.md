# D365 F&O Batch Job Monitoring Agent

A Python-based monitoring agent that connects to **Dynamics 365 Finance & Operations** via the OData API, queries batch job status and start times on a daily basis, and delivers reports through Microsoft Teams and/or email.

---

## Features

| Capability | Details |
|---|---|
| **Authentication** | Azure AD / Entra ID OAuth 2.0 client-credentials flow |
| **Batch Job Queries** | Fetches `BatchJobs` and `BatchJobHistory` OData entities |
| **Daily Reports** | Summarises job counts by status, highlights failures |
| **Teams Notifications** | Adaptive Card sent to a channel via incoming webhook |
| **Email Notifications** | HTML-formatted email via SMTP (Office 365 / custom) |
| **Scheduling** | Built-in cron scheduler (APScheduler); also supports one-shot mode |
| **Containerised** | Ships with a production-ready Dockerfile |

---

## Project Structure

```
├── config/
│   └── settings.example.yaml   # Sample configuration (copy → settings.yaml)
├── src/
│   ├── __init__.py
│   ├── auth.py                 # Azure AD authentication
│   ├── config.py               # Configuration loader (YAML + env vars)
│   ├── monitor.py              # OData queries & report generation
│   ├── notifications.py        # Teams webhook & SMTP email dispatchers
│   └── scheduler.py            # APScheduler cron & CLI entry point
├── tests/                      # Unit tests (pytest)
├── Dockerfile
├── requirements.txt
└── README.md
```

---

## Quick Start

### 1. Clone & install dependencies

```bash
git clone https://github.com/Pankaj1-acc/Batch-Job-Monitoring.git
cd Batch-Job-Monitoring
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

Copy the example config and fill in your values:

```bash
cp config/settings.example.yaml config/settings.yaml
```

**Or** use environment variables (they override the YAML file):

| Variable | Description |
|---|---|
| `AZURE_TENANT_ID` | Azure AD tenant ID |
| `AZURE_CLIENT_ID` | App registration client ID |
| `AZURE_CLIENT_SECRET` | App registration client secret |
| `D365_BASE_URL` | D365 F&O environment URL (e.g. `https://env.operations.dynamics.com`) |
| `MONITOR_CRON` | Cron expression (default `0 7 * * *` — daily at 07:00 UTC) |
| `MONITOR_TZ` | Timezone for the cron schedule (default `UTC`) |
| `TEAMS_ENABLED` | `true` to enable Teams notifications |
| `TEAMS_WEBHOOK_URL` | Teams incoming-webhook URL |
| `EMAIL_ENABLED` | `true` to enable email notifications |
| `SMTP_HOST` | SMTP server hostname |
| `SMTP_PORT` | SMTP server port |
| `EMAIL_SENDER` | Sender email address |
| `EMAIL_PASSWORD` | Sender email password |
| `EMAIL_RECIPIENTS` | Comma-separated list of recipient addresses |
| `LOG_LEVEL` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

### 3. Run

**Scheduled mode** (runs on the configured cron schedule):

```bash
python -m src.scheduler
```

**One-shot mode** (run once and exit):

```bash
python -m src.scheduler --run-once
```

### 4. Docker

```bash
docker build -t batch-monitor .
docker run -d \
  -e AZURE_TENANT_ID=... \
  -e AZURE_CLIENT_ID=... \
  -e AZURE_CLIENT_SECRET=... \
  -e D365_BASE_URL=https://env.operations.dynamics.com \
  -e TEAMS_ENABLED=true \
  -e TEAMS_WEBHOOK_URL=https://... \
  batch-monitor
```

---

## Azure AD App Registration

1. In the Azure Portal, register a new application.
2. Add an **Application permission** for the Dynamics 365 API (or use the environment URL as the scope).
3. Create a **client secret** and note the Tenant ID, Client ID, and Secret.
4. Grant admin consent for the permissions.

---

## Running Tests

```bash
pip install pytest
pytest tests/ -v
```

---

## License

MIT
