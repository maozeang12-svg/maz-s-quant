# -*- coding: utf-8 -*-
"""汇总2026连板竞价策略全部数据 -> 生成详细工作文档(markdown)"""
import pandas as pd, numpy as np, bisect, datetime

BASE = r'c:\Users\11\WorkBuddy\2026-08-19-12-23-40'
t = pd.read_csv(BASE + r'\track_2026_v2.csv')
combo = pd.read_csv(BASE + r'\track_2026_combo.csv')
t['trade_date'] = t['trade_date'].astype(str)
combo['trade_date'] = combo['trade_date'].astype(str)
t['open_pct'] = t['open_pct'].astype(float)

# ADJS
raw = open(r'C:/Users/11/Desktop/adjs.xls', 'rb').read().decode('gbk')
adjs = {}
for line in raw.splitlines()[1:]:
    line = line.strip()
    if not line or '\t' not in line: continue
    d, v = line.split('\t')
    adjs[d.strip().replace('/', '-')] = float(v)
dates = sorted(adjs.keys())
def prev_adjs(day):
    i = bisect.bisect_left(dates, day)
    return adjs[dates[i-1]] if i > 0 else np.nan
t['prev_adjs'] = t['trade_date'].map(prev_adjs)
t['good'] = t['prev_adjs'] >= 0
t['month'] = t['trade_date'].str[:7]

def pct(x):
    return '—' if pd.isna(x) else f'{x*100:+.2f}%'

def stat_block(df, col='T1_close_ret'):
    df = df.dropna(subset=[col])
    n = len(df)
    if n == 0: return (0, np.nan, np.nan, np.nan)
    return (n, (df[col] > 0).mean()*100, df[col].mean()*100, df[col].median()*100)

# ---- 全样本分月 ----
months = ['2026-01','2026-02','2026-03','2026-04','2026-05','2026-06','2026-07','2026-08']
print('=== 全样本分月 ===')
month_rows = []
for m in months:
    sub = t[t.month == m]
    n_all = len(sub)
    n1, w1, m1, md1 = stat_block(sub, 'T1_close_ret')
    # 有T+1的笔数(可能无T+1如8/21)
    n_t1 = sub['T1_close_ret'].notna().sum()
    month_rows.append((m, n_all, n_t1, w1, m1))

# ---- 按开盘涨幅分组(全样本) ----
bins = [-1, 0, 0.02, 0.04, 0.06, 0.098, 2]
labels = ['<0%低开', '0~2%', '2~4%', '4~6%', '6~9.8%', '>=9.8%一字板']
t['ob'] = pd.cut(t.open_pct, bins=bins, labels=labels, right=False)
bucket_rows = []
for lb in labels:
    sub = t[t.ob == lb]
    n, w, m, md = stat_block(sub, 'T1_close_ret')
    bucket_rows.append((lb, n, w, m, md))

# ---- 情绪好/差(全样本) ----
good_rows = []
for nm, mask in [('情绪好(ADJS>=0)', t.good), ('情绪差(ADJS<0)', ~t.good)]:
    sub = t[mask]
    n, w, m, md = stat_block(sub, 'T1_close_ret')
    good_rows.append((nm, n, w, m, md))

# ---- 按T+1是否涨停(全样本) ----
lim_rows = []
for lim, nm in [(True, 'T+1涨停'), (False, 'T+1未涨停')]:
    sub = t[t.T1_limit_up == lim]
    n, w, m, md = stat_block(sub, 'T3_close_ret')
    lim_rows.append((nm, n, w, m, md))

# ---- 组合分月 ----
combo['month'] = combo['trade_date'].str[:7]
combo_month_rows = []
for m in months:
    sub = combo[combo.month == m]
    n, w, m_, md = stat_block(sub, 'T1_close_ret')
    combo_month_rows.append((m, n, w, m_))

# ================= 生成文档 =================
def md_table(headers, rows):
    out = '| ' + ' | '.join(headers) + ' |\n'
    out += '| ' + ' | '.join(['---']*len(headers)) + ' |\n'
    for r in rows:
        out += '| ' + ' | '.join(str(c) for c in r) + ' |\n'
    return out

L = []
L.append('# 连板竞价策略 2026 全年回测工作文档\n')
L.append(f'> 生成时间：{datetime.date.today().isoformat()} ｜ 数据源：MySQL `quant.minute_bar`(127.0.0.1:3306) ｜ 回测区间：2026-01-01 ~ 2026-08-21')
L.append(f'> 信号总数：**{len(t)} 笔** ｜ 组合（情绪好+低开/一字板）：**{len(combo)} 笔**\n')

L.append('## 一、文档目的与概览\n')
L.append('本文档系统记录 2026 年"连板竞价"策略的完整回测过程、数据来源、方法、结果及已知局限，作为后续实盘与迭代的基线。')
L.append('- 策略核心：主板非 ST 个股，T-1 连续涨停 ≥2 板，次日竞价额 >3000 万 且 ≥ 昨日 2 倍，开盘价买入；叠加"情绪闸门（T-1 ADJS≥0）"与两档买点（情绪好+低开 / 情绪好+一字板）。')
L.append('- 跟踪：每笔信号跟踪 T+1 开盘、T+1~T+3 收盘收益（未扣除手续费/滑点）。')
L.append(f'- 关键结果：全样本 {len(t)} 笔，T+1 收盘胜率 {stat_block(t,"T1_close_ret")[1]:.1f}%、均值 {stat_block(t,"T1_close_ret")[2]:.2f}%；组合 {len(combo)} 笔，胜率 {stat_block(combo,"T1_close_ret")[1]:.1f}%、均值 {stat_block(combo,"T1_close_ret")[2]:.2f}%。\n')

L.append('## 二、数据源与覆盖范围\n')
L.append('- **原库（SQLite）**：`E:\\BaiduNetdiskDownload\\示例\\quant_tick.db`，早期 1~2 月回测用。')
L.append('- **现库（MySQL）**：2026 年数据由 `night_migrate` 从 SQLite 迁至 MySQL `quant` 库（约 1.97 亿行，耗时 195 分钟，覆盖至 2026-08-21）。连接：host=127.0.0.1, port=3306, user=quant, database=quant；数据目录 `E:/mysql-data-v2`，启动 `mysqld --defaults-file=C:/mysql-8.4.3/my.ini`。')
L.append('- **覆盖断层（重要）**：')
L.append('  - 1~2 月：全市场约 5430 只，开盘/收盘/竞价齐全。')
L.append('  - 3~7 月：竞价/收盘仅约 3180 只（全市场 58%），存在漏股。')
L.append('  - **8/03**：全市场 5530 只（开盘齐全），但收盘/竞价仅 3189/3180 只（过渡日）。')
L.append('  - **8/04 起**：整库仅约 3190 只股票（开盘/收盘/竞价三件套基本齐全），其余约 2340 只完全缺席——即迁移源 8/4 后只导了这 3190 只子集。')
L.append('  - 最新交易日探测到 **2026-08-21**（8/21 两笔信号无 T+1~T+3，因 8/24 之后数据尚未来源）。')
L.append('- **情绪指标 ADJS**：`C:/Users/11/Desktop/adjs.xls`（实为 GBK 文本，市场级指数非个股），覆盖 2026-01-05 ~ 2026-08-19。规则：T-1 ADJS≥0 视为"情绪好"才交易（反转后规则，原 <0 方向被证伪）。\n')

L.append('## 三、策略定义与买点\n')
L.append('- **连板判定**：主板（沪 600/601/603/605、深 000/001/002/003），非 ST；T-1 `close ≈ round(prev_close×1.1, 2)` 容差 0.005 记为涨停，连续 ≥2 板。')
L.append('- **竞价过滤**：竞价额 = 竞价价 × 竞价量 × 100（DB 中 volume 单位为"手"，需 ×100 转"股"）；要求 竞价额 > 3000 万 且 ≥ 昨日竞价额 2 倍。')
L.append('- **买入**：开盘价买入（不限开盘涨幅）。')
L.append('- **情绪闸门**：仅当 T-1 ADJS ≥ 0（情绪好）才交易。')
L.append('- **两档买点（组合）**：档1 = 情绪好 + 低开（open_pct<0%）；档2 = 情绪好 + 一字板（open_pct≥9.8%）。组合 = 档1 ∪ 档2。')
L.append('- **未实现项**：M3 动态止损（未涨停回落 ≥2% 卖 / 尾盘卖）尚未叠加到组合，需治 5/7 月一字板开板坑。\n')

L.append('## 四、回测方法\n')
L.append('1. 聚合日线：`minute_bar` 按日聚合 high/low/volume；开盘取 09:30 bar，收盘取 15:00 bar（缺失时用当日末根 bar 兜底）；竞价取 09:25 `auction_flag=1` 行。一字板日无 09:30 bar，open 可为 NaN 但保留 close 以维持连板链。')
L.append('2. 信号：在主板非 ST 中筛 `prev_streak≥2`，再过滤 竞价额>3000万 且 `auc_ratio≥2`，要求 open/auction 非空。')
L.append('3. 跟踪：对每笔信号取 T+1~T+3 开盘/收盘（fetch_day 用 15:00 bar 优先、末根兜底）。')
L.append('4. 收益口径：未扣除手续费与滑点（实际单边约 0.1%~0.15%，T+1 卖出需担隔日风险）。\n')

L.append('## 五、全样本回测结果（%d 笔）\n' % len(t))
L.append('### 5.1 分月（T+1 收盘卖）\n')
L.append(md_table(['月份','信号数','有效T+1','胜率','均值'],
                  [(m, na, nt1, '—' if pd.isna(w) else f'{w:.1f}%', '—' if pd.isna(mm) else f'{mm:+.2f}%') for m,na,nt1,w,mm in month_rows]))
L.append('')
L.append('### 5.2 按开盘涨幅分组（T+1 收盘卖）\n')
L.append(md_table(['开盘桶','笔数','胜率','均值','中位'],
                  [(lb, n, '—' if pd.isna(w) else f'{w:.1f}%', '—' if pd.isna(m) else f'{m:+.2f}%', '—' if pd.isna(md) else f'{md:+.2f}%') for lb,n,w,m,md in bucket_rows]))
L.append('')
L.append('### 5.3 情绪好 vs 情绪差（T+1 收盘卖）\n')
L.append(md_table(['情绪','笔数','胜率','均值','中位'],
                  [(nm, n, '—' if pd.isna(w) else f'{w:.1f}%', '—' if pd.isna(m) else f'{m:+.2f}%', '—' if pd.isna(md) else f'{md:+.2f}%') for nm,n,w,m,md in good_rows]))
L.append('')
L.append('### 5.4 按 T+1 是否涨停（T+3 收盘卖，全样本）\n')
L.append(md_table(['T+1状态','笔数','胜率','均值','中位'],
                  [(nm, n, '—' if pd.isna(w) else f'{w:.1f}%', '—' if pd.isna(m) else f'{m:+.2f}%', '—' if pd.isna(md) else f'{md:+.2f}%') for nm,n,w,m,md in lim_rows]))
L.append('')
L.append('> 规律：利润几乎全部来自 T+1 涨停组；T+2/T+3 持有普遍转负，策略本质是"博次日涨停"的彩票型策略，最优持有为 T+1 收盘。\n')

L.append('## 六、组合策略结果（情绪好 + 低开/一字板，%d 笔）\n' % len(combo))
L.append('### 6.1 分月（T+1 收盘卖）\n')
L.append(md_table(['月份','笔数','胜率','均值'],
                  [(m, n, '—' if pd.isna(w) else f'{w:.1f}%', '—' if pd.isna(mm) else f'{mm:+.2f}%') for m,n,w,mm in combo_month_rows]))
L.append('')
# 档1/档2 统计
d1 = combo[combo.d1_good_low == True]
d2 = combo[combo.d1_good_low == False]
def srow(df, tag):
    n,w,m,md = stat_block(df,'T1_close_ret'); n2,w2,m2,md2 = stat_block(df,'T2_close_ret'); n3,w3,m3,md3 = stat_block(df,'T3_close_ret')
    return (tag, n, f'{w:.1f}%' if not pd.isna(w) else '—', f'{m:+.2f}%' if not pd.isna(m) else '—',
            f'{w2:.1f}%' if not pd.isna(w2) else '—', f'{m2:+.2f}%' if not pd.isna(m2) else '—',
            f'{w3:.1f}%' if not pd.isna(w3) else '—', f'{m3:+.2f}%' if not pd.isna(m3) else '—')
L.append('### 6.2 档1（低开）vs 档2（一字板）\n')
L.append(md_table(['档位','笔数','T+1胜率','T+1均值','T+2胜率','T+2均值','T+3胜率','T+3均值'],
                  [srow(d1,'档1 情绪好+低开'), srow(d2,'档2 情绪好+一字板')]))
L.append('')
L.append('> 档1（低开）样本仅 8 笔但质量极高（87.5% / +7.50%，持有越久越好）；档2（一字板）25 笔，60% / +1.65%，T+3 转负（5/7 月开板坑）。组合甜点：T+2 收盘 +3.17% 最优。\n')

L.append('## 七、组合选股明细（%d 笔全表）\n' % len(combo))
hdr = ['选中日','代码','名称','开盘%','竞价倍','连板','买价','T-1ADJS','档','T+1开','T+1收','T+2收','T+3收']
rows = []
for _, r in combo.sort_values('trade_date').iterrows():
    rows.append([r.trade_date, r.ts_code[:6], r['name'],
                 f'{r.open_pct:.2f}', f'{r.auc_ratio:.2f}', int(r.prev_streak), f'{r.buy_px:.2f}',
                 int(r.prev_adjs), '低开' if r.d1_good_low else '一字板',
                 pct(r.T1_open_ret), pct(r.T1_close_ret), pct(r.T2_close_ret), pct(r.T3_close_ret)])
L.append(md_table(hdr, rows))
L.append('')

L.append('## 八、情绪好+低开 8 笔明细（核心利润来源）\n')
hdr2 = ['选中日','代码','名称','开盘%','T+1收','T+2收','T+3收']
rows2 = []
for _, r in d1.sort_values('trade_date').iterrows():
    rows2.append([r.trade_date, r.ts_code[:6], r['name'], f'{r.open_pct:.2f}', pct(r.T1_close_ret), pct(r.T2_close_ret), pct(r.T3_close_ret)])
L.append(md_table(hdr2, rows2))
L.append('')
L.append('> 8 笔 7 赚 1 亏，白银有色(+52%)、金螳螂(+19.9%)、巨力索具(+13.7%) 是主要利润。样本小且 3~7 月仅 58% 覆盖，低开票可能漏记，数字偏乐观。\n')

L.append('## 九、高开分析：高开在什么时候胜率高\n')
L.append('- 高开子集（open_pct≥0）共 251 笔：情绪好 52.9%/+1.21%，情绪差 47.2%/-0.68% —— **高开赚钱几乎取决于情绪好不好，而非开得多高**。')
L.append('- 高开分桶 × 情绪（T+1 收盘）：')
L.append('  - 一字板 ≥9.8% + 情绪好：**60.0% / +1.65%**（组合 D2 档）')
L.append('  - 4~6% 小幅高开 + 情绪好：52.6% / **+3.62%**（均值最高）')
L.append('  - 0~2% 微高开 + 情绪好：55.6% / +2.42%')
L.append('  - ⚠️ 2~4% 高开无论情绪都差（情绪好仅 22%），最易"高开低走"，应回避。')
L.append('- 连板数（情绪好）：3 连板 **66.7% / +4.61%**（最强），4 连板 60%；2 连板最弱（46.6%）。**高开+3~4连板+情绪好 = 黄金组合**。')
L.append('- 月份（情绪好高开）：06 月 66.7%/+2.45%（中位 +7.03% 最稳）、01 月 61.1%/+2.87% 最佳；**05 月情绪好高开仍亏（47.1%/-0.01%）**，是坑。')
L.append('> 结论：高开胜率高的时机 = **情绪好 +（一字板 或 4~6% 或 3 连板）+ 06/01 月**。但高开再优也不如低开（情绪好低开 87.5%/+7.5%），大肉仍在低开档。\n')

L.append('## 十、8 月数据扩展与复盘\n')
L.append('- 回测已由 8/17 扩至 **8/21**，新增 8/18~8/21 共 9 笔信号（8/21 两笔无 T+1）。')
L.append('- 8 月全样本最差：有效 T+1 仅 7 笔，胜率 42.9%、均值 -2.83%。')
L.append('- **组合仍为 33 笔不变**：ADJS 在 8/17=+1286 → 8/18=-452 → 8/19=-1680 急转负，闸门挡掉 8/19/8/20 全部候选（含 -5.1% 低开京粮控股随后 -4.94%、+10% 一字板红四方随后 +5.66%）；8/21 因 ADJS 文件仅到 08/19 也排除。闸门在 8 月实际避开了亏损票（农发种业 -7.24%、京粮控股 -4.94%）。')
L.append('- 8 月 9 笔信号明细见 `track_2026_v2.csv`（筛选 trade_date 含 2026-08）。\n')

L.append('## 十一、数据质量与局限（诚实提醒）\n')
L.append('1. **覆盖断层**：3~7 月仅 58% 覆盖、8/4 起仅 ~3190 只子集，连板信号会漏股，信号数偏少、收益可能高估。')
L.append('2. **ADJS 时效**：情绪指标仅到 2026-08-19，8/20 之后交易无法用情绪闸门。')
L.append('3. **样本量**：档1 低开仅 8 笔、各细分月份/桶样本更小，统计结论需谨慎。')
L.append('4. **无成本**：收益未扣手续费/滑点，T+1 卖出承担隔日跳空风险。')
L.append('5. **8/21 信号**：无 T+1~T+3，无法评估。\n')

L.append('## 十二、后续建议\n')
L.append('1. 叠加 M3 动态止损（未涨停回落 ≥2% 卖）到组合，治 5/7 月一字板开板坑。')
L.append('2. 将"纯情绪好+低开"与"情绪好+一字板+M3 止损"分池管理（低开池拿久、一字板池严格 T+1 止损）。')
L.append('3. 待数据补到全市场、ADJS 补全后，重算 8 月及之后的信号。')
L.append('4. 评估新增"高开+3~4 连板+情绪好"独立一档（历史 66.7%/+4.61%）。\n')

L.append('---\n')
L.append('*配套文件：`track_2026_v2.csv`（287 笔全量信号+跟踪）、`track_2026_combo.csv`（33 笔组合明细）、`high_open_analysis.csv`（251 笔高开分析）、`daily_2026_v2.csv`（日线聚合）。*\n')

doc = '\n'.join(L)
out_path = BASE + r'\2026连板竞价策略回测工作文档.md'
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(doc)
print('文档已生成 ->', out_path, '字符数', len(doc))
