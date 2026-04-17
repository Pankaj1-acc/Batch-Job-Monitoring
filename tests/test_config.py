"""Tests for the configuration loader."""

import os
from unittest import mock

from src.config import load_config


class TestLoadConfig:
    """Tests for load_config()."""

    def test_returns_dict_without_config_file(self, tmp_path):
        """Should return a valid config dict even if no YAML file exists."""
        cfg = load_config(tmp_path / "nonexistent.yaml")
        assert isinstance(cfg, dict)
        assert "azure_ad" in cfg
        assert "d365" in cfg
        assert "schedule" in cfg
        assert "notifications" in cfg

    def test_env_vars_override_defaults(self, tmp_path):
        """Environment variables should override default/file values."""
        env = {
            "AZURE_TENANT_ID": "test-tenant",
            "AZURE_CLIENT_ID": "test-client",
            "AZURE_CLIENT_SECRET": "test-secret",
            "D365_BASE_URL": "https://test.operations.dynamics.com",
            "MONITOR_CRON": "30 8 * * 1-5",
            "TEAMS_ENABLED": "true",
            "TEAMS_WEBHOOK_URL": "https://example.com/webhook",
            "EMAIL_ENABLED": "true",
            "SMTP_HOST": "smtp.example.com",
            "SMTP_PORT": "465",
            "EMAIL_SENDER": "test@example.com",
            "EMAIL_PASSWORD": "pass123",
            "EMAIL_RECIPIENTS": "a@b.com, c@d.com",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            cfg = load_config(tmp_path / "nonexistent.yaml")

        assert cfg["azure_ad"]["tenant_id"] == "test-tenant"
        assert cfg["azure_ad"]["client_id"] == "test-client"
        assert cfg["azure_ad"]["client_secret"] == "test-secret"
        assert cfg["d365"]["base_url"] == "https://test.operations.dynamics.com"
        assert cfg["schedule"]["cron"] == "30 8 * * 1-5"
        assert cfg["notifications"]["teams"]["enabled"] is True
        assert cfg["notifications"]["teams"]["webhook_url"] == "https://example.com/webhook"
        assert cfg["notifications"]["email"]["enabled"] is True
        assert cfg["notifications"]["email"]["smtp_host"] == "smtp.example.com"
        assert cfg["notifications"]["email"]["smtp_port"] == 465
        assert cfg["notifications"]["email"]["sender"] == "test@example.com"
        assert cfg["notifications"]["email"]["recipients"] == ["a@b.com", "c@d.com"]

    def test_loads_yaml_file(self, tmp_path):
        """Should load values from a YAML config file."""
        yaml_content = """\
azure_ad:
  tenant_id: yaml-tenant
  client_id: yaml-client
  client_secret: yaml-secret
d365:
  base_url: https://yaml.operations.dynamics.com
"""
        config_file = tmp_path / "settings.yaml"
        config_file.write_text(yaml_content)

        cfg = load_config(str(config_file))
        assert cfg["azure_ad"]["tenant_id"] == "yaml-tenant"
        assert cfg["d365"]["base_url"] == "https://yaml.operations.dynamics.com"
