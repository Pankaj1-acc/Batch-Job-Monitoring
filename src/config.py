"""Configuration loader for the Batch Job Monitoring Agent.

Loads settings from a YAML config file and/or environment variables.
Environment variables take precedence over the config file values.
"""

import os
import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "settings.yaml"


def load_config(config_path=None):
    """Load configuration from YAML file and overlay environment variables.

    Parameters
    ----------
    config_path : str or Path, optional
        Path to the YAML configuration file.  Falls back to
        ``config/settings.yaml`` relative to the project root, then to
        environment variables only.

    Returns
    -------
    dict
        Merged configuration dictionary.
    """
    config = {}

    path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
    if path.exists():
        logger.info("Loading config from %s", path)
        with open(path, "r", encoding="utf-8") as fh:
            config = yaml.safe_load(fh) or {}
    else:
        logger.info("No config file found at %s – using environment variables", path)

    # --- Azure AD / Entra ID ------------------------------------------------
    azure_ad = config.setdefault("azure_ad", {})
    azure_ad["tenant_id"] = os.getenv("AZURE_TENANT_ID", azure_ad.get("tenant_id", ""))
    azure_ad["client_id"] = os.getenv("AZURE_CLIENT_ID", azure_ad.get("client_id", ""))
    azure_ad["client_secret"] = os.getenv(
        "AZURE_CLIENT_SECRET", azure_ad.get("client_secret", "")
    )

    # --- D365 F&O -----------------------------------------------------------
    d365 = config.setdefault("d365", {})
    d365["base_url"] = os.getenv("D365_BASE_URL", d365.get("base_url", ""))
    d365.setdefault("batch_job_entity", "BatchJobs")
    d365.setdefault("batch_job_history_entity", "BatchJobHistory")

    # --- Schedule ------------------------------------------------------------
    schedule = config.setdefault("schedule", {})
    schedule.setdefault("cron", os.getenv("MONITOR_CRON", "0 7 * * *"))
    schedule.setdefault("timezone", os.getenv("MONITOR_TZ", "UTC"))

    # --- Notifications -------------------------------------------------------
    notifications = config.setdefault("notifications", {})

    teams = notifications.setdefault("teams", {})
    teams["enabled"] = os.getenv("TEAMS_ENABLED", str(teams.get("enabled", False))).lower() in (
        "true",
        "1",
        "yes",
    )
    teams["webhook_url"] = os.getenv("TEAMS_WEBHOOK_URL", teams.get("webhook_url", ""))

    email = notifications.setdefault("email", {})
    email["enabled"] = os.getenv("EMAIL_ENABLED", str(email.get("enabled", False))).lower() in (
        "true",
        "1",
        "yes",
    )
    email["smtp_host"] = os.getenv("SMTP_HOST", email.get("smtp_host", "smtp.office365.com"))
    email["smtp_port"] = int(os.getenv("SMTP_PORT", str(email.get("smtp_port", 587))))
    email["sender"] = os.getenv("EMAIL_SENDER", email.get("sender", ""))
    email["password"] = os.getenv("EMAIL_PASSWORD", email.get("password", ""))
    recipients_env = os.getenv("EMAIL_RECIPIENTS", "")
    if recipients_env:
        email["recipients"] = [r.strip() for r in recipients_env.split(",") if r.strip()]
    else:
        email.setdefault("recipients", [])

    # --- Logging -------------------------------------------------------------
    log_cfg = config.setdefault("logging", {})
    log_cfg.setdefault("level", os.getenv("LOG_LEVEL", "INFO"))
    log_cfg.setdefault("file", os.getenv("LOG_FILE", "logs/batch_monitor.log"))

    return config
