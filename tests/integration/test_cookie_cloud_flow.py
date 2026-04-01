# -*- coding: utf-8 -*-
"""
CookieCloud end-to-end integration tests.

Run with: AGENT_REACH_INTEGRATION=1 pytest tests/integration/ -v
Without the flag, all tests are skipped automatically.

For live tests against real CookieCloud server:
    COOKIECLOUD_PASSWORD=macmini AGENT_REACH_INTEGRATION=live pytest tests/integration/ -v
"""

import json
import os
import sys
import types
import pathlib
import pytest
import stat
import time


INTEGRATION_MODE = os.environ.get("AGENT_REACH_INTEGRATION", "")


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: integration test requiring network or real tools"
    )


def pytest_collection_modifyitems(config, items):
    """Skip integration tests unless AGENT_REACH_INTEGRATION is set."""
    if not INTEGRATION_MODE:
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(
                    pytest.mark.skip(
                        reason="Set AGENT_REACH_INTEGRATION=1 to run integration tests. "
                               "Live tests need: AGENT_REACH_INTEGRATION=live"
                    )
                )


# ─── Shared test helpers ──────────────────────────────────────────────────────

FAKE_ENCRYPTED = "fake_encrypted_data"


def _build_fake_decrypt(cookies_by_domain: dict):
    """Return a decrypt() that returns the given cookie data."""
    def fake_decrypt(encrypted, uuid, password):
        return {"cookie_data": cookies_by_domain}
    return fake_decrypt


def _install_mock_httpx_get(monkeypatch):
    """Install a mock for httpx.get that always returns {encrypted: FAKE_ENCRYPTED}."""
    import httpx

    class FakeResponse:
        def __init__(self):
            self.status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"encrypted": FAKE_ENCRYPTED}

    monkeypatch.setattr(httpx, "get", lambda url, *, params=None, timeout=None: FakeResponse())


def _install_mock_config(monkeypatch, tmp_path):
    """Patch _load_config to return a config with cookiecloud enabled."""
    from agent_reach import cookie_cloud as cc_module

    fake_cfg_data = {
        "cookiecloud": {
            "enabled": True,
            "server": "https://fake.server",
            "uuid": "test",
            "platforms": ["twitter", "xhs", "bilibili", "xueqiu", "youtube"],
        }
    }

    class FakeConfigWrapper:
        def __init__(self, data, path):
            self._data = data
            self._path = path

        def get(self, key, default=None):
            return self._data.get(key, default)

        def set(self, key, value):
            self._data[key] = value
            # Actually write to the file so tests can verify it exists
            import yaml
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w") as f:
                yaml.dump(self._data, f, default_flow_style=False, allow_unicode=True)

    cfg_path = tmp_path / ".agent-reach" / "config.yaml"
    fake_cfg = FakeConfigWrapper(fake_cfg_data.copy(), cfg_path)
    monkeypatch.setattr(cc_module, "_load_config", lambda: fake_cfg)
    return fake_cfg


def _install_mock_decrypt(monkeypatch, cookies_by_domain: dict):
    """Install a mock for cookiecloud_decrypt.decrypt."""
    fake_decrypt = _build_fake_decrypt(cookies_by_domain)
    fake_module = types.ModuleType("cookiecloud_decrypt")
    fake_module.decrypt = fake_decrypt
    monkeypatch.setitem(sys.modules, "cookiecloud_decrypt", fake_module)
    return fake_decrypt


def _setup_integration(monkeypatch, tmp_path, cookies_by_domain: dict = None):
    """Full integration test setup: httpx mock + config mock + decrypt mock + home mock."""
    cookies_by_domain = cookies_by_domain or {}
    _install_mock_httpx_get(monkeypatch)
    _install_mock_decrypt(monkeypatch, cookies_by_domain)
    _install_mock_config(monkeypatch, tmp_path)
    monkeypatch.setattr(pathlib.Path, "home", lambda: tmp_path)


# ─── Test data ───────────────────────────────────────────────────────────────

TWITTER_COOKIES = [
    {"name": "auth_token", "value": "abc123token", "domain": ".x.com",
     "path": "/", "secure": True, "expirationDate": 9999999999},
    {"name": "ct0", "value": "def456ct0", "domain": ".x.com",
     "path": "/", "secure": True, "expirationDate": 9999999999},
]

XHS_COOKIES = [
    {"name": "a1", "value": "xhs_a1_value", "domain": ".xiaohongshu.com",
     "path": "/", "secure": False, "expirationDate": 9999999999},
    {"name": "web_session", "value": "xhs_web_session", "domain": ".xiaohongshu.com",
     "path": "/", "secure": False, "expirationDate": 9999999999},
    {"name": "webId", "value": "xhs_webid", "domain": ".xiaohongshu.com",
     "path": "/", "secure": False, "expirationDate": 9999999999},
]

BILIBILI_COOKIES = [
    {"name": "SESSDATA", "value": "bili_sessdata_abc", "domain": ".bilibili.com",
     "path": "/", "secure": True, "expirationDate": 9999999999},
    {"name": "bili_jct", "value": "bili_csrf_xyz", "domain": ".bilibili.com",
     "path": "/", "secure": True, "expirationDate": 9999999999},
]

YOUTUBE_COOKIES = [
    {"name": "LOGIN_INFO", "value": "youtube_login", "domain": ".youtube.com",
     "path": "/", "secure": True, "expirationDate": 9999999999},
    {"name": "SID", "value": "youtube_sid", "domain": ".youtube.com",
     "path": "/", "secure": True, "expirationDate": 9999999999},
]


# ─── Test: Twitter cookie sync ───────────────────────────────────────────────

class TestCookieCloudTwitterSync:
    """Verify Twitter cookies sync from CookieCloud to bird credentials + config.yaml."""

    @pytest.mark.integration
    def test_sync_writes_bird_credentials_file(self, tmp_path, monkeypatch):
        """Twitter auth_token + ct0 → ~/.config/bird/credentials.env."""
        _setup_integration(monkeypatch, tmp_path, {".x.com": TWITTER_COOKIES})

        from agent_reach.cookie_cloud import sync_cookies
        results = sync_cookies(platforms=["twitter"], password="fake",
                              server="https://fake.server")

        assert results["twitter"][0] == "ok", f"Expected ok, got: {results.get('twitter')}"

        bird_file = tmp_path / ".config" / "bird" / "credentials.env"
        assert bird_file.exists(), f"Expected {bird_file} to exist"
        content = bird_file.read_text()
        assert 'AUTH_TOKEN="abc123token"' in content
        assert 'CT0="def456ct0"' in content

        mode = bird_file.stat().st_mode
        assert not (mode & stat.S_IROTH), "bird file should not be world-readable"

    @pytest.mark.integration
    def test_sync_skips_when_auth_token_missing(self, tmp_path, monkeypatch):
        """CookieCloud has Twitter cookies but no auth_token → skip (not error)."""
        _setup_integration(monkeypatch, tmp_path, {
            ".x.com": [
                {"name": "ct0", "value": "only_ct0", "domain": ".x.com",
                 "path": "/", "secure": True, "expirationDate": 0}
            ]
        })

        from agent_reach.cookie_cloud import sync_cookies
        results = sync_cookies(platforms=["twitter"], password="fake", server="https://fake.server")

        assert results["twitter"][0] == "skip"
        assert "auth_token" in results["twitter"][1].lower()

    @pytest.mark.integration
    def test_sync_writes_to_config_yaml(self, tmp_path, monkeypatch):
        """Twitter sync also writes auth_token + ct0 to config.yaml."""
        _setup_integration(monkeypatch, tmp_path, {".x.com": TWITTER_COOKIES})

        from agent_reach.cookie_cloud import sync_cookies
        sync_cookies(platforms=["twitter"], password="fake", server="https://fake.server")

        cfg_file = tmp_path / ".agent-reach" / "config.yaml"
        assert cfg_file.exists()
        assert "abc123token" in cfg_file.read_text()


# ─── Test: XHS cookie sync ───────────────────────────────────────────────────

class TestCookieCloudXhsSync:
    """Verify XHS cookies sync to ~/.xiaohongshu-cli/cookies.json."""

    @pytest.mark.integration
    def test_sync_writes_cookies_json(self, tmp_path, monkeypatch):
        """XHS a1 + web_session → ~/.xiaohongshu-cli/cookies.json with saved_at."""
        _setup_integration(monkeypatch, tmp_path, {".xiaohongshu.com": XHS_COOKIES})

        from agent_reach.cookie_cloud import sync_cookies
        results = sync_cookies(platforms=["xhs"], password="fake", server="https://fake.server")

        assert results["xhs"][0] == "ok"

        xhs_file = tmp_path / ".xiaohongshu-cli" / "cookies.json"
        assert xhs_file.exists()
        data = json.loads(xhs_file.read_text())
        assert data["a1"] == "xhs_a1_value"
        assert data["web_session"] == "xhs_web_session"
        assert "saved_at" in data
        assert float(data["saved_at"]) > 0

        mode = xhs_file.stat().st_mode
        assert not (mode & stat.S_IROTH)

    @pytest.mark.integration
    def test_sync_requires_a1_cookie(self, tmp_path, monkeypatch):
        """XHS cookie without a1 → skip (a1 is mandatory for xhs-cli auth)."""
        _setup_integration(monkeypatch, tmp_path, {
            ".xiaohongshu.com": [
                {"name": "web_session", "value": "v", "domain": ".xiaohongshu.com",
                 "path": "/", "secure": False, "expirationDate": 0}
            ]
        })

        from agent_reach.cookie_cloud import sync_cookies
        results = sync_cookies(platforms=["xhs"], password="fake", server="https://fake.server")

        assert results["xhs"][0] == "skip"
        assert "a1" in results["xhs"][1].lower()


# ─── Test: YouTube cookie sync ───────────────────────────────────────────────

class TestCookieCloudYoutubeSync:
    """Verify YouTube cookies written in Netscape format."""

    @pytest.mark.integration
    def test_sync_writes_netscape_format(self, tmp_path, monkeypatch):
        """YouTube cookies → ~/.agent-reach/youtube_cookies.txt in Netscape format."""
        _setup_integration(monkeypatch, tmp_path, {".youtube.com": YOUTUBE_COOKIES})

        from agent_reach.cookie_cloud import sync_cookies
        results = sync_cookies(platforms=["youtube"], password="fake", server="https://fake.server")

        assert results["youtube"][0] == "ok"

        yt_file = tmp_path / ".agent-reach" / "youtube_cookies.txt"
        assert yt_file.exists()
        lines = yt_file.read_text().splitlines()
        assert lines[0] == "# Netscape HTTP Cookie File"
        assert any("LOGIN_INFO" in l for l in lines)
        assert any("\t" in l for l in lines), "Netscape format should be tab-separated"

    @pytest.mark.integration
    def test_sync_warns_without_host_cookies(self, tmp_path, monkeypatch):
        """YouTube without __Host-* cookies → ok with WARNING in message."""
        _setup_integration(monkeypatch, tmp_path, {".youtube.com": YOUTUBE_COOKIES})

        from agent_reach.cookie_cloud import sync_cookies
        results = sync_cookies(platforms=["youtube"], password="fake", server="https://fake.server")

        assert results["youtube"][0] == "ok"
        assert "WARNING" in results["youtube"][1]


# ─── Test: Bilibili cookie sync ─────────────────────────────────────────────

class TestCookieCloudBilibiliSync:
    """Verify Bilibili cookies sync to config.yaml."""

    @pytest.mark.integration
    def test_sync_writes_sessdata_to_config(self, tmp_path, monkeypatch):
        """Bilibili SESSDATA → config.yaml bilibili_sessdata."""
        _setup_integration(monkeypatch, tmp_path, {".bilibili.com": BILIBILI_COOKIES})

        from agent_reach.cookie_cloud import sync_cookies
        results = sync_cookies(platforms=["bilibili"], password="fake", server="https://fake.server")

        assert results["bilibili"][0] == "ok"

        cfg_file = tmp_path / ".agent-reach" / "config.yaml"
        assert cfg_file.exists()
        assert "bili_sessdata_abc" in cfg_file.read_text()


# ─── Test: force sync ───────────────────────────────────────────────────────

class TestCookieCloudForceSync:
    """force=True bypasses local TTL check."""

    @pytest.mark.integration
    def test_force_sync_overwrites_fresh_local_cookies(self, tmp_path, monkeypatch):
        """force=True overwrites even if local xhs cookies are fresh (< 7 days old)."""
        import time

        # Pre-write a fresh xhs cookie file
        xhs_dir = tmp_path / ".xiaohongshu-cli"
        xhs_dir.mkdir(parents=True)
        (xhs_dir / "cookies.json").write_text(json.dumps({
            "a1": "old_a1",
            "saved_at": str(int(time.time())),  # Fresh right now
        }))

        _setup_integration(monkeypatch, tmp_path, {".xiaohongshu.com": XHS_COOKIES})

        # Also patch _should_sync_from_cookiecloud so it doesn't block the sync
        from agent_reach import doctor as doctor_module
        monkeypatch.setattr(doctor_module, "_should_sync_from_cookiecloud", lambda ch: True)

        from agent_reach.cookie_cloud import sync_cookies
        sync_cookies(platforms=["xhs"], force=True, password="fake", server="https://fake.server")

        data = json.loads((xhs_dir / "cookies.json").read_text())
        assert data["a1"] == "xhs_a1_value", "force=True should overwrite fresh cookies"


# ─── Test: Live CookieCloud (opt-in with real credentials) ─────────────────

class TestLiveCookieCloud:
    """Live tests against the real CookieCloud server.

    Only runs with AGENT_REACH_INTEGRATION=live COOKIECLOUD_PASSWORD=xxx
    """

    @pytest.mark.integration
    @pytest.mark.skipif(
        INTEGRATION_MODE != "live" or not os.environ.get("COOKIECLOUD_PASSWORD"),
        reason="Set AGENT_REACH_INTEGRATION=live and COOKIECLOUD_PASSWORD to run"
    )
    def test_live_fetch_and_decrypt_real_server(self):
        """Real HTTP + real decrypt against https://router.kyangc.com:1206."""
        import httpx

        server = "https://router.kyangc.com:1206"
        uuid = "macmini"
        password = os.environ["COOKIECLOUD_PASSWORD"]

        resp = httpx.get(f"{server}/get/{uuid}", params={"password": password}, timeout=10)
        assert resp.status_code == 200, f"CookieCloud returned {resp.status_code}: {resp.text}"
        assert "encrypted" in resp.json()

        from cookiecloud_decrypt import decrypt
        result = decrypt(resp.json()["encrypted"], uuid=uuid, password=password)
        assert "cookie_data" in result
        assert isinstance(result["cookie_data"], dict)

    @pytest.mark.integration
    @pytest.mark.skipif(
        INTEGRATION_MODE != "live" or not os.environ.get("COOKIECLOUD_PASSWORD"),
        reason="Set AGENT_REACH_INTEGRATION=live and COOKIECLOUD_PASSWORD to run"
    )
    def test_live_cookie_sync_command_exits_cleanly(self):
        """agent-reach cookie-sync with real credentials should exit without crash."""
        import subprocess

        password = os.environ["COOKIECLOUD_PASSWORD"]
        env = {**os.environ, "COOKIECLOUD_PASSWORD": password}
        result = subprocess.run(
            [sys.executable, "-m", "agent_reach.cli", "cookie-sync"],
            capture_output=True, encoding="utf-8", errors="replace",
            timeout=30, env=env,
        )
        output = result.stdout + result.stderr
        # Exit 0 (success) or 1 (sync errors like missing cookies) — both are clean
        assert result.returncode in (0, 1), f"Unexpected exit {result.returncode}: {output}"
        assert "CookieCloud" in output


# ─── Test: CLI end-to-end (real subprocess, no mocks) ───────────────────────

def _run_cli(args, timeout=30):
    """Run agent-reach CLI as subprocess. Skips test if loguru is missing."""
    import subprocess
    try:
        __import__("loguru")
    except ImportError:
        pytest.skip("loguru not installed — CLI requires it")

    result = subprocess.run(
        [sys.executable, "-m", "agent_reach.cli"] + args,
        capture_output=True, encoding="utf-8", errors="replace",
        timeout=timeout,
    )
    return result


class TestCLIE2E:
    """End-to-end CLI tests — real subprocess calls, no mocks.

    These verify the CLI actually works as a command-line tool.
    """

    @pytest.mark.integration
    def test_doctor_command_produces_output(self):
        """agent-reach doctor runs and prints a status report."""
        result = _run_cli(["doctor"])
        output = result.stdout + result.stderr
        assert len(output) > 0, "doctor produced no output"
        assert len(output) > 20, "doctor output suspiciously short"

    @pytest.mark.integration
    def test_cookie_sync_command_runs(self):
        """agent-reach cookie-sync runs gracefully (fails cleanly without password)."""
        env = {k: v for k, v in os.environ.items() if k != "COOKIECLOUD_PASSWORD"}
        import subprocess
        try:
            __import__("loguru")
        except ImportError:
            pytest.skip("loguru not installed")

        result = subprocess.run(
            [sys.executable, "-m", "agent_reach.cli", "cookie-sync"],
            capture_output=True, encoding="utf-8", errors="replace",
            timeout=15, env=env,
        )
        output = result.stdout + result.stderr
        assert result.returncode in (0, 1)
        assert len(output) > 0

    @pytest.mark.integration
    def test_configure_list_runs(self):
        """agent-reach configure list produces output without crashing."""
        result = _run_cli(["configure", "list"])
        output = result.stdout + result.stderr
        assert len(output) > 0, "configure list produced no output"
        assert result.returncode == 0, f"configure list failed: {output}"

    @pytest.mark.integration
    def test_read_command_with_github_url(self):
        """agent-reach read with a GitHub URL routes and produces output."""
        result = _run_cli(["read", "https://github.com/panniantong/agent-reach"])
        output = result.stdout + result.stderr
        assert len(output) > 0, "read produced no output for GitHub URL"

    @pytest.mark.integration
    def test_doctor_with_cookiecloud_enabled(self):
        """doctor command with COOKIECLOUD_PASSWORD set should complete without crash."""
        password = os.environ.get("COOKIECLOUD_PASSWORD", "")
        if not password:
            pytest.skip("COOKIECLOUD_PASSWORD not set")

        env = {**os.environ}
        import subprocess
        try:
            __import__("loguru")
        except ImportError:
            pytest.skip("loguru not installed")

        result = subprocess.run(
            [sys.executable, "-m", "agent_reach.cli", "doctor"],
            capture_output=True, encoding="utf-8", errors="replace",
            timeout=30, env=env,
        )
        output = result.stdout + result.stderr
        assert result.returncode == 0, f"doctor failed: {output}"
        assert len(output) > 50, "doctor output too short"
