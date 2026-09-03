# A股量化项目集

> 个人量化研究项目仓库，覆盖「数据采集 → 数据存储 → 策略回测 → 监控告警 → 归因分析」完整链路。

## 项目概览

| 项目 | 定位 | 技术栈 | 核心成果 |
|------|------|--------|---------|
| [limit-up-backtest](./limit-up-backtest/) | A股连板竞价策略回测 | Python, pandas, MySQL | 287笔信号回测，组合胜率66.7%，完整归因报告 |
| [stock-alert-platform](./stock-alert-platform/) | 股票监控报警平台 | Python, Flask, Docker, SQLite | 6层架构，双源兜底，策略热加载，7×24监控 |
| [quant-db](./quant-db/) | A股量化行情数据库 | PostgreSQL, MySQL, Python | 14张表，1.97亿行数据迁移，覆盖断层分析 |

## 能力地图

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  数据采集    │ →  │  数据存储    │ →  │  策略回测    │ →  │  监控告警    │ →  │  归因分析    │
│  (Tushare   │    │  (quant-db) │    │  (limit-up- │    │  (stock-    │    │  (月度复盘   │
│   /AkShare) │    │             │    │   backtest) │    │   alert)    │    │   /周报)    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

## 技术栈

- **语言**: Python 3.11+
- **数据分析**: pandas, numpy, matplotlib
- **数据源**: Tushare, AkShare
- **数据库**: MySQL, PostgreSQL, SQLite
- **Web**: Flask, SQLAlchemy
- **部署**: Docker, docker-compose
- **量化平台**: 米筐(RiceQuant), 通达信TQ接口

## 免责声明

本项目所有策略和回测结果仅供学习研究使用，不构成投资建议。回测结果未扣除手续费、滑点等交易成本，实盘表现可能与回测存在显著差异。
