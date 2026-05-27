# AIWaveBrief 部署指南

## 快速开始

### 前置要求

- Python 3.11+ 或 Docker
- Firecrawl API Key（[获取](https://firecrawl.dev)）
- OpenAI API Key（[获取](https://platform.openai.com/api-keys)）

### 方式一：本地运行

```bash
# 1. 克隆项目
git clone <repo-url> && cd AIWaveBrief

# 2. 创建虚拟环境
python -m venv .venv && source .venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API keys

# 5. 单次运行
python main.py

# 6. 定时模式（后台持续运行）
python main.py --daemon
```

### 方式二：Docker 部署（推荐）

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env 填入必要的 API keys 和推送配置

# 2. 修改 config.yaml 启用调度
# 设置 schedule.enabled: true

# 3. 一键启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止
docker-compose down
```

---

## 配置说明

### 环境变量

所有 `config.yaml` 中的配置均可通过环境变量覆盖，格式为 `AIWAVEBRIEF_<段名>_<字段名>`。

| 环境变量 | 说明 | 示例 |
|----------|------|------|
| `FIRECRAWL_API_KEY` | Firecrawl 抓取服务密钥 | `fc-xxx` |
| `OPENAI_API_KEY` | OpenAI API 密钥 | `sk-xxx` |
| `AIWAVEBRIEF_SCHEDULE_ENABLED` | 启用定时调度 | `true` |
| `AIWAVEBRIEF_SCHEDULE_TIME` | 每日执行时间 | `08:00` |
| `AIWAVEBRIEF_PUSH_ENABLED` | 启用推送 | `true` |

完整变量列表见 `.env.example`。

### 邮件推送配置

在 `config.yaml` 的 `push.channels` 中配置邮件，或通过环境变量：

```yaml
push:
  enabled: true
  channels:
    - type: email
      smtp_host: "smtp.gmail.com"
      smtp_port: 465
      smtp_ssl: true
      smtp_user: "your@gmail.com"
      smtp_password: "app-password"
      from_addr: "your@gmail.com"
      to_addrs:
        - "recipient@example.com"
```

Gmail 用户需要使用[应用专用密码](https://support.google.com/accounts/answer/185833)。

### Webhook 推送

```yaml
push:
  enabled: true
  channels:
    - type: webhook
      url: "https://your-webhook-url.com/notify"
      headers:
        Authorization: "Bearer your-token"
```

Webhook 将 POST JSON 格式的简报内容。

---

## CLI 命令

```bash
# 单次运行（默认）
python main.py

# 定时调度模式
python main.py --daemon

# 查看历史简报列表
python main.py --history

# 查看指定日期简报
python main.py --history --date 2024-01-15

# 搜索历史简报
python main.py --history --search "GPT"

# 查看运行状态
python main.py --health
```

---

## 数据目录

```
data/
├── dedup.db        # 去重数据库（URL 和标题记录）
├── history.db      # 历史简报索引
├── health.db       # 运行统计
└── aiwavebrief.log # 运行日志（自动轮转，10MB × 5）

output/
└── YYYY-MM-DD/
    ├── raw.json       # 原始抓取数据
    ├── summaries.json # 摘要数据
    └── brief.md       # 最终简报
```

---

## 功能特性

| 功能 | 配置项 | 默认 |
|------|--------|------|
| 定时调度 | `schedule.enabled` | 关闭 |
| 跨次去重 | `dedup.enabled` | 开启 |
| 邮件推送 | `push.enabled` + channels | 关闭 |
| 历史存档 | `history.enabled` | 开启 |
| 结构化日志 | `logging.format` | structured |
| 并发抓取 | `scraping.max_workers` | 3 |

---

## 故障排查

1. **查看日志**: `cat data/aiwavebrief.log` 或 `docker-compose logs`
2. **检查运行状态**: `python main.py --health`
3. **API 密钥问题**: 确认 `.env` 中的 key 正确且有效
4. **邮件发送失败**: 检查 SMTP 配置，Gmail 需使用应用专用密码
5. **抓取失败率高**: 增加 `scraping.retry_delay_seconds`，减少 `scraping.max_workers`
