import logging
import sys

from datetime import datetime, date, timedelta
from pathlib import Path

__LOGGING_DATE_FORMAT = "%Y-%m-%d"
__LOGGING_TIMESTAMP_FORMAT = "{}_%H-%M-%S".format(__LOGGING_DATE_FORMAT)
__LOGGING_EXPIRATION_IN_DAYS = 60
__script_dir_path = Path(sys.path[0])
__log_dir_path = __script_dir_path / "logs"

def configure_logging():
    timestamp = datetime.today().strftime(__LOGGING_TIMESTAMP_FORMAT)
    logfile_path = __log_dir_path / "{}_phanas.log".format(timestamp)
    # print("logging to {}".format(logfile_path))

    if not __log_dir_path.is_dir():
        __log_dir_path.mkdir()

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s][%(name)-9.9s][%(levelname)-4.4s] %(message)s",
        handlers=[
            logging.FileHandler(logfile_path),
            logging.StreamHandler()
        ]
    )

    __purge_log_dir()

def __purge_log_dir():
    rootLogger = logging.getLogger()

    for file in __log_dir_path.glob("*.log"):
        day = __read_day_from_backup_file(file)
        threshold_day = datetime.today() - timedelta(days = __LOGGING_EXPIRATION_IN_DAYS)
        if day < threshold_day:
            rootLogger.info("deleting old logfile %s...", file)
            file.unlink()


def __read_day_from_backup_file(file_path):
    day_str = file_path.stem[0:len("2020-06-18")]
    return datetime.strptime(day_str, __LOGGING_DATE_FORMAT)