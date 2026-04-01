# -*- coding: utf-8 -*-
"""CookieCloud cookie synchronization.

Fetches cookies from CookieCloud server, decrypts them, and writes
to each platform's native storage location.

Config priority (highest to lowest):
  1. Environment variables   (COOKIECLOUD_PASSWORD / SERVER / UUID)
  2. ~/.agent-reach/.env  (local .env file)
  3. config.yaml          (agent-reach config)
  4. Hardcoded defaults    (server=..., uuid=macmini)

.env file format:
  COOKIECLOUD_PASSWORD=your_password
  COOKIECLOUD_SERVER=https://router.kyangc.com:1206
  COOKIECLOUD_UUID=macmini
"""

from __future__ import annotations

import json
import os
import stat
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

_CC_DEFAULTS = {
    "server": "https://router.kyangc.com:1206",
    "uuid": "macmini",
}


def _load_dotenv():
    """Load ~/.agent-reach/.env into os.environ if it exists."""
    dotenv_path = Path.home() / ".agent-reach" / ".env"
    if dotenv_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(dotenv_path, override=False)
        except Exception:
            # If python-dotenv is not available, parse manually
            with open(dotenv_path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, _, val = line.partition("=")
                        key = key.strip()
                        val = val.strip().strip('"').strip("'")
                        if key and key not in os.environ:
                            os.environ[key] = val


def _get_cc_config() -> Tuple[str, str, str]:
    """Return (server, uuid, password).

    Priority: env var > .env file > config.yaml > hardcoded default
    """
    _load_dotenv()

    cfg = _load_config()
    cc_cfg = cfg.get("cookiecloud", {}) or {}

    # Server: env > .env > config > default
    server = os.environ.get("COOKIECLOUD_SERVER") or cc_cfg.get("server") or _CC_DEFAULTS["server"]

    # UUID: env > .env > config > default
    uuid = os.environ.get("COOKIECLOUD_UUID") or cc_cfg.get("uuid") or _CC_DEFAULTS["uuid"]

    # Password: env > .env (keyring not supported on macOS)
    pwd = os.environ.get("COOKIECLOUD_PASSWORD")
    if pwd:
        return server, uuid, pwd

    if sys.platform == "darwin":
        raise RuntimeError(
            "COOKIECLOUD_PASSWORD not set.\n"
            "Add it to ~/.agent-reach/.env:\n"
            "  COOKIECLOUD_PASSWORD=your_password\n"
            "Or set the environment variable."
        )

    try:
        import keyring
        pwd = keyring.get_password("agent-reach", "cookiecloud")
        if pwd:
            return server, uuid, pwd
    except Exception:
        pass

    raise RuntimeError(
        "COOKIECLOUD_PASSWORD not set.\n"
        "Add it to ~/.agent-reach/.env:\n"
        "  COOKIECLOUD_PASSWORD=your_password"
    )


def fetch_and_decrypt(server: str, uuid: str, password: str) -> Dict[str, List[Dict]]:
    """Fetch encrypted cookies from CookieCloud and decrypt them.

    Returns cookie_data dict: {domain: [CookieEntry, ...]}
    """
    import httpx
    from cookiecloud_decrypt import decrypt

    resp = httpx.get(f"{server}/get/{uuid}", params={"password": password}, timeout=10)
    resp.raise_for_status()
    encrypted = resp.json()["encrypted"]
    data = decrypt(encrypted, uuid=uuid, password=password)
    return data.get("cookie_data", {})


def sync_cookies(
    platforms: Optional[List[str]] = None,
    force: bool = False,
    server: Optional[str] = None,
    uuid: Optional[str] = None,
    password: Optional[str] = None,
) -> Dict[str, Tuple[str, str]]:
    """Sync cookies from CookieCloud to all configured platforms.

    Config priority (per field): explicit arg > env var > config.yaml > hardcoded default

    Args:
        platforms: List of platforms to sync (None = all enabled in config)
        force:     If True, always sync. If False, check local TTL first.
        server:    Override server URL
        uuid:      Override UUID
        password:  Override password (bypasses env/config lookup)

    Returns:
        Dict mapping platform name to (status, message)
        status: "ok" | "skip" | "error"
    """
    cfg = _load_config()
    cc_cfg = cfg.get("cookiecloud", {}) or {}

    # Load .env so COOKIECLOUD_PASSWORD is available in os.environ
    _load_dotenv()

    # Auto-enable if COOKIECLOUD_PASSWORD is set (no manual configure needed)
    if os.environ.get("COOKIECLOUD_PASSWORD") and not cc_cfg.get("enabled"):
        cc_cfg["enabled"] = True
        cfg.data["cookiecloud"] = cc_cfg
        cfg.save()

    if not cc_cfg.get("enabled"):
        return {"_": ("error", "CookieCloud is not enabled. Run: agent-reach configure cookiecloud")}

    # Explicit args override env vars
    if server is None:
        server = os.environ.get("COOKIECLOUD_SERVER") or cc_cfg.get("server") or _CC_DEFAULTS["server"]
    if uuid is None:
        uuid = os.environ.get("COOKIECLOUD_UUID") or cc_cfg.get("uuid") or _CC_DEFAULTS["uuid"]
    if password is None:
        password = os.environ.get("COOKIECLOUD_PASSWORD")
        if not password:
            if sys.platform == "darwin":
                raise RuntimeError("COOKIECLOUD_PASSWORD environment variable not set.")
            try:
                import keyring
                password = keyring.get_password("agent-reach", "cookiecloud")
            except Exception:
                password = None
            if not password:
                raise RuntimeError(
                    "CookieCloud password not set. "
                    "Set the COOKIECLOUD_PASSWORD environment variable, or run:\n"
                    "  python -c \"import keyring; keyring.set_password('agent-reach', 'cookiecloud', 'YOUR_PASSWORD')\""
                )

    enabled_platforms = set(cc_cfg.get("platforms", []))
    target_platforms = set(platforms) if platforms else enabled_platforms

    try:
        cookie_data = fetch_and_decrypt(server, uuid, password)
    except Exception as e:
        return {"_": ("error", f"Failed to fetch from CookieCloud: {e}")}

    results: Dict[str, Tuple[str, str]] = {}

    if "twitter" in target_platforms:
        results["twitter"] = _sync_twitter(cookie_data, force, cfg)
    if "xhs" in target_platforms:
        results["xhs"] = _sync_xhs(cookie_data, force, cfg)
    if "bilibili" in target_platforms:
        results["bilibili"] = _sync_bilibili(cookie_data, force, cfg)
    if "xueqiu" in target_platforms:
        results["xueqiu"] = _sync_xueqiu(cookie_data, force, cfg)
    if "youtube" in target_platforms:
        results["youtube"] = _sync_youtube(cookie_data, force)

    return results


# ─── Platform sync functions ────────────────────────────────────────────────


def _sync_twitter(cookie_data: Dict, force: bool, cfg) -> Tuple[str, str]:
    """Sync Twitter cookies to ~/.config/bird/credentials.env and config.yaml."""
    cookies = _get_cookies_for_domain(cookie_data, ".x.com") or _get_cookies_for_domain(cookie_data, ".twitter.com")
    if not cookies:
        return "skip", "No cookies found for x.com/twitter.com"

    auth_token = next((c["value"] for c in cookies if c["name"] == "auth_token"), None)
    ct0 = next((c["value"] for c in cookies if c["name"] == "ct0"), None)

    if not auth_token:
        return "skip", "auth_token not found in CookieCloud cookies"
    if not ct0:
        return "skip", "ct0 not found in CookieCloud cookies"

    bird_path = Path.home() / ".config" / "bird" / "credentials.env"
    bird_path.parent.mkdir(parents=True, exist_ok=True)
    bird_path.write_text(f'AUTH_TOKEN="{auth_token}"\nCT0="{ct0}"\n')
    os.chmod(bird_path, stat.S_IRUSR | stat.S_IWUSR)

    cfg.set("twitter_auth_token", auth_token)
    cfg.set("twitter_ct0", ct0)

    return "ok", f"Wrote to {bird_path}"


def _sync_xhs(cookie_data: Dict, force: bool, cfg) -> Tuple[str, str]:
    """Sync XHS cookies to ~/.xiaohongshu-cli/cookies.json."""
    cookies = _get_cookies_for_domain(cookie_data, ".xiaohongshu.com")
    if not cookies:
        return "skip", "No cookies found for .xiaohongshu.com"

    cookies_dict = {c["name"]: c["value"] for c in cookies}
    if "a1" not in cookies_dict:
        return "skip", "a1 cookie not found"

    payload = {**cookies_dict, "saved_at": str(int(time.time()))}

    xhs_path = Path.home() / ".xiaohongshu-cli" / "cookies.json"
    xhs_path.parent.mkdir(parents=True, exist_ok=True)
    xhs_path.write_text(json.dumps(payload, indent=2))
    os.chmod(xhs_path, stat.S_IRUSR | stat.S_IWUSR)

    return "ok", f"Wrote {len(cookies_dict)} cookies to {xhs_path}"


def _sync_bilibili(cookie_data: Dict, force: bool, cfg) -> Tuple[str, str]:
    """Sync Bilibili cookies to config.yaml."""
    cookies = _get_cookies_for_domain(cookie_data, ".bilibili.com")
    if not cookies:
        return "skip", "No cookies found for .bilibili.com"

    cookies_dict = {c["name"]: c["value"] for c in cookies}

    sessdata = cookies_dict.get("SESSDATA")
    if not sessdata:
        return "skip", "SESSDATA not found in CookieCloud cookies"

    cfg.set("bilibili_sessdata", sessdata)
    bili_jct = cookies_dict.get("bili_jct")
    if bili_jct:
        cfg.set("bilibili_csrf", bili_jct)

    return "ok", f"Saved SESSDATA{bili_jct and ' + bili_jct' or ' (bili_jct not found)'}"


def _sync_xueqiu(cookie_data: Dict, force: bool, cfg) -> Tuple[str, str]:
    """Sync Xueqiu cookies to config.yaml."""
    cookies = _get_cookies_for_domain(cookie_data, ".xueqiu.com")
    if not cookies:
        return "skip", "No cookies found for .xueqiu.com"

    cookie_str = "; ".join(f'{c["name"]}={c["value"]}' for c in cookies)

    if "xq_a_token" not in cookie_str:
        return "skip", "xq_a_token not found (user may not be logged in)"

    cfg.set("xueqiu_cookie", cookie_str)

    return "ok", f"Saved {len(cookies)} cookies to xueqiu_cookie"


def _sync_youtube(cookie_data: Dict, force: bool) -> Tuple[str, str]:
    """Write YouTube cookies to Netscape format at ~/.agent-reach/youtube_cookies.txt."""
    cookies = _get_cookies_for_domain(cookie_data, ".youtube.com")
    if not cookies:
        return "skip", "No cookies found for .youtube.com"

    has_host_cookies = any(c["name"].startswith("__Host-") for c in cookies)

    yt_path = Path.home() / ".agent-reach" / "youtube_cookies.txt"
    yt_path.parent.mkdir(parents=True, exist_ok=True)

    lines = ["# Netscape HTTP Cookie File", "# This file was generated by Agent-Reach"]
    for c in cookies:
        domain = c.get("domain", ".youtube.com")
        include_sub = "TRUE" if domain.startswith(".") else "FALSE"
        path = c.get("path", "/")
        secure = "TRUE" if c.get("secure") else "FALSE"
        expiry = str(int(c.get("expirationDate", 0)))
        name = c["name"]
        value = c["value"]
        lines.append(f"{domain}\t{include_sub}\t{path}\t{secure}\t{expiry}\t{name}\t{value}")

    yt_path.write_text("\n".join(lines) + "\n")
    os.chmod(yt_path, stat.S_IRUSR | stat.S_IWUSR)

    msg = f"Wrote {len(cookies)} cookies to {yt_path}"
    if not has_host_cookies:
        msg += "\n  WARNING: No __Host-* cookies found; age-restricted videos may not work."
    return "ok", msg


# ─── Helpers ────────────────────────────────────────────────────────────────


def _get_cookies_for_domain(cookie_data: Dict, domain: str) -> Optional[List[Dict]]:
    """Get cookie list for a domain (with or without leading dot)."""
    return cookie_data.get(domain) or cookie_data.get(domain.lstrip(".")) or None


class _ConfigWrapper:
    """Lightweight config read/write wrapper for cookie sync (avoids circular import)."""
    def __init__(self, data: Dict, path: Path):
        self._data = data
        self._path = path

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value: Any):
        self._data[key] = value
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(str(self._path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                         stat.S_IRUSR | stat.S_IWUSR)
            with os.fdopen(fd, "w") as f:
                yaml.dump(self._data, f, default_flow_style=False, allow_unicode=True)
        except OSError:
            with open(self._path, "w") as f:
                yaml.dump(self._data, f, default_flow_style=False, allow_unicode=True)


def _load_config() -> _ConfigWrapper:
    """Load agent-reach config.yaml."""
    cfg_path = Path.home() / ".agent-reach" / "config.yaml"
    if cfg_path.exists():
        with open(cfg_path) as f:
            return _ConfigWrapper(yaml.safe_load(f) or {}, cfg_path)
    return _ConfigWrapper({}, cfg_path)
