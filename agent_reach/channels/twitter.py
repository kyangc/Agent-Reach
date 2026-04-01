# -*- coding: utf-8 -*-
"""Twitter/X — check if twitter-cli or bird CLI is available."""

import shutil
import subprocess
from .base import Channel


class TwitterChannel(Channel):
    name = "twitter"
    description = "Twitter/X 推文"
    backends = ["twitter-cli", "bird CLI (legacy)"]
    tier = 1

    def can_handle(self, url: str) -> bool:
        from urllib.parse import urlparse
        d = urlparse(url).netloc.lower()
        return "x.com" in d or "twitter.com" in d

    def check(self, config=None):
        # Prefer twitter-cli, fallback to bird/birdx
        twitter = shutil.which("twitter")
        bird = shutil.which("bird") or shutil.which("birdx")

        if twitter:
            return self._check_twitter_cli(twitter)
        elif bird:
            return self._check_bird(bird)
        else:
            return "warn", (
                "Twitter CLI 未安装。安装方式：\n"
                "  pipx install twitter-cli\n"
                "或：\n"
                "  uv tool install twitter-cli"
            )

    def _check_twitter_cli(self, binary: str):
        try:
            r = subprocess.run(
                [binary, "status"], capture_output=True,
                encoding="utf-8", errors="replace", timeout=10
            )
            output = (r.stdout or "") + (r.stderr or "")
            if r.returncode == 0 and "ok: true" in output:
                return "ok", (
                    "twitter-cli 完整可用（搜索、读推文、时间线、长文/Article、"
                    "用户查询、Thread）"
                )
            if "not_authenticated" in output:
                return "warn", (
                    "twitter-cli 已安装但未认证。设置方式：\n"
                    "  export TWITTER_AUTH_TOKEN=\"xxx\"\n"
                    "  export TWITTER_CT0=\"yyy\"\n"
                    "或确保已在浏览器中登录 x.com"
                )
            return "warn", (
                "twitter-cli 已安装但认证检查失败。运行：\n"
                "  twitter -v status 查看详细信息"
            )
        except Exception:
            return "warn", "twitter-cli 已安装但连接失败"

    def read(self, url: str) -> str:
        """Read a tweet via twitter-cli."""
        twitter = shutil.which("twitter") or shutil.which("bird") or shutil.which("birdx")
        if not twitter:
            raise RuntimeError("twitter-cli not installed. Run: pipx install twitter-cli")

        import os
        # Priority: env vars > config.yaml (written by CookieCloud sync)
        auth_token = os.environ.get("TWITTER_AUTH_TOKEN")
        ct0 = os.environ.get("TWITTER_CT0")
        if not auth_token or not ct0:
            from agent_reach.config import Config
            cfg = Config()
            auth_token = auth_token or cfg.get("twitter_auth_token")
            ct0 = ct0 or cfg.get("twitter_ct0")

        env = None
        if auth_token and ct0:
            env = {**os.environ.copy(), "TWITTER_AUTH_TOKEN": auth_token, "TWITTER_CT0": ct0}

        tweet_id = self._extract_tweet_id(url)
        result = subprocess.run(
            [twitter, "read", tweet_id],
            capture_output=True, encoding="utf-8", errors="replace", timeout=30,
            env=env,
        )
        return (result.stdout or "") + (result.stderr or "")

    def _extract_tweet_id(self, url: str) -> str:
        """Extract tweet ID from various Twitter URL formats."""
        import re
        patterns = [
            r'/status/(\d+)',
            r'twitter\.com/\w+/status/(\d+)',
            r'x\.com/\w+/status/(\d+)',
        ]
        for pat in patterns:
            m = re.search(pat, url)
            if m:
                return m.group(1)
        raise ValueError(f"Could not extract tweet ID from: {url}")

    def _check_bird(self, binary: str):
        try:
            r = subprocess.run(
                [binary, "check"], capture_output=True,
                encoding="utf-8", errors="replace", timeout=10
            )
            output = (r.stdout or "") + (r.stderr or "")
            if r.returncode == 0:
                return "ok", "bird CLI 可用（读取、搜索推文，含长文/X Article）"
            if "Missing credentials" in output or "missing" in output.lower():
                return "warn", (
                    "bird CLI 已安装但未配置认证。设置环境变量：\n"
                    "  export AUTH_TOKEN=\"xxx\"\n"
                    "  export CT0=\"yyy\""
                )
            return "warn", (
                "bird CLI 已安装但认证检查失败。"
            )
        except Exception:
            return "warn", "bird CLI 已安装但连接失败"
