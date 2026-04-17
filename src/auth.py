"""Azure AD / Entra ID authentication for D365 Finance & Operations.

Obtains an OAuth 2.0 access token using the client-credentials flow and
provides an authenticated ``requests.Session`` for subsequent API calls.
"""

import logging
import time

import requests

logger = logging.getLogger(__name__)

_TOKEN_ENDPOINT = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"


class AuthenticationError(Exception):
    """Raised when an access token cannot be obtained."""


class D365Authenticator:
    """Handles OAuth2 client-credentials authentication against Azure AD.

    Parameters
    ----------
    tenant_id : str
        Azure AD tenant ID (GUID or domain).
    client_id : str
        Application (client) ID registered in Azure AD.
    client_secret : str
        Client secret for the application.
    resource_url : str
        The D365 F&O environment URL used as the token audience
        (e.g. ``https://env.operations.dynamics.com``).
    """

    def __init__(self, tenant_id, client_id, client_secret, resource_url):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.resource_url = resource_url.rstrip("/")
        self._token = None
        self._token_expiry = 0

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_access_token(self):
        """Return a valid access token, refreshing if expired.

        Returns
        -------
        str
            Bearer access token.

        Raises
        ------
        AuthenticationError
            If the token request fails.
        """
        if self._token and time.time() < self._token_expiry:
            return self._token

        url = _TOKEN_ENDPOINT.format(tenant_id=self.tenant_id)
        scope = f"{self.resource_url}/.default"
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": scope,
        }

        logger.debug("Requesting access token from %s", url)
        resp = requests.post(url, data=payload, timeout=30)
        if resp.status_code != 200:
            raise AuthenticationError(
                f"Token request failed ({resp.status_code}): {resp.text}"
            )

        data = resp.json()
        self._token = data["access_token"]
        # Subtract 120 s to refresh before actual expiry
        self._token_expiry = time.time() + data.get("expires_in", 3600) - 120
        logger.info("Access token acquired; expires in ~%s s", data.get("expires_in"))
        return self._token

    def get_session(self):
        """Return a ``requests.Session`` with the Authorization header set.

        Returns
        -------
        requests.Session
        """
        token = self.get_access_token()
        session = requests.Session()
        session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "OData-MaxVersion": "4.0",
                "OData-Version": "4.0",
            }
        )
        return session


def build_authenticator(config):
    """Factory that creates a :class:`D365Authenticator` from a config dict.

    Parameters
    ----------
    config : dict
        Full application configuration (see :mod:`src.config`).

    Returns
    -------
    D365Authenticator
    """
    azure = config["azure_ad"]
    d365 = config["d365"]
    return D365Authenticator(
        tenant_id=azure["tenant_id"],
        client_id=azure["client_id"],
        client_secret=azure["client_secret"],
        resource_url=d365["base_url"],
    )
