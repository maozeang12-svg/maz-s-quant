import datetime, logging
from .screener import screen
from .datafeed import resample_120
from .strategies.monitor import (MacdGoldenCross, RsiOverbought, MacdDeathCross2H)

log = logging.getLogger("engine")


def is_trading_session(now=None):
    """A股交易时段：周一~周五 9:30-11:30 或 13:00-15:00"""
    now = now or datetime.datetime.now()
    if now.weekday() >= 5:          # 周六日
        return False
    t = now.time()
    m1 = datetime.time(9, 30) <= t <= datetime.time(11, 30)
    m2 = datetime.time(13, 0)  <= t <= datetime.time(15, 0)
    return m1 or m2


class Engine:
    def __init__(self, cfg, store, feed, notifier):
        self.cfg = cfg
        self.store = store
        self.feed = feed
        self.notifier = notifier
        self.pool = set()
        self.monitor_strategies = [MacdGoldenCross(), RsiOverbought(), MacdDeathCross2H()]
        self.run_screener()   # 启动即选股

    def run_screener(self):
        """每日收盘后跑一次，刷新监控池"""
        try:
            boards = self.cfg.get("screener_boards")
            pool = screen(self.feed, boards=boards)
            self.pool = set(pool)
            for code in pool:
                self.store.add_symbol(code)
            log.info("选股完成，监控池 %d 只: %s", len(pool), sorted(pool))
        except Exception:
            log.exception("选股失败（保留上一期池）")

    def _build_ctx(self):
        cache = {}
        for sym in self.pool:
            for tf in ("15", "30", "60"):
                cache[(tf, sym)] = self.feed.get_min_bars(sym, tf, self.store, 250)
            cache[("120", sym)] = resample_120(cache.get(("60", sym), []))
        from .strategies.base import Ctx
        return Ctx(pool=self.pool,
                   min_bars=lambda tf, sym: cache.get((tf, sym)),
                   now=datetime.datetime.now())

    def tick(self):
        if not is_trading_session():
            return   # 非交易时段不轮询
        if not self.pool:
            self.run_screener()
            return
        ctx = self._build_ctx()
        for st in self.monitor_strategies:
            try:
                sigs = st.evaluate_pool(ctx)
            except Exception:
                log.exception("策略异常 %s", st.name)
                continue
            for sig in sigs:
                key = f"{st.name}:{sig.symbol}:{sig.tf}"
                prev = self.store.get_state(key)
                if sig.triggered and prev != 1:        # 边沿：未触发→触发
                    self.notifier.send(sig)
                    self.store.record_alert(st.name, key, sig, price=None)
                    self.store.set_state(key, 1)
                    log.info("[触发] %s | %s", sig.title, sig.message)
                elif not sig.triggered:
                    self.store.set_state(key, 0)
