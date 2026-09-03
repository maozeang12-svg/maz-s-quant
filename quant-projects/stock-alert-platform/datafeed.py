import time, datetime
import tushare as ts
import akshare as ak


def to_tushare_code(code):
    """600519 -> 600519.SH ; 000858.SZ 不变"""
    if "." in code:
        return code
    return code + (".SH" if code.startswith(("6", "9")) else ".SZ")


def to_akshare_code(code):
    """600519.SH -> 600519"""
    return code.split(".")[0]


class Bar:
    """一根 K 线 / 实时快照"""
    def __init__(self, symbol, timestamp, open_, high, low, close, volume):
        self.symbol = symbol
        self.timestamp = timestamp
        self.open = open_; self.high = high
        self.low = low; self.close = close; self.volume = volume


class DataFeed:
    def __init__(self, cfg):
        self.cfg = cfg
        self.token = cfg.get("tushare_token", "")
        if self.token:
            ts.set_token(self.token)
            self.pro = ts.pro_api()
        else:
            self.pro = None
        self._cache_t = {}          # 限频时间戳

    def _rate_limit(self, key, min_gap=1.0):
        """同一类请求最小间隔，避免被封"""
        now = time.time()
        last = self._cache_t.get(key, 0)
        if now - last < min_gap:
            time.sleep(min_gap - (now - last))
        self._cache_t[key] = time.time()

    def get_daily_bars(self, code, count=60):
        """返回最近 count 根日 K（旧→新），前复权，用于指标计算"""
        self._rate_limit("daily", 1.0)
        tcode = to_tushare_code(code)
        try:
            if self.pro:
                end = datetime.date.today().strftime("%Y%m%d")
                df = self.pro.daily(ts_code=tcode, end_date=end, count=count)
                df = df.sort_values("trade_date")
            else:
                raise RuntimeError("no tushare")
        except Exception:
            # 兜底：AkShare
            df = ak.stock_zh_a_hist(
                symbol=to_akshare_code(code), period="daily",
                start_date=(datetime.date.today() - datetime.timedelta(days=count * 2)).strftime("%Y%m%d"),
                end_date=datetime.date.today().strftime("%Y%m%d"),
                adjust="qfq")
            df = df.rename(columns={"日期": "trade_date", "开盘": "open", "最高": "high",
                                    "最低": "low", "收盘": "close", "成交量": "vol"})
        bars = []
        for _, r in df.iterrows():
            bars.append(Bar(code, str(r["trade_date"]),
                            float(r["open"]), float(r["high"]),
                            float(r["low"]), float(r["close"]), float(r["vol"])))
        return bars

    def get_realtime_quote(self, code):
        """返回最新实时快照（交易时段内有效，非交易时段返回昨日收盘）"""
        self._rate_limit("rt", 1.0)
        tcode = to_tushare_code(code)
        try:
            df = ts.get_realtime_quotes(tcode)
            r = df.iloc[0]
            return Bar(code, r["date"] + " " + r["time"],
                       float(r["open"]), float(r["high"]),
                       float(r["low"]), float(r["price"]), float(r["volume"]))
        except Exception:
            bars = self.get_daily_bars(code, 1)
            return bars[-1] if bars else None

    def get_min_bars(self, code, freq, store=None, count=250):
        """
        获取分钟 K（前复权）。freq ∈ {"15","30","60"}。
        增量模式（store 非空）：仅拉取「上次缓存之后」的棒并 upsert，
        不再每次全量重拉，大幅降低 AkShare 限流/反爬概率。
        返回最近 count 根【已收盘】Bar（旧→新）。
        末尾丢弃当前未完成那根，避免用未收盘数据判断交叉（防重绘）。
        """
        self._rate_limit(f"min{freq}", 0.5)
        akcode = to_akshare_code(code)
        last = store.last_ts(code, freq) if store else None
        if last:
            # 增量：从「最后缓存日的前一天」起拉，靠 upsert 去重补齐
            try:
                d = datetime.datetime.strptime(last[:19], "%Y-%m-%d %H:%M:%S").date()
            except Exception:
                try:
                    d = datetime.datetime.strptime(last[:16], "%Y-%m-%d %H:%M").date()
                except Exception:
                    d = datetime.date.today()
            start = (d - datetime.timedelta(days=1)).strftime("%Y%m%d")
        else:
            # 首拉回填：按周期估算需要多少自然日才能凑够 count 根
            per_day = {"15": 16, "30": 8, "60": 4}.get(freq, 4)
            days = max(30, (count // per_day) + 15)
            start = (datetime.date.today() - datetime.timedelta(days=days)).strftime("%Y%m%d")
        df = ak.stock_zh_a_hist_min_em(
            symbol=akcode, period=freq,
            start_date=start,
            end_date=datetime.date.today().strftime("%Y%m%d"),
            adjust="qfq")
        bars = []
        for _, r in df.iterrows():
            bars.append(Bar(code, str(r["时间"]), float(r["开盘"]), float(r["最高"]),
                            float(r["最低"]), float(r["收盘"]), float(r["成交量"])))
        if bars:
            bars = bars[:-1]              # 丢弃最后一根未收盘棒
        if store and bars:
            store.upsert_min_bars(code, freq, bars)
        if store:
            return store.get_min_bars(code, freq, count)
        return bars[-count:]


def resample_120(bars_60):
    """
    将 60min Bar 序列聚合成 120min(=2H)。
    沪深每日 4 根 60min 棒，按连续 2 根聚合 → 恰好对齐 上午/下午 两段。
    EMA 对起点敏感，重采样后的 MACD 与交易所原生 120min 略有偏差（已知）。
    """
    out = []
    for i in range(0, len(bars_60) - 1, 2):
        a, b = bars_60[i], bars_60[i + 1]
        out.append(Bar(a.symbol, b.timestamp,
                       a.open,
                       max(a.high, b.high),
                       min(a.low, b.low),
                       b.close,
                       a.volume + b.volume))
    return out
