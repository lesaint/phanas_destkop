import logging
import os
import select
import subprocess
import sys

from datetime import datetime, date, timedelta
from pathlib import Path
from io import StringIO

class Backup:
    __logger = logging.getLogger("backup")

    __script_path = None

    __STATE_FILE_HEADER = "# This file is generated, do not modify it"
    __script_dir = Path(sys.path[0])
    __state_file_path = __script_dir / "state.phanas"

    __LAST_BACKUP_MAX_AGE_IN_DAYS = 4
    __LAST_BACKUP_DATE_FORMAT = "%Y-%m-%d"
    __LAST_BACKUP_TIMESTAMP_FORMAT = "{}_%H-%M-%S".format(__LAST_BACKUP_DATE_FORMAT)
    __LAST_BACKUP_LINE_PREFIX = "last_backup_date="
    __lastbackup_day = None
    
    def __init__(self, config):
        self.__load_backupscript_path(config)
        self.__load_lastbackup_date()

    def __load_backupscript_path(self, config):
        backup_name = "backup"
        script_path_name = "script_path"

        if not config:
            self.__logger.info("no config")
            return False

        if not backup_name in config:
            self.__logger.info("config does not contain %s", backup_name)
            return False

        backup_config = config[backup_name]
        if not isinstance(backup_config, dict) or not script_path_name in backup_config:
            self.__logger.info("'%s' is not an object or does not contain name '%s'", backup_name, script_path_name)
            return False

        script_path_str = backup_config[script_path_name]
        if not isinstance(script_path_str, str) or not script_path_str:
            self.__logger.info("%s is not a string", script_path_name)
            return False

        script_path = Path(script_path_str)
        if not script_path.is_file():
            self.__logger.error("script %s can not be found", script_path)
            return False

        if not os.access(script_path, os.X_OK):
            self.__logger.error("script %s is not executable", script_path)
            return False

        self.__logger.info("backup script: %s", script_path)
        self.__script_path = script_path

        return True

    def __load_lastbackup_date(self):
        if not self.__state_file_path.is_file():
            return

        with open(self.__state_file_path, 'r') as f:
            line = f.readline()
            while line.startswith("#"):
                line = f.readline()

            if not line.startswith(self.__LAST_BACKUP_LINE_PREFIX):
                self.__logger.error("wrong first line in state file")
                return

            prefix_length = len(self.__LAST_BACKUP_LINE_PREFIX)
            lastbackup_day_str = line[prefix_length:prefix_length + len("2020-06-18")]

            self.__lastbackup_day = datetime.strptime(lastbackup_day_str, self.__LAST_BACKUP_DATE_FORMAT).date()
            self.__logger.info("last backup day: %s", self.__lastbackup_day)

    def should_backup(self):
        if self.__script_path:
            return True

        return False

    def can_skip(self):
        if not self.__lastbackup_day:
            return False

        threshold_day = date.today() - timedelta(days = self.__LAST_BACKUP_MAX_AGE_IN_DAYS)
        if self.__lastbackup_day < threshold_day:
            return False

        return True


    def do_backup(self):
        command = [ self.__script_path ]

        proc = subprocess.Popen(command, stdin = subprocess.PIPE, stdout = subprocess.PIPE, stderr = subprocess.STDOUT, universal_newlines = True)

        def check_std(std, loglevel):
           while True:
                output = std.readline()
                if output:
                    self.__logger.log(loglevel, output.strip())
                else:
                    break 

        def check_io():
            check_std(proc.stdout, logging.INFO)

        while proc.poll() is None:
            check_io()
            proc.wait()

        if proc.returncode != 0:
            return False, "backup script had an error. Check the logs"

        self.__persist_backup_date()

        return True, None

    def __persist_backup_date(self):
        self.__logger.debug("writing to %s...", self.__state_file_path)
        add_header = False
        if not self.__state_file_path.is_file():
            add_header = True

        with open(self.__state_file_path, 'w') as f:
            if add_header:
                f.write(self.__STATE_FILE_HEADER + "\n")
            timestamp = datetime.today().strftime(self.__LAST_BACKUP_TIMESTAMP_FORMAT)
            f.write(self.__LAST_BACKUP_LINE_PREFIX + timestamp + "\n")


def run(config):
    logger = logging.getLogger("backup")
    logger.info("Backup to Phanas started")

    backup = Backup(config)

    if backup.should_backup():
        logger.info("Auto backup could skip this run: {}".format(backup.can_skip()))
        status, msg = backup.do_backup()
        if not status:
            logger.error(msg)
    else:
        logger.info("Backup is not configured")

    logger.info("Backup to Phanas done")
