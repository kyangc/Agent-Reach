# -*- coding: utf-8 -*-
"""Reddit — search and read via rdt-cli (public-clis/rdt-cli)."""

import shutil
import subprocess
from .base import Channel, _domain_matches


class RedditChannel(Channel):
    name = "reddit"
    description = "Reddit 帖子和评论"
    backends = ["rdt-cli"]
    tier = 0

    def can_handle(self, url: str) -> bool:
        from urllib.parse import urlparse
        d = urlparse(url).netloc.lower()
        return _domain_matches(d, "reddit.com") or _domain_matches(d, "redd.it")

    def read(self, url: str) -> str:
        """Read a Reddit post via rdt-cli."""
        rdt = shutil.which("rdt")
        if not rdt:
            raise RuntimeError("rdt-cli not installed. Run: pipx install rdt-cli")
        result = subprocess.run(
            [rdt, "read", url],
            capture_output=True, encoding="utf-8", errors="replace", timeout=30,
        )
        return result.stdout or result.stderr or ""

    def check(self, config=None):
        rdt = shutil.which("rdt")
        if rdt:
            return "ok", (
                "rdt-cli 可用（搜索帖子、阅读全文、查看评论，无需登录）"
            )
        return "off", (
            "需要安装 rdt-cli：\n"
            "  pipx install rdt-cli\n"
            "或：\n"
            "  uv tool install rdt-cli"
        )
