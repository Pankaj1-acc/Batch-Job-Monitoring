"""
Entry point for the D365 F&O Batch Job Monitoring Agent.

Usage
-----
Single run (default, used by the GitHub Actions scheduler):
    python main.py

Continuous mode (runs the monitor on a daily schedule):
    python main.py --schedule
"""

import argparse
import logging
import sys

import schedule
import time

from src.config import Config
from src.d365_client import D365Client
from src.monitor import BatchJobMonitor
from src.notifier import Notifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Interval (seconds) between schedule.run_pending() calls in continuous mode
_SCHEDULE_CHECK_INTERVAL = 30


def _run_once(config: Config) -> bool:
    """
    Execute one monitoring cycle.

    Returns True when there are no alert-worthy jobs (exit code 0),
    False when alerts are present (exit code 1).
    """
    client = D365Client(config)
    monitor = BatchJobMonitor(config, client)
    notifier = Notifier(config)

    report = monitor.run()
    notifier.notify(report)
    return not report.has_alerts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="D365 F&O Batch Job Monitoring Agent"
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help=(
            "Run in continuous mode, executing the monitor once per day "
            "at the time specified by --time."
        ),
    )
    parser.add_argument(
        "--time",
        default="06:00",
        help=(
            "Time of day to run the daily check when --schedule is used "
            "(HH:MM, 24-hour clock, default: 06:00)."
        ),
    )
    args = parser.parse_args()

    config = Config()
    try:
        config.validate()
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        sys.exit(2)

    if args.schedule:
        logger.info(
            "Scheduling daily monitoring run at %s (UTC).", args.time
        )
        schedule.every().day.at(args.time).do(_run_once, config=config)
        while True:
            schedule.run_pending()
            time.sleep(_SCHEDULE_CHECK_INTERVAL)
    else:
        healthy = _run_once(config)
        sys.exit(0 if healthy else 1)


if __name__ == "__main__":
    main()
