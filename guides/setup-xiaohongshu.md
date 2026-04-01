# 小红书 (XiaoHongShu) 配置指南

## 快速安装

```bash
pipx install xiaohongshu-cli
```

或使用 `uv`:

```bash
uv tool install xiaohongshu-cli
```

安装完成后，验证是否成功:

```bash
xhs --version
```

---

## 登录认证

### 方式一：自动浏览器登录（推荐）

```bash
xhs login
```

`xhs login` 会自动打开浏览器，跳转到小红书登录页面。登录成功后，Cookie 会自动保存到 `~/.xiaohongshu-cli/cookies.json`，无需手动复制粘贴。

### 方式二：Cookie-Editor 导出（备选）

如果你无法使用浏览器登录，可以通过 Cookie-Editor 插件导出 Cookie：

1. 在 Chrome 浏览器中登录 [xiaohongshu.com](https://xiaohongshu.com)
2. 安装 [Cookie-Editor](https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm) Chrome 插件
3. 点击插件图标 → **Export** → 选择 **Header String** 格式
4. 把导出的字符串发给 Agent：

```bash
agent-reach configure xhs-cookies "a1=xxx; web_session=yyy; ..."
```

或导出 **JSON** 格式：

```bash
agent-reach configure xhs-cookies '[{"name":"web_session","value":"xxx","domain":".xiaohongshu.com",...}]'
```

> **Cookie 安全提醒**：Cookie 等同于完整登录权限，建议使用**专用小号**，不要用主账号。

---

## 验证登录状态

```bash
xhs status
```

如果显示已登录，说明认证成功，可以开始使用。

---

## 使用方式

| 操作 | 命令 |
|------|------|
| 读取笔记 | `xhs read <url>` |
| 搜索笔记 | `xhs search <keyword>` |
| 查看登录状态 | `xhs status` |

示例：

```bash
# 读取一条小红书笔记
xhs read https://www.xiaohongshu.com/explore/xxxxx

# 搜索关键词
xhs search "咖啡店推荐"

# 检查登录状态
xhs status
```

---

## 常见问题

**Q: `xhs login` 提示找不到命令？**

确认安装成功：
```bash
pipx ensurepath   # 确保 pipx 安装路径在 PATH 中
pipx install xiaohongshu-cli
```

**Q: Cookie 登录后还是显示未登录？**

1. 检查 Cookie 是否包含 `a1` 字段（必须）
2. 确认 Cookie 没有过期（重新导出一次）
3. 运行 `xhs status` 查看详细错误信息

**Q: 服务器/海外 IP 无法访问小红书？**

小红书对海外 IP 有访问限制，本地电脑使用通常没有问题。服务器环境可能需要代理。

---

## 相关链接

- xhs-cli GitHub: [github.com/RES的一方/xiaohongshu-cli](https://github.com/RES的一方/xiaohongshu-cli)
- Cookie-Editor: [Chrome Web Store](https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm)
