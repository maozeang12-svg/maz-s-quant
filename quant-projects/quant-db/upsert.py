"""
批量 upsert 到 PostgreSQL
用法:
    from etl.upsert import upsert_dataframe
    upsert_dataframe(df, "daily", ["ts_code", "trade_date"])
"""
from typing import List, Optional

import pandas as pd
import psycopg2

import config


def get_conn():
    """获取数据库连接"""
    return psycopg2.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        dbname=config.DB_NAME,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
    )


def _columns_from_df(df: pd.DataFrame) -> List[str]:
    """统一列名转小写（PostgreSQL 默认小写列名）"""
    return [c.lower() for c in df.columns]


def upsert_dataframe(
    df: pd.DataFrame,
    table: str,
    key_cols: List[str],
    chunk_size: int = 2000,
) -> int:
    """
    将 DataFrame 写入指定表，主键冲突时更新。
    返回写入行数。

    Args:
        df: 待写入数据（列名自动转小写）
        table: 目标表名
        key_cols: 主键列（用于 ON CONFLICT）
        chunk_size: 分批大小，避免单事务过大
    """
    if df is None or df.empty:
        return 0

    df = df.copy()
    df.columns = [c.lower() for c in df.columns]

    # 剔除表中不存在的列（兼容 API 返回的多余字段）
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            """,
            (table,),
        )
        valid_cols = {r[0] for r in cur.fetchall()}
    conn.close()

    cols = [c for c in df.columns if c in valid_cols]
    if not cols:
        raise ValueError(f"表 {table} 中不存在任何可写入列")

    df = df[cols]
    # 处理 NaN -> None
    df = df.where(pd.notnull(df), None)

    update_cols = [c for c in cols if c not in key_cols]
    update_sql = ", ".join(f"{c}=EXCLUDED.{c}" for c in update_cols)

    insert_cols = ", ".join(cols)
    placeholders = ", ".join(["%s"] * len(cols))
    conflict = ", ".join(key_cols)
    sql = f"""
        INSERT INTO {table} ({insert_cols})
        VALUES ({placeholders})
        ON CONFLICT ({conflict}) DO UPDATE SET {update_sql}
    """

    conn = get_conn()
    total = 0
    try:
        with conn.cursor() as cur:
            for start in range(0, len(df), chunk_size):
                chunk = df.iloc[start:start + chunk_size]
                rows = [tuple(row) for row in chunk.itertuples(index=False)]
                cur.executemany(sql, rows)
                total += len(rows)
                print(f"  [upsert] {table}: 已写入 {total}/{len(df)} 行")
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
    return total


def query(table: str, where: Optional[str] = None, columns: str = "*") -> pd.DataFrame:
    """简单查询，返回 DataFrame"""
    conn = get_conn()
    sql = f"SELECT {columns} FROM {table}"
    if where:
        sql += f" WHERE {where}"
    df = pd.read_sql(sql, conn)
    conn.close()
    return df


def get_existing_dates(table: str, where: str) -> set:
    """获取表内已有的日期，用于增量更新判断"""
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(f"SELECT DISTINCT trade_date FROM {table} WHERE {where}")
        dates = {r[0] for r in cur.fetchall()}
    conn.close()
    return dates
