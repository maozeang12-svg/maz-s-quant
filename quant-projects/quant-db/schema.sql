-- ============================================================
-- A股量化数据库 Schema (PostgreSQL + TimescaleDB)
-- 执行方式: psql -U postgres -d quantdb -f schema.sql
-- 若未安装 TimescaleDB，分钟线/Tick 表退化为普通表（功能不受影响，性能差一些）
-- ============================================================

BEGIN;

-- ---------- 1. 基础信息表 ----------

-- 股票基础信息
CREATE TABLE IF NOT EXISTS stock_basic (
    ts_code     VARCHAR(16) PRIMARY KEY,   -- TS代码: 000001.SZ
    symbol      VARCHAR(10) NOT NULL,      -- 股票代码
    name        VARCHAR(50),               -- 股票名称
    area        VARCHAR(50),               -- 地域
    industry    VARCHAR(50),               -- 所属行业
    market      VARCHAR(20),               -- 市场: 主板/创业板/科创板...
    exchange    VARCHAR(20),               -- 交易所: SSE/SZSE
    list_date   DATE,                      -- 上市日期
    list_status VARCHAR(10) DEFAULT 'L',   -- 上市状态: L上市 D退市 P暂停
    is_hs       VARCHAR(10)                -- 沪深港通标的: H沪股通 S深股通 N否
);

-- 交易日历
CREATE TABLE IF NOT EXISTS trade_cal (
    exchange VARCHAR(20) NOT NULL,         -- SSE/SZSE/CFFEX...
    cal_date DATE NOT NULL,
    is_open  BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (exchange, cal_date)
);

-- 指数基础信息
CREATE TABLE IF NOT EXISTS index_basic (
    ts_code     VARCHAR(16) PRIMARY KEY,   -- 指数代码: 000001.SH
    name        VARCHAR(50),
    fullname    VARCHAR(100),
    market      VARCHAR(20),
    publisher   VARCHAR(50),
    index_type  VARCHAR(20),               -- 指数类别
    category    VARCHAR(20),
    base_date   DATE,                      -- 基日
    base_point  DECIMAL(10,2),             -- 基点
    list_date   DATE
);

-- 上市公司基本信息
CREATE TABLE IF NOT EXISTS stock_company (
    ts_code       VARCHAR(16) PRIMARY KEY REFERENCES stock_basic(ts_code),
    name          VARCHAR(50),
    enname        VARCHAR(100),
    province      VARCHAR(50),
    city          VARCHAR(50),
    industry      VARCHAR(50),
    main_business TEXT,                    -- 主营业务
    website       VARCHAR(200),
    reg_address   VARCHAR(200),
    office_address VARCHAR(200),
    chairman      VARCHAR(50),
    reg_capital   DECIMAL(18,2),           -- 注册资本(万元)
    setup_date    DATE,                    -- 成立日期
    ipo_date      DATE,                    -- 上市日期
    employees     INTEGER
);

-- ---------- 2. 日线行情表 ----------

-- 日线行情（未复权）
CREATE TABLE IF NOT EXISTS daily (
    ts_code   VARCHAR(16) NOT NULL,
    trade_date DATE NOT NULL,
    open      DECIMAL(10,2),
    high      DECIMAL(10,2),
    low       DECIMAL(10,2),
    close     DECIMAL(10,2),
    pre_close DECIMAL(10,2),
    change    DECIMAL(10,2),
    pct_chg   DECIMAL(10,4),
    vol       DECIMAL(18,4),               -- 成交量(手)
    amount    DECIMAL(18,4),               -- 成交额(千元)
    PRIMARY KEY (ts_code, trade_date)
);

-- 复权因子
CREATE TABLE IF NOT EXISTS adj_factor (
    ts_code    VARCHAR(16) NOT NULL,
    trade_date DATE NOT NULL,
    adj_factor DECIMAL(12,6) NOT NULL,
    PRIMARY KEY (ts_code, trade_date)
);

-- 每日指标（PE/PB/市值/换手率等）
CREATE TABLE IF NOT EXISTS daily_basic (
    ts_code         VARCHAR(16) NOT NULL,
    trade_date      DATE NOT NULL,
    turnover_rate   DECIMAL(10,4),         -- 换手率(%)
    turnover_rate_f DECIMAL(10,4),         -- 自由换手率(%)
    volume_ratio    DECIMAL(10,4),         -- 量比
    pe              DECIMAL(12,4),         -- 市盈率(总市值/净利润)
    pe_ttm          DECIMAL(12,4),
    pb              DECIMAL(12,4),         -- 市净率
    ps              DECIMAL(12,4),
    ps_ttm          DECIMAL(12,4),
    dv_ratio        DECIMAL(10,4),         -- 股息率(%)
    dv_ttm          DECIMAL(10,4),
    total_share     DECIMAL(18,2),         -- 总股本(万股)
    float_share     DECIMAL(18,2),         -- 流通股本(万股)
    free_share      DECIMAL(18,2),         -- 自由流通股本(万股)
    total_mv        DECIMAL(18,2),         -- 总市值(万元)
    circ_mv         DECIMAL(18,2),         -- 流通市值(万元)
    PRIMARY KEY (ts_code, trade_date)
);

-- 指数日线
CREATE TABLE IF NOT EXISTS index_daily (
    ts_code    VARCHAR(16) NOT NULL,
    trade_date DATE NOT NULL,
    open       DECIMAL(10,2),
    high       DECIMAL(10,2),
    low        DECIMAL(10,2),
    close      DECIMAL(10,2),
    pre_close  DECIMAL(10,2),
    change     DECIMAL(10,2),
    pct_chg    DECIMAL(10,4),
    vol        DECIMAL(18,4),
    amount     DECIMAL(18,4),
    PRIMARY KEY (ts_code, trade_date)
);

-- 指数成分
CREATE TABLE IF NOT EXISTS index_member (
    index_code VARCHAR(16) NOT NULL,
    con_code   VARCHAR(16) NOT NULL,
    in_date    DATE,
    out_date   DATE,
    is_new     BOOLEAN DEFAULT TRUE,
    PRIMARY KEY (index_code, con_code)
);

-- ---------- 3. 分钟线 / Tick (时序表, TimescaleDB hypertable) ----------

-- 分钟线 K 线
CREATE TABLE IF NOT EXISTS minute_bar (
    ts_code    VARCHAR(16) NOT NULL,
    trade_time TIMESTAMPTZ NOT NULL,
    freq       VARCHAR(5) NOT NULL DEFAULT '1min',  -- 1min/5min/15min/30min/60min
    open       DECIMAL(10,2),
    high       DECIMAL(10,2),
    low        DECIMAL(10,2),
    close      DECIMAL(10,2),
    volume     DECIMAL(18,4),
    amount     DECIMAL(18,4),
    PRIMARY KEY (ts_code, trade_time, freq)
);

-- Tick 逐笔成交
CREATE TABLE IF NOT EXISTS tick_data (
    ts_code       VARCHAR(16) NOT NULL,
    trade_time    TIMESTAMPTZ NOT NULL,
    price         DECIMAL(10,2) NOT NULL,
    volume        DECIMAL(18,4) NOT NULL,   -- 该笔成交量(手)
    amount        DECIMAL(18,4),            -- 该笔成交额(元)
    buy_sell_flag VARCHAR(4),               -- 内外盘: B外盘 S内盘
    type          VARCHAR(10),              -- 成交类型
    PRIMARY KEY (ts_code, trade_time)
);

-- ---------- 4. 财务数据 ----------

-- 财务指标（核心字段，完整版可按需加列）
CREATE TABLE IF NOT EXISTS fin_indicator (
    ts_code           VARCHAR(16) NOT NULL,
    ann_date          DATE NOT NULL,        -- 公告日期
    end_date          DATE NOT NULL,        -- 报告期
    eps               DECIMAL(12,4),        -- 每股收益
    dt_eps            DECIMAL(12,4),        -- 稀释每股收益
    bps               DECIMAL(12,4),        -- 每股净资产
    roe               DECIMAL(12,4),        -- 净资产收益率(%)
    grossprofit_margin DECIMAL(12,4),       -- 毛利率(%)
    netprofit_margin  DECIMAL(12,4),        -- 净利率(%)
    debt_to_assets    DECIMAL(12,4),        -- 资产负债率(%)
    current_ratio     DECIMAL(12,4),        -- 流动比率
    quick_ratio       DECIMAL(12,4),        -- 速动比率
    total_revenue     DECIMAL(18,2),        -- 营业总收入(元)
    total_profit      DECIMAL(18,2),        -- 利润总额(元)
    n_income_attr_p   DECIMAL(18,2),        -- 归母净利润(元)
    netprofit_yoy     DECIMAL(12,4),        -- 归母净利润同比(%)
    or_yoy            DECIMAL(12,4),        -- 营业收入同比(%)
    ocfps             DECIMAL(12,4),        -- 每股经营现金流
    PRIMARY KEY (ts_code, end_date, ann_date)
);

-- 资产负债表（精简核心科目）
CREATE TABLE IF NOT EXISTS balance_sheet (
    ts_code      VARCHAR(16) NOT NULL,
    ann_date     DATE NOT NULL,
    end_date     DATE NOT NULL,
    total_assets DECIMAL(18,2),
    total_liab   DECIMAL(18,2),
    money_cap    DECIMAL(18,2),             -- 货币资金
    accounts_receiv DECIMAL(18,2),          -- 应收账款
    inventories  DECIMAL(18,2),             -- 存货
    total_hldr_eqy_exc_min_int DECIMAL(18,2), -- 归母股东权益
    PRIMARY KEY (ts_code, end_date, ann_date)
);

-- 利润表（精简核心科目）
CREATE TABLE IF NOT EXISTS income_statement (
    ts_code      VARCHAR(16) NOT NULL,
    ann_date     DATE NOT NULL,
    end_date     DATE NOT NULL,
    total_revenue DECIMAL(18,2),
    revenue      DECIMAL(18,2),             -- 营业收入
    operate_cost DECIMAL(18,2),             -- 营业成本
    sell_exp     DECIMAL(18,2),             -- 销售费用
    admin_exp    DECIMAL(18,2),             -- 管理费用
    rd_exp       DECIMAL(18,2),             -- 研发费用
    fin_exp      DECIMAL(18,2),             -- 财务费用
    n_income_attr_p DECIMAL(18,2),          -- 归母净利润
    PRIMARY KEY (ts_code, end_date, ann_date)
);

-- ---------- 5. 索引（普通表查询加速） ----------

CREATE INDEX IF NOT EXISTS idx_daily_date ON daily (trade_date);
CREATE INDEX IF NOT EXISTS idx_adj_date  ON adj_factor (trade_date);
CREATE INDEX IF NOT EXISTS idx_db_date   ON daily_basic (trade_date);
CREATE INDEX IF NOT EXISTS idx_idxd_date ON index_daily (trade_date);
CREATE INDEX IF NOT EXISTS idx_fin_end   ON fin_indicator (end_date);
CREATE INDEX IF NOT EXISTS idx_bs_end    ON balance_sheet (end_date);
CREATE INDEX IF NOT EXISTS idx_is_end    ON income_statement (end_date);

-- ---------- 6. TimescaleDB hypertable 设置 ----------

-- 判断扩展是否存在（安装了才建 hypertable）
DO $$
DECLARE
    ts_available BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb'
    ) INTO ts_available;

    IF ts_available THEN
        CREATE EXTENSION IF NOT EXISTS timescaledb;

        -- 分钟线: 按天分区，保留主键约束
        PERFORM create_hypertable('minute_bar', 'trade_time', if_not_exists => TRUE);
        PERFORM add_retention_policy('minute_bar', INTERVAL '5 years', if_not_exists => TRUE);
        -- 注意: 压缩会锁定旧分区，回填该区间数据前需先解压。间隔设长避免误伤
        PERFORM add_compression_policy('minute_bar', INTERVAL '1 year', if_not_exists => TRUE);

        -- Tick: 按天分区
        PERFORM create_hypertable('tick_data', 'trade_time', if_not_exists => TRUE);
        PERFORM add_retention_policy('tick_data', INTERVAL '2 years', if_not_exists => TRUE);
        PERFORM add_compression_policy('tick_data', INTERVAL '6 months', if_not_exists => TRUE);

        RAISE NOTICE 'TimescaleDB hypertable created: minute_bar, tick_data';
    ELSE
        RAISE NOTICE 'TimescaleDB not installed - minute_bar/tick_data are regular tables';
    END IF;
END $$;

COMMIT;
