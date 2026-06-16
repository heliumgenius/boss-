# Web UI — 自然语言搜索与批量操作

## 概述

为 boss-cli 增加一个本地 Web 界面，用户通过一句话自然语言进行职位搜索，
并对结果进行多选、批量打招呼/投递简历。

## 架构

```
浏览器 (HTMX)
    │ POST /search, POST /batch-greet, SSE
    ▼
FastAPI 服务器 (web_ui/app.py)
    ├── parser.py        — 自然语言 → 结构化搜索参数
    ├── BossClient       — 复用 CLI 的 BOSS API 客户端
    ├── SQLite           — 搜索历史/会话缓存
    └── SSE stream       — 批量操作进度推送
```

## 用户流程

```
输入框输入自然语言
    │
    ▼
POST /search → parser 解析 → BossClient.search_jobs
    │
    ▼
结果列表（带复选框，HTMX 渲染）
    │
    ├─→ 勾选单个/多个 → 点击「打招呼」 → SSE 进度
    ├─→ 勾选单个/多个 → 点击「投递简历」 → SSE 进度
    └─→ 勾选单个/多个 → 点击「导出」
```

## 页面布局（单页）

从顶部到底部：

1. **输入区** — 文本框 + 搜索按钮
2. **解析预览** — 自动展示识别到的参数标签（城市/薪资/经验/学历），允许调整
3. **结果列表** — 表格：复选框 + 编号 + 职位名 + 公司 + 薪资 + 经验 + 学历
4. **操作栏** — 全选 / 已选 N 个 / [打招呼] [投递简历] [导出 CSV]
5. **进度面板** — SSE 驱动，逐行更新批量操作状态

## 自然语言解析（规则引擎）

无需 LLM。规则如下：

| 输入片段 | 提取结果 |
|----------|----------|
| `杭州`、`北京`、`上海` | city（从城市词表匹配） |
| `20k以上`、`20-30k`、`15K-25K` | salary（映射到薪资代码） |
| `3年`、`3-5年`、`3年以上` | experience |
| `本科`、`硕士`、`大专` | degree |
| `Python`、`golang`、`Java` | keyword（剩余文本） |

城市词表复用 CLI 已有的 `CITY_CODES`。薪资/经验/学历代码复用 `SALARY_CODES`、`EXP_CODES`、`DEGREE_CODES`。

## 搜索流程

```
POST /search {query: "找杭州Python 20k以上"}

1. parser.parse(query) → {keyword: "Python", city: "杭州", salary: "20-30K"}
2. client.search_jobs(keyword, city_code, salary_code, ...)
3. 获取 job_list，若有多页则逐页拉取（SSE 推送翻页进度）
4. 返回 HTMX HTML 片段（表格行）
```

## 批量操作

### 打招呼 (batch-greet)

```
POST /batch-greet {ids: ["secId1", "secId2", ...], lid: "..."}

→ SSE stream, 每个事件格式:
event: progress
data: {"index": 1, "job_name": "Python后端", "company": "阿里", "status": "ok|fail", "message": "成功"}

event: complete
data: {"success": 10, "fail": 2}
```

逐条调用 `BossClient.add_friend()`，间隔 1.5s 避免频率限制。

### 投递简历 (batch-apply)

同上，逐条调用 `BossClient.add_friend()`（BOSS 的投递和打招呼是同一接口）。

## SSE 进度面板

```
┌─────────────────────────────────────────────────────────┐
│ 对 12 个职位执行批量打招呼...                             │
│                                                         │
│ [████████████░░░░░░░░░░░░] 5/12                         │
│                                                         │
│ #1  Python后端 @ 阿里巴巴     ✅ 成功                   │
│ #2  数据分析师 @ 网易         ✅ 成功                   │
│ #3  Go开发 @ 字节跳动         ❌ 失败: 已打过招呼       │
│ #4  Python工程师 @ 蚂蚁集团   🔄 发送中...              │
│ #5  ...                                                  │
│                                                         │
│ [关闭]                                                  │
└─────────────────────────────────────────────────────────┘
```

## 文件结构

```
boss_cli/web_ui/
├── __init__.py
├── app.py               # FastAPI 应用、路由、SSE
├── parser.py            # 自然语言规则解析器
├── templates/
│   └── index.html       # 单页 UI（HTMX 片段）
└── static/
    └── style.css        # 基础样式
```

## 依赖

- `fastapi` — Web 框架
- `uvicorn` — ASGI 服务器
- `jinja2` — 模板引擎（FastAPI 内置）
- `httpx` — 已安装

## 不包含的范围（YAGNI）

- 用户登录/鉴权（仅本地使用）
- LLM API 集成（规则解析足够）
- 持久化数据库（SQLite 仅做会话缓存，非核心功能）
- WebSocket（SSE 足够轻量）
- 移动端适配（仅桌面浏览器）

## 复用现有代码

| 模块 | 复用方式 |
|------|----------|
| `boss_cli.client.BossClient` | 搜索、打招呼、投递均直接复用 |
| `boss_cli.constants.CITY_CODES` | 城市解析与代码映射 |
| `boss_cli.constants.SALARY_CODES` | 薪资范围解析 |
| `boss_cli.constants.EXP_CODES` | 经验年限解析 |
| `boss_cli.constants.DEGREE_CODES` | 学历解析 |
| `boss_cli.auth.load_credential` | 加载 cookie 凭证 |
