"""Tests for the D365Client."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from src.config import Config
from src.d365_client import D365Client, D365AuthError, D365ApiError


def _make_config() -> Config:
    cfg = Config()
    cfg.tenant_id = "tenant-id"
    cfg.client_id = "client-id"
    cfg.client_secret = "secret"
    cfg.d365_url = "https://contoso.operations.dynamics.com"
    cfg.d365_resource = "https://contoso.operations.dynamics.com"
    cfg.odata_page_size = 100
    return cfg


@patch("src.d365_client.msal.ConfidentialClientApplication")
def test_acquire_token_success(MockMsal):
    mock_app = MagicMock()
    mock_app.acquire_token_for_client.return_value = {
        "access_token": "tok123",
        "expires_in": 3600,
    }
    MockMsal.return_value = mock_app

    client = D365Client(_make_config())
    token = client._acquire_token()
    assert token == "tok123"


@patch("src.d365_client.msal.ConfidentialClientApplication")
def test_acquire_token_failure(MockMsal):
    mock_app = MagicMock()
    mock_app.acquire_token_for_client.return_value = {
        "error": "invalid_client",
        "error_description": "Bad credentials",
    }
    MockMsal.return_value = mock_app

    client = D365Client(_make_config())
    with pytest.raises(D365AuthError, match="Bad credentials"):
        client._acquire_token()


@patch("src.d365_client.msal.ConfidentialClientApplication")
def test_get_batch_jobs_no_filter(MockMsal):
    mock_app = MagicMock()
    mock_app.acquire_token_for_client.return_value = {
        "access_token": "tok",
        "expires_in": 3600,
    }
    MockMsal.return_value = mock_app

    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = {
        "value": [
            {
                "BatchJobId": "1",
                "Caption": "Cleanup",
                "Status": "Finished",
                "StartDateTime": "2024-01-01T00:00:00Z",
                "EndDateTime": "2024-01-01T01:00:00Z",
                "CreatedDateTime": "2024-01-01T00:00:00Z",
                "Company": "USMF",
                "CreatedBy": "admin",
                "Description": "Daily cleanup",
            }
        ]
    }

    client = D365Client(_make_config())
    with patch.object(client._session, "get", return_value=mock_response):
        jobs = client.get_batch_jobs()

    assert len(jobs) == 1
    assert jobs[0]["Caption"] == "Cleanup"


@patch("src.d365_client.msal.ConfidentialClientApplication")
def test_get_batch_jobs_with_status_filter(MockMsal):
    mock_app = MagicMock()
    mock_app.acquire_token_for_client.return_value = {
        "access_token": "tok",
        "expires_in": 3600,
    }
    MockMsal.return_value = mock_app

    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = {"value": []}

    client = D365Client(_make_config())
    with patch.object(client._session, "get", return_value=mock_response) as mock_get:
        client.get_batch_jobs(status_filter=["Error"])

    call_kwargs = mock_get.call_args
    params = call_kwargs[1].get("params") or call_kwargs[0][1]
    assert "$filter" in params
    assert "Error" in params["$filter"]


@patch("src.d365_client.msal.ConfidentialClientApplication")
def test_get_raises_on_http_error(MockMsal):
    mock_app = MagicMock()
    mock_app.acquire_token_for_client.return_value = {
        "access_token": "tok",
        "expires_in": 3600,
    }
    MockMsal.return_value = mock_app

    mock_response = MagicMock()
    mock_response.ok = False
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"

    client = D365Client(_make_config())
    with patch.object(client._session, "get", return_value=mock_response):
        with pytest.raises(D365ApiError, match="401"):
            client.get_batch_jobs()


@patch("src.d365_client.msal.ConfidentialClientApplication")
def test_pagination_follows_next_link(MockMsal):
    mock_app = MagicMock()
    mock_app.acquire_token_for_client.return_value = {
        "access_token": "tok",
        "expires_in": 3600,
    }
    MockMsal.return_value = mock_app

    page1 = MagicMock()
    page1.ok = True
    page1.json.return_value = {
        "value": [{"BatchJobId": "1", "Caption": "Job1", "Status": "Finished",
                   "StartDateTime": "", "EndDateTime": "", "CreatedDateTime": "",
                   "Company": "", "CreatedBy": "", "Description": ""}],
        "@odata.nextLink": "https://contoso.operations.dynamics.com/data/BatchJobs?$skip=1",
    }
    page2 = MagicMock()
    page2.ok = True
    page2.json.return_value = {
        "value": [{"BatchJobId": "2", "Caption": "Job2", "Status": "Error",
                   "StartDateTime": "", "EndDateTime": "", "CreatedDateTime": "",
                   "Company": "", "CreatedBy": "", "Description": ""}],
    }

    client = D365Client(_make_config())
    with patch.object(client._session, "get", side_effect=[page1, page2]):
        jobs = client.get_batch_jobs()

    assert len(jobs) == 2
    assert jobs[1]["Caption"] == "Job2"
