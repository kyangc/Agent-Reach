# -*- coding: utf-8 -*-
"""GitHub — check if gh CLI is available."""

import shutil
import subprocess
from .base import Channel, _domain_matches


class GitHubChannel(Channel):
    name = "github"
    description = "GitHub 仓库和代码"
    backends = ["gh CLI"]
    tier = 0

    def can_handle(self, url: str) -> bool:
        from urllib.parse import urlparse
        return _domain_matches(urlparse(url).netloc.lower(), "github.com")

    def read(self, url: str) -> str:
        """Read a GitHub repo/file/issue/PR via gh CLI."""
        gh = shutil.which("gh")
        if not gh:
            raise RuntimeError("gh CLI not installed. Run: brew install gh")

        parsed = self._parse_github_url(url)
        result = subprocess.run(
            self._gh_command(parsed),
            capture_output=True, encoding="utf-8", errors="replace", timeout=30,
        )
        return (result.stdout or "") + (result.stderr or "")

    def _parse_github_url(self, url: str) -> dict:
        """Parse GitHub URL to dict with type, owner, repo, and path/number."""
        from urllib.parse import urlparse
        import re

        parsed = urlparse(url)
        path = parsed.path.strip("/").split("/")
        if len(path) < 2:
            raise ValueError(f"Invalid GitHub URL: {url}")

        owner, repo = path[0], path[1].rstrip(".git")

        if len(path) == 2:
            return {"type": "repo", "owner": owner, "repo": repo}
        elif len(path) == 4 and path[2] in ("pull", "issues"):
            return {"type": path[2], "owner": owner, "repo": repo, "number": path[3]}
        elif len(path) >= 5 and path[2] == "blob":
            return {"type": "file", "owner": owner, "repo": repo, "path": "/".join(path[4:])}
        else:
            return {"type": "repo", "owner": owner, "repo": repo}

    def _gh_command(self, parsed: dict) -> list:
        """Build gh CLI command from parsed URL dict."""
        t = parsed["type"]
        owner, repo = parsed["owner"], parsed["repo"]
        if t == "repo":
            return ["gh", "repo", "view", f"{owner}/{repo}"]
        elif t == "issues":
            return ["gh", "issue", "view", parsed["number"], "--repo", f"{owner}/{repo}"]
        elif t == "pull":
            return ["gh", "pr", "view", parsed["number"], "--repo", f"{owner}/{repo}"]
        elif t == "file":
            return ["gh", "api", f"/repos/{owner}/{repo}/contents/{parsed['path']}"]
        return ["gh", "repo", "view", f"{owner}/{repo}"]

    def check(self, config=None):
        gh = shutil.which("gh")
        if not gh:
            return "warn", "gh CLI 未安装。安装：https://cli.github.com"
        try:
            r = subprocess.run(
                [gh, "auth", "status"],
                capture_output=True, encoding="utf-8", errors="replace", timeout=5
            )
            if r.returncode == 0:
                return "ok", "完整可用（读取、搜索、Fork、Issue、PR 等）"
            return "warn", "gh CLI 已安装但未认证。运行 gh auth login 可解锁完整功能"
        except Exception:
            return "warn", "gh CLI 状态检查失败，运行 gh auth status 查看详情"
