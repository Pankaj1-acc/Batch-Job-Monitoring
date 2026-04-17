"""Scheduler — runs the monitoring job on a cron schedule.

Uses APScheduler to trigger :func:`run_monitoring_cycle` according to
the cron expression defined in the configuration.
"""

import logging
import signal
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.auth import build_authenticator
from src.config import load_config
from src.monitor import BatchJobMonitor
from src.notifications import dispatch_notifications

logger = logging.getLogger(__name__)


def run_monitoring_cycle(config):
    """Execute a single monitoring cycle: fetch, report, notify.

    Parameters
    ----------
    config : dict
        Full application configuration.
    """
    logger.info("=== Starting monitoring cycle ===")
    try:
        authenticator = build_authenticator(config)
        session = authenticator.get_session()

        d365 = config["d365"]
        monitor = BatchJobMonitor(
            session=session,
            base_url=d365["base_url"],
            batch_job_entity=d365.get("batch_job_entity", "BatchJobs"),
            batch_job_history_entity=d365.get("batch_job_history_entity", "BatchJobHistory"),
        )

        report = monitor.generate_daily_report()

        # Log summary to console / file
        logger.info(
            "Daily summary — Total: %d | Errors: %d",
            report["total_jobs"],
            len(report["failed_jobs"]),
        )

        dispatch_notifications(config, report)
    except Exception:
        logger.exception("Monitoring cycle failed")

    logger.info("=== Monitoring cycle complete ===")


def start_scheduler(config):
    """Start the APScheduler blocking scheduler.

    Parameters
    ----------
    config : dict
        Full application configuration.
    """
    sched_cfg = config.get("schedule", {})
    cron_expr = sched_cfg.get("cron", "0 7 * * *")
    tz = sched_cfg.get("timezone", "UTC")

    parts = cron_expr.split()
    if len(parts) != 5:
        logger.error("Invalid cron expression: %s", cron_expr)
        sys.exit(1)

    trigger = CronTrigger(
        minute=parts[0],
        hour=parts[1],
        day=parts[2],
        month=parts[3],
        day_of_week=parts[4],
        timezone=tz,
    )

    scheduler = BlockingScheduler()
    scheduler.add_job(run_monitoring_cycle, trigger, args=[config], id="batch_monitor")

    # Graceful shutdown on SIGINT / SIGTERM
    def _shutdown(signum, _frame):
        logger.info("Received signal %s — shutting down scheduler", signum)
        scheduler.shutdown(wait=False)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logger.info("Scheduler started — next run according to cron '%s' (%s)", cron_expr, tz)
    scheduler.start()


def main():
    """Entry point: load config, set up logging, and either run once or start scheduler."""
    import argparse

    parser = argparse.ArgumentParser(description="D365 F&O Batch Job Monitoring Agent")
    parser.add_argument("--config", "-c", help="Path to YAML config file")
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Run a single monitoring cycle and exit (do not start scheduler)",
    )
    args = parser.parse_args()

    config = load_config(args.config)

    # Configure logging
    log_cfg = config.get("logging", {})
    log_level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)
    log_file = log_cfg.get("file")

    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        from pathlib import Path

        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )

    logger.info("D365 F&O Batch Job Monitoring Agent starting")

    if args.run_once:
        run_monitoring_cycle(config)
    else:
        start_scheduler(config)


if __name__ == "__main__":
    main()
