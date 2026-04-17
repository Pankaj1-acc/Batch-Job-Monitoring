"""Batch job monitoring — query D365 F&O OData APIs.

Fetches batch job records and history from the Dynamics 365 Finance &
Operations OData endpoint, and produces a structured daily report.
"""

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


class BatchJobMonitor:
    """Query and report on D365 F&O batch jobs.

    Parameters
    ----------
    session : requests.Session
        Authenticated HTTP session (see :mod:`src.auth`).
    base_url : str
        D365 F&O environment URL.
    batch_job_entity : str
        OData entity set name for batch jobs (default ``BatchJobs``).
    batch_job_history_entity : str
        OData entity set name for batch job history (default ``BatchJobHistory``).
    """

    # D365 batch job status enum mapping
    STATUS_MAP = {
        0: "Hold",
        1: "Waiting",
        2: "Executing",
        3: "Error",
        4: "Finished",
        5: "Ready",
        6: "NotRun",
        7: "Cancelling",
        8: "Cancelled",
    }

    def __init__(
        self,
        session,
        base_url,
        batch_job_entity="BatchJobs",
        batch_job_history_entity="BatchJobHistory",
    ):
        self.session = session
        self.base_url = base_url.rstrip("/")
        self.batch_job_entity = batch_job_entity
        self.batch_job_history_entity = batch_job_history_entity

    # ------------------------------------------------------------------
    # Data retrieval
    # ------------------------------------------------------------------

    def _odata_url(self, entity):
        return f"{self.base_url}/data/{entity}"

    def _get_all_pages(self, url, params=None):
        """Retrieve all pages from an OData endpoint.

        Parameters
        ----------
        url : str
            Full OData URL.
        params : dict, optional
            Query-string parameters (``$filter``, ``$select``, …).

        Returns
        -------
        list[dict]
            Accumulated ``value`` records from all pages.
        """
        results = []
        next_url = url
        query_params = params

        while next_url:
            logger.debug("GET %s  params=%s", next_url, query_params)
            resp = self.session.get(next_url, params=query_params, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            results.extend(data.get("value", []))
            next_url = data.get("@odata.nextLink")
            query_params = None  # nextLink already contains params
        return results

    def fetch_batch_jobs(self, since=None):
        """Fetch current batch job records.

        Parameters
        ----------
        since : datetime, optional
            Only return jobs created/modified after this timestamp.
            Defaults to the last 24 hours.

        Returns
        -------
        list[dict]
            Raw batch job records from D365 F&O.
        """
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(days=1)

        iso = since.strftime("%Y-%m-%dT%H:%M:%SZ")
        url = self._odata_url(self.batch_job_entity)
        params = {
            "$filter": f"CreatedDateTime ge {iso}",
            "$orderby": "CreatedDateTime desc",
        }
        logger.info("Fetching batch jobs since %s", iso)
        return self._get_all_pages(url, params)

    def fetch_batch_job_history(self, since=None):
        """Fetch batch job execution history.

        Parameters
        ----------
        since : datetime, optional
            Only return history entries after this timestamp.
            Defaults to the last 24 hours.

        Returns
        -------
        list[dict]
            Raw batch job history records.
        """
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(days=1)

        iso = since.strftime("%Y-%m-%dT%H:%M:%SZ")
        url = self._odata_url(self.batch_job_history_entity)
        params = {
            "$filter": f"StartDateTime ge {iso}",
            "$orderby": "StartDateTime desc",
        }
        logger.info("Fetching batch job history since %s", iso)
        return self._get_all_pages(url, params)

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    @classmethod
    def _status_label(cls, code):
        """Convert a numeric status code to a human-readable label."""
        try:
            return cls.STATUS_MAP.get(int(code), f"Unknown({code})")
        except (TypeError, ValueError):
            return str(code)

    def generate_daily_report(self, since=None):
        """Build a structured daily monitoring report.

        Parameters
        ----------
        since : datetime, optional
            Report window start.  Defaults to the last 24 hours.

        Returns
        -------
        dict
            Report payload with summary statistics and per-job details.
        """
        jobs = self.fetch_batch_jobs(since)
        history = self.fetch_batch_job_history(since)

        # Build summary counts
        status_counts = {}
        for job in jobs:
            label = self._status_label(job.get("Status"))
            status_counts[label] = status_counts.get(label, 0) + 1

        # Per-job details
        job_details = []
        for job in jobs:
            job_details.append(
                {
                    "JobId": job.get("BatchJobId", job.get("RecId", "")),
                    "Caption": job.get("Caption", "N/A"),
                    "Status": self._status_label(job.get("Status")),
                    "CreatedDateTime": job.get("CreatedDateTime", ""),
                    "StartDateTime": job.get("StartDateTime", ""),
                    "EndDateTime": job.get("EndDateTime", ""),
                    "CreatedBy": job.get("CreatedBy", ""),
                }
            )

        # History details
        history_details = []
        for entry in history:
            history_details.append(
                {
                    "JobId": entry.get("BatchJobId", entry.get("RecId", "")),
                    "Caption": entry.get("Caption", "N/A"),
                    "Status": self._status_label(entry.get("Status")),
                    "StartDateTime": entry.get("StartDateTime", ""),
                    "EndDateTime": entry.get("EndDateTime", ""),
                    "ServerName": entry.get("ServerName", ""),
                }
            )

        report = {
            "report_time": datetime.now(timezone.utc).isoformat(),
            "period_start": (since or datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
            "total_jobs": len(jobs),
            "total_history_entries": len(history),
            "status_summary": status_counts,
            "failed_jobs": [j for j in job_details if j["Status"] == "Error"],
            "jobs": job_details,
            "history": history_details,
        }

        logger.info(
            "Report generated: %d jobs, %d history entries, %d failures",
            report["total_jobs"],
            report["total_history_entries"],
            len(report["failed_jobs"]),
        )
        return report
