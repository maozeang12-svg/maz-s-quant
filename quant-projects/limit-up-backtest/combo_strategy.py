# -*- coding: utf-8 -*-
"""最终增强策略组合测算:
   闸门: T-1 ADJS >= 0 (情绪好才交易)
   买点两档:
     档1 情绪好 + 低开 (<0%)
     档2 情绪好 + 一字板 (>=9.8%)
   组合 = 档1 ∪ 档2
复用 track_2026_v2.csv 的 T+1~T+3 收益, 不重跑 MySQL。
"""
import pandas as pd
import numpy as np
import bisect

# ---------- 1. 读 adjs.xls (GBK 文本) ----------
raw = open(r'C:/Users/11/Desktop/adjs.xls', 'rb').read().decode('gbk')
adjs = {}
for line in raw.splitlines()[1:]:
    line = line.strip()
    if not line or '\t' not in line:
        continue
    d, v = line.split('\t')
    d = d.strip().replace('/', '-')
    adjs[d] = float(v)
dates = sorted(adjs.keys())

def prev_adjs(day):
    i = bisect.bisect_left(dates, day)
    if i <= 0:
        return np.nan
    return adjs[dates[i - 1]]

# ---------- 2. 读信号 ----------
t = pd.read_csv('track_2026_v2.csv')
t['trade_date'] = t['trade_date'].astype(str)
t['prev_adjs'] = t['trade_date'].map(prev_adjs)
t['open_pct'] = t['open_pct'].astype(float)

good = t['prev_adjs'] >= 0                                   # 情绪好
low  = t['open_pct'] < 0.0                                   # 低开
yb   = t['open_pct'] >= 0.098                                # 一字板(>=9.8%)
t['d1_good_low']  = good & low                               # 档1
t['d2_good_yb']   = good & yb                                # 档2
t['combo']        = t['d1_good_low'] | t['d2_good_yb']       # 组合

print(f"信号总数: {len(t)}", flush=True)
print(f"  档1 情绪好+低开:   {t.d1_good_low.sum()} 笔", flush=True)
print(f"  档2 情绪好+一字板: {t.d2_good_yb.sum()} 笔", flush=True)
print(f"  组合(档1∪档2):     {t.combo.sum()} 笔", flush=True)

# ---------- 3. 统计 ----------
def stat(df, col, label):
    df = df.dropna(subset=[col])
    n = len(df)
    if n == 0:
        print(f"  {label:<16} n=0", flush=True); return
    win = (df[col] > 0).mean() * 100
    mean = df[col].mean() * 100
    med = df[col].median() * 100
    print(f"  {label:<18} n={n:<4} 胜率={win:5.1f}%  均值={mean:6.2f}%  中位={med:6.2f}%", flush=True)

def summary(df, tag):
    print(f"\n=== {tag} (n={len(df)}) ===", flush=True)
    stat(df, 'T1_open_ret',  'T+1开盘卖')
    stat(df, 'T1_close_ret', 'T+1收盘卖(持有1日)')
    stat(df, 'T2_close_ret', 'T+2收盘卖(持有2日)')
    stat(df, 'T3_close_ret', 'T+3收盘卖(持有3日)')
    print("  分月(T+1收盘卖):", flush=True)
    for m in sorted(df.trade_date.str[:7].unique()):
        sub = df[df.trade_date.str.startswith(m)]
        st = sub.dropna(subset=['T1_close_ret'])
        if len(st):
            print(f"    {m}: n={len(st):<3} 胜率={(st.T1_close_ret>0).mean()*100:5.1f}%  均值={st.T1_close_ret.mean()*100:6.2f}%", flush=True)

# ---------- 4. 四口径对比 ----------
summary(t, "A. 全样本(不过滤)")
summary(t[t.prev_adjs >= 0], "C. 反转规则(情绪好全买)")
summary(t[t.d1_good_low], "D1. 档1 情绪好+低开")
summary(t[t.d2_good_yb],  "D2. 档2 情绪好+一字板")
summary(t[t.combo], "E. 组合(情绪好 + 低开∪一字板)")

# ---------- 5. 输出组合明细 ----------
out = t[t.combo][['trade_date','ts_code','name','open_pct','auc_ratio','auction_amount',
                  'prev_streak','buy_px','prev_adjs','d1_good_low','T1_open_ret','T1_close_ret',
                  'T2_close_ret','T3_close_ret']].copy()
out['open_pct'] = (out['open_pct']*100).round(2)
out.to_csv('track_2026_combo.csv', index=False)
print(f"\n组合明细已保存 -> track_2026_combo.csv  ({len(out)} 笔)", flush=True)
