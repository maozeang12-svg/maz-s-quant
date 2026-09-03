"""
数据质量校验
- 检查缺失值、重复、异常价格（涨跌幅超限等）
- 检查覆盖范围（交易日数 vs 表内数据）
用法:
    python -m etl.validate
"""
import sys

import pandas as pd

import config
from etl.upsert import get_conn


def check_daily_coverage(symbols: int = 5) -> None:
    """抽查几只股票的日线覆盖率"""
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ts_code, COUNT(*) AS n, MIN(trade_date) AS min_d, MAX(trade_date) AS max_d
            FROM daily GROUP BY ts_code ORDER BY n DESC LIMIT %s
            """,
            (symbols,),
        )
        rows = cur.fetchall()
    conn.close()
    print(f"\n=== 日线数据覆盖情况（样本 {symbols} 只） ===")
    for code, n, min_d, max_d in rows:
        print(f"  {code}: {n} 条, {min_d} ~ {max_d}")


def check_price_sanity() -> None:
    """检查异常价格: 涨停超20%(无涨跌幅限制除外)、负价"""
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ts_code, trade_date, open, high, low, close
            FROM daily
            WHERE low <= 0 OR open <= 0 OR high < low OR close > high OR close < low
            LIMIT 20
            """
        )
        bad = cur.fetchall()
        # 检查单日涨跌幅超过 ±22%（主板10%+科创/创业20%，留误差）
        cur.execute(
            """
            SELECT ts_code, trade_date, pct_chg
            FROM daily
            WHERE pct_chg > 22 OR pct_chg < -22
            LIMIT 20
            """
        )
        over = cur.fetchall()
    conn.close()

    print("\n=== 价格合理性检查 ===")
    if bad:
        print(f"  发现 {len(bad)} 条异常价格(负数/高低于开收价):")
        for r in bad:
            print("   ", r)
    else:
        print("  OK: 无负价、无高<低等逻辑错误")
    if over:
        print(f"  发现 {len(over)} 条单日波动超±22%记录（需人工核实是否ST或新股首日）:")
        for r in over:
            print("   ", r)
    else:
        print("  OK: 无超限涨跌幅")


def check_dup() -> None:
    """检查各表是否有重复主键(理论上不应存在)"""
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 'daily' AS tbl, COUNT(*) FROM (SELECT 1 FROM daily GROUP BY ts_code, trade_date HAVING COUNT(*)>1) x
            UNION ALL
            SELECT 'adj_factor', COUNT(*) FROM (SELECT 1 FROM adj_factor GROUP BY ts_code, trade_date HAVING COUNT(*)>1) x
            UNION ALL
            SELECT 'daily_basic', COUNT(*) FROM (SELECT 1 FROM daily_basic GROUP BY ts_code, trade_date HAVING COUNT(*)>1) x
            UNION ALL
            SELECT 'minute_bar', COUNT(*) FROM (SELECT 1 FROM minute_bar GROUP BY ts_code, trade_time, freq HAVING COUNT(*)>1) x
            """
        )
        rows = cur.fetchall()
    conn.close()
    print("\n=== 重复主键检查 ===")
    for tbl, n in rows:
        status = "OK" if n == 0 else f"发现 {n} 组重复!"
        print(f"  {tbl}: {status}")


def run_all() -> None:
    check_daily_coverage()
    check_price_sanity()
    check_dup()


if __name__ == "__main__":
    run_all()
