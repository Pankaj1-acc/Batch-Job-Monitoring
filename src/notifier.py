"""
Notification module.

Supports two channels:
  1. Email (SMTP / TLS)
  2. Microsoft Teams incoming webhook

Both channels are optional; at least one must be configured to send alerts.
"""

import json
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import requests

from .config import Config
from .monitor import MonitoringReport

logger = logging.getLogger(__name__)

_EMAIL_SUBJECT_OK = "✅ D365 F&O Batch Job Monitor — All jobs healthy"
_EMAIL_SUBJECT_ALERT = "⚠️ D365 F&O Batch Job Monitor — Action required"

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body  {{ font-family: Arial, sans-serif; font-size: 14px; color: #333; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ccc; padding: 6px 10px; text-align: left; }}
    th    {{ background: #4472C4; color: #fff; }}
    tr:nth-child(even) {{ background: #f2f2f2; }}
    .status-Error, .status-Canceling, .status-Canceled {{ color: #c00; font-weight: bold; }}
    .status-Finished  {{ color: #080; }}
    .status-Executing {{ color: #00c; }}
    .banner-ok    {{ background:#d4edda; border:1px solid #c3e6cb; padding:10px; border-radius:4px; }}
    .banner-alert {{ background:#f8d7da; border:1px solid #f5c6cb; padding:10px; border-radius:4px; }}
  </style>
</head>
<body>
<h2>D365 F&amp;O Batch Job Monitoring Report</h2>
<p><b>Run time:</b> {run_timestamp}<br>
   <b>Environment:</b> {d365_url}<br>
   <b>Total batch jobs:</b> {total_jobs}</p>

{banner}

<h3>Jobs by Status</h3>
<table>
  <tr><th>Status</th><th>Count</th></tr>
  {status_rows}
</table>

{alert_table}
</body>
</html>
"""

_STATUS_ROW = '<tr><td class="status-{status}">{status}</td><td>{count}</td></tr>'

_ALERT_TABLE_HEADER = """\
<h3>&#9888; Jobs Requiring Attention</h3>
<table>
  <tr>
    <th>ID</th><th>Caption</th><th>Status</th>
    <th>Company</th><th>Created By</th><th>Start</th><th>End</th>
  </tr>
  {rows}
</table>
"""

_ALERT_ROW = (
    '<tr>'
    '<td>{batch_job_id}</td>'
    '<td>{caption}</td>'
    '<td class="status-{status}">{status}</td>'
    '<td>{company}</td>'
    '<td>{created_by}</td>'
    '<td>{start_datetime}</td>'
    '<td>{end_datetime}</td>'
    '</tr>'
)


def _build_html(report: MonitoringReport) -> str:
    status_rows = "\n  ".join(
        _STATUS_ROW.format(status=s, count=len(jobs))
        for s, jobs in sorted(report.jobs_by_status.items())
    )
    if report.has_alerts:
        banner = (
            '<div class="banner-alert">&#9888; <b>'
            f"{len(report.alert_jobs)} job(s) require immediate attention.</b></div>"
        )
        alert_rows = "\n  ".join(
            _ALERT_ROW.format(
                batch_job_id=j.batch_job_id,
                caption=j.caption,
                status=j.status,
                company=j.company,
                created_by=j.created_by,
                start_datetime=j.start_datetime or "—",
                end_datetime=j.end_datetime or "—",
            )
            for j in report.alert_jobs
        )
        alert_table = _ALERT_TABLE_HEADER.format(rows=alert_rows)
    else:
        banner = '<div class="banner-ok">&#10003; All batch jobs are healthy.</div>'
        alert_table = ""

    return _HTML_TEMPLATE.format(
        run_timestamp=report.run_timestamp,
        d365_url=report.d365_url,
        total_jobs=report.total_jobs,
        banner=banner,
        status_rows=status_rows,
        alert_table=alert_table,
    )


def _build_teams_payload(report: MonitoringReport) -> dict:
    """Build a Microsoft Teams Adaptive Card payload."""
    color = "attention" if report.has_alerts else "good"
    title = (
        "⚠️ D365 F&O Batch Job Alert" if report.has_alerts
        else "✅ D365 F&O Batch Jobs Healthy"
    )
    facts = [
        {"title": "Environment", "value": report.d365_url},
        {"title": "Run time", "value": report.run_timestamp},
        {"title": "Total jobs", "value": str(report.total_jobs)},
    ]
    for status, jobs in sorted(report.jobs_by_status.items()):
        facts.append({"title": status, "value": str(len(jobs))})

    body = [
        {
            "type": "TextBlock",
            "size": "Large",
            "weight": "Bolder",
            "color": color,
            "text": title,
        },
        {
            "type": "FactSet",
            "facts": facts,
        },
    ]

    if report.has_alerts:
        alert_lines = [
            f"• [{j.status}] **{j.caption}** (ID: {j.batch_job_id}, "
            f"Company: {j.company})"
            for j in report.alert_jobs
        ]
        body.append(
            {
                "type": "TextBlock",
                "text": "\n".join(alert_lines),
                "wrap": True,
                "color": "attention",
            }
        )

    return {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": body,
                },
            }
        ],
    }


class Notifier:
    """Sends monitoring reports via email and/or Teams webhook."""

    def __init__(self, config: Config) -> None:
        self._config = config

    def notify(self, report: MonitoringReport) -> None:
        """Dispatch notifications for the given report."""
        sent_any = False
        if self._config.alert_recipients and self._config.smtp_host:
            self._send_email(report)
            sent_any = True
        if self._config.teams_webhook_url:
            self._send_teams(report)
            sent_any = True
        if not sent_any:
            logger.warning(
                "No notification channel configured. "
                "Set SMTP_* / ALERT_RECIPIENTS or TEAMS_WEBHOOK_URL."
            )

    def _send_email(self, report: MonitoringReport) -> None:
        subject = (
            _EMAIL_SUBJECT_ALERT if report.has_alerts else _EMAIL_SUBJECT_OK
        )
        html_body = _build_html(report)
        plain_body = "\n".join(report.summary_lines())

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self._config.alert_sender or self._config.smtp_user
        msg["To"] = ", ".join(self._config.alert_recipients)
        msg.attach(MIMEText(plain_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        try:
            with smtplib.SMTP(self._config.smtp_host, self._config.smtp_port) as smtp:
                smtp.ehlo()
                smtp.starttls()
                if self._config.smtp_user:
                    smtp.login(self._config.smtp_user, self._config.smtp_password)
                smtp.sendmail(
                    msg["From"],
                    self._config.alert_recipients,
                    msg.as_string(),
                )
            logger.info(
                "Email notification sent to %s.", self._config.alert_recipients
            )
        except smtplib.SMTPException as exc:
            logger.error("Failed to send email notification: %s", exc)
            raise

    def _send_teams(self, report: MonitoringReport) -> None:
        payload = _build_teams_payload(report)
        try:
            response = requests.post(
                self._config.teams_webhook_url,
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=15,
            )
            response.raise_for_status()
            logger.info("Teams notification sent successfully.")
        except requests.RequestException as exc:
            logger.error("Failed to send Teams notification: %s", exc)
            raise
