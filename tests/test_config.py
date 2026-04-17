"""Tests for the Config dataclass."""

import os
import pytest

from src.config import Config


def test_defaults_read_from_env(monkeypatch):
    monkeypatch.setenv("AZURE_TENANT_ID", "tid")
    monkeypatch.setenv("AZURE_CLIENT_ID", "cid")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("D365_URL", "https://contoso.operations.dynamics.com")

    cfg = Config()
    assert cfg.tenant_id == "tid"
    assert cfg.client_id == "cid"
    assert cfg.client_secret == "secret"
    assert cfg.d365_url == "https://contoso.operations.dynamics.com"


def test_default_alert_statuses():
    cfg = Config()
    assert "Error" in cfg.alert_statuses
    assert "Canceled" in cfg.alert_statuses
    assert "Canceling" in cfg.alert_statuses


def test_custom_alert_statuses(monkeypatch):
    monkeypatch.setenv("ALERT_STATUSES", "Error,Hold")
    cfg = Config()
    assert cfg.alert_statuses == ["Error", "Hold"]


def test_validate_raises_on_missing_fields():
    cfg = Config()
    cfg.tenant_id = ""
    cfg.client_id = ""
    cfg.client_secret = ""
    cfg.d365_url = ""
    with pytest.raises(ValueError) as exc_info:
        cfg.validate()
    assert "AZURE_TENANT_ID" in str(exc_info.value)


def test_validate_passes_when_all_fields_set():
    cfg = Config()
    cfg.tenant_id = "t"
    cfg.client_id = "c"
    cfg.client_secret = "s"
    cfg.d365_url = "https://example.com"
    cfg.validate()  # should not raise


def test_alert_recipients_parsed(monkeypatch):
    monkeypatch.setenv("ALERT_RECIPIENTS", "a@x.com, b@x.com")
    cfg = Config()
    assert cfg.alert_recipients == ["a@x.com", "b@x.com"]


def test_empty_alert_recipients(monkeypatch):
    monkeypatch.setenv("ALERT_RECIPIENTS", "")
    cfg = Config()
    assert cfg.alert_recipients == []
