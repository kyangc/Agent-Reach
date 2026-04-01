# -*- coding: utf-8 -*-
"""Tests for doctor module."""

import pytest

import agent_reach.doctor as doctor
from agent_reach.config import Config


class _StubChannel:
    def __init__(self, name, description, tier, status, message, backends=None):
        self.name = name
        self.description = description
        self.tier = tier
        self._status = status
        self._message = message
        self.backends = backends or []

    def check(self, config=None):
        return self._status, self._message


@pytest.fixture
def tmp_config(tmp_path):
    return Config(config_path=tmp_path / "config.yaml")


class TestDoctor:
    def test_check_all_collects_channel_results(self, tmp_config, monkeypatch):
        monkeypatch.setattr(
            doctor,
            "get_all_channels",
            lambda: [
                _StubChannel("web", "网页", 0, "ok", "可抓取网页", ["requests"]),
                _StubChannel("github", "GitHub", 0, "warn", "gh 未安装", ["gh"]),
                _StubChannel("exa_search", "全网语义搜索", 1, "off", "mcporter 未配置", ["Exa"]),
            ],
        )

        results = doctor.check_all(tmp_config)

        assert results == {
            "web": {
                "status": "ok",
                "name": "网页",
                "message": "可抓取网页",
                "tier": 0,
                "backends": ["requests"],
            },
            "github": {
                "status": "warn",
                "name": "GitHub",
                "message": "gh 未安装",
                "tier": 0,
                "backends": ["gh"],
            },
            "exa_search": {
                "status": "off",
                "name": "全网语义搜索",
                "message": "mcporter 未配置",
                "tier": 1,
                "backends": ["Exa"],
            },
        }

    def test_format_report(self):
        report = doctor.format_report(
            {
                "web": {
                    "status": "ok",
                    "name": "网页",
                    "message": "可抓取网页",
                    "tier": 0,
                    "backends": ["requests"],
                },
                "exa_search": {
                    "status": "off",
                    "name": "全网语义搜索",
                    "message": "mcporter 未配置",
                    "tier": 1,
                    "backends": ["Exa"],
                },
                "xiaohongshu": {
                    "status": "warn",
                    "name": "小红书",
                    "message": "MCP 已配置，但健康检查超时",
                    "tier": 2,
                    "backends": ["mcporter"],
                },
            }
        )

        # Strip Rich markup tags for assertion (PR #170 added [bold], [yellow] etc.)
        import re
        plain = re.sub(r"\[[^\]]*\]", "", report)
        assert "Agent Reach" in plain
        assert "装好即用：" in plain
        assert "1/3 个渠道可用" in plain
        # Inactive optional channels should be summarized in one line
        assert "可选渠道可以解锁" in plain


class TestDoctorCookieCloudIntegration:
    """doctor.py CookieCloud auto-sync integration tests."""

    def test_sync_fails_silently_does_not_crash_doctor(self, tmp_config, monkeypatch, capsys):
        """CookieCloud sync failure should not crash doctor.check_all()."""
        import sys as _sys

        def fake_should_sync(ch):
            return True

        def fake_sync(*args, **kwargs):
            raise RuntimeError("network error")

        monkeypatch.setattr(doctor, "_should_sync_from_cookiecloud", fake_should_sync)
        monkeypatch.setattr("agent_reach.cookie_cloud.sync_cookies", fake_sync)
        monkeypatch.setattr(doctor, "get_all_channels", lambda: [
            _StubChannel("twitter", "Twitter", 1, "warn", "no auth", ["twitter-cli"]),
        ])

        # Should not raise
        doctor.check_all(tmp_config)
        err = capsys.readouterr().err
        assert "CookieCloud" in err or "sync failed" in err.lower()

    def test_sync_triggered_when_twitter_cookie_missing(self, tmp_config, monkeypatch):
        """_should_sync_from_cookiecloud returns True when twitter auth_token is missing."""
        # _should_sync_from_cookiecloud creates its own Config() internally.
        # Mock Config so it reads from tmp_config (which has no twitter_auth_token)
        # but has cookiecloud enabled.
        class FakeConfig:
            data = {"cookiecloud": {"enabled": True}}
            def get(self, key, default=None):
                return self.data.get(key, default)

        monkeypatch.setattr(doctor, "Config", lambda: FakeConfig())
        # cfg has no twitter_auth_token set → should trigger sync
        result = doctor._should_sync_from_cookiecloud("twitter")
        assert result is True

    def test_sync_not_triggered_for_non_cookie_channel(self, tmp_config, monkeypatch):
        """_should_sync_from_cookiecloud returns False for channels that don't need cookie."""
        assert doctor._should_sync_from_cookiecloud("github") is False
        assert doctor._should_sync_from_cookiecloud("web") is False
