# Edge Cookie 扩展方案

通过 Edge 浏览器扩展绕过 v20 磁盘加密，从浏览器内存中读取 `__zp_stoken__`。

## 问题

Edge 120+ 使用 AES-256-GCM-SIV 加密 Cookie 值（v20 格式），解密密钥受 SYSTEM DPAPI 保护，普通用户进程无法读取。导致 `browser-cookie3`、`edge_cookie_extractor.py` 等方案无法获取 `__zp_stoken__`。

## 方案原理

Chromium 扩展的 `chrome.cookies.getAll()` API 从浏览器进程内存中读取 cookie 值，**不受磁盘加密影响**。扩展将读取到的 cookie 推送到本地 HTTP 服务器，服务器写入 `credential.json`，CLI 自动读取。

```
Edge（已登录 zhipin.com）
  │
  ├── Extension (background.js)
  │   ├── chrome.alarms 每 60s 轮询
  │   ├── chrome.cookies.onChanged 实时推送
  │   └── 断连重试 3 次（间隔 1s）
  │
  └── → fetch POST http://127.0.0.1:9876/cookies
          │
          cookie_server.py
          │
          └── → credential.json → boss search/recommend/...
```

## 设置步骤

### 1. 启动 Cookie 服务器

```powershell
# 方法 A：CLI 子命令（推荐，后台运行）
boss cookie-server start

# 方法 B：直接运行（前台，新开终端）
python -m boss_cli.cookie_server

# 方法 C：一键脚本（启动服务器 + 打开 Edge）
start-boss.bat
```

### 2. 加载扩展

1. 打开 Edge 浏览器，地址栏输入 `edge://extensions/`
2. 开启右上角 **开发者模式**
3. 点击 **加载解压缩的扩展**
4. 选择项目中的 `extension/` 目录

### 3. 验证

```powershell
# 检查服务器和登录态
boss doctor

# 检查 cookie 状态
boss cookie-server status
```

## 命令说明

| 命令 | 说明 |
|------|------|
| `boss cookie-server start` | 后台启动服务器 |
| `boss cookie-server stop` | 停止服务器 |
| `boss cookie-server status` | 查看运行状态 |
| `boss doctor` | 诊断全部环境 |

## 故障排查

| 问题 | 原因 | 解决 |
|------|------|------|
| `Server not running` | 服务器未启动 | `boss cookie-server start` |
| `Cookies: none` | 扩展未连接 | 检查 Edge 是否加载了扩展 |
| `__zp_stoken__: missing` | 未登录 zhipin.com | 在 Edge 中登录 BOSS |
| `环境异常` | Cookie 过期 | 扩展每 60s 自动续期，等待即可 |
