from sqlalchemy import (create_engine, Column, Integer, String, Float,
                        DateTime, Text, UniqueConstraint)
from sqlalchemy.orm import declarative_base, sessionmaker
import datetime, os

from .datafeed import Bar

Base = declarative_base()


class Symbol(Base):
    __tablename__ = "symbols"
    id = Column(Integer, primary_key=True)
    code = Column(String(16), unique=True, index=True)   # 如 600519.SH 或 600519
    name = Column(String(64))
    added_at = Column(DateTime, default=datetime.datetime.now)


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True)
    strategy = Column(String(64), index=True)
    symbol = Column(String(16), index=True)
    title = Column(String(128))
    message = Column(Text)
    level = Column(String(16), default="info")   # info | warning | danger
    price = Column(Float)
    triggered_at = Column(DateTime, default=datetime.datetime.now)


class StrategyState(Base):
    """用于告警去重：记录每个 (策略:标的:周期) 上次触发状态"""
    __tablename__ = "strategy_state"
    id = Column(Integer, primary_key=True)
    key = Column(String(160), unique=True, index=True)   # f"{strategy}:{symbol}:{tf}"
    last_triggered_at = Column(DateTime)
    last_state = Column(Integer, default=0)              # 0 未触发 / 1 触发


class MinuteBar(Base):
    """增量维护的分钟 K（按 标的+周期+时间 去重），生产环境必做，规避 AkShare 限流。"""
    __tablename__ = "minute_bars"
    id = Column(Integer, primary_key=True)
    symbol = Column(String(16), index=True)
    period = Column(String(8), index=True)        # 15 / 30 / 60
    ts = Column(String(32), index=True)            # Bar 时间字符串
    open = Column(Float); high = Column(Float)
    low = Column(Float); close = Column(Float); volume = Column(Float)
    __table_args__ = (UniqueConstraint("symbol", "period", "ts",
                                        name="uq_minbar"),)


class Storage:
    def __init__(self, cfg):
        db_path = cfg.get("db_path", "data/stock.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.engine = create_engine(f"sqlite:///{db_path}",
                                     connect_args={"timeout": 15})
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    @property
    def session(self):
        return self.Session()

    def add_symbol(self, code, name=""):
        with self.session as s:
            if not s.query(Symbol).filter_by(code=code).first():
                s.add(Symbol(code=code, name=name))
                s.commit()

    def list_symbols(self):
        with self.session as s:
            return [(x.code, x.name) for x in s.query(Symbol).all()]

    def recently_alerted(self, key, cooldown_min):
        """key 在冷却时间内已报过 → True（预留，本策略用边沿触发）"""
        with self.session as s:
            st = s.query(StrategyState).filter_by(key=key).first()
            if not st or not st.last_triggered_at:
                return False
            return (datetime.datetime.now() - st.last_triggered_at).total_seconds() < cooldown_min * 60

    def record_alert(self, strategy, key, sig, price):
        with self.session as s:
            s.add(Alert(strategy=strategy, symbol=sig.symbol, title=sig.title,
                        message=sig.message, level=sig.level, price=price))
            st = s.query(StrategyState).filter_by(key=key).first() or StrategyState(key=key)
            st.last_triggered_at = datetime.datetime.now()
            st.last_state = 1
            s.add(st)
            s.commit()

    def recent_alerts(self, limit=50):
        with self.session as s:
            rows = s.query(Alert).order_by(Alert.triggered_at.desc()).limit(limit).all()
            return [(r.strategy, r.symbol, r.title, r.level, r.price,
                     r.triggered_at.strftime("%m-%d %H:%M")) for r in rows]

    # ---- 边沿状态（策略落地扩展） ----
    def get_state(self, key):
        with self.session as s:
            st = s.query(StrategyState).filter_by(key=key).first()
            return st.last_state if st else 0

    def set_state(self, key, val):
        with self.session as s:
            st = s.query(StrategyState).filter_by(key=key).first() or StrategyState(key=key)
            st.last_state = val
            s.add(st)
            s.commit()

    # ---- 分钟 K 增量缓存（生产必做，规避 AkShare 限流） ----
    def upsert_min_bars(self, symbol, period, bars):
        """把新收盘的分钟棒写入缓存；按 ts 去重，已存在的跳过。"""
        with self.session as s:
            existing = {b.ts for b in
                        s.query(MinuteBar.ts)
                        .filter_by(symbol=symbol, period=period).all()}
            fresh = []
            for b in bars:
                if b.timestamp in existing:
                    continue
                fresh.append(MinuteBar(symbol=symbol, period=period, ts=b.timestamp,
                                       open=b.open, high=b.high, low=b.low,
                                       close=b.close, volume=b.volume))
            if fresh:
                s.bulk_save_objects(fresh)
                s.commit()

    def get_min_bars(self, symbol, period, count=250):
        """返回最近 count 根已收盘分钟棒（旧→新），以 Bar 对象返回（兼容指标/绘图）。"""
        with self.session as s:
            rows = (s.query(MinuteBar)
                    .filter_by(symbol=symbol, period=period)
                    .order_by(MinuteBar.ts)
                    .limit(count).all())
            return [Bar(r.symbol, r.ts, r.open, r.high, r.low, r.close, r.volume)
                    for r in rows]

    def last_ts(self, symbol, period):
        """该 (标的,周期) 缓存中最后一根棒的时间；用于增量拉取起点。"""
        with self.session as s:
            r = (s.query(MinuteBar.ts)
                 .filter_by(symbol=symbol, period=period)
                 .order_by(MinuteBar.ts.desc()).first())
            return r.ts if r else None

    def alerts_for_symbol(self, symbol, limit=50):
        with self.session as s:
            rows = (s.query(Alert)
                    .filter_by(symbol=symbol)
                    .order_by(Alert.triggered_at.desc())
                    .limit(limit).all())
            return [(r.title, r.level, r.triggered_at, r.message) for r in rows]
