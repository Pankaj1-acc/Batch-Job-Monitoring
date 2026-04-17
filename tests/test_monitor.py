"""Tests for the batch job monitor module."""

import json
from datetime import datetime, timezone
from unittest import mock

from src.monitor import BatchJobMonitor


def _mock_session(pages):
    """Return a mock requests.Session that yields the given pages in order."""
    session = mock.Mock()
    responses = []
    for page in pages:
        resp = mock.Mock()
        resp.json.return_value = page
        resp.raise_for_status.return_value = None
        responses.append(resp)
    session.get = mock.Mock(side_effect=responses)
    return session


class TestBatchJobMonitor:
    """Tests for BatchJobMonitor."""

    def test_status_label_known(self):
        assert BatchJobMonitor._status_label(3) == "Error"
        assert BatchJobMonitor._status_label(4) == "Finished"

    def test_status_label_unknown(self):
        assert BatchJobMonitor._status_label(99) == "Unknown(99)"

    def test_fetch_batch_jobs_single_page(self):
        page = {"value": [{"BatchJobId": "1", "Status": 4}]}
        session = _mock_session([page])

        monitor = BatchJobMonitor(session, "https://env.operations.dynamics.com")
        jobs = monitor.fetch_batch_jobs(since=datetime(2024, 1, 1, tzinfo=timezone.utc))
        assert len(jobs) == 1
        assert jobs[0]["BatchJobId"] == "1"

    def test_fetch_batch_jobs_pagination(self):
        page1 = {
            "value": [{"BatchJobId": "1"}],
            "@odata.nextLink": "https://env.operations.dynamics.com/data/BatchJobs?$skip=1",
        }
        page2 = {"value": [{"BatchJobId": "2"}]}
        session = _mock_session([page1, page2])

        monitor = BatchJobMonitor(session, "https://env.operations.dynamics.com")
        jobs = monitor.fetch_batch_jobs(since=datetime(2024, 1, 1, tzinfo=timezone.utc))
        assert len(jobs) == 2

    def test_generate_daily_report_structure(self):
        jobs_page = {
            "value": [
                {"BatchJobId": "1", "Caption": "Job A", "Status": 4, "CreatedDateTime": "2024-01-01T00:00:00Z"},
                {"BatchJobId": "2", "Caption": "Job B", "Status": 3, "CreatedDateTime": "2024-01-01T01:00:00Z"},
            ]
        }
        history_page = {
            "value": [
                {"BatchJobId": "1", "Caption": "Job A", "Status": 4, "StartDateTime": "2024-01-01T00:00:00Z"},
            ]
        }
        session = _mock_session([jobs_page, history_page])
        monitor = BatchJobMonitor(session, "https://env.operations.dynamics.com")
        report = monitor.generate_daily_report(since=datetime(2024, 1, 1, tzinfo=timezone.utc))

        assert report["total_jobs"] == 2
        assert report["total_history_entries"] == 1
        assert len(report["failed_jobs"]) == 1
        assert report["failed_jobs"][0]["Caption"] == "Job B"
        assert "Finished" in report["status_summary"]
        assert "Error" in report["status_summary"]
