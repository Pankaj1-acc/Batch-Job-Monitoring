"""Notification dispatchers — Teams webhook and SMTP email.

Sends daily batch-job monitoring reports to configured channels.
"""

import json
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

logger = logging.getLogger(__name__)


# ======================================================================
# Microsoft Teams
# ======================================================================

def _build_teams_card(report):
    """Build an Adaptive Card payload for a Teams incoming webhook.

    Parameters
    ----------
    report : dict
        Report produced by :meth:`BatchJobMonitor.generate_daily_report`.

    Returns
    -------
    dict
        Adaptive Card message payload.
    """
    failed = report.get("failed_jobs", [])
    status_lines = "\n".join(
        f"- **{status}**: {count}"
        for status, count in report.get("status_summary", {}).items()
    )

    failed_lines = ""
    if failed:
        failed_lines = "\n\n**⚠️ Failed Jobs:**\n" + "\n".join(
            f"- **{j['Caption']}** (ID: {j['JobId']}) — started {j['StartDateTime']}"
            for j in failed
        )

    body_text = (
        f"**Report Time:** {report['report_time']}\n"
        f"**Period Start:** {report['period_start']}\n"
        f"**Total Jobs:** {report['total_jobs']}\n"
        f"**Total History Entries:** {report['total_history_entries']}\n\n"
        f"**Status Summary:**\n{status_lines}"
        f"{failed_lines}"
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
                    "body": [
                        {
                            "type": "TextBlock",
                            "size": "Large",
                            "weight": "Bolder",
                            "text": "📊 D365 F&O — Daily Batch Job Report",
                        },
                        {
                            "type": "TextBlock",
                            "text": body_text,
                            "wrap": True,
                        },
                    ],
                },
            }
        ],
    }


def send_teams_notification(webhook_url, report):
    """Post the daily report to a Microsoft Teams channel via webhook.

    Parameters
    ----------
    webhook_url : str
        Teams incoming-webhook URL.
    report : dict
        Report produced by :meth:`BatchJobMonitor.generate_daily_report`.
    """
    payload = _build_teams_card(report)
    logger.info("Sending Teams notification")
    resp = requests.post(
        webhook_url,
        data=json.dumps(payload),
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    if resp.status_code in (200, 202):
        logger.info("Teams notification sent successfully")
    else:
        logger.error("Teams notification failed (%s): %s", resp.status_code, resp.text)


# ======================================================================
# Email (SMTP)
# ======================================================================

def _build_html_report(report):
    """Render the report as an HTML email body.

    Parameters
    ----------
    report : dict
        Report produced by :meth:`BatchJobMonitor.generate_daily_report`.

    Returns
    -------
    str
        HTML string.
    """
    status_rows = "".join(
        f"<tr><td>{status}</td><td>{count}</td></tr>"
        for status, count in report.get("status_summary", {}).items()
    )

    failed_rows = ""
    for j in report.get("failed_jobs", []):
        failed_rows += (
            f"<tr><td>{j['JobId']}</td><td>{j['Caption']}</td>"
            f"<td>{j['StartDateTime']}</td><td>{j['EndDateTime']}</td></tr>"
        )

    job_rows = ""
    for j in report.get("jobs", []):
        job_rows += (
            f"<tr><td>{j['JobId']}</td><td>{j['Caption']}</td>"
            f"<td>{j['Status']}</td><td>{j['StartDateTime']}</td>"
            f"<td>{j['EndDateTime']}</td></tr>"
        )

    html = f"""\
<html>
<head>
<style>
  body {{ font-family: Segoe UI, Arial, sans-serif; margin: 20px; }}
  h2 {{ color: #0078D4; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
  th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
  th {{ background-color: #0078D4; color: white; }}
  tr:nth-child(even) {{ background-color: #f9f9f9; }}
  .error {{ background-color: #ffe0e0; }}
</style>
</head>
<body>
  <h2>📊 D365 F&amp;O — Daily Batch Job Report</h2>
  <p><strong>Report Time:</strong> {report['report_time']}</p>
  <p><strong>Period Start:</strong> {report['period_start']}</p>
  <p><strong>Total Jobs:</strong> {report['total_jobs']} &nbsp;|&nbsp;
     <strong>History Entries:</strong> {report['total_history_entries']}</p>

  <h3>Status Summary</h3>
  <table>
    <tr><th>Status</th><th>Count</th></tr>
    {status_rows}
  </table>

  {"<h3>⚠️ Failed Jobs</h3><table><tr><th>Job ID</th><th>Caption</th><th>Start</th><th>End</th></tr>" + failed_rows + "</table>" if failed_rows else ""}

  <h3>All Jobs</h3>
  <table>
    <tr><th>Job ID</th><th>Caption</th><th>Status</th><th>Start</th><th>End</th></tr>
    {job_rows}
  </table>
</body>
</html>"""
    return html


def send_email_notification(smtp_cfg, report):
    """Send the daily report via SMTP email.

    Parameters
    ----------
    smtp_cfg : dict
        Email configuration block (host, port, sender, password, recipients).
    report : dict
        Report produced by :meth:`BatchJobMonitor.generate_daily_report`.
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"D365 F&O Batch Job Report — {report['report_time'][:10]}"
    msg["From"] = smtp_cfg["sender"]
    msg["To"] = ", ".join(smtp_cfg["recipients"])

    html = _build_html_report(report)
    msg.attach(MIMEText(html, "html"))

    logger.info("Sending email to %s via %s:%s", msg["To"], smtp_cfg["smtp_host"], smtp_cfg["smtp_port"])
    try:
        with smtplib.SMTP(smtp_cfg["smtp_host"], smtp_cfg["smtp_port"]) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_cfg["sender"], smtp_cfg["password"])
            server.sendmail(smtp_cfg["sender"], smtp_cfg["recipients"], msg.as_string())
        logger.info("Email sent successfully")
    except Exception:
        logger.exception("Failed to send email notification")


# ======================================================================
# Dispatcher
# ======================================================================

def dispatch_notifications(config, report):
    """Send the report through all enabled notification channels.

    Parameters
    ----------
    config : dict
        Full application configuration.
    report : dict
        Report produced by :meth:`BatchJobMonitor.generate_daily_report`.
    """
    notif = config.get("notifications", {})

    teams = notif.get("teams", {})
    if teams.get("enabled") and teams.get("webhook_url"):
        send_teams_notification(teams["webhook_url"], report)

    email = notif.get("email", {})
    if email.get("enabled") and email.get("recipients"):
        send_email_notification(email, report)
