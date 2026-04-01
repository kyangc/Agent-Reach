# Agent-Reach v1.5 改造设计文档

> 日期：2026-04-01
> 目标版本：v1.5.0
> 状态：已评审（所有 TODO 已确认）

---

## 一、背景与目标

本次改造包含四个独立子项：

1. **文档与事实对齐** — 修复 README/guides/docs 与实际代码实现不符的问题
2. **CLI 通用命令** — 将 Skill-only 功能扩展为 CLI 顶层命令
3. **Raw Output 确认** — 确认 Agent-Reach 不做 LLM 精简，补充 `--raw` 信号
4. **CookieCloud 优先架构** — 构建以 CookieCloud 为 primary source 的 cookie 管理体系

---

## 二、改造一：文档与事实对齐

### 2.1 问题清单

| 文档 | 问题描述 |
|------|---------|
| `README.md` / `README_en.md` / `README_ja.md` | XHS 仍描述为 `xiaohongshu-mcp (Docker)`，实际已迁移至 `xhs-cli` |
| `docs/install.md` | 安装流程仍包含 Docker MCP 步骤 |
| `docs/README_ja.md` | GitHub 链接指向错误的 `github.com/user/` |
| `guides/setup-xiaohongshu.md` | 全篇基于 xiaohongshu-mcp，需重写为 xhs-cli |
| `config/mcporter.json` | 包含已废弃的 `xiaohongshu` MCP 条目 |
| `cli.py` | 遗留 `xiaohongshu-mcp` Docker cookie 注入函数 |
| `docs/update.md` | 正确记载了 xhs-cli 迁移，信息未回填到 README |
| `CHANGELOG.md` | 停留在 v1.3.1，v1.4.0 未记录 |

### 2.2 修复方案

**Step 1：重写 `guides/setup-xiaohongshu.md`**
- 替换所有 `xiaohongshu-mcp` / Docker 部署为 `xhs-cli` 安装流程
- 保留 Cookie-Editor 导出方式作为推荐认证方法
- 添加 `xhs login` 自动浏览器提取流程
- 移除 Docker 相关步骤

**Step 2：更新 README 系列**
- `README.md`：XHS 部分替换为 `xhs-cli`，更新目录结构树（移除 xiaohongshu.py → mcporter MCP 行）
- `README_en.md` / `README_ja.md`：同步替换
- 将 `docs/update.md` 中 xhs-cli 迁移的已知问题说明回填 README FAQ

**Step 3：清理 `docs/install.md`**
- 移除 Docker + xiaohongshu-mcp 安装步骤
- 替换为 `xhs-cli` 安装命令

**Step 4：更新 `config/mcporter.json`**
- 移除 `xiaohongshu` 条目
- 或标记为 deprecated 注释，保留作可选备用方案

**Step 5：清理 `cli.py`**
- 移除 `_import_xhs_cookies_to_docker()` 函数
- 移除 `mcporter call xiaohongshu.check_login_status()` 验证调用
- 移除 `xiaohongshu-mcp` Docker 容器相关代码

**Step 6：补全 CHANGELOG.md**
- 补充 v1.4.0 的完整变更记录

---

## 三、改造二：CLI 通用命令

### 3.1 新增命令

```
agent-reach read <url>              # 通用内容读取
agent-reach search [platform] <query>  # 通用搜索
agent-reach download <url>           # 音视频下载
agent-reach cookie-sync [flags]      # CookieCloud 同步
```

### 3.2 `agent-reach read <url>`

**行为**：
1. 解析 URL，自动匹配对应 Channel
2. 调用对应 Channel 的 `read(url)` 方法（新增到 base.py 接口）
3. 返回原始输出，不做任何过滤或总结
4. `--raw` 参数：显式声明返回原始格式（给 AI agent 明确信号）

**频道支持**：

| 频道 | 方法 | 说明 |
|------|------|------|
| Twitter | `twitter-cli` / `bird` | 推文读取 |
| XHS | `xhs read <url>` | 笔记读取 |
| Reddit | `rdt-cli` | 帖子读取 |
| GitHub | `gh` CLI | Issue/PR/文件 |
| V2EX | 公开 API | 帖子读取 |
| Bilibili | `yt-dlp --dump-json` | 视频元数据 |
| YouTube | `yt-dlp --dump-json` | 视频元数据 |
| Web | `curl r.jina.ai/<url>` | 通用网页 |

**未匹配到频道时**：回退到 Web (Jina Reader)，打印 INFO 日志

**Channel 接口变更**（`channels/base.py`）：

```python
from abc import abstractmethod

class Channel(ABC):
    # ... existing methods ...

    def read(self, url: str) -> str:
        """Read content from URL. Override for custom implementation.
        Default: raise NotImplementedError."""
        raise NotImplementedError(
            f"{self.name} channel does not support direct URL reading"
        )
```

### 3.3 `agent-reach search [platform] <query>`

**行为**：

| 调用方式 | 行为 |
|---------|------|
| `agent-reach search <query>` | 全网搜索，走 Exa（`mcporter call exa.search`） |
| `agent-reach search xhs <query>` | 小红书搜索，`xhs search <query>` |
| `agent-reach search twitter <query>` | Twitter 搜索，`twitter-cli` |
| `agent-reach search reddit <query>` | Reddit 搜索，`rdt-cli` |
| `agent-reach search github <query>` | GitHub 搜索，`gh search` |
| `agent-reach search bilibili <query>` | B站搜索，`bili-cli` |

**通用搜索（无 platform）**：调用 `mcporter call 'exa.search(query: "<query>", numResults: 10)'`，返回 Exa 原始结果

**平台搜索**：分发到对应 CLI/API，返回原始输出

### 3.4 `agent-reach download <url>`

**行为**：
- 自动识别视频/音频平台
- 调用 `yt-dlp <url>` 执行下载
- `--format <spec>` 参数透传给 yt-dlp（如 `--format bestvideo`）
- `--output <path>` 指定输出路径

**支持平台**：YouTube、Bilibili、抖音、小红书（图片）

**未识别为视频平台时**：报错退出，提示不支持的平台

---

## 四、改造三：Raw Output 确认

### 4.1 现状

Agent-Reach 所有 Channel 输出均为 pass-through：
- Skill 层只记录命令，不做处理
- Channel 层返回原生输出（JSON/API raw output）
- `format_xhs_result()` 是数据字段过滤（去嵌套），非 LLM 操作

**结论**：Agent-Reach 本身不做任何 LLM 精简，无需代码改造。

### 4.2 补充 `--raw` 信号

在 `agent-reach read` 新增 `--raw` 参数：

```python
parser.add_argument("--raw", action="store_true",
    help="Return raw output without any formatting or summarization")
```

Channel 实现中若存在格式化逻辑（如 XHS），`--raw` 时跳过格式化，直接输出原始 JSON。

---

## 五、改造四：CookieCloud 优先架构

### 5.1 设计原则

- **CookieCloud 为 primary source of truth**
- 每次同步：CookieCloud → 格式转换 → 写入各 consumer 存储位置
- 各 consumer（xhs-cli、twitter-cli、config.yaml）继续使用原有读取逻辑，**不做侵入性改造**
- xhs-cli 保留独立 cookie 生命周期管理，CookieCloud 作为外部补充来源

### 5.2 新增文件

```
agent_reach/
  cookie_cloud.py       # CookieCloud 拉取 + 格式转换 + 写入
```

### 5.3 核心模块：`cookie_cloud.py`

**依赖**：`cookiecloud-decrypt`（已确认接口满足需求）

**配置来源**：`~/.agent-reach/config.yaml` 的 `cookiecloud` 节

```yaml
cookiecloud:
  enabled: true
  server: https://router.kyangc.com:1206
  uuid: macmini
  password_env: COOKIECLOUD_PASSWORD   # 从环境变量读取密码
  platforms:
    - twitter
    - xhs
    - bilibili
    - xueqiu
    - youtube
```

**Password 管理**：
- 优先从 `COOKIECLOUD_PASSWORD` 环境变量读取
- 若未设置，尝试 `keyring`（`keyring.get_password("agent-reach", "cookiecloud")`）
- 均不可用时报错，提示用户设置

### 5.4 同步流程

```
1. 从 config 读取 cookiecloud 配置
2. GET https://<server>/get/<uuid>?password=<password>
3. decrypt(encrypted, uuid, password)
4. 遍历启用的 platforms，对每个平台：
   a. 调用对应格式转换函数
   b. 写入对应存储位置
5. 打印同步结果摘要
```

### 5.5 格式转换映射

| 平台 | 写入位置 | 写入格式 | 转换函数 |
|------|---------|---------|---------|
| twitter | `~/.config/bird/credentials.env` | `AUTH_TOKEN=xxx\nCT0=xxx` | `_to_bird_env()` |
| xhs | `~/.xiaohongshu-cli/cookies.json` | `{"a1": "...", "web_session": "...", "webId": "..."}` | `_to_xhs_cli()` |
| bilibili | `~/.agent-reach/config.yaml` | `bilibili_sessdata`, `bilibili_csrf` | `_to_config_yaml("bilibili")` |
| xueqiu | `~/.agent-reach/config.yaml` | `xueqiu_cookie` | `_to_config_yaml("xueqiu")` |
| youtube | `~/.agent-reach/youtube_cookies.txt` | Netscape cookie 格式 | `_to_netscape()` |

**`_to_bird_env()` 实现**：
```python
# CookieCloud domain: .x.com
# 提取 auth_token → AUTH_TOKEN
# 提取 ct0 → CT0
# 写入 ~/.config/bird/credentials.env
# 设置 0o600 权限
```

**`_to_xhs_cli()` 实现**：
```python
# CookieCloud domain: .xiaohongshu.com
# 提取 a1, web_session, webId 等 cookie
# 写入 ~/.xiaohongshu-cli/cookies.json
# 设置 0o600 权限
```

**`_to_netscape()` 实现（YouTube）**：
```python
# CookieCloud domain: .youtube.com
# 写入 Netscape cookie 格式到 ~/.agent-reach/youtube_cookies.txt
# yt-dlp 优先使用 --cookies-from-browser，CookieCloud 文件作为 fallback
# 缺少 __Host-* 强认证 cookie 时打印 WARNING，不报错
```

> **YouTube 说明**：CookieCloud 中的 YouTube cookie 缺少 `__Host-*` 前缀的强认证 cookie，
> 仅能覆盖普通视频。对于年龄限制/会员内容，仍需 `--cookies-from-browser Chrome`。
> 本同步为 best-effort，缺关键 cookie 时仅打印 WARNING，不中断流程。

### 5.6 CLI 命令

```
agent-reach cookie-sync                  # 从 CookieCloud 拉取并同步所有已启用平台
agent-reach cookie-sync --platforms=xhs,twitter  # 仅同步指定平台
agent-reach cookie-sync --force          # 强制覆盖，不检查 TTL
```

### 5.7 Doctor/Watch 集成

`doctor.py` 的 `check()` 流程中：

```python
def check_channel(channel_name):
    # ... existing check logic ...
    # 如果该 channel 需要 cookie 且本地 cookie 不存在或已过期
    if needs_cookie(channel_name) and cookie_missing_or_expired(channel_name):
        print("[*] Syncing cookies from CookieCloud...")
        from agent_reach.cookie_cloud import sync_cookies
        sync_cookies(platforms=[channel_name], force=False)
```

关键行为：
- **静默同步**：不阻塞 doctor 报告输出
- **仅在 cookie 确实缺失/过期时触发**：不每次 doctor 都强制同步
- **失败时降级**：打印警告，继续检查（不因同步失败而中断 doctor）

### 5.8 `agent-reach configure` credential 管理

顺带完善 `configure` 子命令（CookieCloud 改造的附带优化）：

```
agent-reach configure github --token <token>    # 存 github_token 到 config.yaml
agent-reach configure groq --api-key <key>      # 存 groq_api_key 到 config.yaml
agent-reach configure proxy --url <url>          # 存代理到 config.yaml
agent-reach configure list                        # 列出所有已配置 credential（脱敏）
agent-reach configure cookiecloud --enable       # 启用 CookieCloud
agent-reach configure cookiecloud --disable      # 禁用 CookieCloud
agent-reach configure cookiecloud --show         # 显示当前 CookieCloud 配置
```

---

## 六、依赖变更

| 依赖 | 变更 | 说明 |
|------|------|------|
| `cookiecloud-decrypt` | 新增 | CookieCloud 解密 |
| `httpx` | 新增/确认 | cookiecloud-decrypt 内部依赖，确认已安装 |
| `keyring` | 可选 | 密码存储，不可得时退化到 env var |

---

## 七、实施顺序

建议分四个独立 PR 实施：

1. **PR-1：Doc fixes** — 文档对齐、cli.py 清理、CHANGELOG 补全（纯文案，无风险）
2. **PR-2：CLI read/search/download** — 新增命令，对现有代码无破坏性
3. **PR-3：cookie_cloud.py** — 新文件实现，不改动现有 channel
4. **PR-4：doctor/watch 集成 + configure 完善** — 最终集成

---

## 八、测试策略

### 8.1 测试分层

| 层级 | 目标 | 测试方式 |
|------|------|---------|
| 单元测试 | 格式转换逻辑、密码读取、配置写入 | `pytest` + `unittest.mock` |
| CLI 命令测试 | read/search/download/cookie-sync 命令路由 | `patch("sys.argv")` + `capsys` |
| Channel 接口测试 | 各 channel `read()` 返回类型和格式 | mock subprocess + assertions |
| 退化测试 | 现有功能不被破坏 | 完整测试套件 |
| 集成测试 | CookieCloud 端到端同步 | 真实环境（`bash test.sh`） |

### 8.2 新增测试文件

```
tests/
  test_channel_read.py     # 新增：各 channel read() 接口契约
  test_cookie_cloud.py    # 新增：CookieCloud 同步逻辑
```

### 8.3 PR-1 关键测试

`_configure_xhs_cookies()` 从写 Docker 容器改为写 xhs-cli 文件，需验证：

1. **格式解析**：头部字符串 `"a1=xxx; web_session=yyy"` → `cookies.json`
2. **JSON 导入**：Cookie-Editor JSON 导出 → `cookies.json`
3. **a1 必填**：缺少 a1 时拒绝写入
4. **权限 0o600**：文件权限正确
5. **零 Docker 调用**：不执行任何 `docker` 子命令

### 8.4 PR-2 关键测试

**CLI 路由**（`read` / `search` / `download`）：
- 正确分发到对应 channel/tool
- 工具缺失时输出友好错误，退出码 1
- `--raw` 标志透传原始输出
- `--format` 等参数透传给 yt-dlp

**Channel `read()` 接口**：
- 所有 channel 的 `read()` 返回 `str`
- Web channel 返回 Markdown
- XHS channel 使用 `--json` 标志

### 8.5 PR-3 关键测试

**各平台格式转换**：

| 测试场景 | 预期 |
|---------|------|
| Twitter cookie 含 `auth_token` + `ct0` | 写入 `~/.config/bird/credentials.env` |
| 缺少 `auth_token` | skip，不写文件 |
| XHS cookie 含 `a1` | 写入 `~/.xiaohongshu-cli/cookies.json`，含 `saved_at` |
| 缺少 `a1` | skip |
| Bilibili cookie 含 `SESSDATA` + `bili_jct` | 写入 `config.yaml` |
| YouTube cookie 无 `__Host-*` | 写入 Netscape 文件，含 WARNING |
| YouTube cookie 有 `__Host-*` | 正常写入，无 WARNING |

**密码读取**：
- `COOKIECLOUD_PASSWORD` 环境变量优先
- 未设置时报错（不隐式读取）

### 8.6 PR-4 关键测试

**Doctor 集成**：
- CookieCloud 同步失败不阻塞 doctor 报告
- 仅在 cookie 确实缺失时触发同步（非每次 doctor 都同步）

**`configure list`**：
- 敏感信息（token、cookie）必须脱敏显示

### 8.7 退化测试清单

每个 PR 完成后运行完整测试套件，以下测试必须全部通过：

```
tests/test_cli.py          — version, doctor_runs, parse_twitter_cookie_input_*
tests/test_channel_contracts.py — registry, can_handle, check_contract
tests/test_doctor.py       — check_all, format_report
tests/test_config.py       — 全量
```

---

## 九、TODO / 待确认

- [x] `config/mcporter.json` 的 `xiaohongshu` 条目：确认移除
- [x] YouTube cookie：写入 `~/.agent-reach/youtube_cookies.txt`（Netscape 格式），best-effort 模式（无 `__Host-*` 强认证 cookie 时打印 WARNING）
- [x] `--daemon` 定时任务：不实现，用户确认无此需求
- [x] `cookie-sync --show`：不需要，用户确认仅需更新本地文件
- [x] Weibo / GitHub：保持现状（MCP/CLI 自管，CookieCloud 有数据但暂不同步）
