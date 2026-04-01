# -*- coding: utf-8 -*-
"""WeChat Official Account articles — read and search.

Read:   exa-py direct API (primary) / Jina Reader (fallback)
Search: Exa web search with includeDomains mp.weixin.qq.com
"""

import os
import urllib.request
from .base import Channel, _domain_matches


def _get_exa():
    """Return an Exa client, or None if exa-py is not installed / key not set."""
    try:
        from exa_py import Exa
    except ImportError:
        return None
    api_key = os.environ.get("EXA_API_KEY")
    if not api_key:
        dotenv_path = os.path.expanduser("~/.agent-reach/.env")
        try:
            with open(dotenv_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("EXA_API_KEY") and "=" in line:
                        api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        except OSError:
            pass
    if not api_key:
        return None
    return Exa(api_key=api_key)


class WeChatChannel(Channel):
    name = "wechat"
    description = "微信公众号文章"
    backends = ["exa-py (推荐)", "Jina Reader (兜底)"]
    tier = 0

    def can_handle(self, url: str) -> bool:
        from urllib.parse import urlparse
        d = urlparse(url).netloc.lower()
        return _domain_matches(d, "mp.weixin.qq.com") or _domain_matches(d, "weixin.qq.com")

    def read(self, url: str) -> str:
        """Read a WeChat article via exa-py or Jina Reader fallback."""
        # Try exa-py first
        exa = _get_exa()
        if exa:
            try:
                result = exa.get_contents([url], text={"max_characters": 15000})
                for r in result.results:
                    if r.text and len(r.text) > 50:
                        return r.text.strip()
            except Exception:
                pass

        # Fallback: Jina Reader
        jina_url = f"https://r.jina.ai/{url}"
        req = urllib.request.Request(
            jina_url,
            headers={"User-Agent": "Mozilla/5.0", "Accept": "text/plain"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8")

    def check(self, config=None):
        exa = _get_exa()
        if exa:
            return "ok", "exa-py 可用（推荐，读取微信公众号文章）"
        try:
            import exa_py  # noqa: F401
            return "warn", "exa-py 已安装但 EXA_API_KEY 未配置。设置 EXA_API_KEY 环境变量或在 ~/.agent-reach/.env 中添加 EXA_API_KEY=xxx"
        except ImportError:
            pass
        return "off", (
            "需要安装 exa-py 并配置 EXA_API_KEY：\n"
            "  pip install exa-py\n"
            "  # 在 ~/.agent-reach/.env 中添加：\n"
            "  EXA_API_KEY=your_api_key\n"
            "  获取 API key: https://dashboard.exa.ai/api-keys"
        )
