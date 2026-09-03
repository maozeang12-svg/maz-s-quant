# -*- coding: utf-8 -*-
"""
连板竞价策略回测主程序
选股(T日, 3条件同时满足):
  1. T-1日连续涨停>=2 (主板10%涨停), 非ST, 主板股票(60/00开头)
  2. T日集合竞价成交额 >= 2 * T-1日竞价成交额, 且 > 3000万元
  3. T日开盘涨幅 >= 4% (买入约束, 从选股条件3展开)

买入(T日):
  开盘涨幅4%~6%   : 挂单价=昨收(0%), 盘中最低价触及则成交
  开盘涨幅>6%     : 挂单价=昨收*1.05, 盘中最低价触及则成交
  未触及挂单价     : 当日不成交(空仓)
  对比口径B        : 开盘价直接买入

卖出: 多方案输出
  S1: T+1开盘卖出
  S2: T+1收盘卖出
  S3: T日尾盘卖出(15:00)
  S4: T+1涨停继续持有, 次日开盘卖; 否则T+1开盘卖
"""
import sqlite3
import pandas as pd
import numpy as np
from datetime import date, timedelta
import sys

DB = r'E:\BaiduNetdiskDownload\示例\quant_tick.db'
DAILY = r'c:\Users\11\WorkBuddy\2026-08-19-12-23-40\daily_2026.csv'
NAMES = r'c:\Users\11\WorkBuddy\2026-08-19-12-23-40\stock_names_20260819.csv'

def log(msg):
    print(msg, flush=True)
    sys.stdout.flush()

# ---------- 1. 加载数据 ----------
daily = pd.read_csv(DAILY)
log(f"日线数据: {len(daily)} 行, 日期 {daily.trade_date.min()} ~ {daily.trade_date.max()}")

# 主板过滤: 沪60开头(600/601/603/605), 深00开头(000/001/002/003)
def is_main_board(code):
    if code.endswith('.SH'):
        return code.startswith(('600', '601', '603', '605'))
    if code.endswith('.SZ'):
        return code.startswith(('000', '001', '002', '003'))
    return False
daily['main_board'] = daily.ts_code.map(is_main_board)

# 非ST
names = pd.read_csv(NAMES)
st_codes = set(names[names['name'].str.contains('ST', na=False)]['code'].astype(str).str.zfill(6))
def is_st(code):
    return code[:6] in st_codes
daily['is_st'] = daily.ts_code.map(is_st)

# 排序
daily = daily.sort_values(['ts_code', 'trade_date']).reset_index(drop=True)
log(f"主板股票 {daily[daily.main_board].ts_code.nunique()} 只")

# ---------- 2. 日特征 ----------
# 前收盘(用上一交易日close)
daily['prev_close'] = daily.groupby('ts_code')['close'].shift(1)
daily['prev_trade_date'] = daily.groupby('ts_code')['trade_date'].shift(1)
# 当日涨幅
daily['pct_chg'] = (daily['close'] - daily['prev_close']) / daily['prev_close']
# 涨停价(主板10%)
daily['limit_price'] = np.round(daily['prev_close'] * 1.1, 2)
# 涨停判定 (考虑四舍五入误差)
daily['is_limit_up'] = (daily['close'] - daily['limit_price']).abs() < 0.005
# 连板数(连续涨停天数)
daily['streak'] = 0
grp = daily.groupby('ts_code')['is_limit_up']
daily['streak'] = grp.transform(lambda s: s.groupby((~s).cumsum()).cumsum())
daily['streak'] = np.where(daily['is_limit_up'], daily['streak'], 0)

# 开盘涨幅
daily['open_pct'] = (daily['open'] - daily['prev_close']) / daily['prev_close']

log("日特征计算完成")

# ---------- 3. 信号生成 ----------
# 只关注2026年
d2026 = daily[daily.trade_date >= '2026-01-01'].copy()
# T日候选: 主板, 非ST, T-1连板>=2
d2026 = d2026[d2026.main_board & ~d2026.is_st]
d2026['prev_streak'] = d2026.groupby('ts_code')['streak'].shift(1)
# 竞价对比: 必须在完整日线上算昨日竞价(相邻交易日)
d2026['prev_auction'] = d2026.groupby('ts_code')['auction_amount'].shift(1)
cand = d2026[d2026.prev_streak >= 2].copy()

cand['has_auction'] = cand['auction_amount'].notna() & cand['prev_auction'].notna()
cand['auc_ratio'] = cand['auction_amount'] / cand['prev_auction']

# 三条件:
#  1. prev_streak>=2 (已满足)
#  2. auction_amount > 3000万 且 auction_amount >= 2*prev_auction
#  3. open_pct >= 0.04
sig = cand[
    cand['has_auction'] &
    (cand['auction_amount'] > 3000e4) &
    (cand['auc_ratio'] >= 2.0) &
    (cand['open_pct'] >= 0.04)
].copy()

log(f"满足连板池条件: 连板>=2 共 {len(cand)} 笔, 竞价3条件全部满足: {len(sig)} 笔")

# ---------- 4. 买入模拟 ----------
conn = sqlite3.connect(DB)
conn.execute('PRAGMA cache_size = -200000')

sig = sig.sort_values('trade_date').reset_index(drop=True)
buy_entries = []
for i, row in sig.iterrows():
    day = row['trade_date']
    code = row['ts_code']
    prev_close = row['prev_close']
    r_open = row['open_pct']
    if 0.04 <= r_open < 0.06:
        limit_buy = prev_close            # 0% 挂单
    elif r_open >= 0.06:
        limit_buy = np.round(prev_close * 1.05, 2)  # 5% 挂单
    else:
        limit_buy = None                  # 开盘涨幅<4%, 不买
    # 取T日分钟线计算最低价
    m = pd.read_sql_query(
        "SELECT ts_code, trade_time, low, open, close FROM minute_bar "
        "WHERE trade_time >= ? AND trade_time < ? AND ts_code = ? "
        "ORDER BY trade_time",
        conn, params=(day + ' 09:30:00', day + ' 24:00:00', code))
    if m.empty:
        continue
    day_low = m['low'].min()
    # 口径A: 挂单等回落
    if limit_buy is not None and day_low <= limit_buy:
        buy_price = limit_buy
        fill_a = True
    else:
        buy_price = None
        fill_a = False
    # 口径B: 开盘直接买
    buy_price_b = row['open']
    buy_entries.append({
        'trade_date': day, 'ts_code': code,
        'close_0': m['close'].iloc[-1],
        'open': row['open'], 'open_pct': r_open,
        'auction_amount': row['auction_amount'],
        'auc_ratio': row['auc_ratio'],
        'prev_close': prev_close,
        'limit_buy': limit_buy, 'day_low': day_low,
        'fill_a': fill_a, 'buy_a': buy_price,
        'buy_b': buy_price_b,
    })

trades = pd.DataFrame(buy_entries)
log(f"信号 {len(sig)} 笔 -> 挂单成交(口径A) {trades.fill_a.sum()} 笔")
trades.to_csv('trades_2026.csv', index=False)

# ---------- 5. 卖出模拟 ----------
# 需要T日和T+1日的日线/分钟数据
trade_days = sorted(daily[daily.trade_date >= '2026-01-01']['trade_date'].unique())
day_idx = {d: i for i, d in enumerate(trade_days)}

out = []
for _, t in trades.iterrows():
    i = day_idx[t.trade_date]
    # T+1日
    if i + 1 >= len(trade_days):
        continue
    d1 = trade_days[i + 1]
    # T+2日(用于S4)
    d2 = trade_days[i + 2] if i + 2 < len(trade_days) else None

    # T+1分钟数据
    m1 = pd.read_sql_query(
        "SELECT trade_time, open, high, low, close FROM minute_bar "
        "WHERE trade_time >= ? AND trade_time < ? AND ts_code = ? ORDER BY trade_time",
        conn, params=(d1 + ' 09:30:00', d1 + ' 24:00:00', t.ts_code))
    if m1.empty:
        continue
    o1, h1, l1, c1 = m1['open'].iloc[0], m1['high'].max(), m1['low'].min(), m1['close'].iloc[-1]
    # T+1涨停价
    lp1 = np.round(t.close_0 * 1.1, 2) if 'close_0' in t else np.round(t.prev_close * 1.1, 2)
    lim1 = abs(c1 - lp1) < 0.005

    # T+2分钟数据
    if d2:
        m2 = pd.read_sql_query(
            "SELECT open FROM minute_bar "
            "WHERE trade_time >= ? AND trade_time < ? AND ts_code = ? ORDER BY trade_time LIMIT 1",
            conn, params=(d2 + ' 09:30:00', d2 + ' 09:31:00', t.ts_code))
        o2 = m2['open'].iloc[0] if not m2.empty else None
    else:
        o2 = None

    for which, bp in [('A', t.buy_a), ('B', t.buy_b)]:
        if bp is None or pd.isna(bp):
            continue
        # S1 T+1开盘
        r1 = o1 / bp - 1
        # S2 T+1收盘
        r2 = c1 / bp - 1
        # S3 T日尾盘 (用T日close)
        r3 = t.close_0 / bp - 1 if 'close_0' in t else t.prev_close / bp - 1
        # S4 T+1涨停持有->T+2开盘; 否则T+1开盘
        r4 = (o2 / bp - 1) if lim1 and o2 else r1
        out.append({
            'trade_date': t.trade_date, 'ts_code': t.ts_code,
            'buy_type': which, 'buy_price': bp,
            'open_pct': t.open_pct, 'auc_ratio': t.auc_ratio,
            'auction_amount': t.auction_amount,
            'T1_open': o1, 'T1_high': h1, 'T1_low': l1, 'T1_close': c1,
            'T1_limit_up': lim1, 'T2_open': o2,
            'S1_T1open_ret': r1, 'S2_T1close_ret': r2, 'S3_Tdayclose_ret': r3,
            'S4_hold_ret': r4,
            'T1_open_pct': o1 / t.close_0 - 1 if 'close_0' in t else None,
        })

res = pd.DataFrame(out)
res.to_csv('results_2026.csv', index=False)
log(f"卖出模拟完成: {len(res)} 条记录")

# ---------- 6. 绩效汇总 ----------
def stats(df, retcol, name):
    r = df[retcol]
    n = len(r)
    if n == 0:
        log(f"{name}: 无交易")
        return
    win = (r > 0).sum()
    log(f"\n=== {name} (n={n}) ===")
    log(f"  胜率: {win/n*100:.1f}%  ({win}/{n})")
    log(f"  平均收益: {r.mean()*100:.2f}%  中位数: {r.median()*100:.2f}%")
    log(f"  最大盈利: {r.max()*100:.2f}%  最大亏损: {r.min()*100:.2f}%")
    log(f"  盈亏比(均值): {r[r>0].mean()/abs(r[r<=0].mean()):.2f}" if (r>0).any() and (r<=0).any() else f"  单边:{ '盈' if (r>0).all() else '亏'}")
    log(f"  累计(等权): {(1+r).prod()*100:.1f}%")

for which in ['A', 'B']:
    sub = res[res.buy_type == which]
    if sub.empty:
        continue
    log(f"\n########## 买入口径 {which} ({'挂单等回落' if which=='A' else '开盘价买入'}) ##########")
    for col, nm in [('S1_T1open_ret', 'S1 T+1开盘卖'),
                    ('S2_T1close_ret', 'S2 T+1收盘卖'),
                    ('S3_Tdayclose_ret', 'S3 T日尾盘卖'),
                    ('S4_hold_ret', 'S4 涨停持有')]:
        stats(sub, col, nm)

conn.close()
log("\n完成")
