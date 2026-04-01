# Agent-Reach v1.5 实施计划

> 日期：2026-04-01
> 版本：基于设计文档 v1.5
> 目标版本：v1.5.0

---

## 概述

实施分 4 个独立 PR，建议按顺序执行。PR-1 最安全（纯文案），PR-4 最终集成。

| PR | 内容 | 风险 | 文件变化 |
|----|------|------|---------|
| PR-1 | 文档对齐 + 代码清理 | 无 | 多文档 + cli.py |
| PR-2 | CLI read/search/download | 低 | cli.py + core.py + 多个 channel |
| PR-3 | cookie_cloud.py | 中（新增文件） | 新增 agent_reach/cookie_cloud.py |
| PR-4 | doctor 集成 + configure 完善 | 中（修改 doctor.py） | doctor.py + cli.py |

---

## PR-1：文档对齐 + 代码清理

### Step 1.1：重写 `guides/setup-xiaohongshu.md`

**目标**：替换全部 Docker MCP 内容为 xhs-cli 流程。

**变更内容**：
- 删除 Docker + xiaohongshu-mcp 相关内容
- 新增 `pipx install xiaohongshu-cli` 安装说明
- 新增 `xhs login` 自动浏览器提取说明
- 保留 Cookie-Editor 导出方式说明
- 移除 "从源码编译" 章节（不再相关）

**参考**：`cli.py` 中 `_install_xhs_deps()` 函数（行 655-675）

---

### Step 1.2：更新 `README.md`

**变更内容**：

1. **目录结构树**（约第 177 行附近）：
   ```
   - 旧：xiaohongshu.py  → mcporter MCP
   - 新：xiaohongshu.py  → xhs-cli（pipx install xiaohongshu-cli）
   ```

2. **小红书支持平台说明**（约第 198 行附近）：
   ```
   - 旧：⭐9K+，Go 语言，Docker 一键部署
   - 新：pipx install xiaohongshu-cli，无 Docker 依赖
   ```

3. **小红书使用说明**（约第 336 行附近）：
   ```
   - 旧：mcporter call 'xiaohongshu.get_feed_detail(...)'
   - 新：xhs read <url> | xhs search <keyword> | xhs status
   ```

4. **依赖列表**（约第 363 行附近）：
   ```
   - 保留：mcporter, xiaohongshu-mcp（已废弃，删除）
   - 新增：xhs-cli
   ```

5. **FAQ 小红书部分**：合并 `docs/update.md` 中关于 xhs-cli 迁移的已知问题

---

### Step 1.3：同步更新 `README_en.md` 和 `README_ja.md`

与 Step 1.2 相同的四处变更，分别对应英文和日文版本。

**`README_ja.md` 额外修复**：GitHub 链接 `github.com/user/xiaohongshu-mcp` → 改为不存在的链接说明（实际该 repo 已不用）

---

### Step 1.4：更新 `docs/install.md`

**变更内容**：
- 删除小红书 Docker 部署步骤（约第 163-170 行）
- 删除 `mcporter config add xiaohongshu ...` 行
- 替换为 `agent-reach install --channels=xiaohongshu` 安装说明
- 删除代理配置示例中的 xiaohongshu MCP 代理配置段落

---

### Step 1.5：更新 `config/mcporter.json`

```json
// 变更前
{
  "mcpServers": {
    "xiaohongshu": { "baseUrl": "http://localhost:18060/mcp" }
  }
}

// 变更后：删除 xiaohongshu 条目
{
  "mcpServers": {
    "exa": { "baseUrl": "https://mcp.exa.ai/mcp" }
  },
  "imports": []
}
```

---

### Step 1.6：清理 `cli.py` 中的遗留代码

**变更 1：清理 `_configure_xhs_cookies()` 函数（行 1123-1296）**

该函数原设计为往 xiaohongshu-mcp Docker 容器注入 cookie，现改为写 xhs-cli cookie 文件。

新函数逻辑：

```python
def _configure_xhs_cookies(value):
    """Parse cookie input and write to xhs-cli cookie file.

    Accepts:
    1. Cookie-Editor JSON export (array of {name, value, ...})
    2. Header String: "name1=val1; name2=val2; ..."

    Writes to ~/.xiaohongshu-cli/cookies.json in xhs-cli format.
    """
    import json
    import os
    import pathlib

    value = value.strip()
    if not value:
        print("[X] Missing cookie value.")
        return

    cookies_dict = {}

    # Parse JSON format
    if value.startswith("["):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                for c in parsed:
                    if isinstance(c, dict) and "name" in c:
                        cookies_dict[c["name"]] = c["value"]
        except json.JSONDecodeError:
            pass

    # Parse header string format
    if not cookies_dict:
        for part in value.split(";"):
            part = part.strip()
            if "=" not in part:
                continue
            name, _, val = part.partition("=")
            name, val = name.strip(), val.strip()
            if name:
                cookies_dict[name] = val

    if not cookies_dict:
        print("[X] Could not parse cookies.")
        return

    # Ensure a1 is present
    if "a1" not in cookies_dict:
        print("[X] a1 cookie is required for xhs-cli.")
        return

    # Write to xhs-cli cookie file
    cookie_file = pathlib.Path.home() / ".xiaohongshu-cli" / "cookies.json"
    cookie_file.parent.mkdir(parents=True, exist_ok=True)
    # xhs-cli expects: { "a1": "...", "web_session": "...", "saved_at": timestamp }
    payload = {**cookies_dict, "saved_at": str(int(__import__("time").time()))}
    cookie_file.write_text(json.dumps(payload, indent=2))
    cookie_file.chmod(0o600)

    print(f"✅ Cookies written to {cookie_file}")
    print("   Run `xhs status` to verify authentication.")
```

**变更 2：清理 `_cmd_uninstall()` 中 xiaohongshu 的 mcporter 清理（行 1358）**

```python
# 变更前
for mcp_name in ("exa", "xiaohongshu"):

# 变更后
for mcp_name in ("exa",):
```

**变更 3：保留 `_sync_bird_env()` 函数（不清理）**

`cookie_extract.py` 中的 `_sync_bird_env()`（行 177-195）是 Twitter cookie 同步到 bird CLI 的正确实现，**保留不动**。

---

### Step 1.7：补全 `CHANGELOG.md`

补充 v1.4.0 变更记录，至少包含：
- XHS 从 Docker MCP 迁移到 xhs-cli
- README 多语言更新
- mcporter.json 清理

---

## PR-2：CLI 通用命令

### Step 2.1：`base.py` — 为 `read()` 接口做预备

`WebChannel` 已实现 `read()`。其他 channel 在 Step 2.3 中逐个实现。`base.py` 无需改动（`read()` 是可选方法）。

---

### Step 2.2：`cli.py` — 新增 `read` / `search` / `download` 子命令

**在 `main()` 的 subparsers 区添加（约行 116-117 后）**：

```python
# ── read ──
p_read = sub.add_parser("read", help="Read content from a URL")
p_read.add_argument("url", help="URL to read")
p_read.add_argument("--raw", action="store_true",
    help="Return raw output without formatting or summarization")

# ── search ──
p_search = sub.add_parser("search", help="Search across platforms")
p_search.add_argument("query", nargs="+", help="Search query")
p_search.add_argument("--platform", "-p", default="",
    choices=["", "xhs", "twitter", "reddit", "github", "bilibili", "v2ex", "exa"],
    help="Target platform (default: all platforms via Exa)")

# ── download ──
p_dl = sub.add_parser("download", help="Download video/audio from a URL")
p_dl.add_argument("url", help="URL to download")
p_dl.add_argument("--format", "-f", default="",
    help="yt-dlp format spec (e.g. bestvideo, mp4)")
p_dl.add_argument("--output", "-o", default="",
    help="Output file/directory path")
```

**在命令路由添加（约行 149 后）**：

```python
elif args.command == "read":
    _cmd_read(args)
elif args.command == "search":
    _cmd_search(args)
elif args.command == "download":
    _cmd_download(args)
```

---

### Step 2.3：各 channel 实现 `read()` 方法

**`twitter.py`** — 新增：

```python
def read(self, url: str) -> str:
    """Read a tweet via twitter-cli."""
    twitter = shutil.which("twitter") or shutil.which("bird") or shutil.which("birdx")
    if not twitter:
        raise RuntimeError("twitter-cli not installed. Run: pipx install twitter-cli")

    import os
    auth_token = os.environ.get("TWITTER_AUTH_TOKEN") or _get_config("twitter_auth_token")
    ct0 = os.environ.get("TWITTER_CT0") or _get_config("twitter_ct0")
    env = None
    if auth_token and ct0:
        env = {**os.environ.copy(), "TWITTER_AUTH_TOKEN": auth_token, "TWITTER_CT0": ct0}

    # Extract tweet ID from URL
    tweet_id = _extract_tweet_id(url)
    result = subprocess.run(
        [twitter, "read", tweet_id],
        capture_output=True, encoding="utf-8", errors="replace", timeout=30,
        env=env,
    )
    return (result.stdout or "") + (result.stderr or "")
```

`_extract_tweet_id()` 辅助函数：从 `x.com/user/status/123` 提取 `123`。

**`xhs.py`（xiaohongshu.py）** — 新增：

```python
def read(self, url: str) -> str:
    """Read a XHS note via xhs-cli, return raw JSON."""
    xhs = shutil.which("xhs")
    if not xhs:
        raise RuntimeError("xhs-cli not installed. Run: pipx install xiaohongshu-cli")
    result = subprocess.run(
        [xhs, "read", url, "--json"],
        capture_output=True, encoding="utf-8", errors="replace", timeout=30,
    )
    return result.stdout or result.stderr or ""
```

**`reddit.py`** — 新增：

```python
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
```

**`github.py`** — 新增：

```python
def read(self, url: str) -> str:
    """Read a GitHub file/issue/PR via gh CLI."""
    gh = shutil.which("gh")
    if not gh:
        raise RuntimeError("gh CLI not installed. Run: brew install gh")

    # gh view supports both repos and issues/PRs by URL
    result = subprocess.run(
        [gh, "api", "--cache", "300", f"repos/{owner}/{repo}/..."],
        # More precisely: parse URL to determine read type
        capture_output=True, encoding="utf-8", errors="replace", timeout=30,
    )
    return result.stdout or result.stderr or ""
```

> **注意**：`github.py` 的 `read()` 需要解析 URL 判断是 file/issue/PR/repo，然后调用对应 gh 子命令。完整解析逻辑见 Step 2.3 详细说明。

**`bilibili.py`** — 新增：

```python
def read(self, url: str) -> str:
    """Dump video metadata as JSON via yt-dlp."""
    if not shutil.which("yt-dlp"):
        raise RuntimeError("yt-dlp not installed. Run: pip install yt-dlp")
    result = subprocess.run(
        ["yt-dlp", "--dump-json", "--no-download", url],
        capture_output=True, encoding="utf-8", errors="replace", timeout=60,
    )
    return result.stdout or result.stderr or ""
```

**`youtube.py`** — 新增：

```python
def read(self, url: str) -> str:
    """Dump video metadata as JSON via yt-dlp."""
    if not shutil.which("yt-dlp"):
        raise RuntimeError("yt-dlp not installed. Run: pip install yt-dlp")
    result = subprocess.run(
        ["yt-dlp", "--dump-json", "--no-download", url],
        capture_output=True, encoding="utf-8", errors="replace", timeout=60,
    )
    return result.stdout or result.stderr or ""
```

> **注意**：`bilibili.py` 和 `youtube.py` 的 `read()` 实现完全相同，未来可重构为共享逻辑。

**GitHub URL 解析详细说明**：

```python
def _parse_github_url(url: str) -> dict:
    """Parse GitHub URL to determine type and return (type, owner, repo, path)."""
    from urllib.parse import urlparse
    import re

    parsed = urlparse(url)
    path = parsed.path.strip("/").split("/")

    if len(path) < 2:
        raise ValueError(f"Invalid GitHub URL: {url}")

    owner, repo = path[0], path[1]

    if len(path) == 2:
        return {"type": "repo", "owner": owner, "repo": repo.rstrip(".git")}
    elif len(path) == 4 and path[2] in ("pull", "issues"):
        return {"type": path[2], "owner": owner, "repo": repo, "number": path[3]}
    elif len(path) >= 5 and path[2] == "blob":
        return {"type": "file", "owner": owner, "repo": repo, "path": "/".join(path[4:])}
    # ...
```

---

### Step 2.4：`cli.py` — 实现 `_cmd_read()`

```python
def _cmd_read(args):
    """Route URL to appropriate channel read() method."""
    from agent_reach.doctor import get_all_channels

    url = args.url
    raw = args.raw

    channels = get_all_channels()
    for ch in channels:
        if ch.can_handle(url):
            try:
                if not hasattr(ch, "read") or not callable(getattr(ch, "read", None)):
                    print(f"[!] {ch.name} channel does not support URL reading.", file=sys.stderr)
                    sys.exit(1)
                result = ch.read(url)
                if raw:
                    print(result)
                else:
                    # Default: raw output (no summarization)
                    print(result)
            except NotImplementedError:
                print(f"[!] {ch.name} channel does not support direct URL reading.", file=sys.stderr)
                sys.exit(1)
            except RuntimeError as e:
                print(f"[X] {e}", file=sys.stderr)
                sys.exit(1)
            return

    # Fallback: Web (Jina Reader)
    print(f"[*] No specific channel for this URL, falling back to Web (Jina Reader)...", file=sys.stderr)
    from agent_reach.channels.web import WebChannel
    print(WebChannel().read(url))
```

---

### Step 2.5：`cli.py` — 实现 `_cmd_search()`

```python
def _cmd_search(args):
    """Search across platforms."""
    import subprocess
    import shutil

    query = " ".join(args.query)
    platform = args.platform or "exa"

    if platform == "exa":
        # 全网搜索：mcporter call exa.search
        mcporter = shutil.which("mcporter")
        if not mcporter:
            print("[X] mcporter not installed. Run: npm install -g mcporter", file=sys.stderr)
            sys.exit(1)
        result = subprocess.run(
            [mcporter, "call", f"exa.search(query: '{query}', numResults: 10)"],
            capture_output=True, encoding="utf-8", errors="replace", timeout=30,
        )
        print(result.stdout or result.stderr or "")

    elif platform == "xhs":
        xhs = shutil.which("xhs")
        if not xhs:
            print("[X] xhs-cli not installed. Run: pipx install xiaohongshu-cli", file=sys.stderr)
            sys.exit(1)
        result = subprocess.run(
            [xhs, "search", query, "--json"],
            capture_output=True, encoding="utf-8", errors="replace", timeout=30,
        )
        print(result.stdout or result.stderr or "")

    elif platform == "twitter":
        twitter = shutil.which("twitter")
        if not twitter:
            print("[X] twitter-cli not installed. Run: pipx install twitter-cli", file=sys.stderr)
            sys.exit(1)
        result = subprocess.run(
            [twitter, "search", query],
            capture_output=True, encoding="utf-8", errors="replace", timeout=30,
        )
        print(result.stdout or result.stderr or "")

    elif platform == "reddit":
        rdt = shutil.which("rdt")
        if not rdt:
            print("[X] rdt-cli not installed. Run: pipx install rdt-cli", file=sys.stderr)
            sys.exit(1)
        result = subprocess.run(
            [rdt, "search", query],
            capture_output=True, encoding="utf-8", errors="replace", timeout=30,
        )
        print(result.stdout or result.stderr or "")

    elif platform == "github":
        gh = shutil.which("gh")
        if not gh:
            print("[X] gh CLI not installed. Run: brew install gh", file=sys.stderr)
            sys.exit(1)
        result = subprocess.run(
            ["gh", "search", "code", query, "--limit", "20"],
            capture_output=True, encoding="utf-8", errors="replace", timeout=30,
        )
        print(result.stdout or result.stderr or "")

    elif platform == "bilibili":
        # Fall back to Exa if no bili-cli
        bili = shutil.which("bili")
        if bili:
            result = subprocess.run(
                [bili, "search", query],
                capture_output=True, encoding="utf-8", errors="replace", timeout=30,
            )
        else:
            # bili-cli unavailable: use Exa with site:bilibili.com
            mcporter = shutil.which("mcporter")
            if not mcporter:
                print("[X] Neither bili-cli nor mcporter available.", file=sys.stderr)
                sys.exit(1)
            result = subprocess.run(
                [mcporter, "call",
                 f"exa.search(query: '{query} site:bilibili.com', numResults: 10)"],
                capture_output=True, encoding="utf-8", errors="replace", timeout=30,
            )
        print(result.stdout or result.stderr or "")

    elif platform == "v2ex":
        from agent_reach.channels.v2ex import V2EXChannel
        import json
        ch = V2EXChannel()
        try:
            results = ch.search(query)
            print(json.dumps(results, ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"[X] V2EX search error: {e}", file=sys.stderr)
            sys.exit(1)
```

> **注意**：`search reddit <query>` → rdt-cli 支持 `rdt search <query>`。

---

### Step 2.6：`cli.py` — 实现 `_cmd_download()`

```python
def _cmd_download(args):
    """Download video/audio via yt-dlp."""
    import subprocess
    import shutil

    url = args.url
    if not shutil.which("yt-dlp"):
        print("[X] yt-dlp not installed. Run: pip install yt-dlp", file=sys.stderr)
        sys.exit(1)

    cmd = ["yt-dlp"]
    if args.format:
        cmd += ["-f", args.format]
    if args.output:
        cmd += ["-o", args.output]
    cmd.append(url)

    result = subprocess.run(
        cmd,
        capture_output=True, encoding="utf-8", errors="replace", timeout=600,
    )
    print(result.stdout or result.stderr or "")
    if result.returncode != 0:
        sys.exit(result.returncode)
```

> **注意**：抖音（douyin）和小红书图片下载超出 scope，目前只支持 YouTube/Bilibili 通过 yt-dlp 直接工作。

---

### Step 2.7：更新 `SKILL.md`（可选，非必须）

`SKILL.md` 中的命令引用已经和实际实现一致，无需强制修改。

---

## PR-3：CookieCloud 优先架构

### Step 3.1：`agent_reach/cookie_cloud.py` — 核心模块

**新增文件**：`agent_reach/cookie_cloud.py`

```python
# -*- coding: utf-8 -*-
"""CookieCloud cookie synchronization.

Fetches cookies from CookieCloud server, decrypts them, and writes
to each platform's native storage location.

Server: https://router.kyangc.com:1206
UUID:   macmini
Password: from COOKIECLOUD_PASSWORD env var (or keyring fallback)
"""

from __future__ import annotations

import json
import os
import stat
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


def _get_password() -> str:
    """Get CookieCloud password from env or keyring."""
    pwd = os.environ.get("COOKIECLOUD_PASSWORD")
    if pwd:
        return pwd
    try:
        import keyring
        pwd = keyring.get_password("agent-reach", "cookiecloud")
        if pwd:
            return pwd
    except Exception:
        pass
    raise RuntimeError(
        "CookieCloud password not set. "
        "Set the COOKIECLOUD_PASSWORD environment variable, or run:\n"
        "  python -c \"import keyring; keyring.set_password('agent-reach', 'cookiecloud', 'YOUR_PASSWORD')\""
    )


def fetch_and_decrypt(server: str, uuid: str, password: str) -> Dict[str, Any]:
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
) -> Dict[str, Any]:
    """Sync cookies from CookieCloud to all configured platforms.

    Args:
        platforms: List of platforms to sync (None = all enabled in config)
        force:     If True, always sync. If False, check local TTL first.
        server:    Override CookieCloud server URL
        uuid:      Override UUID
        password:  Override password (bypasses _get_password)

    Returns:
        Dict mapping platform name to ("ok"/"skip"/"error", message)
    """
    # Load config
    cfg = _load_config()
    cc_cfg = cfg.get("cookiecloud", {})

    if not cc_cfg.get("enabled"):
        return {"_": ("error", "CookieCloud is not enabled. Run: agent-reach configure cookiecloud --enable")}

    server = server or cc_cfg.get("server", "https://router.kyangc.com:1206")
    uuid_ = uuid or cc_cfg.get("uuid", "macmini")
    password = password or _get_password()
    enabled_platforms = set(cc_cfg.get("platforms", []))
    target_platforms = set(platforms) if platforms else enabled_platforms

    # Fetch and decrypt
    try:
        cookie_data = fetch_and_decrypt(server, uuid_, password)
    except Exception as e:
        return {"_": ("error", f"Failed to fetch from CookieCloud: {e}")}

    results = {}

    # Twitter / X
    if "twitter" in target_platforms:
        results["twitter"] = _sync_twitter(cookie_data, force, cfg)

    # XHS
    if "xhs" in target_platforms:
        results["xhs"] = _sync_xhs(cookie_data, force, cfg)

    # Bilibili
    if "bilibili" in target_platforms:
        results["bilibili"] = _sync_bilibili(cookie_data, force, cfg)

    # Xueqiu
    if "xueqiu" in target_platforms:
        results["xueqiu"] = _sync_xueqiu(cookie_data, force, cfg)

    # YouTube
    if "youtube" in target_platforms:
        results["youtube"] = _sync_youtube(cookie_data, force)

    return results


# ─── Platform sync functions ────────────────────────────────────────────────


def _sync_twitter(cookie_data: Dict, force: bool, cfg) -> tuple:
    """Sync Twitter cookies to ~/.config/bird/credentials.env."""
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
    bird_path.chmod(0o600)

    # Also update agent-reach config (for twitter-cli which reads env vars directly)
    cfg.set("twitter_auth_token", auth_token)
    cfg.set("twitter_ct0", ct0)

    return "ok", f"Wrote to {bird_path} (auth_token={auth_token[:8]}...)"


def _sync_xhs(cookie_data: Dict, force: bool, cfg) -> tuple:
    """Sync XHS cookies to ~/.xiaohongshu-cli/cookies.json."""
    cookies = _get_cookies_for_domain(cookie_data, ".xiaohongshu.com")
    if not cookies:
        return "skip", "No cookies found for .xiaohongshu.com"

    # Build xhs-cli format: {name: value, ...} + saved_at
    cookies_dict = {c["name"]: c["value"] for c in cookies}
    if "a1" not in cookies_dict:
        return "skip", "a1 cookie not found"

    payload = {**cookies_dict, "saved_at": str(int(time.time()))}

    xhs_path = Path.home() / ".xiaohongshu-cli" / "cookies.json"
    xhs_path.parent.mkdir(parents=True, exist_ok=True)
    xhs_path.write_text(json.dumps(payload, indent=2))
    xhs_path.chmod(0o600)

    return "ok", f"Wrote {len(cookies_dict)} cookies to {xhs_path}"


def _sync_bilibili(cookie_data: Dict, force: bool, cfg) -> tuple:
    """Sync Bilibili cookies to config.yaml."""
    cookies = _get_cookies_for_domain(cookie_data, ".bilibili.com")
    if not cookies:
        return "skip", "No cookies found for .bilibili.com"

    cookies_dict = {c["name"]: c["value"] for c in cookies}

    sessdata = cookies_dict.get("SESSDATA")
    bili_jct = cookies_dict.get("bili_jct")

    if not sessdata:
        return "skip", "SESSDATA not found in CookieCloud cookies"

    cfg.set("bilibili_sessdata", sessdata)
    if bili_jct:
        cfg.set("bilibili_csrf", bili_jct)

    return "ok", f"Saved SESSDATA (bili_jct={'saved' if bili_jct else 'not found'})"


def _sync_xueqiu(cookie_data: Dict, force: bool, cfg) -> tuple:
    """Sync Xueqiu cookies to config.yaml."""
    cookies = _get_cookies_for_domain(cookie_data, ".xueqiu.com")
    if not cookies:
        return "skip", "No cookies found for .xueqiu.com"

    # Build header string for Xueqiu
    cookie_str = "; ".join(f'{c["name"]}={c["value"]}' for c in cookies)

    if "xq_a_token" not in cookie_str:
        return "skip", "xq_a_token not found (user may not be logged in)"

    cfg.set("xueqiu_cookie", cookie_str)

    return "ok", f"Saved {len(cookies)} cookies to xueqiu_cookie"


def _sync_youtube(cookie_data: Dict, force: bool) -> tuple:
    """Write YouTube cookies to Netscape format at ~/.agent-reach/youtube_cookies.txt."""
    cookies = _get_cookies_for_domain(cookie_data, ".youtube.com")
    if not cookies:
        return "skip", "No cookies found for .youtube.com"

    # Check for __Host-* cookies (needed for full auth)
    has_host_cookies = any(c["name"].startswith("__Host-") for c in cookies)
    if not has_host_cookies:
        warning = "WARNING: No __Host-* cookies found; age-restricted videos may not work."

    yt_path = Path.home() / ".agent-reach" / "youtube_cookies.txt"
    yt_path.parent.mkdir(parents=True, exist_ok=True)

    # Netscape cookie format: domain\tinclude_subdomains\tpath\tsecure\texpiry\tname\tvalue
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
    yt_path.chmod(0o600)

    msg = f"Wrote {len(cookies)} cookies to {yt_path}"
    if not has_host_cookies:
        msg += f"\n  {warning}"
    return "ok", msg


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _get_cookies_for_domain(cookie_data: Dict, domain: str) -> Optional[List[Dict]]:
    """Get cookie list for a domain (with or without leading dot)."""
    return cookie_data.get(domain) or cookie_data.get(domain.lstrip("."))


def _load_config() -> Any:
    """Load agent-reach config.yaml."""
    cfg_path = Path.home() / ".agent-reach" / "config.yaml"
    if cfg_path.exists():
        with open(cfg_path) as f:
            return _ConfigWrapper(yaml.safe_load(f) or {}, cfg_path)
    return _ConfigWrapper({}, cfg_path)


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
            import stat as _stat
            fd = os.open(str(self._path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, _stat.S_IRUSR | _stat.S_IWUSR)
            with os.fdopen(fd, "w") as f:
                yaml.dump(self._data, f, default_flow_style=False, allow_unicode=True)
        except OSError:
            with open(self._path, "w") as f:
                yaml.dump(self._data, f, default_flow_style=False, allow_unicode=True)
```

---

### Step 3.2：更新 `pyproject.toml`

```toml
dependencies = [
    ...
    "cookiecloud-decrypt>=1.0.0",
    "httpx>=0.25.0",
]
```

> `keyring` 保持为可选依赖（try/except 保护）

---

### Step 3.3：`cli.py` — 新增 `cookie-sync` 子命令

**subparser 添加**（约行 117 后）：

```python
# ── cookie-sync ──
p_sync = sub.add_parser("cookie-sync", help="Sync cookies from CookieCloud")
p_sync.add_argument("--platforms", default="",
    help="Comma-separated platforms (twitter,xhs,bilibili,xueqiu,youtube). Default: all")
p_sync.add_argument("--force", action="store_true",
    help="Force sync even if local cookies appear fresh")
```

**命令路由添加**（约行 150 后）：

```python
elif args.command == "cookie-sync":
    _cmd_cookie_sync(args)
```

**实现 `_cmd_cookie_sync()`**：

```python
def _cmd_cookie_sync(args):
    """Sync cookies from CookieCloud to all configured platforms."""
    from agent_reach.cookie_cloud import sync_cookies

    platforms = None
    if args.platforms:
        platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]

    try:
        results = sync_cookies(platforms=platforms, force=args.force)
    except RuntimeError as e:
        print(f"[X] {e}", file=sys.stderr)
        sys.exit(1)

    if "_" in results and results["_"][0] == "error":
        print(f"[X] {results['_'][1]}", file=sys.stderr)
        sys.exit(1)

    ok_count = sum(1 for v in results.values() if v[0] == "ok")
    skip_count = sum(1 for v in results.values() if v[0] == "skip")
    err_count = sum(1 for v in results.values() if v[0] == "error")

    print(f"\nCookieCloud Sync Results:")
    print(f"  ✅ {ok_count} synced")
    print(f"  -- {skip_count} skipped")
    print(f"  [X] {err_count} failed")

    for name, (status, msg) in results.items():
        prefix = "  ✅" if status == "ok" else "  --" if status == "skip" else "  [X]"
        print(f"{prefix} {name}: {msg}")
```

---

## PR-4：Doctor 集成 + configure 完善

### Step 4.1：`doctor.py` — 集成 CookieCloud 自动同步

**变更位置**：`doctor.py` 的 `check_channel()` 或 `check_all()` 中

在需要 cookie 的频道检查之前，检查是否需要从 CookieCloud 同步：

```python
# In doctor.py — add after imports
_NEEDS_COOKIE = {"twitter", "xhs", "bilibili", "xueqiu", "youtube"}

def _should_sync_from_cookiecloud(channel_name: str) -> bool:
    """Check if channel needs cookie and CookieCloud is configured."""
    if channel_name not in _NEEDS_COOKIE:
        return False

    try:
        from agent_reach.config import Config
        cfg = Config()
        cc = cfg.data.get("cookiecloud", {})
        if not cc.get("enabled"):
            return False
        # Check if local cookie is missing/expired
        if channel_name == "twitter":
            return not cfg.get("twitter_auth_token")
        elif channel_name == "xhs":
            # Check xhs-cli cookie file
            p = Path.home() / ".xiaohongshu-cli" / "cookies.json"
            if not p.exists():
                return True
            # Check saved_at TTL (7 days)
            import time, json
            data = json.loads(p.read_text())
            saved_at = float(data.get("saved_at", 0))
            return time.time() - saved_at > 7 * 86400
        elif channel_name == "bilibili":
            return not cfg.get("bilibili_sessdata")
        elif channel_name == "xueqiu":
            return not cfg.get("xueqiu_cookie")
        elif channel_name == "youtube":
            # Always sync YouTube (best-effort)
            return True
        return False
    except Exception:
        return False
```

**在 `check_channel()` 中调用**：

```python
def check_channel(channel_name: str, config=None):
    ...
    # Before running the actual check, try CookieCloud sync if needed
    if _should_sync_from_cookiecloud(channel_name):
        try:
            from agent_reach.cookie_cloud import sync_cookies
            print(f"  [*] Syncing cookies from CookieCloud...", end=" ", flush=True)
            results = sync_cookies(platforms=[channel_name], force=False)
            if results.get(channel_name, ("skip", ""))[0] == "ok":
                print("✅")
            else:
                print("-- (sync skipped)")
        except Exception as e:
            print(f"-- (CookieCloud sync failed: {e})")

    status, msg = _actual_check(channel_name, config)
    return {"name": name, "status": status, "message": msg, "backends": ...}
```

> **关键**：同步是静默的，打印不超过一行，不阻塞 doctor 报告。

---

### Step 4.2：`cli.py` — 完善 `configure` 子命令

**Step 4.2.1：新增 configure cookiecloud 选项**

```python
p_conf.add_argument("key", nargs="?", default=None,
    choices=["proxy", "github-token", "groq-key",
             "twitter-cookies", "youtube-cookies",
             "xhs-cookies",
             "cookiecloud"],   # ← 新增
```

**Step 4.2.2：在 `_cmd_configure()` 中新增分支**

```python
elif args.key == "cookiecloud":
    from agent_reach.config import Config
    cfg = Config()
    cc = cfg.data.get("cookiecloud", {})
    if not cc:
        cc = {"enabled": True, "server": "https://router.kyangc.com:1206",
              "uuid": "macmini", "platforms": ["twitter", "xhs", "bilibili", "xueqiu", "youtube"]}
        cfg.data["cookiecloud"] = cc
        cfg.save()
        print("✅ CookieCloud enabled!")
        print(f"   Server: {cc['server']}")
        print(f"   UUID: {cc['uuid']}")
        print(f"   Password: set COOKIECLOUD_PASSWORD env var")
    else:
        print("CookieCloud is already configured:")
        print(f"   enabled: {cc.get('enabled')}")
        print(f"   server: {cc.get('server')}")
        print(f"   uuid: {cc.get('uuid')}")
        print(f"   platforms: {', '.join(cc.get('platforms', []))}")

elif args.key == "github-token":
    ...

elif args.key == "groq-key":
    ...
```

**Step 4.2.3：新增 `configure list`**

```python
# In _cmd_configure() when no key provided:
if not args.key:
    # Print usage
    ...

# Add list sub-case:
elif args.key == "list":
    from agent_reach.config import Config
    cfg = Config()
    print("Configured credentials:")
    sensitive_keys = {"twitter_auth_token", "twitter_ct0", "xhs_cookie",
                      "bilibili_sessdata", "bilibili_csrf", "xueqiu_cookie",
                      "github_token", "groq_api_key"}
    for k, v in cfg.data.items():
        if k in sensitive_keys:
            masked = f"{str(v)[:8]}..." if v else "(not set)"
            print(f"  {k}: {masked}")
        elif v:
            print(f"  {k}: {v}")
    cc = cfg.data.get("cookiecloud", {})
    print(f"  cookiecloud.enabled: {cc.get('enabled', False)}")
    if cc.get("enabled"):
        print(f"  cookiecloud.server: {cc.get('server')}")
        print(f"  cookiecloud.uuid: {cc.get('uuid')}")
```

---

## 测试计划

每个 PR 完成后执行：

```bash
# 通用测试
pytest tests/ -v

# PR-1 额外：检查无残留 xiaohongshu-mcp 引用
grep -r "xiaohongshu-mcp" agent_reach/ docs/ guides/
grep -r "xiaohongshu.*mcp" agent_reach/ docs/

# PR-2 额外：手动测试
agent-reach read "https://x.com/elonmusk/status/123"
agent-reach search xhs "机器学习"
agent-reach download "https://www.youtube.com/watch?v=xxx"

# PR-3 额外：
COOKIECLOUD_PASSWORD=macmini python -c "from agent_reach.cookie_cloud import sync_cookies; print(sync_cookies())"

# PR-4 额外：
COOKIECLOUD_PASSWORD=macmini agent-reach doctor
```

---

## 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| xhs-cli cookie 文件格式变更 | 高 | 从 CookieCloud 同步前检查 `a1` 存在，不破坏现有手动登录 |
| YouTube `__Host-*` cookie 缺失 | 低 | Best-effort，WARNING 而非报错 |
| CookieCloud 服务器不可达 | 中 | Doctor 静默降级，打印警告，继续检查 |
| `cookiecloud-decrypt` 依赖安装失败 | 低 | pipx/uv 安装时处理 |
| `_ConfigWrapper` 与 `Config` 类行为不一致 | 中 | 仅用于 cookie 同步，简单 key get/set，无复杂逻辑 |
