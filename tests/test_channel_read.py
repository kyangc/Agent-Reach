# -*- coding: utf-8 -*-
"""Tests for channel read() implementations."""

import pytest
from unittest.mock import Mock
import shutil
import subprocess


class TestChannelReadInterface:
    """All channel read() methods must satisfy the interface contract."""

    def test_twitter_read_returns_string(self, monkeypatch):
        """TwitterChannel.read() returns str"""
        from agent_reach.channels.twitter import TwitterChannel

        def fake_run(cmd, **kwargs):
            r = Mock()
            r.stdout = '{"id": "123", "text": "hello"}'
            r.stderr = ""
            return r

        monkeypatch.setattr(subprocess, "run", fake_run)
        monkeypatch.setattr(shutil, "which", lambda x: "/bin/twitter" if x == "twitter" else None)

        ch = TwitterChannel()
        result = ch.read("https://x.com/user/status/123")
        assert isinstance(result, str)
        assert "123" in result

    def test_xhs_read_calls_xhs_with_json_flag(self, monkeypatch):
        """XiaoHongShuChannel.read() uses --json flag"""
        from agent_reach.channels.xiaohongshu import XiaoHongShuChannel

        captured = []
        def fake_run(cmd, **kwargs):
            captured.append(cmd)
            r = Mock()
            r.stdout = '{"note_id": "n1"}'
            r.stderr = ""
            return r

        monkeypatch.setattr(subprocess, "run", fake_run)
        monkeypatch.setattr(shutil, "which", lambda x: "/bin/xhs")

        ch = XiaoHongShuChannel()
        ch.read("https://www.xiaohongshu.com/explore/abc")
        assert "--json" in captured[0]

    def test_web_read_returns_markdown(self, monkeypatch):
        """WebChannel.read() returns Jina Reader Markdown"""
        import urllib.request
        from agent_reach.channels.web import WebChannel

        def fake_urlopen(req, timeout=None):
            class FR:
                def __enter__(self): return self
                def __exit__(self, *a): pass
                def read(self): return b"# Title\nParagraph text."
            return FR()

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

        ch = WebChannel()
        result = ch.read("https://example.com/article")
        assert isinstance(result, str)
        assert "Title" in result
