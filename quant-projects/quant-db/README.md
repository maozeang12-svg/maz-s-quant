# A股量化行情数据库

> 从零搭建的A股行情数据基础设施，覆盖日线、分钟线、Tick逐笔、财务三表、复权因子等14张表，支持亿级数据量。

## 设计原则

1. **标的代码统一格式**: `600000.SH` / `000001.SZ` / `430047.BJ`，跨市场不撞车
2. **复权分离**: 原始表存不复权价，另算后复权和前复权，回测用复权、展示用不复权
3. **时区统一**: 全部北京时间(UTC+8)，时间戳存epoch毫秒
4. **Tick防丢单**: 主键用 `(code, ts, seq)`，同一毫秒多笔成交不丢失

## 存储演进路线

| 阶段 | 日线/基础信息 | 分钟线 | Tick(逐笔) |
|------|-------------|--------|-----------|
| 起步 (<千万行) | SQLite | SQLite | SQLite |
| 成长 (亿级) | PostgreSQL | PostgreSQL+分区表 | TimescaleDB |
| 机构级 | 列式(Parquet) | 时序库 | 时序库+冷归档 |

## 核心表结构

| 表名 | 说明 | 主键 |
|------|------|------|
| `instruments` | 标的基础信息 | `ts_code` |
| `daily_bars` | 日线 | `(ts_code, trade_date)` |
| `minute_bars` | 1分钟K线 | `(ts_code, trade_time)` |
| `tick_trades` | 逐笔成交 | `(ts_code, trade_time, seq)` |
| `tick_quotes` | 十档盘口快照 | `(ts_code, trade_time, seq)` |
| `factor_values` | 预计算因子 | `(ts_code, trade_date, factor_name)` |

## 文件说明

| 文件 | 说明 |
|------|------|
| `schema.sql` | 完整建表SQL，含索引设计 |
| `upsert.py` | 批量upsert写入：主键冲突自动更新，分chunk避免事务过大 |
| `validate.py` | 数据质量校验：覆盖率检查、异常价格检测、重复主键排查 |

## ETL核心逻辑

```python
from etl.upsert import upsert_dataframe

# 批量写入日线数据，主键冲突时自动更新
upsert_dataframe(
    df=daily_df,           # pandas DataFrame
    table="daily_bars",    # 目标表
    key_cols=["ts_code", "trade_date"]  # 主键
)
```

## 数据迁移记录

- **迁移量**: 分钟线 + Tick 数据约 **1.97亿行**
- **迁移时间**: 195分钟
- **发现问题**: 3~7月仅覆盖全市场58%，8/4起仅3190只子集
- **根因定位**: 源数据子集问题，非迁移逻辑错误

## 索引设计

```sql
-- 按股票+时间查询（最常用）
CREATE INDEX idx_daily_code_date ON daily_bars(ts_code, trade_date);

-- 按日期全市场扫描（选股/横截面）
CREATE INDEX idx_daily_date ON daily_bars(trade_date);

-- Tick数据主键（防丢单）
CREATE UNIQUE INDEX idx_tick_pk ON tick_trades(ts_code, trade_time, seq);
```

## 依赖

```bash
pip install pandas psycopg2-binary
```

## 快速开始

```bash
# 1. 创建数据库
psql -U quant -d quant -f schema.sql

# 2. 运行数据质量校验
python etl/validate.py

# 3. 批量导入数据
python -c "from etl.upsert import upsert_dataframe; upsert_dataframe(df, 'daily_bars', ['ts_code', 'trade_date'])"
```
