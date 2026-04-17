"""
Core monitoring logic.

Fetches all batch jobs from D365 F&O, classifies them by status, and
produces a structured MonitoringReport that can be consumed by the
notifier or logged directly.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

from .config import Config
from .d365_client import D365Client

logger = logging.getLogger(__name__)


@dataclass
class BatchJobSummary:
    """Condensed representation of a single batch job."""

    batch_job_id: str
    caption: str
    status: str
    company: str
    created_by: str
    description: str
    start_datetime: str
    end_datetime: str
    created_datetime: str

    @classmethod
    def from_odata(cls, record: Dict[str, Any]) -> "BatchJobSummary":
        return cls(
            batch_job_id=str(record.get("BatchJobId", "")),
            caption=record.get("Caption", ""),
            status=record.get("Status", ""),
            company=record.get("Company", ""),
            created_by=record.get("CreatedBy", ""),
            description=record.get("Description", ""),
            start_datetime=record.get("StartDateTime", ""),
            end_datetime=record.get("EndDateTime", ""),
            created_datetime=record.get("CreatedDateTime", ""),
        )


@dataclass
class MonitoringReport:
    """Full report produced after one monitoring run."""

    run_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    d365_url: str = ""
    total_jobs: int = 0
    jobs_by_status: Dict[str, List[BatchJobSummary]] = field(default_factory=dict)
    alert_jobs: List[BatchJobSummary] = field(default_factory=list)
    has_alerts: bool = False

    def summary_lines(self) -> List[str]:
        """Human-readable summary lines for logging / plain-text email."""
        lines = [
            f"D365 F&O Batch Job Monitoring Report",
            f"Run time : {self.run_timestamp}",
            f"Environment: {self.d365_url}",
            f"Total jobs : {self.total_jobs}",
            "",
        ]
        for status, jobs in sorted(self.jobs_by_status.items()):
            lines.append(f"  {status}: {len(jobs)}")
        if self.has_alerts:
            lines.append("")
            lines.append(f"⚠  ALERT — {len(self.alert_jobs)} job(s) require attention:")
            for job in self.alert_jobs:
                lines.append(
                    f"  [{job.status}] {job.caption} (ID: {job.batch_job_id}, "
                    f"Company: {job.company})"
                )
        return lines


class BatchJobMonitor:
    """Orchestrates the daily monitoring run."""

    def __init__(self, config: Config, client: D365Client) -> None:
        self._config = config
        self._client = client

    def run(self) -> MonitoringReport:
        """
        Execute one monitoring cycle.

        Returns a MonitoringReport with all job data and alert information.
        """
        logger.info("Starting D365 F&O batch job monitoring run…")

        raw_jobs = self._client.get_batch_jobs()
        logger.info("Retrieved %d batch job(s) from D365.", len(raw_jobs))

        jobs_by_status: Dict[str, List[BatchJobSummary]] = {}
        alert_jobs: List[BatchJobSummary] = []

        for record in raw_jobs:
            summary = BatchJobSummary.from_odata(record)
            jobs_by_status.setdefault(summary.status, []).append(summary)
            if summary.status in self._config.alert_statuses:
                alert_jobs.append(summary)

        report = MonitoringReport(
            d365_url=self._config.d365_url,
            total_jobs=len(raw_jobs),
            jobs_by_status=jobs_by_status,
            alert_jobs=alert_jobs,
            has_alerts=bool(alert_jobs),
        )

        for line in report.summary_lines():
            logger.info(line)

        return report
