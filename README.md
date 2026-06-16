# boss-cli

终端版 BOSS 直聘 — 搜索职位、查看推荐、管理投递、与招聘者沟通。

## 功能

- 🔐 **登录** — 自动提取浏览器 Cookie，支持二维码扫码登录
- 🔍 **搜索** — 按关键词/城市/薪资/经验/学历/行业/规模/融资阶段/职位类型筛选
- ⭐ **推荐** — 基于求职期望的个性化推荐
- 📋 **详情 & 导出** — 职位详情、编号导航、CSV/JSON 导出
- 💬 **沟通** — 查看沟通过列表、打招呼、批量投递
- 👤 **个人** — 查看个人资料、投递记录、面试邀请、浏览历史
- 👔 **招聘方模式** — 查看职位、候选人管理、聊天、简历下载、导出
- 🏙️ **城市** — 40+ 城市支持

## 安装

```bash
pip install kabi-boss-cli
```

从源码安装:

```bash
git clone https://github.com/heliumgenius/boss-.git
cd boss-
pip install .
```

## 使用

```bash
# ─── 登录 ─────────────────────────────────────────
boss login                             # 自动提取浏览器 Cookie
boss login --cookie-source chrome      # 指定浏览器
boss status                            # 检查登录状态
boss logout                            # 清除登录态

# ─── 搜索 ─────────────────────────────────────────
boss search "Python"                   # 搜索职位
boss search "Python" --city 北京       # 按城市筛选
boss search "Go" --salary 20-30K       # 按薪资筛选

# ─── Edge Cookie 扩展（解决 v20 加密）─────────────
# 先启动服务器:
python -m boss_cli.cookie_server
# 在 edge://extensions 加载 extension/ 目录
# 登录 zhipin.com 后扩展自动推送 Cookie

# ─── 详情 & 导出 ────────────────────────────────
boss show 3                            # 查看上次搜索第 3 条
boss detail <securityId>               # 查看职位详情
boss export "Python" -o jobs.csv       # 导出 CSV

# ─── 推荐 & 历史 ────────────────────────────────
boss recommend                         # 个性化推荐
boss history                           # 浏览历史

# ─── 个人中心 ──────────────────────────────────
boss me                                # 个人资料
boss applied                           # 已投递
boss interviews                        # 面试邀请
boss chat                              # 沟通列表

# ─── 打招呼 ────────────────────────────────────
boss greet <securityId>                # 打招呼/投递
boss batch-greet "Python" -n 5         # 批量打招呼

# ─── 招聘方模式 ────────────────────────────────
boss recruiter jobs                    # 查看招聘职位
boss recruiter search "Go" --city 深圳 # 搜索候选人
boss recruiter inbox                   # 查看候选人消息
boss recruiter export -o cand.csv      # 导出候选人
```

## 项目结构

```text
boss_cli/
├── __init__.py
├── cli.py                # CLI 入口
├── auth.py               # 认证（浏览器 Cookie、二维码、扩展服务器）
├── cookie_server.py      # Edge Cookie 接收服务器
├── constants.py          # 常量
├── exceptions.py         # 异常
├── client/               # API 客户端
│   ├── transport.py      # HTTP 传输
│   ├── antidetect.py     # 反检测
│   └── throttle.py       # 频率控制
└── commands/             # 子命令
    ├── auth.py
    ├── search.py
    ├── personal.py
    ├── social.py
    └── recruiter.py

extension/                # Edge 浏览器扩展
├── manifest.json
├── background.js
└── popup.html/js
```

## 授权

Apache-2.0
