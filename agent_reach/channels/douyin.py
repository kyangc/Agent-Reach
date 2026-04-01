# -*- coding: utf-8 -*-
"""Douyin (抖音) — check if mcporter + douyin-mcp-server is available."""

import json
import shutil
import subprocess
from .base import Channel, _domain_matches


class DouyinChannel(Channel):
    name = "douyin"
    description = "抖音短视频"
    backends = ["douyin-mcp-server"]
    tier = 2

    def can_handle(self, url: str) -> bool:
        from urllib.parse import urlparse
        d = urlparse(url).netloc.lower()
        return _domain_matches(d, "douyin.com") or _domain_matches(d, "iesdouyin.com")

    def read(self, url: str) -> str:
        """Parse a Douyin video via douyin-mcp-server (mcporter).

        Accepts any Douyin URL format: share links (v.douyin.com),
        direct video URLs (douyin.com/video/xxx), etc.
        """
        mcporter = shutil.which("mcporter")
        if not mcporter:
            raise RuntimeError(
                "Douyin MCP not configured. Install:\n"
                "  1. pip install douyin-mcp-server\n"
                "  2. Start server: douyin-mcp-server (runs on port 18070)\n"
                "  3. mcporter config add douyin http://localhost:18070/mcp"
            )

        r = subprocess.run(
            [mcporter, "call", "douyin.parse_douyin_video_info"],
            input=json.dumps({"share_link": url}),
            capture_output=True, encoding="utf-8", errors="replace", timeout=30,
        )
        if r.returncode != 0 or not r.stdout.strip():
            raise RuntimeError(
                f"Douyin MCP call failed: {r.stderr or r.stdout}\n"
                "Ensure douyin-mcp-server is running on port 18070."
            )
        try:
            result = json.loads(r.stdout)
        except json.JSONDecodeError:
            raise RuntimeError(f"Douyin MCP returned invalid JSON: {r.stdout[:200]}")

        # Format nicely
        video_info = result if isinstance(result, dict) else {}
        lines = []
        if video_info.get("title"):
            lines.append(f"# {video_info['title']}")
        if video_info.get("desc"):
            lines.append(f"描述: {video_info['desc']}")
        if video_info.get("author"):
            lines.append(f"作者: {video_info['author']}")
        if video_info.get("download_url"):
            lines.append(f"无水印下载: {video_info['download_url']}")
        if video_info.get("cover"):
            lines.append(f"封面: {video_info['cover']}")
        if not lines:
            lines.append(str(video_info))
        return "\n".join(lines)

    def check(self, config=None):
        mcporter = shutil.which("mcporter")
        if not mcporter:
            return "off", (
                "需要 mcporter + douyin-mcp-server。安装步骤：\n"
                "  1. npm install -g mcporter\n"
                "  2. pip install douyin-mcp-server\n"
                "  3. 启动服务（见下方说明）\n"
                "  4. mcporter config add douyin http://localhost:18070/mcp\n"
                "  详见 https://github.com/yzfly/douyin-mcp-server"
            )
        try:
            r = subprocess.run(
                [mcporter, "config", "list"], capture_output=True,
                encoding="utf-8", errors="replace", timeout=5
            )
            if "douyin" not in r.stdout:
                return "off", (
                    "mcporter 已装但抖音 MCP 未配置。运行：\n"
                    "  pip install douyin-mcp-server\n"
                    "  # 启动服务后：\n"
                    "  mcporter config add douyin http://localhost:18070/mcp"
                )
        except Exception:
            return "off", "mcporter 连接异常"
        # Verify MCP connectivity by listing available tools instead of
        # calling with a hardcoded (invalid) share link that always fails.
        try:
            r = subprocess.run(
                [mcporter, "list", "douyin"],
                capture_output=True, encoding="utf-8", errors="replace", timeout=15
            )
            if r.returncode == 0 and r.stdout.strip():
                return "ok", "完整可用（视频解析、下载链接获取）"
            return "warn", "MCP 已连接但工具列表为空，检查 douyin-mcp-server 服务是否在运行"
        except Exception:
            return "warn", "MCP 连接异常，检查 douyin-mcp-server 服务是否在运行"
