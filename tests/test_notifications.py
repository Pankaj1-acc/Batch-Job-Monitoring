"""Tests for the notification module."""

import json
from unittest import mock

from src.notifications import (
    _build_html_report,
    _build_teams_card,
    dispatch_notifications,
    send_teams_notification,
)


def _sample_report():
    return {
        "report_time": "2024-01-02T07:00:00+00:00",
        "period_start": "2024-01-01T07:00:00+00:00",
        "total_jobs": 5,
        "total_history_entries": 10,
        "status_summary": {"Finished": 3, "Error": 1, "Executing": 1},
        "failed_jobs": [
            {"JobId": "42", "Caption": "Bad Job", "Status": "Error", "StartDateTime": "2024-01-01T08:00:00Z", "EndDateTime": ""},
        ],
        "jobs": [
            {"JobId": "1", "Caption": "Job A", "Status": "Finished", "StartDateTime": "", "EndDateTime": ""},
        ],
        "history": [],
    }


class TestTeamsNotification:
    def test_build_teams_card(self):
        card = _build_teams_card(_sample_report())
        assert card["type"] == "message"
        assert len(card["attachments"]) == 1
        body_text = card["attachments"][0]["content"]["body"][1]["text"]
        assert "Total Jobs" in body_text
        assert "Bad Job" in body_text

    @mock.patch("src.notifications.requests.post")
    def test_send_teams_notification_success(self, mock_post):
        mock_post.return_value = mock.Mock(status_code=200)
        send_teams_notification("https://webhook.example.com", _sample_report())
        mock_post.assert_called_once()


class TestEmailNotification:
    def test_build_html_report_contains_table(self):
        html = _build_html_report(_sample_report())
        assert "<table>" in html
        assert "Finished" in html
        assert "Bad Job" in html


class TestDispatcher:
    @mock.patch("src.notifications.send_teams_notification")
    @mock.patch("src.notifications.send_email_notification")
    def test_dispatch_teams_only(self, mock_email, mock_teams):
        config = {
            "notifications": {
                "teams": {"enabled": True, "webhook_url": "https://hook.example.com"},
                "email": {"enabled": False, "recipients": []},
            }
        }
        dispatch_notifications(config, _sample_report())
        mock_teams.assert_called_once()
        mock_email.assert_not_called()

    @mock.patch("src.notifications.send_teams_notification")
    @mock.patch("src.notifications.send_email_notification")
    def test_dispatch_nothing_when_disabled(self, mock_email, mock_teams):
        config = {
            "notifications": {
                "teams": {"enabled": False},
                "email": {"enabled": False},
            }
        }
        dispatch_notifications(config, _sample_report())
        mock_teams.assert_not_called()
        mock_email.assert_not_called()
