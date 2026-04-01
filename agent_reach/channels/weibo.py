# -*- coding: utf-8 -*-
"""Weibo (微博) — check if mcporter + mcp-server-weibo is available."""

import json
import re
import shutil
import subprocess
import time
import urllib.request
from .base import Channel, _domain_matches

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
_TIMEOUT = 30


class WeiboChannel(Channel):
    name = "weibo"
    description = "微博动态与热搜"
    backends = ["mcp-server-weibo", "Playwright + CookieCloud"]
    tier = 1

    def can_handle(self, url: str) -> bool:
        from urllib.parse import urlparse
        d = urlparse(url).netloc.lower()
        return _domain_matches(d, "weibo.com") or _domain_matches(d, "weibo.cn")

    def read(self, url: str) -> str:
        """Read a Weibo post via Playwright (CookieCloud cookies) or Jina Reader fallback."""
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

        # Try to get cookies from CookieCloud
        try:
            from agent_reach.cookie_cloud import fetch_and_decrypt, _get_cc_config, _get_cookies_for_domain
            server, uuid, pwd = _get_cc_config()
            cookie_data = fetch_and_decrypt(server, uuid, pwd)
            weibo_cookies = _get_cookies_for_domain(cookie_data, ".weibo.com")
            if not weibo_cookies:
                return None
        except Exception:
            return None

        # Extract post ID from URL
        # https://weibo.com/2256404085/QyLAR5nEB
        # https://m.weibo.cn/status/123456
        post_id = None
        if "/status/" in url:
            post_id = url.split("/status/")[-1].split("?")[0].split("/")[0]
        else:
            m = re.search(r'/weibo\.com/\d+/([A-Za-z0-9_-]+)', url)
            if m:
                post_id = m.group(1)

        try:
            pw_cookies = []
            for c in weibo_cookies:
                pw_cookies.append({
                    "name": c["name"],
                    "value": c["value"],
                    "domain": c.get("domain", ".weibo.com"),
                    "path": c.get("path", "/"),
                    "secure": c.get("secure", False),
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
                page.wait_for_timeout(6000)

                current_url = page.url
                # Check if redirected to login
                if "login" in current_url.lower():
                    browser.close()
                    return None

                lines = []
                # Try main content selectors
                for sel in ["[class*='WB_detail']", "[class*='detail']", "[class*='content']"]:
                    try:
                        el = page.locator(sel).first
                        if el.count() > 0 and el.is_visible(timeout=3000):
                            text = el.inner_text()
                            if len(text) > 50:
                                lines.append(text)
                                break
                    except Exception:
                        pass

                if not lines:
                    # Fallback: get all visible text
                    text = page.inner_text("body")
                    if len(text) > 100:
                        lines.append(text)

                browser.close()

                if lines:
                    return self._format_weibo_content(lines[0], post_id)
        except Exception:
            pass
        return None

    def _format_weibo_content(self, text: str, post_id: str | None) -> str:
        """Clean up and format Weibo text."""
        # Remove navigation sidebar and other noise
        parts = text.split("\n")
        content_lines = []
        skip_keywords = ["首页", "全部关注", "最新微博", "特别关注", "好友圈", "管理", "WB_face", "按热度", "按时间"]
        in_content = False
        for line in parts:
            line = line.strip()
            if not line:
                continue
            if any(kw in line for kw in skip_keywords):
                continue
            if line in ["公开", "私密", "群可见"]:
                continue
            # Skip very short lines that are UI elements
            if len(line) < 3 and line not in ["赞", "评", "转", "发"]:
                continue
            content_lines.append(line)
            if len(line) > 50 and not in_content:
                in_content = True

        result = "\n".join(content_lines[:80])
        if post_id:
            result = f"[微博帖子 {post_id}]\n{result}"
        return result

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
                has_weibo_mcp = "weibo" in r.stdout
            except Exception:
                has_weibo_mcp = False
        else:
            has_weibo_mcp = False

        if has_weibo_mcp:
            return "ok", "完整可用（热搜、搜索、用户动态、评论）"
        elif has_playwright:
            try:
                from agent_reach.cookie_cloud import fetch_and_decrypt, _get_cc_config, _get_cookies_for_domain
                server, uuid, pwd = _get_cc_config()
                cookie_data = fetch_and_decrypt(server, uuid, pwd)
                if _get_cookies_for_domain(cookie_data, ".weibo.com"):
                    return "ok", "Playwright + CookieCloud 可用（帖子读取）"
            except Exception:
                pass
            return "warn", (
                "Playwright 可用但 CookieCloud 未配置。\n"
                "运行 `agent-reach doctor` 确认 CookieCloud 已同步微博 Cookie。"
            )
        else:
            return "off", (
                "需要 mcporter + mcp-server-weibo，或 Playwright + CookieCloud。\n"
                "  方式1（推荐）：npm install -g mcporter && pip install git+...mcp-server-weibo\n"
                "  方式2：pip install playwright && playwright install chromium\n"
                "  详见 https://github.com/Panniantong/mcp-server-weibo"
            )
