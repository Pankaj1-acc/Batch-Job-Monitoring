"""Tests for the Notifier module."""

import json
from unittest.mock import MagicMock, patch, call
import smtplib

import pytest

from src.config import Config
from src.monitor import BatchJobSummary, MonitoringReport
from src.notifier import Notifier, _build_html, _build_teams_payload


def _make_config(**kwargs) -> Config:
    cfg = Config()
    cfg.tenant_id = "t"
    cfg.client_id = "c"
    cfg.client_secret = "s"
    cfg.d365_url = "https://example.operations.dynamics.com"
    cfg.smtp_host = kwargs.get("smtp_host", "")
    cfg.smtp_port = kwargs.get("smtp_port", 587)
    cfg.smtp_user = kwargs.get("smtp_user", "")
    cfg.smtp_password = kwargs.get("smtp_password", "")
    cfg.alert_sender = kwargs.get("alert_sender", "monitor@example.com")
    cfg.alert_recipients = kwargs.get("alert_recipients", [])
    cfg.teams_webhook_url = kwargs.get("teams_webhook_url", "")
    return cfg


def _make_report(has_alerts=False) -> MonitoringReport:
    alert_job = BatchJobSummary(
        batch_job_id="1",
        caption="Failing Job",
        status="Error",
        company="USMF",
        created_by="admin",
        description="",
        start_datetime="2024-01-01T00:00:00Z",
        end_datetime="",
        created_datetime="",
    )
    if has_alerts:
        return MonitoringReport(
            d365_url="https://example.com",
            total_jobs=3,
            jobs_by_status={"Error": [alert_job], "Finished": []},
            alert_jobs=[alert_job],
            has_alerts=True,
        )
    return MonitoringReport(
        d365_url="https://example.com",
        total_jobs=5,
        jobs_by_status={"Finished": [], "Executing": []},
        alert_jobs=[],
        has_alerts=False,
    )


# ------------------------------------------------------------------ #
# HTML builder tests                                                   #
# ------------------------------------------------------------------ #

def test_build_html_no_alerts():
    report = _make_report(has_alerts=False)
    html = _build_html(report)
    assert "banner-ok" in html
    assert "All batch jobs are healthy" in html
    assert 'class="banner-alert"' not in html


def test_build_html_with_alerts():
    report = _make_report(has_alerts=True)
    html = _build_html(report)
    assert "banner-alert" in html
    assert "Failing Job" in html
    assert "status-Error" in html


# ------------------------------------------------------------------ #
# Teams payload tests                                                  #
# ------------------------------------------------------------------ #

def test_teams_payload_no_alerts():
    report = _make_report(has_alerts=False)
    payload = _build_teams_payload(report)
    body_text = json.dumps(payload)
    assert "good" in body_text
    assert "attention" not in body_text or "Failing" not in body_text


def test_teams_payload_with_alerts():
    report = _make_report(has_alerts=True)
    payload = _build_teams_payload(report)
    body_text = json.dumps(payload)
    assert "attention" in body_text
    assert "Failing Job" in body_text


# ------------------------------------------------------------------ #
# Notifier dispatch tests                                              #
# ------------------------------------------------------------------ #

def test_notify_sends_email_when_configured():
    config = _make_config(
        smtp_host="smtp.example.com",
        smtp_user="user",
        smtp_password="pass",
        alert_recipients=["admin@example.com"],
    )
    notifier = Notifier(config)
    report = _make_report(has_alerts=True)

    with patch.object(notifier, "_send_email") as mock_email, \
         patch.object(notifier, "_send_teams") as mock_teams:
        notifier.notify(report)

    mock_email.assert_called_once_with(report)
    mock_teams.assert_not_called()


def test_notify_sends_teams_when_configured():
    config = _make_config(teams_webhook_url="https://outlook.office.com/webhook/xyz")
    notifier = Notifier(config)
    report = _make_report(has_alerts=False)

    with patch.object(notifier, "_send_email") as mock_email, \
         patch.object(notifier, "_send_teams") as mock_teams:
        notifier.notify(report)

    mock_teams.assert_called_once_with(report)
    mock_email.assert_not_called()


def test_notify_sends_both_channels():
    config = _make_config(
        smtp_host="smtp.example.com",
        alert_recipients=["a@example.com"],
        teams_webhook_url="https://outlook.office.com/webhook/xyz",
    )
    notifier = Notifier(config)
    report = _make_report()

    with patch.object(notifier, "_send_email") as mock_email, \
         patch.object(notifier, "_send_teams") as mock_teams:
        notifier.notify(report)

    mock_email.assert_called_once()
    mock_teams.assert_called_once()


def test_notify_warns_when_no_channel_configured(caplog):
    config = _make_config()
    notifier = Notifier(config)
    report = _make_report()

    import logging
    with caplog.at_level(logging.WARNING, logger="src.notifier"):
        notifier.notify(report)

    assert any("No notification channel" in r.message for r in caplog.records)


def test_send_teams_posts_to_webhook():
    config = _make_config(teams_webhook_url="https://outlook.office.com/webhook/xyz")
    notifier = Notifier(config)
    report = _make_report(has_alerts=True)

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None

    with patch("src.notifier.requests.post", return_value=mock_response) as mock_post:
        notifier._send_teams(report)

    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args[0][0] == "https://outlook.office.com/webhook/xyz"
