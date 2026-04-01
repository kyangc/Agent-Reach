# -*- coding: utf-8 -*-
"""RSS — check if feedparser is available."""

import feedparser
from .base import Channel


class RSSChannel(Channel):
    name = "rss"
    description = "RSS/Atom 订阅源"
    backends = ["feedparser"]
    tier = 0

    def can_handle(self, url: str) -> bool:
        return any(x in url.lower() for x in ["/feed", "/rss", ".xml", "atom"])

    def read(self, url: str) -> str:
        """Parse an RSS/Atom feed and return entries as readable text."""
        feed = feedparser.parse(url)
        if feed.bozo and not feed.entries:
            raise RuntimeError(f"RSS feed parse error: {feed.bozo_exception}")

        lines = [f"# {feed.feed.get('title', 'RSS Feed')}"]
        if feed.feed.get("subtitle"):
            lines.append(f"## {feed.feed['subtitle']}")
        lines.append("")

        for i, e in enumerate(feed.entries[:20], 1):
            title = e.get("title", "No title")
            link = e.get("link", "")
            date = e.get("published", "") or e.get("updated", "")
            summary = (e.get("summary") or e.get("description") or "")[:300]
            lines.append(f"### {i}. {title}")
            if date:
                lines.append(f"Date: {date}")
            lines.append(f"Link: {link}")
            if summary:
                lines.append(f"Summary: {summary}")
            lines.append("")

        return "\n".join(lines)

    def check(self, config=None):
        try:
            import feedparser
            return "ok", "可读取 RSS/Atom 源"
        except ImportError:
            return "off", "feedparser 未安装。安装：pip install feedparser"
