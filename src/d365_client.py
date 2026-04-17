"""
D365 F&O API client.

Handles OAuth2 token acquisition via MSAL and provides typed methods for
querying the D365 OData BatchJobs entity set.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import msal
import requests

from .config import Config

logger = logging.getLogger(__name__)

# D365 F&O OData entity path for batch jobs
_BATCH_JOBS_ENTITY = "data/BatchJobs"

# Seconds before token expiry at which a new token is pre-fetched
_TOKEN_REFRESH_BUFFER_SECONDS = 60

# Supported batch job status values in D365 F&O
BATCH_STATUS_WAITING = "Waiting"
BATCH_STATUS_EXECUTING = "Executing"
BATCH_STATUS_FINISHED = "Finished"
BATCH_STATUS_ERROR = "Error"
BATCH_STATUS_CANCELING = "Canceling"
BATCH_STATUS_CANCELED = "Canceled"
BATCH_STATUS_HOLD = "Hold"

ALL_STATUSES = [
    BATCH_STATUS_WAITING,
    BATCH_STATUS_EXECUTING,
    BATCH_STATUS_FINISHED,
    BATCH_STATUS_ERROR,
    BATCH_STATUS_CANCELING,
    BATCH_STATUS_CANCELED,
    BATCH_STATUS_HOLD,
]


class D365AuthError(Exception):
    """Raised when token acquisition fails."""


class D365ApiError(Exception):
    """Raised when an OData request returns a non-2xx response."""


class D365Client:
    """Thin client for D365 F&O OData endpoints."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Accept": "application/json",
                "OData-MaxVersion": "4.0",
                "OData-Version": "4.0",
            }
        )

    # ------------------------------------------------------------------ #
    # Authentication                                                       #
    # ------------------------------------------------------------------ #

    def _acquire_token(self) -> str:
        """Acquire an OAuth2 access token using MSAL client credentials."""
        authority = (
            f"https://login.microsoftonline.com/{self._config.tenant_id}"
        )
        resource = self._config.d365_resource.rstrip("/")
        scope = [f"{resource}/.default"]

        app = msal.ConfidentialClientApplication(
            self._config.client_id,
            authority=authority,
            client_credential=self._config.client_secret,
        )
        result = app.acquire_token_for_client(scopes=scope)
        if "access_token" not in result:
            error = result.get("error_description", result.get("error", "unknown"))
            raise D365AuthError(f"Failed to acquire token: {error}")

        expires_in = int(result.get("expires_in", 3600))
        self._token_expiry = datetime.now(timezone.utc).timestamp() + expires_in - _TOKEN_REFRESH_BUFFER_SECONDS
        logger.debug("OAuth2 token acquired successfully.")
        return result["access_token"]

    def _get_token(self) -> str:
        """Return a valid access token, refreshing if necessary."""
        now = datetime.now(timezone.utc).timestamp()
        if self._token is None or (
            self._token_expiry is not None and now >= self._token_expiry
        ):
            self._token = self._acquire_token()
        return self._token

    def _auth_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self._get_token()}"}

    # ------------------------------------------------------------------ #
    # OData helpers                                                        #
    # ------------------------------------------------------------------ #

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Execute a GET request against the D365 OData endpoint."""
        base = self._config.d365_url.rstrip("/")
        url = f"{base}/{path}"
        response = self._session.get(
            url, headers=self._auth_headers(), params=params, timeout=30
        )
        if not response.ok:
            raise D365ApiError(
                f"OData request failed [{response.status_code}]: {response.text}"
            )
        return response.json()

    def _get_all_pages(
        self, path: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Follow OData @odata.nextLink pagination and collect all records."""
        params = params or {}
        params.setdefault("$top", self._config.odata_page_size)
        results: List[Dict[str, Any]] = []

        url: Optional[str] = None
        first = True
        while True:
            if first:
                data = self._get(path, params)
                first = False
            else:
                response = self._session.get(
                    url, headers=self._auth_headers(), timeout=30  # type: ignore[arg-type]
                )
                if not response.ok:
                    raise D365ApiError(
                        f"OData pagination request failed [{response.status_code}]: "
                        f"{response.text}"
                    )
                data = response.json()

            results.extend(data.get("value", []))
            url = data.get("@odata.nextLink")
            if not url:
                break

        return results

    # ------------------------------------------------------------------ #
    # Batch job queries                                                    #
    # ------------------------------------------------------------------ #

    def get_batch_jobs(
        self,
        status_filter: Optional[List[str]] = None,
        extra_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return batch jobs, optionally filtered by status.

        Parameters
        ----------
        status_filter:
            List of status strings to include (e.g. ["Error", "Canceled"]).
            When None, all statuses are returned.
        extra_filter:
            Additional raw OData ``$filter`` expression appended with ``and``.
        """
        filter_parts: List[str] = []

        if status_filter:
            status_clauses = " or ".join(
                f"Status eq Microsoft.Dynamics.DataEntities.BatchStatus'{s}'"
                for s in status_filter
            )
            filter_parts.append(f"({status_clauses})")

        if extra_filter:
            filter_parts.append(f"({extra_filter})")

        params: Dict[str, Any] = {
            "$select": (
                "BatchJobId,Caption,Status,StartDateTime,EndDateTime,"
                "CreatedDateTime,Company,CreatedBy,Description"
            ),
            "$orderby": "StartDateTime desc",
        }
        if filter_parts:
            params["$filter"] = " and ".join(filter_parts)

        return self._get_all_pages(_BATCH_JOBS_ENTITY, params)
