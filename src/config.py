"""
Configuration management for D365 F&O Batch Job Monitoring Agent.

Reads settings from environment variables (or a .env file) and exposes
them as a typed Config dataclass so the rest of the codebase never has
to call os.environ directly.
"""

import os
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    # ------------------------------------------------------------------ #
    # Azure AD / OAuth2 settings                                          #
    # ------------------------------------------------------------------ #
    tenant_id: str = field(
        default_factory=lambda: os.environ.get("AZURE_TENANT_ID", "")
    )
    client_id: str = field(
        default_factory=lambda: os.environ.get("AZURE_CLIENT_ID", "")
    )
    client_secret: str = field(
        default_factory=lambda: os.environ.get("AZURE_CLIENT_SECRET", "")
    )

    # ------------------------------------------------------------------ #
    # D365 F&O environment                                                #
    # ------------------------------------------------------------------ #
    d365_url: str = field(
        default_factory=lambda: os.environ.get("D365_URL", "")
    )
    # Scope / resource for token acquisition
    d365_resource: str = field(
        default_factory=lambda: os.environ.get(
            "D365_RESOURCE",
            os.environ.get("D365_URL", ""),
        )
    )

    # ------------------------------------------------------------------ #
    # Monitoring settings                                                  #
    # ------------------------------------------------------------------ #
    # Batch job statuses considered as failures that should trigger alerts
    alert_statuses: List[str] = field(
        default_factory=lambda: [
            s.strip()
            for s in os.environ.get(
                "ALERT_STATUSES", "Error,Canceling,Canceled"
            ).split(",")
        ]
    )
    # Maximum number of results returned per OData page
    odata_page_size: int = field(
        default_factory=lambda: int(os.environ.get("ODATA_PAGE_SIZE", "1000"))
    )

    # ------------------------------------------------------------------ #
    # Notification settings                                                #
    # ------------------------------------------------------------------ #
    # SMTP
    smtp_host: str = field(
        default_factory=lambda: os.environ.get("SMTP_HOST", "")
    )
    smtp_port: int = field(
        default_factory=lambda: int(os.environ.get("SMTP_PORT", "587"))
    )
    smtp_user: str = field(
        default_factory=lambda: os.environ.get("SMTP_USER", "")
    )
    smtp_password: str = field(
        default_factory=lambda: os.environ.get("SMTP_PASSWORD", "")
    )
    alert_sender: str = field(
        default_factory=lambda: os.environ.get("ALERT_SENDER", "")
    )
    alert_recipients: List[str] = field(
        default_factory=lambda: [
            r.strip()
            for r in os.environ.get("ALERT_RECIPIENTS", "").split(",")
            if r.strip()
        ]
    )

    # Microsoft Teams incoming webhook (optional)
    teams_webhook_url: str = field(
        default_factory=lambda: os.environ.get("TEAMS_WEBHOOK_URL", "")
    )

    def validate(self) -> None:
        """Raise ValueError if required fields are missing."""
        required = {
            "AZURE_TENANT_ID": self.tenant_id,
            "AZURE_CLIENT_ID": self.client_id,
            "AZURE_CLIENT_SECRET": self.client_secret,
            "D365_URL": self.d365_url,
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise ValueError(
                f"Missing required configuration: {', '.join(missing)}"
            )
