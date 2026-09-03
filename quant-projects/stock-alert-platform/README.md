# 股票监控报警平台

> A股策略监控报警系统：支持自定义策略热加载、双源行情兜底、钉钉/邮件多渠道告警、Docker容器化部署。

## 系统架构

```
                         ┌─────────────────────────────────────────┐
                         │              云服务器 (Docker)            │
   钉钉 Webhook    ─────►│   ┌──────────┐    ┌──────────────────┐   │
   邮件 SMTP       ─────►│   │ Notifier │◄───│     Engine       │   │
                         │   └──────────┘    │ (APScheduler 定时)│   │
                         │        ▲          └────────┬─────────┘   │
                         │        │                   │ 调用        │
                         │   ┌────┴─────┐      ┌──────▼──────┐      │
   行情源                 │   │ Storage  │      │ DataFeed    │      │
   Tushare/AkShare ──────┼──►│ (SQLite) │      │(限流/重试/兜底)│    │
                         │   └────┬─────┘      └──────┬──────┘      │
                         │        │                   │            │
                         │   ┌────┴───────────────────┴────┐       │
                         │   │  strategies/ (用户自定义)    │       │
                         │   │  MACross / Breakout / RSI … │       │
                         │   └────────────────────────────┘       │
                         │        ▲                                │
                         │   ┌────┴─────┐                         │
                         │   │  Flask    │  ── 浏览器/手机看板      │
                         │   │  Web看板  │                         │
                         │   └──────────┘                         │
                         └─────────────────────────────────────────┘
```

## 核心特性

- **策略热加载**: 策略写成独立Python文件，修改后自动生效，无需重启
- **双源兜底**: Tushare为主数据源，AkShare为备用，主源失效自动切换
- **去重冷却**: 同一(策略:标的)在冷却时间内只告警一次，避免刷屏
- **交易时段判断**: 自动识别A股交易时段，非交易时段跳过轮询
- **7×24自重启**: 调度器崩溃后30秒自动重启，Docker `restart: unless-stopped`

## 文件说明

| 文件 | 职责 |
|------|------|
| `main.py` | 程序入口：加载配置 → 初始化组件 → 启动Web看板 → 启动定时调度 |
| `engine.py` | 引擎核心：交易时段判断 → 选股 → 拉取多周期K线 → 运行策略 → 去重告警 |
| `datafeed.py` | 行情层：A股代码转换、复权处理、限流、Tushare→AkShare兜底 |
| `notifier.py` | 告警层：钉钉Webhook机器人 + 邮件SMTP |
| `storage.py` | 存储层：SQLite + SQLAlchemy，存监控标的、告警历史、策略状态 |

## 策略示例

```python
# strategies/macd_cross.py
from strategies.base import BaseStrategy, Signal

class MacdGoldenCross(BaseStrategy):
    name = "MACD金叉预警"
    def evaluate_pool(self, ctx):
        # 遍历监控池，检测MACD金叉
        signals = []
        for sym in ctx.pool:
            bars = ctx.min_bars("60", sym)
            if len(bars) < 26: continue
            # ... 计算MACD ...
            if 金叉条件满足:
                signals.append(Signal(...))
        return signals
```

## 部署

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 TUSHARE_TOKEN / DINGTALK_WEBHOOK 等

# 2. Docker部署
docker compose up -d --build

# 3. 查看日志
docker compose logs -f

# 4. 打开看板
# http://服务器IP:8080
```

## 配置

`config.yaml`:
```yaml
scan_interval_seconds: 90      # 轮询间隔（交易时段内）
cooldown_minutes: 60            # 同一(策略:标的)告警冷却
screener_hour: 16               # 每日选股时间（收盘后）
screener_minute: 10
symbols:                        # 监控标的
  - {code: "600519.SH", name: "贵州茅台"}
```

## 技术栈

- Python 3.11
- Flask + SQLAlchemy
- APScheduler
- Tushare / AkShare
- Docker + docker-compose

## 风险边界

**当前版本只监控报警，不自动下单。** 如需自动交易需额外接入券商API并增加风控模块。
