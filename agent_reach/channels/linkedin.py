# -*- coding: utf-8 -*-
"""LinkedIn — read via Playwright (CookieCloud) or Jina Reader."""

import shutil
import subprocess
import urllib.request
from .base import Channel, _domain_matches

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
_TIMEOUT = 30


class LinkedInChannel(Channel):
    name = "linkedin"
    description = "LinkedIn 职业社交"
    backends = ["linkedin-scraper-mcp", "Playwright + CookieCloud"]
    tier = 2

    def can_handle(self, url: str) -> bool:
        from urllib.parse import urlparse
        return _domain_matches(urlparse(url).netloc.lower(), "linkedin.com")

    def read(self, url: str) -> str:
        """Read a LinkedIn page via Playwright (CookieCloud) or Jina Reader fallback."""
        content = self._read_via_playwright(url)
        if content:
            return content
        return self._read_via_jina(url)

    def _read_via_playwright(self, url: str) -> str | None:
        """Fetch via Playwright with CookieCloud cookies. Returns None on failure."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return None

        try:
            from agent_reach.cookie_cloud import fetch_and_decrypt, _get_cc_config, _get_cookies_for_domain
            server, uuid, pwd = _get_cc_config()
            cookie_data = fetch_and_decrypt(server, uuid, pwd)
            li_cookies = _get_cookies_for_domain(cookie_data, ".linkedin.com")
            if not li_cookies:
                return None
        except Exception:
            return None

        try:
            pw_cookies = []
            for c in li_cookies:
                pw_cookies.append({
                    "name": c["name"],
                    "value": c["value"],
                    "domain": c.get("domain", ".linkedin.com"),
                    "path": c.get("path", "/"),
                    "secure": c.get("secure", True),
                    "httpOnly": c.get("httpOnly", False),
                    "expires": c.get("expirationDate", -1),
                })

            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                context = browser.new_context(
                    user_agent=_UA,
                    viewport={"width": 1280, "height": 800},
                )
                context.add_cookies(pw_cookies)
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(5000)

                if "login" in page.url.lower():
                    browser.close()
                    return None

                # Extract text
                lines = []
                for sel in ["[class*='profile']", "[class*='detail']", "main", "[role='main']"]:
                    try:
                        el = page.locator(sel).first
                        if el.count() > 0 and el.is_visible(timeout=2000):
                            text = el.inner_text()
                            if len(text) > 50:
                                lines.append(text)
                                break
                    except Exception:
                        pass

                if not lines:
                    text = page.inner_text("body")
                    if len(text) > 100:
                        lines.append(text)

                browser.close()
                if lines:
                    return lines[0]
        except Exception:
            pass
        return None

    def _read_via_jina(self, url: str) -> str:
        """Fallback: read via Jina Reader."""
        jina_url = f"https://r.jina.ai/{url}"
        req = urllib.request.Request(
            jina_url,
            headers={"User-Agent": _UA, "Accept": "text/plain"},
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return resp.read().decode("utf-8")

    def check(self, config=None):
        try:
            from playwright.sync_api import sync_playwright
            has_playwright = True
        except ImportError:
            has_playwright = False

        mcporter = shutil.which("mcporter")
        if mcporter:
            try:
                r = subprocess.run(
                    [mcporter, "config", "list"], capture_output=True,
                    encoding="utf-8", errors="replace", timeout=5
                )
                has_li_mcp = "linkedin" in r.stdout.lower()
            except Exception:
                has_li_mcp = False
        else:
            has_li_mcp = False

        if has_li_mcp:
            return "ok", "完整可用（Profile、公司、职位搜索）"
        elif has_playwright:
            try:
                from agent_reach.cookie_cloud import fetch_and_decrypt, _get_cc_config, _get_cookies_for_domain
                server, uuid, pwd = _get_cc_config()
                cookie_data = fetch_and_decrypt(server, uuid, pwd)
                if _get_cookies_for_domain(cookie_data, ".linkedin.com"):
                    return "ok", "Playwright + CookieCloud 可用（Profile 读取）"
            except Exception:
                pass
            return "warn", (
                "Playwright 可用但 LinkedIn Cookie 未在 CookieCloud 中配置。\n"
                "请在浏览器登录 LinkedIn 后同步 Cookie 到 CookieCloud。"
            )
        else:
            return "off", (
                "基本内容可通过 Jina Reader 读取（可能受限）。\n"
                "完整功能需要 Playwright + CookieCloud 或 linkedin-scraper-mcp。\n"
                "  pip install playwright && playwright install chromium\n"
                "  pip install linkedin-scraper-mcp\n"
                "  mcporter config add linkedin http://localhost:3000/mcp"
            )
