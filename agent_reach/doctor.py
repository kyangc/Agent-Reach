# -*- coding: utf-8 -*-
"""Environment health checker — powered by channels.

Each channel knows how to check itself. Doctor just collects the results.
"""

from typing import Dict
from agent_reach.config import Config
from agent_reach.channels import get_all_channels

_NEEDS_COOKIE = {"twitter", "xhs", "bilibili", "xueqiu", "youtube"}

def _should_sync_from_cookiecloud(channel_name: str) -> bool:
    """Check if channel needs cookie and CookieCloud is configured and cookies are missing."""
    if channel_name not in _NEEDS_COOKIE:
        return False

    try:
        from pathlib import Path
        from agent_reach.config import Config
        cfg = Config()
        cc = cfg.data.get("cookiecloud", {})
        if not cc.get("enabled"):
            return False

        if channel_name == "twitter":
            return not cfg.get("twitter_auth_token")
        elif channel_name == "xhs":
            p = Path.home() / ".xiaohongshu-cli" / "cookies.json"
            if not p.exists():
                return True
            import json, time
            data = json.loads(p.read_text())
            saved_at = float(data.get("saved_at", 0))
            return time.time() - saved_at > 7 * 86400
        elif channel_name == "bilibili":
            return not cfg.get("bilibili_sessdata")
        elif channel_name == "xueqiu":
            return not cfg.get("xueqiu_cookie")
        elif channel_name == "youtube":
            return True  # best-effort
        return False
    except Exception:
        return False


def check_all(config: Config) -> Dict[str, dict]:
    import sys as _sys
    results = {}
    for ch in get_all_channels():
        # Try CookieCloud sync if needed (silent, non-blocking)
        if _should_sync_from_cookiecloud(ch.name):
            try:
                from agent_reach.cookie_cloud import sync_cookies
                print("  [*] Syncing cookies from CookieCloud...", end=" ", flush=True, file=_sys.stderr)
                results_cc = sync_cookies(platforms=[ch.name], force=False)
                status_cc = results_cc.get(ch.name, ("skip", ""))[0]
                print("✅" if status_cc == "ok" else "--", file=_sys.stderr)
            except Exception as e:
                print(f"-- (CookieCloud sync failed: {e})", file=_sys.stderr)

        status, message = ch.check(config)
        results[ch.name] = {
            "status": status,
            "name": ch.description,
            "message": message,
            "tier": ch.tier,
            "backends": ch.backends,
        }
    return results


def format_report(results: Dict[str, dict]) -> str:
    """Format results as a readable text report (with Rich markup)."""
    try:
        from rich.markup import escape
    except ImportError:
        escape = lambda x: x

    lines = []
    lines.append("[bold cyan]Agent Reach 状态[/bold cyan]")
    lines.append("[cyan]" + "=" * 40 + "[/cyan]")

    ok_count = sum(1 for r in results.values() if r["status"] == "ok")
    total = len(results)

    # Tier 0 — zero config
    lines.append("")
    lines.append("[bold]✅ 装好即用：[/bold]")
    for key, r in results.items():
        if r["tier"] == 0:
            name_msg = f"[bold]{escape(r['name'])}[/bold] — {escape(r['message'])}"
            if r["status"] == "ok":
                lines.append(f"  [green]✅[/green] {name_msg}")
            elif r["status"] == "warn":
                lines.append(f"  [yellow][!][/yellow]  {name_msg}")
            elif r["status"] in ("off", "error"):
                lines.append(f"  [red][X][/red]  {name_msg}")

    # Tier 1 — needs free key / login
    tier1 = {k: r for k, r in results.items() if r["tier"] == 1}
    tier1_active = {k: r for k, r in tier1.items() if r["status"] == "ok"}
    tier1_inactive = {k: r for k, r in tier1.items() if r["status"] != "ok"}
    if tier1_active:
        lines.append("")
        lines.append("[bold]可选渠道（已安装）：[/bold]")
        for key, r in tier1_active.items():
            name_msg = f"[bold]{escape(r['name'])}[/bold] — {escape(r['message'])}"
            lines.append(f"  [green]✅[/green] {name_msg}")

    # Tier 2 — optional complex setup
    tier2 = {k: r for k, r in results.items() if r["tier"] == 2}
    tier2_active = {k: r for k, r in tier2.items() if r["status"] == "ok"}
    tier2_inactive = {k: r for k, r in tier2.items() if r["status"] != "ok"}
    if tier2_active:
        if not tier1_active:
            lines.append("")
            lines.append("[bold]可选渠道（已安装）：[/bold]")
        for key, r in tier2_active.items():
            name_msg = f"[bold]{escape(r['name'])}[/bold] — {escape(r['message'])}"
            lines.append(f"  [green]✅[/green] {name_msg}")

    lines.append("")
    status_color = "green" if ok_count == total else ("yellow" if ok_count > 0 else "red")
    lines.append(f"状态：[{status_color}]{ok_count}/{total}[/{status_color}] 个渠道可用")

    # Summarize inactive optional channels in one line instead of listing each
    all_inactive = list(tier1_inactive.values()) + list(tier2_inactive.values())
    if all_inactive:
        names = [r["name"] for r in all_inactive]
        lines.append(
            f"还有 {len(names)} 个可选渠道可以解锁（{'、'.join(names)}），"
            "告诉你的 Agent「帮我装 XXX」即可"
        )

    # Security check: config file permissions (Unix only)
    import os
    import stat
    import sys

    config_path = Config.CONFIG_DIR / "config.yaml"
    if config_path.exists() and sys.platform != "win32":
        try:
            mode = config_path.stat().st_mode
            if mode & (stat.S_IRGRP | stat.S_IROTH):
                lines.append("")
                lines.append(
                    "[bold red][!]  安全提示：config.yaml 权限过宽（其他用户可读）[/bold red]"
                )
                lines.append("   修复：chmod 600 ~/.agent-reach/config.yaml")
        except OSError:
            pass

    return "\n".join(lines)
