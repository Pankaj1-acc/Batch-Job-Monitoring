"""Tests for the BatchJobMonitor."""

from unittest.mock import MagicMock

import pytest

from src.config import Config
from src.d365_client import D365Client
from src.monitor import BatchJobMonitor, BatchJobSummary, MonitoringReport


def _make_config(alert_statuses=None) -> Config:
    cfg = Config()
    cfg.tenant_id = "t"
    cfg.client_id = "c"
    cfg.client_secret = "s"
    cfg.d365_url = "https://example.operations.dynamics.com"
    cfg.alert_statuses = alert_statuses or ["Error", "Canceled", "Canceling"]
    return cfg


def _fake_job(job_id: str, caption: str, status: str) -> dict:
    return {
        "BatchJobId": job_id,
        "Caption": caption,
        "Status": status,
        "Company": "USMF",
        "CreatedBy": "admin",
        "Description": "",
        "StartDateTime": "2024-01-01T00:00:00Z",
        "EndDateTime": "2024-01-01T01:00:00Z",
        "CreatedDateTime": "2024-01-01T00:00:00Z",
    }


def test_monitor_run_no_alerts():
    config = _make_config()
    client = MagicMock(spec=D365Client)
    client.get_batch_jobs.return_value = [
        _fake_job("1", "Job A", "Finished"),
        _fake_job("2", "Job B", "Executing"),
    ]

    monitor = BatchJobMonitor(config, client)
    report = monitor.run()

    assert report.total_jobs == 2
    assert not report.has_alerts
    assert report.alert_jobs == []
    assert "Finished" in report.jobs_by_status
    assert "Executing" in report.jobs_by_status


def test_monitor_run_with_alerts():
    config = _make_config()
    client = MagicMock(spec=D365Client)
    client.get_batch_jobs.return_value = [
        _fake_job("1", "Good Job", "Finished"),
        _fake_job("2", "Bad Job", "Error"),
        _fake_job("3", "Another Error", "Canceled"),
    ]

    monitor = BatchJobMonitor(config, client)
    report = monitor.run()

    assert report.total_jobs == 3
    assert report.has_alerts
    assert len(report.alert_jobs) == 2
    alert_captions = [j.caption for j in report.alert_jobs]
    assert "Bad Job" in alert_captions
    assert "Another Error" in alert_captions


def test_monitor_empty_result():
    config = _make_config()
    client = MagicMock(spec=D365Client)
    client.get_batch_jobs.return_value = []

    monitor = BatchJobMonitor(config, client)
    report = monitor.run()

    assert report.total_jobs == 0
    assert not report.has_alerts
    assert report.jobs_by_status == {}


def test_batch_job_summary_from_odata():
    record = _fake_job("42", "Test Job", "Error")
    summary = BatchJobSummary.from_odata(record)

    assert summary.batch_job_id == "42"
    assert summary.caption == "Test Job"
    assert summary.status == "Error"
    assert summary.company == "USMF"


def test_report_summary_lines_no_alerts():
    report = MonitoringReport(
        d365_url="https://example.com",
        total_jobs=5,
        jobs_by_status={"Finished": [MagicMock()], "Executing": [MagicMock()]},
        alert_jobs=[],
        has_alerts=False,
    )
    lines = "\n".join(report.summary_lines())
    assert "Total jobs" in lines
    assert "Finished" in lines
    assert "ALERT" not in lines


def test_report_summary_lines_with_alerts():
    alert_job = BatchJobSummary(
        batch_job_id="99",
        caption="Failing Job",
        status="Error",
        company="USMF",
        created_by="admin",
        description="",
        start_datetime="",
        end_datetime="",
        created_datetime="",
    )
    report = MonitoringReport(
        d365_url="https://example.com",
        total_jobs=3,
        jobs_by_status={"Error": [alert_job]},
        alert_jobs=[alert_job],
        has_alerts=True,
    )
    lines = "\n".join(report.summary_lines())
    assert "ALERT" in lines
    assert "Failing Job" in lines
