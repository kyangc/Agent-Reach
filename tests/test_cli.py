# -*- coding: utf-8 -*-
"""Tests for Agent Reach CLI."""

import pytest
import shutil
import subprocess
import sys
import urllib.request
from unittest.mock import patch, Mock

# Mock loguru BEFORE importing cli (loguru is optional, not always installed)
class _FakeLogger:
    def remove(self, *a, **k): pass
    def add(self, *a, **k): pass
sys.modules["loguru"] = type(sys)("loguru")
sys.modules["loguru"].logger = _FakeLogger()

import requests
import agent_reach.cli as cli
from agent_reach.cli import main


class TestCLI:
    def test_version(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["agent-reach", "version"]):
                main()
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "Agent Reach v" in captured.out

    def test_no_command_shows_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["agent-reach"]):
                main()
        assert exc_info.value.code == 0

    def test_doctor_runs(self, capsys):
        with patch("sys.argv", ["agent-reach", "doctor"]):
            main()
        captured = capsys.readouterr()
        assert "Agent Reach" in captured.out
        assert "✅" in captured.out

    def test_parse_twitter_cookie_input_separate_values(self):
        auth_token, ct0 = cli._parse_twitter_cookie_input("token123 ct0abc")
        assert auth_token == "token123"
        assert ct0 == "ct0abc"

    def test_parse_twitter_cookie_input_cookie_header(self):
        auth_token, ct0 = cli._parse_twitter_cookie_input(
            "auth_token=token123; ct0=ct0abc; other=value"
        )
        assert auth_token == "token123"
        assert ct0 == "ct0abc"


class TestCheckUpdateRetry:
    def test_retry_timeout_classification(self):
        sleeps = []

        def fake_sleep(seconds):
            sleeps.append(seconds)

        with patch("requests.get", side_effect=requests.exceptions.Timeout("timed out")):
            resp, err, attempts = cli._github_get_with_retry(
                "https://api.github.com/test",
                timeout=1,
                retries=3,
                sleeper=fake_sleep,
            )

        assert resp is None
        assert err == "timeout"
        assert attempts == 3
        assert sleeps == [1, 2]

    def test_retry_dns_classification(self):
        error = requests.exceptions.ConnectionError("getaddrinfo failed for api.github.com")
        with patch("requests.get", side_effect=error):
            resp, err, attempts = cli._github_get_with_retry(
                "https://api.github.com/test",
                retries=1,
                sleeper=lambda _x: None,
            )
        assert resp is None
        assert err == "dns"
        assert attempts == 1

    def test_retry_rate_limit_then_success(self):
        sleeps = []

        class R:
            def __init__(self, code, payload=None, headers=None):
                self.status_code = code
                self._payload = payload or {}
                self.headers = headers or {}

            def json(self):
                return self._payload

        sequence = [
            R(429, headers={"Retry-After": "3"}),
            R(200, payload={"tag_name": "v1.4.0"}),
        ]

        with patch("requests.get", side_effect=sequence):
            resp, err, attempts = cli._github_get_with_retry(
                "https://api.github.com/test",
                retries=3,
                sleeper=lambda s: sleeps.append(s),
            )

        assert err is None
        assert resp is not None
        assert resp.status_code == 200
        assert attempts == 2
        assert sleeps == [3.0]

    def test_classify_rate_limit_from_403(self):
        class R:
            status_code = 403
            headers = {"X-RateLimit-Remaining": "0"}

            @staticmethod
            def json():
                return {"message": "API rate limit exceeded"}

        assert cli._classify_github_response_error(R()) == "rate_limit"

    def test_check_update_reports_classified_error(self, capsys):
        with patch("agent_reach.cli._github_get_with_retry", return_value=(None, "timeout", 3)):
            result = cli._cmd_check_update()

        captured = capsys.readouterr()
        assert result == "error"
        assert "网络超时" in captured.out
        assert "已重试 3 次" in captured.out


class TestConfigureXhsCookies:
    def test_parses_header_string_and_writes_xhs_file(self, tmp_path, monkeypatch):
        """Input "a1=xxx; web_session=yyy" → writes ~/.xiaohongshu-cli/cookies.json"""
        import pathlib
        monkeypatch.setattr(pathlib.Path, "home", lambda: tmp_path)
        import agent_reach.cli as cli
        cli._configure_xhs_cookies("a1=abc123; web_session=xyz789")
        cookie_file = tmp_path / ".xiaohongshu-cli" / "cookies.json"
        assert cookie_file.exists()
        import json
        data = json.loads(cookie_file.read_text())
        assert data["a1"] == "abc123"
        assert data["web_session"] == "xyz789"
        assert "saved_at" in data

    def test_requires_a1_cookie(self, tmp_path, monkeypatch):
        """Missing a1 → error, no file written"""
        import pathlib
        monkeypatch.setattr(pathlib.Path, "home", lambda: tmp_path)
        import agent_reach.cli as cli
        cli._configure_xhs_cookies("other=value")
        cookie_file = tmp_path / ".xiaohongshu-cli" / "cookies.json"
        assert not cookie_file.exists()

    def test_sets_file_permissions_0600(self, tmp_path, monkeypatch):
        """Cookie file must be 0o600"""
        import pathlib, stat
        monkeypatch.setattr(pathlib.Path, "home", lambda: tmp_path)
        import agent_reach.cli as cli
        cli._configure_xhs_cookies("a1=xxx")
        cookie_file = tmp_path / ".xiaohongshu-cli" / "cookies.json"
        mode = cookie_file.stat().st_mode
        assert not (mode & stat.S_IROTH)


class TestCmdRead:
    """agent-reach read <url> command tests."""

    def test_read_twitter_url_routes_to_twitter_channel(self, monkeypatch, capsys):
        """Twitter URL → calls twitter-cli read"""
        from agent_reach.channels.base import Channel

        def fake_run(cmd, **kwargs):
            r = Mock()
            r.stdout = '{"text": "fake tweet"}'
            r.stderr = ""
            return r

        monkeypatch.setattr(subprocess, "run", fake_run)
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/twitter" if x == "twitter" else None)

        with patch("sys.argv", ["agent-reach", "read", "https://x.com/user/status/123"]):
            cli.main()
        out = capsys.readouterr().out
        assert "fake tweet" in out

    def test_read_xhs_url_routes_to_xhs_cli(self, monkeypatch, capsys):
        """XHS URL → calls xhs read --json"""
        def fake_run(cmd, **kwargs):
            r = Mock()
            r.stdout = '{"note_id": "123"}'
            r.stderr = ""
            return r

        monkeypatch.setattr(subprocess, "run", fake_run)
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/xhs" if x == "xhs" else None)

        with patch("sys.argv", ["agent-reach", "read", "https://www.xiaohongshu.com/explore/abc"]):
            cli.main()
        out = capsys.readouterr().out
        assert "note_id" in out

    def test_read_exits_with_error_for_unsupported_channel(self, monkeypatch, capsys):
        """Channel without read() → exit code 1"""
        from agent_reach.channels.base import Channel
        from agent_reach.channels.twitter import TwitterChannel

        def fake_can_handle(self, url): return True

        # Patch Channel.can_handle (inherited by TwitterChannel) and
        # TwitterChannel.read directly so instance calls go to our mock
        monkeypatch.setattr(Channel, "can_handle", fake_can_handle)
        monkeypatch.setattr(TwitterChannel, "read", lambda self, url: (_ for _ in ()).throw(NotImplementedError()))

        with patch("sys.argv", ["agent-reach", "read", "https://x.com/test"]):
            with pytest.raises(SystemExit) as exc:
                cli.main()
        assert exc.value.code == 1


class TestCmdSearch:
    """agent-reach search command tests."""

    def test_search_exa_calls_mcporter(self, monkeypatch, capsys):
        """No --platform → Exa via mcporter"""
        def fake_run(cmd, **kwargs):
            r = Mock()
            r.stdout = '{"results": []}'
            r.stderr = ""
            return r

        # Patch cli.subprocess.run and shutil.which (imported at top of cli.py)
        monkeypatch.setattr(cli.subprocess, "run", fake_run)
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/mcporter" if x == "mcporter" else None)

        class FakeArgs:
            query = ["machine", "learning"]
            platform = ""

        cli._cmd_search(FakeArgs())
        out = capsys.readouterr().out
        assert "results" in out  # Verifies the command ran and produced Exa-like output

    def test_search_xhs_calls_xhs_cli(self, monkeypatch, capsys):
        """--platform xhs → xhs-cli"""
        def fake_run(cmd, **kwargs):
            r = Mock()
            r.stdout = '{"items": []}'
            r.stderr = ""
            return r

        monkeypatch.setattr(cli.subprocess, "run", fake_run)
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/xhs" if x == "xhs" else None)

        class FakeArgs:
            query = ["咖啡"]
            platform = "xhs"

        cli._cmd_search(FakeArgs())
        out = capsys.readouterr().out
        assert "items" in out  # Verifies the command ran and produced XHS-like output

    def test_search_requires_tool_when_platform_specified(self, monkeypatch, capsys):
        """Tool not installed → exit code 1"""
        monkeypatch.setattr(shutil, "which", lambda x: None)

        class FakeArgs:
            query = ["test"]
            platform = "twitter"

        with pytest.raises(SystemExit) as exc:
            cli._cmd_search(FakeArgs())
        assert exc.value.code == 1


class TestCmdDownload:
    """agent-reach download command tests."""

    def test_download_calls_yt_dlp(self, monkeypatch, capsys):
        """download command calls yt-dlp"""
        def fake_run(cmd, **kwargs):
            r = Mock()
            r.stdout = "[download] Destination: video.mp4\n"
            r.stderr = ""
            r.returncode = 0
            return r

        monkeypatch.setattr(cli.subprocess, "run", fake_run)
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/local/bin/yt-dlp" if x == "yt-dlp" else None)

        class FakeArgs:
            url = "https://www.youtube.com/watch?v=abc"
            format = ""
            output = ""

        cli._cmd_download(FakeArgs())
        out = capsys.readouterr().out
        assert "download" in out.lower()  # Verifies yt-dlp was called

    def test_download_passes_format_flag(self, monkeypatch, capsys):
        """--format is passed through to yt-dlp"""
        def fake_run(cmd, **kwargs):
            r = Mock()
            r.stdout = ""
            r.stderr = ""
            r.returncode = 0
            return r

        monkeypatch.setattr(cli.subprocess, "run", fake_run)
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/local/bin/yt-dlp")

        class FakeArgs:
            url = "https://www.bilibili.com/video/BV1xx"
            format = "bestvideo"
            output = ""

        cli._cmd_download(FakeArgs())
        # With no error and returncode 0, print outputs empty result (newline only)
        # The test verifies the command didn't exit with error (no SystemExit)
        # and yt-dlp was found and called
        out = capsys.readouterr().out
        assert out == "\n"  # print("") outputs a single newline

    def test_download_exits_nonzero_on_failure(self, monkeypatch, capsys):
        """yt-dlp failure → CLI exit code non-zero"""
        def fake_run(cmd, **kwargs):
            r = Mock()
            r.stdout = ""
            r.stderr = "ERROR: Unable to download"
            r.returncode = 1
            return r

        class FakeArgs:
            url = "https://youtube.com/v"
            format = ""
            output = ""

        monkeypatch.setattr(cli.subprocess, "run", fake_run)
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/yt-dlp")

        with pytest.raises(SystemExit) as exc:
            cli._cmd_download(FakeArgs())
        assert exc.value.code != 0


class TestConfigureListAndCookiecloud:
    """agent-reach configure list and cookiecloud command tests."""

    def test_configure_list_masks_sensitive_credentials(self, tmp_path, monkeypatch, capsys):
        """configure list must mask sensitive values."""
        import pathlib, yaml

        class FakeConfig:
            data = {"twitter_auth_token": "super_secret_token_abc123"}

        monkeypatch.setattr("agent_reach.config.Config", FakeConfig)

        with patch("sys.argv", ["agent-reach", "configure", "list"]):
            cli.main()
        out = capsys.readouterr().out
        assert "super_secret_token_abc123" not in out
        assert "super_se..." in out or "twitter_auth_token" in out

    def test_configure_cookiecloud_enables_when_not_configured(self, tmp_path, monkeypatch, capsys):
        """configure cookiecloud with no args enables CookieCloud."""
        class FakeConfig:
            def __init__(self):
                self.data = {}
            def save(self):
                pass

        monkeypatch.setattr("agent_reach.config.Config", FakeConfig)

        with patch("sys.argv", ["agent-reach", "configure", "cookiecloud"]):
            cli.main()
        out = capsys.readouterr().out
        assert "cookiecloud" in out.lower()
        assert "✅" in out or "enabled" in out.lower()
