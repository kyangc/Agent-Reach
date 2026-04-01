# -*- coding: utf-8 -*-
"""Tests for CookieCloud synchronization module."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, Mock
import os


class _FakeConfig:
    """Test double for Config that avoids file I/O."""
    def __init__(self):
        self.data = {}
    def get(self, k, default=None):
        return self.data.get(k, default)
    def set(self, k, v):
        self.data[k] = v


class TestSyncTwitter:
    """Twitter cookie sync tests."""

    def _fake_twitter_data(self):
        return {
            ".x.com": [
                {"name": "auth_token", "value": "tok1234567890abcdef",
                 "domain": ".x.com", "path": "/", "secure": True, "expirationDate": 9999999999},
                {"name": "ct0", "value": "ct0abcdef123456",
                 "domain": ".x.com", "path": "/", "secure": True, "expirationDate": 9999999999},
            ]
        }

    def test_writes_bird_credentials_env(self, tmp_path, monkeypatch):
        import agent_reach.cookie_cloud as cc
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        cc._sync_twitter(self._fake_twitter_data(), False, _FakeConfig())

        bird_file = tmp_path / ".config" / "bird" / "credentials.env"
        assert bird_file.exists()
        content = bird_file.read_text()
        assert 'AUTH_TOKEN="tok1234567890abcdef"' in content
        assert 'CT0="ct0abcdef123456"' in content

    def test_sets_file_permissions_0600(self, tmp_path, monkeypatch):
        import stat
        import agent_reach.cookie_cloud as cc
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        cc._sync_twitter(self._fake_twitter_data(), False, _FakeConfig())
        bird_file = tmp_path / ".config" / "bird" / "credentials.env"
        assert not (bird_file.stat().st_mode & stat.S_IROTH)

    def test_skips_when_auth_token_missing(self, tmp_path, monkeypatch):
        import agent_reach.cookie_cloud as cc
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        status, _ = cc._sync_twitter({".x.com": [{"name": "ct0", "value": "x"}]}, False, _FakeConfig())
        assert status == "skip"

    def test_also_updates_config(self, tmp_path, monkeypatch):
        import agent_reach.cookie_cloud as cc
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        cfg = _FakeConfig()
        cc._sync_twitter(self._fake_twitter_data(), False, cfg)
        assert cfg.data.get("twitter_auth_token") == "tok1234567890abcdef"


class TestSyncXhs:
    """XHS cookie sync tests."""

    def _fake_xhs_data(self):
        return {
            ".xiaohongshu.com": [
                {"name": "a1", "value": "a1val",
                 "domain": ".xiaohongshu.com", "path": "/", "secure": False, "expirationDate": 9999999999},
                {"name": "web_session", "value": "wsval",
                 "domain": ".xiaohongshu.com", "path": "/", "secure": False, "expirationDate": 9999999999},
            ]
        }

    def test_writes_xhs_cli_cookies_json(self, tmp_path, monkeypatch):
        import agent_reach.cookie_cloud as cc
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        cc._sync_xhs(self._fake_xhs_data(), False, _FakeConfig())
        xhs_file = tmp_path / ".xiaohongshu-cli" / "cookies.json"
        assert xhs_file.exists()
        data = json.loads(xhs_file.read_text())
        assert data["a1"] == "a1val"
        assert data["web_session"] == "wsval"
        assert "saved_at" in data

    def test_requires_a1_cookie(self, tmp_path, monkeypatch):
        import agent_reach.cookie_cloud as cc
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        status, _ = cc._sync_xhs(
            {".xiaohongshu.com": [{"name": "other", "value": "x"}]}, False, _FakeConfig()
        )
        assert status == "skip"


class TestSyncBilibili:
    """Bilibili cookie sync tests."""

    def _fake_bilibili_data(self):
        return {
            ".bilibili.com": [
                {"name": "SESSDATA", "value": "sess_data_val",
                 "domain": ".bilibili.com", "path": "/", "secure": True, "expirationDate": 9999999999},
                {"name": "bili_jct", "value": "bili_jct_val",
                 "domain": ".bilibili.com", "path": "/", "secure": True, "expirationDate": 9999999999},
            ]
        }

    def test_sets_sessdata_and_csrf(self, tmp_path, monkeypatch):
        import agent_reach.cookie_cloud as cc
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        cfg = _FakeConfig()
        cc._sync_bilibili(self._fake_bilibili_data(), False, cfg)
        assert cfg.data["bilibili_sessdata"] == "sess_data_val"
        assert cfg.data["bilibili_csrf"] == "bili_jct_val"


class TestSyncYouTube:
    """YouTube cookie sync tests."""

    def _fake_youtube_data(self, with_host=True):
        cookies = [
            {"name": "LOGIN_INFO", "value": "login_val",
             "domain": ".youtube.com", "path": "/", "secure": True, "expirationDate": 9999999999},
            {"name": "SID", "value": "sid_val",
             "domain": ".youtube.com", "path": "/", "secure": True, "expirationDate": 9999999999},
        ]
        if with_host:
            cookies.append({"name": "__Secure-1PSID", "value": "host_val",
                           "domain": ".youtube.com", "path": "/", "secure": True, "expirationDate": 9999999999})
        return {".youtube.com": cookies}

    def test_writes_netscape_format(self, tmp_path, monkeypatch):
        import agent_reach.cookie_cloud as cc
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        cc._sync_youtube(self._fake_youtube_data(), False)
        yt_file = tmp_path / ".agent-reach" / "youtube_cookies.txt"
        assert yt_file.exists()
        lines = yt_file.read_text().splitlines()
        assert lines[0] == "# Netscape HTTP Cookie File"
        assert any("LOGIN_INFO" in l for l in lines)

    def test_warns_when_no_host_cookies(self, tmp_path, monkeypatch):
        import agent_reach.cookie_cloud as cc
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        status, msg = cc._sync_youtube(self._fake_youtube_data(with_host=False), False)
        assert status == "ok"
        assert "WARNING" in msg or "__Host-" in msg


class TestGetCcConfig:
    """_get_cc_config() tests: server, uuid, password from env / config / defaults."""

    def test_raises_when_password_missing(self, monkeypatch):
        """No COOKIECLOUD_PASSWORD → raises RuntimeError."""
        import agent_reach.cookie_cloud as cc
        monkeypatch.delenv("COOKIECLOUD_PASSWORD", raising=False)
        monkeypatch.delenv("COOKIECLOUD_SERVER", raising=False)
        monkeypatch.delenv("COOKIECLOUD_UUID", raising=False)
        monkeypatch.setattr(cc, "_load_dotenv", lambda: None)
        with pytest.raises(RuntimeError, match="COOKIECLOUD_PASSWORD"):
            cc._get_cc_config()

    def test_uses_env_password(self, monkeypatch):
        """COOKIECLOUD_PASSWORD env var is returned as the password."""
        import agent_reach.cookie_cloud as cc
        monkeypatch.setenv("COOKIECLOUD_PASSWORD", "env_secret")
        monkeypatch.delenv("COOKIECLOUD_SERVER", raising=False)
        monkeypatch.delenv("COOKIECLOUD_UUID", raising=False)
        server, uuid, password = cc._get_cc_config()
        assert password == "env_secret"

    def test_env_server_overrides_default(self, monkeypatch):
        """COOKIECLOUD_SERVER env var overrides the hardcoded default."""
        import agent_reach.cookie_cloud as cc
        monkeypatch.setenv("COOKIECLOUD_PASSWORD", "x")
        monkeypatch.setenv("COOKIECLOUD_SERVER", "https://custom.server:9999")
        monkeypatch.delenv("COOKIECLOUD_UUID", raising=False)
        server, uuid, password = cc._get_cc_config()
        assert server == "https://custom.server:9999"
        assert uuid == "macmini"  # falls back to default
        assert password == "x"

    def test_env_uuid_overrides_default(self, monkeypatch):
        """COOKIECLOUD_UUID env var overrides the hardcoded default."""
        import agent_reach.cookie_cloud as cc
        monkeypatch.setenv("COOKIECLOUD_PASSWORD", "x")
        monkeypatch.delenv("COOKIECLOUD_SERVER", raising=False)
        monkeypatch.setenv("COOKIECLOUD_UUID", "custom-uuid")
        server, uuid, password = cc._get_cc_config()
        assert server == "https://router.kyangc.com:1206"  # default
        assert uuid == "custom-uuid"
        assert password == "x"
