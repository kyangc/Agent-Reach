# 小红书 (XiaoHongShu) 配置指南

## 功能说明

读取和搜索小红书笔记。通过 [xhs-cli](https://github.com/RES的一方/xiaohongshu-cli)（pipx install xiaohongshu-cli）实现，无需 Docker。

## 前置条件

- pipx（用来安装 xhs-cli）
- pipx 已安装：`python3 -m pip install pipx && pipx ensurepath`

## Agent 可自动完成的步骤

### 1. 安装 xhs-cli
```bash
pipx install xiaohongshu-cli
```

或使用 uv：
```bash
uv tool install xiaohongshu-cli
```

### 2. 验证安装
```bash
xhs --version
```

## 需要用户手动做的步骤

### 方式一：自动浏览器登录（推荐）
```bash
xhs login
```
`xhs login` 会自动打开浏览器，跳转到小红书登录页面。登录成功后，Cookie 自动保存到 `~/.xiaohongshu-cli/cookies.json`。

### 方式二：Cookie-Editor 导出
1. 在 Chrome 浏览器中登录 [xiaohongshu.com](https://xiaohongshu.com)
2. 安装 [Cookie-Editor](https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm) Chrome 插件
3. 点击插件图标 → **Export** → 选择 **Header String** 格式
4. 把导出的字符串发给 Agent：
   ```bash
   agent-reach configure xhs-cookies "a1=xxx; web_session=yyy; ..."
   ```

> **Cookie 安全提醒**：Cookie 等同于完整登录权限，建议使用**专用小号**，不要用主账号。

## 验证
```bash
xhs status
```
如果显示已登录，说明认证成功。

## 使用方式

| 操作 | 命令 |
|------|------|
| 读取笔记 | `xhs read <url>` |
| 搜索笔记 | `xhs search <keyword>` |
| 查看登录状态 | `xhs status` |

## 常见问题

**Q: `xhs login` 提示找不到命令？**
A: 确认安装成功：
```bash
pipx ensurepath   # 确保 pipx 安装路径在 PATH 中
pipx install xiaohongshu-cli
```

**Q: Cookie 导入后还是显示未登录？**
A:
1. 检查 Cookie 是否包含 `a1` 字段（必须）
2. 确认 Cookie 没有过期（重新导出一次）
3. 运行 `xhs status` 查看详细错误信息

**Q: 服务器/海外 IP 无法访问小红书？**
A: 本地电脑通常没有问题。服务器环境可能需要代理（xhs-cli 支持 HTTP_PROXY 环境变量）。
