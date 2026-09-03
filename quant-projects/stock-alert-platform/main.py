import time, logging, threading
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from src.config import load_config
from src.storage import Storage
from src.datafeed import DataFeed
from src.notifier import Notifier
from src.engine import Engine
from src.web.app import create_app

logging.basicConfig(
    filename="data/app.log", level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")
log = logging.getLogger("main")


def main():
    cfg = load_config()
    store = Storage(cfg)
    feed = DataFeed(cfg)
    notifier = Notifier(cfg)
    engine = Engine(cfg, store, feed, notifier)

    # Web 看板放后台线程
    app = create_app(store)
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=cfg.get("web_port", 8080)),
        daemon=True).start()
    log.info("Web 看板已启动 :%s", cfg.get("web_port", 8080))

    # 调度器自重启：崩了 30s 后重启，保证 7×24
    while True:
        try:
            sched = BlockingScheduler()
            sched.add_job(engine.tick, "interval",
                          seconds=cfg.get("scan_interval_seconds", 90))
            sched.add_job(engine.run_screener,
                          CronTrigger(hour=cfg.get("screener_hour", 16),
                                      minute=cfg.get("screener_minute", 10)))
            log.info("调度器启动，扫描间隔 %ss，每日 %02d:%02d 选股",
                     cfg.get("scan_interval_seconds", 90),
                     cfg.get("screener_hour", 16),
                     cfg.get("screener_minute", 10))
            sched.start()
        except Exception:
            log.exception("调度器崩溃，30s 后重启")
            time.sleep(30)


if __name__ == "__main__":
    main()
