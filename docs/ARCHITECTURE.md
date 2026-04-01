# Agent-Reach 项目深度理解文档

> 本文档是 Agent-Reach 项目的系统性知识沉淀，旨在为后续的功能迭代、架构调整和二次开发提供理论依据。
>
> 作者：Claude Code | 日期：2026-04-01
> 项目版本：v1.3.0 | 仓库：github.com/Panniantong/Agent-Reach

---

## 一、项目定位与核心价值

### 1.1 是什么

Agent-Reach 是一个 **Python CLI + 库**，核心功能是：**给 AI Agent 安装配置 14+ 互联网平台的读取/搜索能力**。

它的定位是 **installer + doctor + configurator**，而不是 wrapper。项目明确声明：

> "After installation, agents call upstream tools directly. No wrapper layer needed."

这意味着 Agent-Reach 本身不实现任何平台的数据抓取逻辑，它只负责：
1. **安装**上游工具（CLI、Python 包、MCP 服务器）
2. **配置**认证信息（Cookie、API Key、环境变量）
3. **诊断**各渠道健康状态（doctor）
4. **路由** Agent 的请求（通过 SKILL.md）

### 1.2 目标用户

AI Agent（通过 OpenClaw / Claude Code 等框架调用），以及使用 Agent 的开发者。

### 1.3 技术栈

- **语言**：Python 3.10+，类型提示
- **日志**：loguru
- **CLI 输出**：rich（彩色终端输出）
- **配置**：YAML（`~/.agent-reach/config.yaml`）
- **包管理**：pyproject.toml，pip install
- **测试**：pytest

---

## 二、整体架构

### 2.1 核心模块

```
agent_reach/
├── cli.py              # CLI 入口点（argparse，约 1700 行）
├── core.py             # AgentReach 主类（43 行）
├── config.py          # Config 配置管理（110 行）
├── doctor.py           # 健康检查引擎（109 行）
├── cookie_extract.py   # 浏览器 Cookie 提取（268 行）
├── channels/           # 16 个平台渠道实现
│   ├── base.py         # Channel 抽象基类
│   ├── __init__.py     # 渠道注册表（ALL_CHANNELS）
│   └── [16 个平台文件]
├── integrations/
│   └── mcp_server.py   # MCP Server 实现（轻量）
├── skill/              # Agent 技能文件（路由表）
│   ├── SKILL.md        # 主路由器
│   └── references/     # 6 个分类详细文档
├── scripts/
│   └── transcribe_xiaoyuzhou.sh  # 小宇宙转录脚本
└── guides/            # 用户安装指南
```

### 2.2 架构原则

1. **Channel 契约**：每个平台独立文件，继承 `Channel` 抽象基类，实现 `can_handle(url)` 和 `check(config)` 方法
2. **零封装**：调用上游 CLI/API，不重复造轮子
3. **配置优先**：YAML 配置 > 环境变量 > 硬编码默认值
4. **渐进式复杂**：Tier 0（零配置）→ Tier 1（需要免费 Key）→ Tier 2（复杂 MCP 配置）

---

## 三、渠道注册与调度机制

### 3.1 渠道注册表

所有渠道在 `agent_reach/channels/__init__.py` 的 `ALL_CHANNELS` 列表中集中注册：

```python
ALL_CHANNELS = [
    GitHubChannel(),      # Tier 0
    TwitterChannel(),     # Tier 1
    YouTubeChannel(),    # Tier 0
    RedditChannel(),      # Tier 0
    BilibiliChannel(),    # Tier 1
    XiaoHongShuChannel(), # Tier 1
    DouyinChannel(),      # Tier 2
    LinkedInChannel(),    # Tier 2
    WeChatChannel(),      # Tier 0
    WeiboChannel(),       # Tier 1
    XiaoyuzhouChannel(),  # Tier 1
    V2EXChannel(),        # Tier 0
    XueqiuChannel(),      # Tier 1
    RSSChannel(),         # Tier 0
    ExaSearchChannel(),   # Tier 0
    WebChannel(),         # Tier 0（兜底）
]
```

顺序有讲究：**特殊渠道在前，通用的兜底渠道（RSS、Exa、Web）在最后**，保证 URL 匹配按优先级来。

### 3.2 16 个平台一览

| 平台 | Channel 类 | 上游工具 | Tier | 认证方式 | 备注 |
|------|-----------|---------|------|---------|------|
| Web | `WebChannel` | Jina Reader API | 0 | 无 | 通用兜底读取 |
| GitHub | `GitHubChannel` | `gh` CLI | 0 | Token（可选） | 免费限额 60req/h，认证 5000/h |
| YouTube | `YouTubeChannel` | `yt-dlp` | 0 | Cookie（可选） | 需要 Node.js 运行时 |
| Reddit | `RedditChannel` | `rdt-cli` | 0 | 无 | 公开 API |
| RSS | `RSSChannel` | `feedparser` | 0 | 无 | 内置 Python 库 |
| Bilibili | `BilibiliChannel` | `yt-dlp` + `bili-cli` | 1 | Cookie（SESSDATA） | 海外需要代理 |
| Exa Search | `ExaSearchChannel` | `mcporter` + Exa MCP | 0 | 无 | 搜索专用 |
| WeChat | `WeChatChannel` | Exa + Camoufox | 0 | 无 | 公众号文章 |
| Twitter/X | `TwitterChannel` | `twitter-cli` 或 `bird` | 1 | Cookie（auth_token + ct0） | 双 CLI 支持 |
| XiaoHongShu | `XiaoHongShuChannel` | `xhs-cli` | 1 | Cookie | xsec_token 限制 |
| Xueqiu | `XueqiuChannel` | Xueqiu API | 1 | Cookie（xq_a_token） | 股票+社区 |
| Xiaoyuzhou | `XiaoyuzhouChannel` | Groq Whisper + ffmpeg | 1 | Groq API Key | 播客转录 |
| Weibo | `WeiboChannel` | `mcp-server-weibo` + mcporter | 1 | MCP 登录 | |
| V2EX | `V2EXChannel` | V2EX 公开 API | 0 | 无 | |
| Douyin | `DouyinChannel` | `douyin-mcp-server` + mcporter | 2 | 无 | 需要 MCP 服务 |
| LinkedIn | `LinkedInChannel` | `linkedin-scraper-mcp` + mcporter | 2 | MCP 登录 | |

---

## 四、各渠道实现原理详解

### 4.1 Web 渠道 — 通用网页兜底

**原理**：调用 Jina Reader 的免费 API，将任意网页转换为 Markdown。

```bash
curl -s "https://r.jina.ai/https://example.com"
```

代码中使用 `urllib.request` 发起 HTTP 请求，设置 `User-Agent` 和 `Accept: text/plain` 请求头。始终返回 `"ok"`，因为它不依赖任何本地工具。

**适用场景**：任何未被专用渠道覆盖的网页。

---

### 4.2 GitHub 渠道 — gh CLI 封装

**原理**：直接调用 `gh` CLI，不做任何封装。

常用命令：
```bash
gh search repos "query" --sort stars --limit 10
gh repo view owner/repo
gh issue list -R owner/repo --state open
gh api /user
```

`check()` 方法执行 `gh auth status` 来判断是否已认证。

**Tier 0 的原因**：`gh` CLI 可通过系统包管理器安装，且 GitHub 公开 API 无需认证即可使用（有频率限制）。

---

### 4.3 YouTube 渠道 — yt-dlp

**原理**：
- 视频元数据：`yt-dlp --dump-json URL`
- 字幕提取：`yt-dlp --write-sub --skip-download -o "/tmp/%(id)s" URL`
- 评论提取：`yt-dlp --write-comments --skip-download URL`

**check() 的特殊性**：
1. 检查 `yt-dlp` 是否安装
2. 检查 Node.js 或 Deno 是否安装（YouTube 需要 JS 运行时）
3. 如果是 Node.js，还要验证 `yt-dlp.conf` 中包含 `--js-runtimes node`

---

### 4.4 Twitter 渠道 — 双 CLI 支持

**实现亮点**：同时支持 `twitter-cli`（首选）和 `bird`/`birdx`（遗留兼容）。

**Cookie 同步机制**：
1. 从浏览器提取 `auth_token` + `ct0`
2. 写入 `~/.agent-reach/config.yaml`（信任源）
3. 同步到 `~/.config/xfetch/session.json`（legacy xreach 兼容）
4. 同步到 `~/.config/bird/credentials.env`（bird CLI 环境变量文件）

**check() 的三种返回**：
- `ok`：CLI 存在 + `twitter status` 返回 `ok: true`
- `warn`：`not_authenticated` → 已装但未认证
- `warn`：其他异常 → 连接失败

---

### 4.5 XiaoHongShu 渠道 — xhs-cli + xsec_token 限制

**xsec_token 机制**：这是小红书平台的核心限制。
- 小红书强制要求通过搜索结果获取带 `xsec_token` 的 URL
- 不能直接用裸 `note_id` 构造 URL 访问（会被拦截）
- **正确流程**：`xhs search` → 获取 URL/ID → `xhs read URL`

**输出格式化**：`format_xhs_result()` 函数清理 API 原始响应，去掉冗余字段（`note_card` 嵌套、原始长字段），大幅降低 token 消耗。

**POST 操作问题**：发帖、评论、点赞在 v0.6.x 因签名问题可能返回 406，建议降级到 v0.3.5。

---

### 4.6 Xueqiu 渠道 — 三级 Cookie 回退

**Cookie 加载优先级（三层降级）**：
1. `~/.agent-reach/config.yaml` 中的 `xueqiu_cookie`
2. 从 Chrome 浏览器实时读取（rookiepy 或 browser_cookie3）
3. 访问首页获取 anti-DDoS cookie（`acw_tc`，但不足以访问股票 API）

**数据方法**：
- `get_stock_quote(symbol)`：批量行情（支持沪/深/美/港股）
- `search_stock(query)`：股票搜索
- `get_hot_posts(limit)`：雪球热门帖子（社区）
- `get_hot_stocks(limit)`：热股排行榜

**check() 逻辑**：调用 `SH000001` 的行情 API，成功返回数据即 OK。

---

### 4.7 Xiaoyuzhou 渠道 — 播客转录

**工作流**：
1. 解析小宇宙播客页面，提取音频 URL
2. `curl` 下载音频
3. `ffmpeg` 转换为 mono MP3（64kbps，Groq 要求）
4. 如果 > 20MB（Grov 限制 25MB，保险起见用 20MB），分段
5. 每段调用 Groq Whisper API
6. 合并所有转录文本

**check() 检查**：ffmpeg + `~/.agent-reach/tools/xiaoyuzhou/transcribe.sh` + `GROQ_API_KEY`。

---

### 4.8 Douyin / LinkedIn / Weibo — MCP 架构

这三个渠道使用 **MCP（Model Context Protocol）** 作为通信层：

```
Agent-Reach (mcporter)
    └── mcporter (NPM 全局工具)
            ├── exa (HTTP MCP, 远程)
            ├── douyin (本地 MCP Server)
            ├── linkedin (本地 MCP Server)
            └── weibo (本地 MCP Server)
```

**mcporter** 是核心枢纽（`npm install -g mcporter`）：
- `mcporter list <server>` — 列出某 MCP 服务可用工具
- `mcporter call '<tool(args)>'` — 调用工具
- `mcporter config add <name> <url>` — 添加 MCP 服务

**check() 的通用模式**：
1. 检查 `mcporter` 是否安装
2. 检查对应的 MCP 服务是否在 `mcporter config list` 中
3. 调用 `mcporter list <server>` 验证工具列表非空

---

### 4.9 WeChat 渠道 — 公众号文章

**双层策略**：
- **主**：Exa MCP 的 `web_search_exa` + `crawling_exa`（`includeDomains: mp.weixin.qq.com`）
- **备**：Camoufox（无头浏览器，可选安装）

公众号文章被微信做了反爬处理，Jina Reader 效果差，所以依赖 Exa 的爬取能力或 Camoufox 的无头浏览。

---

## 五、配置系统

### 5.1 配置文件路径

`~/.agent-reach/config.yaml`，权限 0o600（仅所有者可读写）。

### 5.2 加载优先级

```
config.get("key")
    ├── ~/.agent-reach/config.yaml 中的 key
    ├── 环境变量（KEY_UPPERCASE）
    └── default
```

### 5.3 敏感信息处理

`to_dict()` 方法对包含 `key`/`token`/`password`/`proxy` 的配置值做脱敏，只显示前 8 个字符。

### 5.4 安全检查

`doctor.py` 的 `format_report()` 会检查 `config.yaml` 的权限，如果其他用户可读（`S_IRGRP | S_IROTH`），会输出警告并提示修复命令。

---

## 六、Cookie 提取系统

### 6.1 支持的平台和 Cookie

| 平台 | 域名 | 需要的 Cookie | Config Key |
|------|------|-------------|-----------|
| Twitter/X | .x.com, .twitter.com | `auth_token`, `ct0` | `twitter_auth_token`, `twitter_ct0` |
| XiaoHongShu | .xiaohongshu.com | 全部（header 字符串） | `xhs_cookie` |
| Bilibili | .bilibili.com | `SESSDATA`, `bili_jct` | `bilibili_sessdata`, `bilibili_csrf` |
| Xueqiu | .xueqiu.com | 全部（含 `xq_a_token`） | `xueqiu_cookie` |

### 6.2 提取工具优先级

1. **rookiepy**（Rust 实现，推荐，更稳定）
2. **browser_cookie3**（Python 备选）

### 6.3 浏览器支持

Chrome、Firefox、Edge、Brave、Opera。

### 6.4 使用方式

```bash
agent-reach configure --from-browser chrome
```

这会自动从 Chrome 提取所有支持平台的 Cookie 并写入 config.yaml。

---

## 七、Doctor 诊断系统

### 7.1 检查流程

```
cli doctor
    → AgentReach.doctor()
    → check_all(config)
    → 遍历 ALL_CHANNELS，调用 ch.check(config)
    → format_report(results)
    → 渲染 Rich 格式彩色报告
```

### 7.2 状态分类

| 状态 | 含义 | 显示颜色 |
|------|------|---------|
| `ok` | 完全可用 | 绿色 ✅ |
| `warn` | 已安装但配置不全 | 黄色 ⚠ |
| `off` | 未安装 | 红色 ✗ |
| `error` | 检查失败 | 红色 ✗ |

### 7.3 分组显示

- **Tier 0**：装好即用（绿色标题）
- **Tier 1**：可选渠道（已安装/未安装）
- **Tier 2**：可选渠道（复杂配置）

---

## 八、MCP Server 集成

### 8.1 实现方式

轻量级 MCP Server（`mcp_server.py`），只暴露一个工具：

```python
Tool: get_status
  → 调用 AgentReach.doctor_report()
  → 返回彩色健康报告
```

### 8.2 mcporter.json 配置

`config/mcporter.json` 定义了所有远程 MCP 服务端点：

```json
{
  "mcpServers": {
    "exa": { "baseUrl": "https://mcp.exa.ai/mcp" },
    "xiaohongshu": { "baseUrl": "http://localhost:18060/mcp" }
  }
}
```

---

## 九、Skill 系统（Agent 路由）

### 9.1 SKILL.md — 主路由器

位于 `agent_reach/skill/SKILL.md`，是 Agent 的入口文件，包含：
- **触发词**（triggers）：意图分类
- **路由表**：意图 → 分类 → 详细文档
- **零配置快速命令**：常用命令速查
- **安装目录**：`~/.agents/skills/agent-reach/`（优先）、`~/.openclaw/skills/`、`~/.claude/skills/`

### 9.2 6 个分类参考文档

| 文档 | 覆盖平台 | 内容 |
|------|---------|------|
| `search.md` | Exa | 搜索命令、参数 |
| `social.md` | 小红书/抖音/Twitter/微博/B站/V2EX/Reddit | 各平台稳定命令、已知坑 |
| `web.md` | Jina Reader/微信/RSS | 网页读取、RSS 解析 |
| `video.md` | YouTube/B站/小宇宙 | 字幕下载、转录 |
| `dev.md` | GitHub | gh CLI 命令 |
| `career.md` | LinkedIn | 职位搜索、资料获取 |

---

## 十、测试覆盖

### 10.1 测试文件

| 文件 | 覆盖内容 |
|------|---------|
| `test_channel_contracts.py` | 渠道注册契约、URL 路由、YouTube JS 运行时 |
| `test_channels.py` | V2EX、Xueqiu、XiaoHongShu 实现 |
| `test_cli.py` | CLI 命令、Cookie 解析、更新检查重试 |
| `test_config.py` | 配置加载、环境变量覆盖、文件权限 |
| `test_core.py` | AgentReach 类初始化 |
| `test_doctor.py` | 健康检查聚合、报告格式化 |
| `test_skill_command.py` | Skill 安装/卸载 |
| `test_twitter_channel.py` | Twitter CLI 检测、认证状态 |
| `test_xhs_format.py` | XHS 输出格式化 |
| `test_xiaoyuzhou_install.py` | 小宇宙依赖检查 |

### 10.2 测试原则

- 不 mock 数据库（依赖真实环境）
- 配置测试用临时路径隔离
- 集成测试通过 `bash test.sh` 运行

---

## 十一、外部依赖全景图

### 11.1 按依赖来源分类

**Python 内置 / 核心依赖**：
- `requests`（HTTP 调用）
- `feedparser`（RSS 解析）
- `urllib`（内置）
- `yaml`（PyYAML）

**需要安装的 CLI 工具**：
- `gh`（系统包管理器）
- `yt-dlp`（pip/conda）
- `mcporter`（npm）
- `twitter-cli`（pipx/uv）
- `rdt-cli`（pipx）
- `xhs-cli`（pipx）

**MCP 服务器**（需本地启动）：
- `douyin-mcp-server`（pip + 手动启动）
- `linkedin-scraper-mcp`（pip + 手动启动）
- `mcp-server-weibo`（pip + 手动启动）

**浏览器 Cookie 提取**：
- `rookiepy`（Rust，高性能）
- `browser_cookie3`（Python 备选）

**可选增强**：
- `Camoufox`（无头浏览器，WeChat 增强）
- `mcp`（Python MCP SDK）

### 11.2 版本管理要点

版本号在三个地方必须保持一致：
1. `pyproject.toml`
2. `agent_reach/__init__.py`
3. `tests/test_cli.py`（doctor 输出的版本号）

---

## 十二、CLI 命令体系

### 12.1 核心命令

```
agent-reach doctor          # 健康检查
agent-reach install        # 安装渠道
agent-reach setup          # 交互式配置向导
agent-reach configure      # 设置配置项
agent-reach configure --from-browser chrome  # 自动提取 Cookie
agent-reach uninstall      # 卸载
agent-reach skill --install   # 安装 SKILL.md
agent-reach skill --uninstall # 卸载 SKILL.md
agent-reach check-update   # 检查更新
```

### 12.2 install 的环境参数

- `--env=local`：本地开发环境
- `--env=server`：服务器环境
- `--env=auto`：自动检测
- `--safe`：预览要安装的内容，不实际安装
- `--dry-run`：模拟运行
- `--channels=...`：指定安装特定渠道

---

## 十三、架构设计亮点与局限

### 13.1 亮点

1. **Channel 契约简洁**：只需实现两个方法即可扩展新平台
2. **Tier 渐进式复杂度**：用户体验清晰，从零配置到高级配置
3. **Cookie 提取自动化**：一行命令搞定所有平台认证
4. **双 CLI 兼容**：Twitter 同时支持 twitter-cli 和 bird，降低单点依赖风险
5. **Skill 路由**：Agent 无需硬编码指令，通过 SKILL.md 动态路由
6. **配置安全**：0o600 权限、安全提示
7. **输出格式化**：XHS 等平台的 token 优化（`format_xhs_result`）

### 13.2 局限与风险

1. **上游强依赖**：几乎所有渠道都依赖第三方上游工具/API，任何上游变更都可能破坏功能（如 Twitter 改 GraphQL 端点）
2. **Cookie 失效**：所有 Cookie 认证的平台都面临登录失效问题，Cookie-Editor 导出方法相对稳定但仍需手动更新
3. **MCP 架构复杂度**：Douyin/LinkedIn/Weibo 需要本地启动 MCP 服务，用户配置门槛高
4. **xsec_token 限制**：小红书的 token 机制导致无法直接用 note_id 访问，需要两步操作
5. **IP 风控**：Twitter API 对数据中心 IP 敏感，VPS 使用有封号风险
6. **没有写入操作**：Agent-Reach 是纯读取工具，不支持发帖、评论等写操作（这是设计选择，但也限制了用途）
7. **测试覆盖率**：部分渠道（尤其是 MCP 相关）缺乏深度测试

---

## 十四、未来可能的演进方向

（基于代码分析推断，供调整改造参考）

1. **写入操作**：可以扩展部分渠道的写入能力（发小红书帖、发 Twitter）
2. **更多 Tier 0 渠道**：持续降低配置门槛
3. **缓存层**：对频繁访问的内容增加本地缓存（减少 API 调用）
4. **流式响应**：对长内容（YouTube 字幕、长推文）增加流式输出
5. **统一输出格式**：各渠道目前输出格式各异，可考虑统一 JSON 输出
6. **Webhook/通知**：当关注的内容更新时主动推送（Twitter 监测等）
7. **多语言支持**：SKILL.md 目前主要是中文，可扩展英文路由
8. **配置文件云同步**：在多设备场景下同步 Cookie/Key

---

## 附录：关键文件速查

| 文件 | 行数 | 核心职责 |
|------|------|---------|
| `cli.py` | ~1700 | 所有 CLI 命令、argparse、install/setup/configure |
| `cookie_extract.py` | 268 | 浏览器 Cookie 提取、平台同步 |
| `channels/__init__.py` | 66 | 渠道注册表 |
| `doctor.py` | 109 | 健康检查 + 报告渲染 |
| `config.py` | 110 | YAML 配置读写、权限管理 |
| `mcp_server.py` | 68 | MCP Server（轻量） |
| `transcribe_xiaoyuzhou.sh` | ~150 | 小宇宙播客转录脚本 |

---

*文档版本：1.0 | 生成时间：2026-04-01*
