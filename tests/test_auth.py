"""Tests for the authentication module."""

from unittest import mock

import pytest
import requests

from src.auth import AuthenticationError, D365Authenticator, build_authenticator


class TestD365Authenticator:
    """Tests for D365Authenticator."""

    def _make_auth(self):
        return D365Authenticator(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            resource_url="https://test.operations.dynamics.com",
        )

    @mock.patch("src.auth.requests.post")
    def test_get_access_token_success(self, mock_post):
        """Should return a token on successful authentication."""
        mock_post.return_value = mock.Mock(
            status_code=200,
            json=mock.Mock(return_value={"access_token": "abc123", "expires_in": 3600}),
        )
        auth = self._make_auth()
        token = auth.get_access_token()
        assert token == "abc123"
        mock_post.assert_called_once()

    @mock.patch("src.auth.requests.post")
    def test_get_access_token_failure(self, mock_post):
        """Should raise AuthenticationError on failure."""
        mock_post.return_value = mock.Mock(status_code=401, text="Unauthorized")
        auth = self._make_auth()
        with pytest.raises(AuthenticationError):
            auth.get_access_token()

    @mock.patch("src.auth.requests.post")
    def test_get_access_token_caches(self, mock_post):
        """Should cache the token and not call the endpoint again."""
        mock_post.return_value = mock.Mock(
            status_code=200,
            json=mock.Mock(return_value={"access_token": "abc123", "expires_in": 3600}),
        )
        auth = self._make_auth()
        auth.get_access_token()
        auth.get_access_token()
        assert mock_post.call_count == 1

    @mock.patch("src.auth.requests.post")
    def test_get_session(self, mock_post):
        """Should return a Session with the Authorization header set."""
        mock_post.return_value = mock.Mock(
            status_code=200,
            json=mock.Mock(return_value={"access_token": "abc123", "expires_in": 3600}),
        )
        auth = self._make_auth()
        session = auth.get_session()
        assert isinstance(session, requests.Session)
        assert session.headers["Authorization"] == "Bearer abc123"

    def test_build_authenticator(self):
        """Factory should create an authenticator from config dict."""
        config = {
            "azure_ad": {
                "tenant_id": "t",
                "client_id": "c",
                "client_secret": "s",
            },
            "d365": {"base_url": "https://env.operations.dynamics.com"},
        }
        auth = build_authenticator(config)
        assert auth.tenant_id == "t"
        assert auth.client_id == "c"
        assert auth.resource_url == "https://env.operations.dynamics.com"
